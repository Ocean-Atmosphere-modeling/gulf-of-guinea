#!/usr/bin/env python
"""
make_rivers_GulfOfGuinea.py

Create a ROMS river (point source, LwSrc) forcing file for the Gulf of Guinea
4 km grid from GloFAS daily river discharge, in the same format as
riv_gulfofguinea_2024_v2.nc:

  * 7 rivers (Volta, Niger, Cross, Sanaga, Ogooue, Kouilou-Niari, Congo)
    at the source cells selected by John Wilkin (2025-07-31)
  * LwSrc point sources (river_direction = 2), uniform Vshape over N levels
  * river_salt = 0, river_temp left as fill (LtracerSrc == F T in roms.in)
  * daily discharge (dis24) placed at noon of each day (day + 0.5), plus an
    extra record at 00:00 of the first day (copy of day 1) so that ROMS
    has river data from the very start of the run ("_v2" convention)

GloFAS data come from the Copernicus Early Warning Data Store (EWDS) dataset
"cems-glofas-historical" (version 4.0). Either give an existing GloFAS netCDF
file with --glofas-file, or use --download to fetch it with cdsapi. That needs
`pip install cdsapi`, a ~/.cdsapirc containing
    url: https://ewds.climate.copernicus.eu/api
    key: <your API token>
and the dataset licence accepted once at
https://ewds.climate.copernicus.eu/datasets/cems-glofas-historical?tab=download
Consolidated data lag real time by several months; by default (--product-type
auto) the script uses consolidated data where available and intermediate data
for the most recent months.

Examples
  python make_rivers_GulfOfGuinea.py --year 2024 --download
  python make_rivers_GulfOfGuinea.py --year 2025 --glofas-file glofas_dis24_2025.nc
  python make_rivers_GulfOfGuinea.py --start 2025-06-01 --end 2025-12-31 --download \
         --product-type intermediate

Created by Cody Benton 11/2026, following riv_gulfofguinea_2024_v2.nc
(John Wilkin / Becca Horwitz).
"""
import os
import argparse
import datetime as dt

import numpy as np
import pandas as pd
import xarray as xr
import netCDF4 as nc

# USER SETTINGS ---------------------------------------------------------------

# Directory for downloaded GloFAS files and for the output river file
glofasdir = '/projects/f_omg_1/moa/africa/data/glofas/'
outdir = '/projects/f_omg_1/moa/africa/inp/riv/'
outname = 'riv_gulfofguinea_{tag}_v2.nc'      # {tag} = year, or start_end

# ROMS grid (only recorded as an attribute)
grdfile = '/projects/f_omg_1/moa/africa/data/imp_files/grd_GulfOfGuinea_4km.nc'
N = 50                                        # number of s_rho levels

# GloFAS subset area [North, West, South, East] -- same box as the Mercator
# downloads. I/J_index_glofas_subset are 1-based indices into this subset.
area = [8.0, -16.0, -11.0, 13.5]

# Rivers: name, ROMS i (Xposition), ROMS j (Eposition), GloFAS lat, GloFAS lon
rivers = [
    ('Volta',         382, 378,  5.775,  0.675),
    ('Niger',         516, 342,  4.325,  5.975),
    ('Cross',         567, 354,  4.775,  8.275),
    ('Sanaga',        597, 325,  3.525,  9.625),
    ('Ogooué',        578, 217, -0.975,  8.925),
    ('Kouilou-Niari', 647, 133, -4.475, 11.725),
    ('Congo',         664,  94, -6.075, 12.475),
]

# Daily mean discharge for calendar day D is placed at D + time_offset days
time_offset = 0.5

# END USER SETTINGS -----------------------------------------------------------


def available_months(year, product_type):
    """Months (ints) of `year` that EWDS has for this GloFAS v4 product,
    or None if the availability check itself fails."""
    import requests
    url = ('https://ewds.climate.copernicus.eu/api/retrieve/v1/processes/'
           'cems-glofas-historical/constraints')
    q = {'system_version': ['version_4_0'], 'product_type': [product_type],
         'variable': ['average_river_discharge_in_the_last_24_hours'],
         'year': [str(year)]}
    try:
        r = requests.post(url, json={'inputs': q}, timeout=60)
        r.raise_for_status()
        return [int(m) for m in r.json().get('month', [])]
    except Exception as e:
        print(f'  WARNING: could not check GloFAS availability ({e})')
        return None


def plan_downloads(year, months, product_type):
    """Split the months of one year into [(product, months), ...]."""
    products = ['consolidated', 'intermediate'] if product_type == 'auto' else [product_type]
    plan, todo = [], list(months)
    for pt in products:
        avail = available_months(year, pt)
        if avail is None:                      # can't check: just try it
            avail = todo
        use = [m for m in todo if m in avail]
        if use:
            plan.append((pt, use))
        todo = [m for m in todo if m not in use]
    if todo:
        raise SystemExit(f'GloFAS {"/".join(products)} has no data for {year} months {todo}. '
                         'Consolidated data lag by months; try --product-type intermediate '
                         '(or auto), or an earlier end date.')
    return plan


def download_glofas(year, months, fname, product_type='consolidated'):
    """Download GloFAS v4 daily mean discharge for the subset area, one year
    (only the given months) per request, from the Early Warning Data Store."""
    try:
        import cdsapi
    except ImportError:
        raise SystemExit('cdsapi is not installed: pip install cdsapi, and set up '
                         '~/.cdsapirc with url: https://ewds.climate.copernicus.eu/api')
    request = {
        'system_version': ['version_4_0'],
        'hydrological_model': ['lisflood'],
        'product_type': [product_type],
        'variable': ['average_river_discharge_in_the_last_24_hours'],
        'timespan': ['time_mean'],
        'year': [str(year)],
        'month': [f'{m:02d}' for m in months],
        'day': [f'{d:02d}' for d in range(1, 32)],
        'data_format': 'netcdf',
        'download_format': 'unarchived',
        'area': area,
    }
    print(f'  Downloading GloFAS {product_type} {year} months {months[0]}-{months[-1]} '
          f'-> {fname}  (the EWDS queue can take a while)')
    cdsapi.Client().retrieve('cems-glofas-historical', request, fname)


def read_glofas(files, start, end):
    """Return (dates, discharge[time, river], I, J, lat, lon) at the river points."""
    ds = xr.open_mfdataset(files, combine='by_coords') if len(files) > 1 \
        else xr.open_dataset(files[0])
    tname = 'valid_time' if 'valid_time' in ds.coords else 'time'
    ds = ds.rename({tname: 'time'})
    if 'lat' in ds.coords:
        ds = ds.rename({'lat': 'latitude', 'lon': 'longitude'})
    var = next((v for v in ('avg_dis', 'dis24', 'dis') if v in ds), None)
    if var is None:
        raise SystemExit(f'No discharge variable in {files}: {list(ds.data_vars)}')
    ds = ds.sortby('time')

    # Daily records: one per calendar day. In current EWDS files (avg_dis)
    # valid_time is the END of the 24 h averaging window, so the record stamped
    # Jan 2 00:00 is the mean for Jan 1 -> shift back one day.
    days = pd.DatetimeIndex(ds['time'].values).floor('D')
    if var == 'avg_dis':
        days = days - pd.Timedelta(days=1)
    ds = ds.assign_coords(time=days)
    ds = ds.sel(time=slice(start, end))
    if ds.sizes['time'] == 0:
        raise SystemExit(f'No GloFAS data between {start.date()} and {end.date()}')
    expected = pd.date_range(start, end, freq='D')
    missing = expected.difference(pd.DatetimeIndex(ds['time'].values))
    if len(missing):
        print(f'  WARNING: {len(missing)} days missing from GloFAS, e.g. {missing[:3].date}')

    glat = ds['latitude'].values
    glon = ds['longitude'].values
    I, J, Q, lats, lons = [], [], [], [], []
    for name, _, _, rlat, rlon in rivers:
        j = int(np.abs(glat - rlat).argmin())
        i = int(np.abs(glon - rlon).argmin())
        if abs(glat[j] - rlat) > 0.03 or abs(glon[i] - rlon) > 0.03:
            raise SystemExit(f'{name}: GloFAS point ({rlat},{rlon}) not inside the '
                             f'GloFAS file (nearest {glat[j]:.3f},{glon[i]:.3f})')
        q = ds[var].isel(latitude=j, longitude=i).values.astype('f8')
        if np.isnan(q).any():
            raise SystemExit(f'{name}: NaN discharge at GloFAS point ({rlat},{rlon})')
        Q.append(q)
        I.append(i + 1)          # 1-based like the original MATLAB-made file
        J.append(j + 1)
        lats.append(float(glat[j]))
        lons.append(float(glon[i]))
    dates = pd.DatetimeIndex(ds['time'].values)
    return dates, np.array(Q).T, I, J, lats, lons


def write_river_file(fname, reftime, dates, Q, I, J, lats, lons, glofas_src):
    nriv = len(rivers)
    nt = len(dates)

    # river_time: 00:00 of first day (copy of day 1), then noon of each day
    t = (dates - reftime) / pd.Timedelta(days=1) + time_offset
    t0 = (dates[0] - reftime) / pd.Timedelta(days=1)
    rtime = np.concatenate([[t0], t])
    Q = np.vstack([Q[:1], Q])
    nt += 1

    fh = nc.Dataset(fname, 'w', format='NETCDF4', clobber=True)
    fh.type = 'ROMS FORCING file'
    fh.title = 'Gulf of Guinea River Forcing from GloFAS'
    fh.grd_file = grdfile
    fh.rivers = ' \n'.join(f'({k+1}) {r[0]}' for k, r in enumerate(rivers)) + ' '
    fh.source = ('Daily discharge from GloFAS Global Flood Awareness Program globalfloods.eu '
                 'accessed from Copernicus\n'
                 'https://cds.climate.copernicus.eu/cdsapp#!/dataset/cems-glofas-historical?tab=form\n'
                 'Source point locations selected interactively John Wilkin 2025-07-31.')
    fh.glofas_download = glofas_src
    fh.citation = ('Harrigan, S., Zsoter, E., Alfieri, L., Prudhomme, C., Salamon, P., '
                   'Wetterhall, F., Barnard, C., Cloke, H. and Pappenberger, F., 2020. '
                   'GloFAS-ERA5 operational global river discharge reanalysis 1979–present. '
                   'Earth System Science Data, 12(3), pp.2043-2060., '
                   'https://doi.org/10.5194/essd-12-2043-2020')
    fh.history = 'Created by make_rivers_GulfOfGuinea.py on ' + \
        dt.datetime.now().strftime('%Y/%m/%d %H:%M:%S')

    fh.createDimension('river_time', None)
    fh.createDimension('river', nriv)
    fh.createDimension('s_rho', N)

    def var(name, dims, dtype='f8', fill=np.nan, **atts):
        v = fh.createVariable(name, dtype, dims, fill_value=fill)
        for k, a in atts.items():
            v.setncattr(k, a)
        return v

    var('distributed_source_fraction', ('river',),
        long_name='fraction of true river_transport at this source cell',
        valid_min=0., valid_max=1.)[:] = 1.0
    var('num_real_source', (), 'i4', fill=False,
        long_name='number of true river sources if there are any distributed sources',
        equals_zero='no distributed sources - number of true sources matches dimension RIVER'
        ).assignValue(nriv)
    var('river_Xposition', ('river',), long_name='river XI-position at RHO-points',
        valid_min=1., valid_max=1665.,
        LuvSrc_meaning='i-index grid cell of U- or V-face source/sink',
        LwSrc_meaning='i-index grid cell of RHO-centered source/sink'
        )[:] = [r[1] for r in rivers]
    var('river_Eposition', ('river',), long_name='river ETA-position at RHO-points',
        valid_min=1., valid_max=1441.,
        LuvSrc_meaning='j-index grid cell of U- or V-face source/sink',
        LwSrc_meaning='j-index grid cell of RHO-centered source/sink'
        )[:] = [r[2] for r in rivers]
    var('river_direction', ('river',), long_name='river runoff grid-cell face flag',
        flag_values='0, 1, 2',
        flag_meanings='LuvSrc flow across U-face, LuvSrc flow across V-face, '
                      'LwSrc flow into cell center')[:] = 2.0
    var('river_lat', ('river',), long_name='latitude of grid cell in GloFAS')[:] = lats
    var('river_lon', ('river',), long_name='longitude of grid cell in GloFAS')[:] = lons
    var('river_Vshape', ('s_rho', 'river'),
        long_name='river runoff mass transport vertical profile',
        requires='must sum to 1 over s_rho')[:] = np.full((N, nriv), 1.0 / N)
    salt = var('river_salt', ('river_time', 's_rho', 'river'),
               long_name='river runoff salinity', time='river_time')
    sign = var('river_sign', ('river',), long_name='river runoff sense of flow',
               flag_values='-1, 1',
               LuvSrc_meaning='flow in negative u,v direction, flow in positive u,v, direction',
               LwSrc_meaning='flag not used')
    temp = var('river_temp', ('river_time', 's_rho', 'river'),
               long_name='river runoff potential temperature', units='Celsius',
               time='river_time')
    trans = var('river_transport', ('river_time', 'river'),
                long_name='river runoff vertically integrated mass transport',
                units='meter3 second-1',
                positive='LuvSrc=T flow in positive u,v direction, LwSrc=T flow into RHO-cell',
                negative='LuvSrc=T flow in negative u,v direction, LwSrc=T flow out of RHO-cell',
                time='river_time')
    var('I_index_glofas_subset', ('river',), 'i4', fill=False,
        description='I index to glofas*.nc files to extract discharge at near coastal sources'
        )[:] = I
    var('J_index_glofas_subset', ('river',), 'i4', fill=False,
        description='J index to glofas*.nc files to extract discharge at near coastal sources'
        )[:] = J
    var('river', ('river',), long_name='river runoff identification number',
        distributed_source='duplicate values connect to a source distributed over multiple cells'
        )[:] = np.arange(1, nriv + 1)
    tv = var('river_time', ('river_time',), long_name='river runoff time',
             units=reftime.strftime('days since %Y-%m-%d %H:%M:%S'))

    # Temperature is not used (LtracerSrc == F T) and sign is not used for LwSrc;
    # write netCDF default fill values, as in riv_gulfofguinea_2024_v2.nc
    spval = nc.default_fillvals['f8']
    tv[:] = rtime
    trans[:] = Q
    salt[:] = np.zeros((nt, N, nriv))
    temp[:] = np.full((nt, N, nriv), spval)
    sign[:] = np.full(nriv, spval)
    fh.close()


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--year', type=int, help='calendar year to process (e.g. 2024)')
    p.add_argument('--start', help='start date YYYY-MM-DD (instead of --year)')
    p.add_argument('--end', help='end date YYYY-MM-DD (instead of --year)')
    p.add_argument('--reftime', help='river_time reference date YYYY-MM-DD '
                   '(default: Jan 1 of the start year)')
    p.add_argument('--glofas-file', nargs='+', help='existing GloFAS netCDF file(s)')
    p.add_argument('--download', action='store_true',
                   help='download GloFAS from CDS into glofasdir (needs cdsapi)')
    p.add_argument('--product-type', default='auto',
                   choices=['auto', 'consolidated', 'intermediate'],
                   help='GloFAS product. "auto" (default) uses consolidated where it '
                        'exists and intermediate for the most recent months')
    p.add_argument('--outdir', default=outdir)
    p.add_argument('--outfile', help='output file name (default ' + outname + ')')
    p.add_argument('--clobber', action='store_true', help='overwrite existing output')
    a = p.parse_args()

    if a.year:
        start, end = pd.Timestamp(a.year, 1, 1), pd.Timestamp(a.year, 12, 31)
        tag = str(a.year)
    elif a.start and a.end:
        start, end = pd.Timestamp(a.start), pd.Timestamp(a.end)
        tag = f'{start:%Y%m%d}_{end:%Y%m%d}'
    else:
        p.error('give --year, or both --start and --end')
    reftime = pd.Timestamp(a.reftime) if a.reftime else pd.Timestamp(start.year, 1, 1)

    if a.glofas_file:
        files = a.glofas_file
    elif a.download:
        os.makedirs(glofasdir, exist_ok=True)
        files = []
        for yr in range(start.year, end.year + 1):
            m1 = start.month if yr == start.year else 1
            m2 = end.month if yr == end.year else 12
            for pt, months in plan_downloads(yr, list(range(m1, m2 + 1)), a.product_type):
                f = os.path.join(glofasdir, f'glofas_v4_{pt}_GulfOfGuinea_'
                                            f'{yr}{months[0]:02d}-{yr}{months[-1]:02d}.nc')
                if not os.path.exists(f):
                    download_glofas(yr, months, f, pt)
                files.append(f)
    else:
        p.error('give --glofas-file or --download')

    os.makedirs(a.outdir, exist_ok=True)
    fname = os.path.join(a.outdir, a.outfile or outname.format(tag=tag))
    if os.path.exists(fname) and not a.clobber:
        raise SystemExit(f'{fname} exists; use --clobber to overwrite')

    print(f'  Reading GloFAS {start.date()} to {end.date()} from {files}')
    dates, Q, I, J, lats, lons = read_glofas(files, start, end)
    for k, r in enumerate(rivers):
        print(f'  {r[0]:14s} I={I[k]:4d} J={J[k]:4d}  mean Q = {Q[:, k].mean():9.1f} m3/s')

    write_river_file(fname, reftime, dates, Q, I, J, lats, lons, ', '.join(files))
    print(f'  Wrote {fname} ({len(dates) + 1} records)')


if __name__ == '__main__':
    main()
