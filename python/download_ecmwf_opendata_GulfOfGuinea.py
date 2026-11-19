#!/usr/bin/env python
"""
download_ecmwf_opendata_GulfOfGuinea.py

Download ECMWF IFS (HRES) real-time open data, subset it to the Gulf of
Guinea box, and save one small NetCDF per forecast run. The model and grid
spacing are configurable (0.25 deg or 0.1 deg; see MODEL/RESOL below).
Modeled on the Copernicus Marine (Mercator) download script.

Output files (one per forecast run, 00z and 12z):
    <outdir>/ecmwf_<model>_<resol>_GulfOfGuinea_YYYYMMDDHH.nc
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
  * The ECMWF server keeps only the last ~4 days. With SOURCE = 'auto' each
    run is taken from there while it lasts and from the cloud mirror (which
    holds 0.25 deg back to 2024-02-29) once it is older; see the SOURCE block.
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
from site_paths import DOWNLOADS, user_tmp

# USER SETTINGS FOR DOWNLOAD --------------------------------------------

outdir = DOWNLOADS
# Per-user temp folder, so users don't need write access to each other's tmp
# and simultaneous runs don't delete each other's temporary GRIB files
# tmpdir is per-user AND per-grid; it is defined with MODEL/RESOL below, so a
# 0.25 deg and a 0.1 deg run cannot share a scratch folder.

# GULF OF GUINEA BOUNDING BOX -16.0000   13.5000  -11.0000    8.0000
latmin = -11.0
latmax = 8.0
lonmin = -16.0
lonmax = 13.5

# WHERE THE DATA COMES FROM
# The real-time ECMWF server (data.ecmwf.int) keeps only the last few days;
# the cloud mirrors hold the whole open-data archive at 0.25 deg. Measured on
# 2026-11-11 by requesting the per-run .index files:
#     data.ecmwf.int   oldest run available was 3 days + 12 h back (~4 days)
#     google / aws     ifs/0p25   2024-02-29 -> today   (0.25 deg)
#                      0p4-beta   2023-07-15 -> 2024-02-28 (0.4 deg, superseded)
# Re-check either boundary with (HTTP 200 = that run is there):
#     curl -I https://storage.googleapis.com/ecmwf-open-data/YYYYMMDD/00z/ifs/0p25/oper/YYYYMMDD000000-0h-oper-fc.index
#
# 'auto' takes each run from the real-time server while it is still there and
# falls back to the archive mirror for anything older (or if the real-time
# request fails). Set SOURCE to one name to force that source for every run.
SOURCE = 'auto'          # 'auto' | 'ecmwf' | 'aws' | 'google' | 'azure'
REALTIME_SOURCE = 'ecmwf'
# AWS throttles heavy use from Amarel (HTTP 503 "SlowDown"); Google works.
ARCHIVE_SOURCE = 'google'
# How many days back the real-time server is trusted to still hold a run
REALTIME_DAYS = int(os.environ.get('ECMWF_REALTIME_DAYS', 3))
# ARCHIVE_START depends on the grid; it is set with MODEL/RESOL below.

# IFS short names in the open data -> cfgrib names after reading
PARAMS = ['10u', '10v', '2t', '2d', 'msl', 'ssr', 'str', 'strd', 'tp']
EXPECTED = ['u10', 'v10', 't2m', 'd2m', 'msl', 'ssr', 'str', 'strd', 'tp']

# Time window: one shared definition (bash_scripts/window.conf, or
# NDAYS_BACK/NDAYS_FWD or START_DATE/END_DATE in the environment)
from run_window import get_window, setting
tstart, tend, window_mode = get_window()
ndays_fwd = max((tend - date.today()).days, 0)  # forecast days past today (step range)
print(f'{window_mode} window: {tstart} to {tend}')

# MODEL AND GRID SPACING
# Open data are published per model and grid. Measured 2026-11-12 by listing
# the Google mirror:
#     ifs          0p25   2024-02-29 -> today   (0.25 deg, 721 x 1440)
#     ifs          0p1    2026-10-21 -> today   (0.1 deg, 1801 x 3600)
#     aifs-single  0p25   data-driven deterministic forecast
#     aifs-ens     0p25   data-driven ensemble
# 0.1 deg exists for the ifs model only, and its GRIB is split into -sfc and
# -pl parts (the client assembles them). A 0.1 deg field is about 4.6x the
# bytes of a 0.25 deg one, so expect a correspondingly longer download.
# Set these in bash_scripts/window.conf, or per run with the driver's -m/-r.
MODEL = setting('ECMWF_MODEL', 'ifs')     # 'ifs' | 'aifs-single' | 'aifs-ens'
RESOL = setting('ECMWF_RESOL', '0p25')    # '0p25' | '0p1'

VALID_RESOL = ('0p25', '0p1')
if RESOL not in VALID_RESOL:
    raise SystemExit(f'ECMWF_RESOL must be one of {VALID_RESOL}, got {RESOL!r}')
if RESOL == '0p1' and MODEL != 'ifs':
    raise SystemExit(f'0.1 deg open data exist for model ifs only, not {MODEL!r}')

# First day each grid exists on the mirrors (nothing earlier is published)
ARCHIVE_START = {'0p25': date(2024, 2, 29), '0p1': date(2026, 10, 21)}[RESOL]

# Scratch folder for the raw global GRIB, per user and per grid. Two runs at
# different resolutions must not share it: this script deletes every *.grib2,
# *.idx and *.tmp in its own tmpdir when it finishes, which would otherwise
# wipe a concurrent run's downloads.
tmpdir = user_tmp(DOWNLOADS, f'tmp_{MODEL}_{RESOL}')

print(f'ECMWF model {MODEL}, grid {RESOL} (published from {ARCHIVE_START})')
print(f'  downloads -> {outdir}')
print(f'  scratch   -> {tmpdir}')


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


_clients = {}


def client_for(source):
    """One Client per source, made on first use."""
    if source not in _clients:
        _clients[source] = Client(source=source, model=MODEL, resol=RESOL)
    return _clients[source]


def sources_for(run_date):
    """Sources to try for one run, best first.

    Within REALTIME_DAYS the real-time server is tried first and the archive
    mirror is the fallback; older runs only exist on the mirror.
    """
    if SOURCE != 'auto':
        return [SOURCE]
    if (date.today() - run_date).days <= REALTIME_DAYS:
        return [REALTIME_SOURCE, ARCHIVE_SOURCE]
    return [ARCHIVE_SOURCE]


def retrieve_run(run, steps, grib):
    """Download one run, falling back to the next source. Returns the source used."""
    errors = []
    sources = sources_for(run.date())
    for n, src in enumerate(sources, start=1):
        try:
            client_for(src).retrieve(
                date=int(run.strftime('%Y%m%d')),
                time=run.hour,
                type='fc',
                stream='oper',     # since IFS cycle 50r1 06/18z use 'oper' too
                step=steps,
                param=PARAMS,
                target=grib,
            )
            return src
        except Exception as e:
            errors.append(f'{src}: {e}')
            if n < len(sources):
                print(f'  not on {src} ({e}); trying {sources[n]}')
    raise RuntimeError('; '.join(errors))


def main(argv):
    os.makedirs(outdir, exist_ok=True)
    os.makedirs(tmpdir, exist_ok=True)

    # The window must be inside the open-data archive
    first_needed = pd.Timestamp(tstart) - pd.Timedelta(hours=12)
    if first_needed.date() < ARCHIVE_START:
        hint = ('Use 0.25 deg (ECMWF_RESOL=0p25, published from 2024-02-29) '
                'or ERA5 for earlier periods.' if RESOL == '0p1' else
                'Use ERA5 (or the 0.4 deg 0p4-beta open data, 2023-07-15 to '
                '2024-02-28) for anything earlier.')
        raise SystemExit(
            f'ECMWF open data for {MODEL} at {RESOL} start {ARCHIVE_START}, '
            f'but this window needs runs from {first_needed.date()}. {hint}')

    max_step = (ndays_fwd + 1) * 24
    assert max_step <= 144, 'ndays_fwd too large for 3-hourly open data steps'
    fwd_steps = list(range(3, max_step + 1, 3))

    # Latest run for which the full forecast range is available
    probe = os.path.join(tmpdir, f'TMP_probe_{MODEL}_{RESOL}.grib2')
    latest_source = sources_for(date.today())[0]
    newest = pd.Timestamp(client_for(latest_source).latest(
        type='fc', stream='oper', step=max_step, param='2t', target=probe))

    # The 06z and 18z runs are short-cutoff runs: they reach 90 h, so they can
    # satisfy the step request above, but they are not part of the 12-hourly
    # 00z/12z series this script stitches. Left as they are, `latest` would
    # match no run in `runs` below, `is_latest` would never be true, and the
    # long forecast steps would never be downloaded - leaving the forcing
    # short by up to 36 h. Step back to the 00z/12z run that precedes them.
    latest = newest.floor('12h')
    if latest != newest:
        print(f'Latest available run: {newest} ({newest:%H}z, short cutoff) - '
              f'using {latest} for the forecast steps')
    else:
        print(f'Latest available run: {latest}  (from {latest_source})')

    # one extra run before the window so the first valid time (00 UTC) is covered
    runs = pd.date_range(first_needed, latest, freq='12h')

    for run in runs:
        ncfile = os.path.join(
            outdir,
            run.strftime(f'ecmwf_{MODEL}_{RESOL}_GulfOfGuinea_%Y%m%d%H.nc'))
        is_latest = (run == latest)

        if os.path.exists(ncfile) and not is_latest:
            print(f'Skipping {run} (already downloaded)')
            continue

        steps = fwd_steps if is_latest else SHORT_STEPS
        grib = os.path.join(
            tmpdir, run.strftime(f'TMP_{MODEL}_{RESOL}_%Y%m%d%H.grib2'))
        print(f'Downloading run {run}  steps {steps[0]}..{steps[-1]}')

        try:
            used = retrieve_run(run, steps, grib)
            grib_to_regional_netcdf(grib, ncfile)
            print(f'  wrote {ncfile}  (source: {used})')
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
