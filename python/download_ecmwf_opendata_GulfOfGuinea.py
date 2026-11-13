#!/usr/bin/env python
"""
download_ecmwf_opendata_GulfOfGuinea.py

Download ECMWF IFS (HRES) real-time open data at 0.25 deg, subset it to the
Gulf of Guinea box, and save one small NetCDF per forecast run.
Modeled on the Copernicus Marine (Mercator) download script.

Output files (one per forecast run, 00z and 12z):
    <outdir>/ecmwf_ifs_0p25_GulfOfGuinea_YYYYMMDDHH.nc
They contain the RAW fields (accumulated fluxes are NOT yet converted);
convert_ecmwf_to_roms_frc_GulfOfGuinea.py turns them into the bulk-flux
forcing file.

Which steps are downloaded
  - every run in the window: steps 3,6,9,12 h  (the "short lead" part used to
    stitch a continuous record)
  - the latest available run: steps 3 ... (ndays_fwd+1)*24 h  (the forecast)

Requirements
  pip install ecmwf-opendata
  conda install -c conda-forge eccodes python-eccodes cfgrib xarray netcdf4 pandas

Notes
  * The ECMWF server keeps only a few days (rolling archive). For older runs
    set SOURCE to 'aws', 'google' or 'azure' (check how far back they go).
  * The server cannot subset by area: global GRIB is downloaded to tmpdir,
    subset locally, then deleted.
  * Open data steps are 3-hourly, so the forcing will be 3-hourly.
"""
import os
import sys
import glob
import time
from datetime import date, timedelta

import pandas as pd
import xarray as xr
import cfgrib
from ecmwf.opendata import Client

# USER SETTINGS FOR DOWNLOAD --------------------------------------------

outdir = '/projects/f_omg_1/moa/africa/data/downloads/'
# Per-user temp folder, so users don't need write access to each other's tmp
# and simultaneous runs don't delete each other's temporary GRIB files
tmpdir = f'/projects/f_omg_1/moa/africa/data/downloads/tmp_{os.environ.get("USER", "user")}/'

# GULF OF GUINEA BOUNDING BOX -16.0000   13.5000  -11.0000    8.0000
latmin = -11.0
latmax = 8.0
lonmin = -16.0
lonmax = 13.5

# 'ecmwf' keeps only the last few days; use an archive mirror for past dates.
# AWS throttles heavy use from Amarel (HTTP 503 "SlowDown"); Google works.
SOURCE = 'google'       # 'ecmwf' | 'aws' | 'google' | 'azure'

# IFS short names in the open data -> cfgrib names after reading
PARAMS = ['10u', '10v', '2t', '2d', 'msl', 'ssr', 'str', 'strd', 'tp']
EXPECTED = ['u10', 'v10', 't2m', 'd2m', 'msl', 'ssr', 'str', 'strd', 'tp']

# Time window (same convention as the Mercator script)
ndays_back = int(os.environ.get('NDAYS_BACK', 3)) # days of past data
ndays_fwd = int(os.environ.get('NDAYS_FWD', 2))# days of forecast

# Model selection (ifs, aifs-single, aifs-ens)
# Note: 0.1 degree resolution is only available in ifs variant
mod_set= 'ifs'

# Resolution adjustment (0p25 or 0p1)
res_set= '0p1' 


SHORT_STEPS = [3, 6, 9, 12]

# END USER SETTINGS FOR DOWNLOAD ----------------------------------------


def grib_to_regional_netcdf(grib, ncfile):
    """Open the GRIB with cfgrib, subset to the box, write NetCDF."""
    dss = cfgrib.open_datasets(grib)   # splits instant / accumulated fields
    clean = []
    for ds in dss:
        drop = [c for c in ('heightAboveGround', 'surface', 'meanSea', 'number')
                if c in ds.coords]
        clean.append(ds.drop_vars(drop))
    ds = xr.merge(clean, compat='override', join='outer')

    missing = [v for v in EXPECTED if v not in ds.data_vars]
    if missing:
        raise RuntimeError(f'Variables missing from GRIB: {missing}. '
                           f'Found: {list(ds.data_vars)}')
    ds = ds[EXPECTED]

    # 0..360 -> -180..180, ascending lon and lat, then cut the box.
    # (The box crosses the prime meridian, so this must be done first.)
    ds = ds.assign_coords(longitude=(((ds.longitude + 180) % 360) - 180))
    ds = ds.sortby('longitude').sortby('latitude')
    ds = ds.sel(latitude=slice(latmin, latmax),
                longitude=slice(lonmin, lonmax)).load()

    print(f'  subset: {ds.sizes["step"]} steps, {ds.sizes["latitude"]} lat x '
          f'{ds.sizes["longitude"]} lon')
    enc = {v: {'zlib': True, 'complevel': 4} for v in EXPECTED}
    ds.to_netcdf(ncfile, encoding=enc)
    ds.close()


def main(argv):
    os.makedirs(outdir, exist_ok=True)
    os.makedirs(tmpdir, exist_ok=True)

    client = Client(source=SOURCE, model=mod_set, resol=res_set)

    max_step = (ndays_fwd + 1) * 24
    assert max_step <= 144, 'ndays_fwd too large for 3-hourly open data steps'
    fwd_steps = list(range(3, max_step + 1, 3))

    # Latest run for which the full forecast range is available
    probe = os.path.join(tmpdir, 'TMP_probe.grib2')
    latest = pd.Timestamp(client.latest(type='fc', stream='oper',
                                        step=max_step, param='2t',
                                        target=probe))
    print('Latest available run:', latest)

    tstart = date.today() - timedelta(days=ndays_back)
    # one extra run before the window so the first valid time (00 UTC) is covered
    first_run = pd.Timestamp(tstart) - pd.Timedelta(hours=12)
    runs = pd.date_range(first_run, latest, freq='12h')

    for run in runs:
        ncfile = os.path.join(
            outdir, run.strftime(f'ecmwf_{mod_set}_{res_set}_GulfOfGuinea_%Y%m%d%H.nc'))
        is_latest = (run == latest)

        if os.path.exists(ncfile) and not is_latest:
            print(f'Skipping {run} (already downloaded)')
            continue

        steps = fwd_steps if is_latest else SHORT_STEPS
        grib = os.path.join(tmpdir, run.strftime('TMP_ifs_%Y%m%d%H.grib2'))
        print(f'Downloading run {run}  steps {steps[0]}..{steps[-1]}')

        try:
            client.retrieve(
                date=int(run.strftime('%Y%m%d')),
                time=run.hour,
                type='fc',
                stream='oper',     # since IFS cycle 50r1 06/18z use 'oper' too
                step=steps,
                param=PARAMS,
                target=grib,
            )
            grib_to_regional_netcdf(grib, ncfile)
            print('  wrote', ncfile)
            time.sleep(2)      # be gentle with the server between runs
        except Exception as e:
            print(f'  !! could not get run {run}: {e}')
            if os.path.exists(ncfile) and not is_latest:
                os.remove(ncfile)


if __name__ == '__main__':
    print('RUNNING')
    try:
        main(sys.argv)
    finally:
        for pat in ('*.grib2', '*.idx', '*.tmp'):
            for f in glob.glob(os.path.join(tmpdir, pat)):
                os.remove(f)
    print('FINISHED')
