#!/usr/bin/env python
"""
convert_ecmwf_to_roms_frc_GulfOfGuinea.py

Read the regional IFS files written by download_ecmwf_opendata_GulfOfGuinea.py
and write ONE ROMS bulk-flux forcing file with the same layout as
GulfOfGuinea_frc_ERA5_bulkflux_YYYYMM.nc:

    dims : lon, lat, time (unlimited)
    vars : spherical, lon(lon), lat(lat), time(time),
           Uwind, Vwind, Pair, Tair, Qair, swrad, lwrad_down, lwrad, rain
           all (time, lat, lon), float32

Processing
  * accumulated fields (ssr, str, strd, tp) are de-accumulated within each
    forecast run (accumulation starts at zero at step 0) and divided by the
    interval -> W m-2, kg m-2 s-1
  * a continuous series is stitched together by taking, for every valid time,
    the most recent run that covers it (smallest lead time)
  * flux values are the mean over the 3 h ENDING at the time stamp (same
    convention as ERA5 accumulations)

The data are already on a regular 0.25 deg grid, so by default there is no
regridding: the output is the native grid cut to the box. Set REF_FRC_FILE to
interpolate (linear) onto the lon/lat of an existing forcing file.
"""
import os
import glob
import sys
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd
import xarray as xr
import netCDF4 as nc

# USER SETTINGS ---------------------------------------------------------


indir = '/projects/f_omg_1/moa/africa/data/downloads/'
outdir = '/projects/f_omg_1/moa/africa/data/blk/'

# Same time-window convention as the download script
ndays_back = int(os.environ.get('NDAYS_BACK', 3))
ndays_fwd = int(os.environ.get('NDAYS_FWD', 2))

# Optional: existing forcing file whose 1-D lon/lat define the target grid
REF_FRC_FILE = None
# Optional: ROMS grid file, only used to warn if the forcing does not cover it
ROMS_GRID_FILE = '/projects/f_omg_1/moa/africa/data/imp_files/grd_GulfOfGuinea_4km.nc'

# Variable used for Pair (the download script fetches msl, mean sea-level pressure)
PAIR_VAR = 'msl'

NC_FORMAT = 'NETCDF3_64BIT_OFFSET'   # or 'NETCDF4'

# Time reference: first of the year of the run start (as in the bry script)
tstart = date.today() - timedelta(days=ndays_back)
tend = date.today() + timedelta(days=ndays_fwd)
REFTIME = datetime(tstart.year, 1, 1)

# END USER SETTINGS -----------------------------------------------------

ACCUM = ['ssr', 'str', 'strd', 'tp']

# name, long_name, units, extra attributes (matches the ERA5 target file)
FLUX_ATTR = {'positive_value': 'downward flux, heating',
             'negative_value': 'upward flux, cooling'}
VARS = [
    ('Uwind', 'surface u-wind component (east) at 10 m', 'meter second-1', {}),
    ('Vwind', 'surface v-wind component (north) at 10 m', 'meter second-1', {}),
    ('Pair', 'surface air pressure', 'millibar', {}),
    ('Tair', 'surface air temperature at 2 m', 'Celsius', {}),
    ('Qair', 'surface air relative humidity at 2 m', 'percentage', {}),
    ('swrad', 'net solar shortwave radiation flux', 'Watt meter-2', FLUX_ATTR),
    ('lwrad_down', 'downwelling longwave radiation flux', 'Watt meter-2', FLUX_ATTR),
    ('lwrad', 'net longwave radiation flux', 'Watt meter-2', FLUX_ATTR),
    ('rain', 'rain fall', 'kilogram meter-2 second-1', {}),
]


def esat(t_c):
    """Saturation vapour pressure (hPa), Bolton/Magnus, t in Celsius."""
    return 6.112 * np.exp(17.67 * t_c / (t_c + 243.5))


def process_run(fname):
    """Return dict of ROMS-unit fields for one run, plus times and grid."""
    ds = xr.open_dataset(fname)
    init = pd.Timestamp(ds['time'].values)
    steps = ds['step'].values
    steps_s = (steps / np.timedelta64(1, 's')).astype('float64')
    # interval for every step; accumulation starts from zero at step 0
    dt = np.diff(np.concatenate([[0.0], steps_s]))[:, None, None]

    def get(name):
        return (ds[name].transpose('step', 'latitude', 'longitude')
                .values.astype('float64'))

    def deacc(name):
        a = get(name)
        prev = np.concatenate([np.zeros_like(a[:1]), a[:-1]], axis=0)
        return (a - prev) / dt

    t2m = get('t2m') - 273.15
    d2m = get('d2m') - 273.15
    rh = np.clip(100.0 * esat(d2m) / esat(t2m), 0.0, 100.0)

    out = {
        'Uwind': get('u10'),
        'Vwind': get('v10'),
        'Pair': get(PAIR_VAR) / 100.0,            # Pa -> mb
        'Tair': t2m,
        'Qair': rh,
        'swrad': deacc('ssr'),                    # net SW, downward positive
        'lwrad_down': deacc('strd'),
        'lwrad': deacc('str'),                    # net LW, downward positive
        'rain': np.clip(deacc('tp') * 1000.0, 0.0, None),   # m -> kg m-2 s-1
    }
    valid = pd.DatetimeIndex(init + pd.to_timedelta(steps_s, unit='s'))
    lat = ds['latitude'].values.astype('float64')
    lon = ds['longitude'].values.astype('float64')
    ds.close()
    return out, valid, init, lat, lon


def build_dataset():
    files = sorted(glob.glob(os.path.join(indir, 'ecmwf_ifs_0p25_GulfOfGuinea_*.nc')))
    if not files:
        raise FileNotFoundError(f'No input files found in {indir}')
    print(f'Reading {len(files)} run files')

    fields = {v[0]: [] for v in VARS}
    valids, inits = [], []
    lat0 = lon0 = None
    for f in files:
        out, valid, init, lat, lon = process_run(f)
        if lat0 is None:
            lat0, lon0 = lat, lon
        elif not (np.array_equal(lat, lat0) and np.array_equal(lon, lon0)):
            raise RuntimeError(f'Grid of {f} differs from the first file')
        for k in fields:
            fields[k].append(out[k])
        valids.append(valid)
        inits.extend([init] * len(valid))

    valid = valids[0].append(valids[1:]) if len(valids) > 1 else valids[0]
    df = pd.DataFrame({'valid': valid, 'init': pd.DatetimeIndex(inits),
                       'i': np.arange(len(valid))})

    # keep, for every valid time, the most recent run
    df = (df.sort_values(['valid', 'init'])
            .drop_duplicates('valid', keep='last'))
    lo = pd.Timestamp(tstart)
    hi = pd.Timestamp(tend) + pd.Timedelta(days=1)
    df = df[(df['valid'] >= lo) & (df['valid'] <= hi)]
    if df.empty:
        raise RuntimeError('No data inside the requested time window')
    idx = df['i'].values
    times = pd.DatetimeIndex(df['valid'].values)

    gaps = np.unique(np.diff(times.values) / np.timedelta64(1, 'h'))
    print('Time spacing (h):', gaps)
    if len(gaps) > 1:
        print('  WARNING: time axis is not uniform - check missing runs')
    if times[-1] < pd.Timestamp(tend):
        print(f'  WARNING: data end at {times[-1]}, before requested {tend}')

    data = {k: np.concatenate(fields[k], axis=0)[idx] for k in fields}
    ds = xr.Dataset(
        {k: (('time', 'lat', 'lon'), v) for k, v in data.items()},
        coords={'time': times, 'lat': lat0, 'lon': lon0})
    ds.attrs['init_times_used'] = ', '.join(
        sorted({i.strftime('%Y-%m-%d %HZ') for i in df['init']}))
    return ds


def regrid_to_reference(ds):
    ref = xr.open_dataset(REF_FRC_FILE)
    lat = np.asarray(ref['lat'].values).ravel()
    lon = np.asarray(ref['lon'].values).ravel()
    print(f'Interpolating to reference grid {len(lat)} x {len(lon)}')
    ds = ds.interp(lat=lat, lon=lon, method='linear')
    if any(bool(ds[v].isnull().any()) for v in ds.data_vars):
        print('  WARNING: reference grid extends beyond the data (NaNs)')
    return ds


def check_covers_roms_grid(ds):
    if not ROMS_GRID_FILE or not os.path.exists(ROMS_GRID_FILE):
        return
    g = xr.open_dataset(ROMS_GRID_FILE)
    lo, la = g['lon_rho'].values, g['lat_rho'].values
    ok = (lo.min() >= ds.lon.min() and lo.max() <= ds.lon.max() and
          la.min() >= ds.lat.min() and la.max() <= ds.lat.max())
    print('Forcing covers ROMS grid:', ok)
    if not ok:
        print(f'  ROMS grid  lon {lo.min():.2f}..{lo.max():.2f} '
              f'lat {la.min():.2f}..{la.max():.2f}')
        print(f'  forcing    lon {float(ds.lon.min()):.2f}..{float(ds.lon.max()):.2f} '
              f'lat {float(ds.lat.min()):.2f}..{float(ds.lat.max()):.2f}')
    g.close()


def write_forcing(ds, fname):
    nt, nlat, nlon = ds.sizes['time'], ds.sizes['lat'], ds.sizes['lon']
    tdays = ((pd.DatetimeIndex(ds['time'].values) - pd.Timestamp(REFTIME))
             / pd.Timedelta(days=1)).values.astype('float64')
    lat = ds['lat'].values.astype('float64')
    lon = ds['lon'].values.astype('float64')
    t0 = pd.DatetimeIndex(ds['time'].values)

    with nc.Dataset(fname, 'w', format=NC_FORMAT) as f:
        f.createDimension('lon', nlon)
        f.createDimension('lat', nlat)
        f.createDimension('time', None)

        v = f.createVariable('spherical', 'i4')
        v.long_name = 'grid type logical switch'
        v.flag_values = np.array([0, 1], dtype='i4')
        v.flag_meanings = 'Cartesian spherical'
        v[...] = 1

        v = f.createVariable('lon', 'f8', ('lon',))
        v.long_name = 'longitude'
        v.units = 'degree_east'
        v.standard_name = 'longitude'
        v[:] = lon

        v = f.createVariable('lat', 'f8', ('lat',))
        v.long_name = 'latitude'
        v.units = 'degree_north'
        v.standard_name = 'latitude'
        v[:] = lat

        v = f.createVariable('time', 'f8', ('time',))
        v.long_name = 'time since initialization'
        v.units = 'days since ' + REFTIME.strftime('%Y-%m-%d %H:%M:%S')
        v.calendar = 'gregorian'
        v[:] = tdays

        for name, long_name, units, extra in VARS:
            v = f.createVariable(name, 'f4', ('time', 'lat', 'lon'))
            v.long_name = long_name
            v.units = units
            for k, val in extra.items():
                v.setncattr(k, val)
            v.setncattr('time', 'time')
            v.coordinates = 'lon lat time'
            arr = ds[name].transpose('time', 'lat', 'lon').values.astype('f4')
            if np.isnan(arr).any():
                raise RuntimeError(f'NaNs found in {name}')
            v[:] = arr

        f.type = 'FORCING file'
        f.title = 'ECMWF IFS HRES (open data, 0.25 deg) meteorology forcing for GulfOfGuinea'
        f.history = (f'Created {datetime.utcnow():%a %b %d %H:%M:%S %Y} UTC with '
                     f'{os.path.basename(__file__)}')
        f.citation = ('Contains ECMWF open data, licensed CC BY 4.0, '
                      'https://www.ecmwf.int/en/forecasts/datasets/open-data . '
                      'Forecast runs used: ' + ds.attrs.get('init_times_used', ''))
        f.geospatial_lat_max = float(lat.max())
        f.geospatial_lat_min = float(lat.min())
        f.geospatial_lat_resolution = float(abs(lat[1] - lat[0]))
        f.geospatial_lon_max = float(lon.max())
        f.geospatial_lon_min = float(lon.min())
        f.geospatial_lon_resolution = float(abs(lon[1] - lon[0]))
        f.time_coverage_start = t0[0].strftime('%Y-%m-%d %H:%M:%S')
        f.time_coverage_end = t0[-1].strftime('%Y-%m-%d %H:%M:%S')
        f.roms_application = 'Geospatial extent for application GulfOfGuinea'
    print(f'Wrote {fname}  ({nt} times, {nlat} lat x {nlon} lon)')


def main(argv):
    os.makedirs(outdir, exist_ok=True)
    ds = build_dataset()
    if REF_FRC_FILE:
        ds = regrid_to_reference(ds)
    check_covers_roms_grid(ds)
    fname = os.path.join(
        outdir, f'GulfOfGuinea_frc_IFS_bulkflux_{tstart:%Y%m%d}.nc')
    write_forcing(ds, fname)
    print('Check with:  ncdump -h', fname)


if __name__ == '__main__':
    print('Running forcing conversion')
    main(sys.argv)
    print('Finished')
