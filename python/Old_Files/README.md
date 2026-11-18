# Gulf of Guinea ROMS pre-processing: ocean (Mercator) and atmosphere (ECMWF IFS)

Scripts that prepare all the forcing for a Gulf of Guinea ROMS forecast on the grid `grd_GulfOfGuinea_4km.nc`.

**Ocean.** Daily Mercator fields (Copernicus Marine, `GLOBAL_ANALYSISFORECAST_PHY_001_024`) are downloaded and regridded onto the ROMS grid to produce boundary, climatology and initial condition files.

**Atmosphere.** ECMWF IFS (HRES) open data at 0.25 degrees is downloaded, subset to the Gulf of Guinea box, and converted to a ROMS bulk-flux forcing file.

| Output | Script | File(s) written |
|---|---|---|
| Raw Mercator daily files | `download_mercator_GulfOfGuinea.py` | `mercator_GulfOfGuinea_RT_YYYY_MM_DD.nc` (one per day) |
| Open-boundary conditions | `downscale_mercator_to_roms_GulfOfGuinea_BRY.py` | `bry_gulfofguinea_Mercator_YYYYMMDD.nc` |
| Climatology / nudging files | `downscale_mercator_to_roms_GulfOfGuinea_CLM.py` | `clm_gulfofguinea_Mercator_YYYY_MM_DD.nc` (one per day) |
| Initial conditions | `downscale_mercator_to_roms_GulfOfGuinea_INI.py` | `ini_gulfofguinea_Mercator_YYYYMMDD.nc` |
| Raw ECMWF regional files | `download_ecmwf_opendata_GulfOfGuinea.py` | `ecmwf_ifs_0p25_GulfOfGuinea_YYYYMMDDHH.nc` (one per forecast run, 00z and 12z) |
| Bulk-flux forcing | `convert_ecmwf_to_roms_frc_GulfOfGuinea.py` | `GulfOfGuinea_frc_IFS_bulkflux_YYYYMMDD.nc` (one file for the whole window) |
| Driver for all of the above | `run_gulfofguinea_all.sh` | logs in `logs/run_<timestamp>/` |

> The script names above are the names the driver expects. If your files are named differently, edit the six
> `*_PY=` variables at the top of `run_gulfofguinea_all.sh`.

All scripts share one time window: **N days back and M days forward of today** (for example 3 back, 2 forward).
The driver sets it for all of them at once.

---

## Quick start

```bash
# 1. create the python environment (section 2)
# 2. register with Copernicus Marine and log in once (section 3)
# 3. edit the directories, grid settings and time window lines (section 4)
# 4. run everything
chmod +x run_gulfofguinea_all.sh
./run_gulfofguinea_all.sh -b 3 -f 2
```

Driver options:

```text
-b DAYS_BACK   days of past data before today   (default 3)
-f DAYS_FWD    days of forecast after today     (default 2, max 5 when the met steps run)
-s STEPS       comma-separated steps to run     (default all)
-h             help
```

Steps:

| Step | What it runs | Part |
|---|---|---|
| `download` | Mercator download | ocean |
| `bry` | boundary file | ocean |
| `clm` | climatology files | ocean |
| `ini` | initial conditions file | ocean |
| `metdl` | ECMWF open data download | atmosphere |
| `frc` | conversion to ROMS bulk-flux forcing | atmosphere |

Shortcuts for `-s`: `ocean` (= `download,bry,clm,ini`), `met` (= `metdl,frc`) and `all` (everything).

Examples:

```bash
./run_gulfofguinea_all.sh                         # everything, 3 days back, 2 forward
./run_gulfofguinea_all.sh -b 2 -f 5               # everything, 2 back, 5 forward
./run_gulfofguinea_all.sh -s met                  # only the atmospheric forcing
./run_gulfofguinea_all.sh -s ocean -b 7 -f 2      # only the ocean files, with a longer record
./run_gulfofguinea_all.sh -s bry,ini,frc          # pick individual steps
```

Steps always run in the order download, bry, clm, ini, metdl, frc, whatever order you give them, and the driver
stops at the first failure.

**Why the default is 3 days back.** The ECMWF open data server only keeps a few days of history, so a longer
shared window fails in the `metdl` step. If you want a longer record for the ocean files, run the ocean and met
steps separately (see the example above), or set `SOURCE` to `'aws'`, `'google'` or `'azure'` in the ECMWF download
script (check how far back those archives go).

**Why `-f` is limited to 5 for the met steps.** The open data forecast goes out to 144 hours, and the download
script requests up to `(ndays_fwd + 1) * 24` hours. An ocean-only run (`-s ocean`) can use a longer forecast
window if Mercator provides it.

---

## 1. What you need before you start

1. A **Copernicus Marine account** (free, section 3). No account is needed for ECMWF open data.
2. A **ROMS grid NetCDF file** for your domain (standard ROMS grid with `lon_rho`, `lat_rho`, `mask_rho`, `h`,
   `pm`, `pn`, `angle`) such as `grd_GulfOfGuinea_4km.nc`.
3. **`romsutil.py`**, the in-house ROMS helper module imported as `import romsutil as rutil`. Included in this
   repository (`create_init_file` and `uv_rot`). It is used by the ocean scripts only.
4. The **s-coordinate settings of your ROMS configuration** (section 4.4), so the ocean output matches your model.
5. Disk space for the daily downloads and output files. Size depends on your domain.

---

## 2. Python environment and dependencies

A conda environment from `conda-forge` is strongly recommended, because `xesmf` depends on `esmpy`, which is
difficult to install with pip. `Homebrew` (https://brew.sh/) can also be used to install esmpy if conda or pip are
causing issues. The ECMWF scripts also need `eccodes`, which is easiest to get from conda-forge.

```bash
conda create -n gog-roms -c conda-forge python=3.11 \
    numpy scipy pandas xarray dask netcdf4 matplotlib cartopy \
    xesmf esmpy xroms psutil nco \
    eccodes python-eccodes cfgrib
conda activate gog-roms
pip install copernicusmarine ecmwf-opendata
```

| Package | Used for |
|---|---|
| `numpy`, `scipy`, `pandas` | arrays, vertical interpolation (`scipy.interpolate.interp1d`), date ranges |
| `xarray`, `dask` | reading the daily files (`open_mfdataset` needs dask) |
| `netCDF4` | writing into the output files |
| `xesmf`, `esmpy` | horizontal regridding of the ocean fields (bilinear, nearest-neighbour extrapolation) |
| `xroms` | ROMS grid handling and depth calculation (also installs `xgcm` and `cf_xarray`) |
| `cartopy`, `matplotlib` | imported by the ocean scripts for optional plotting helpers (not called in normal runs) |
| `psutil` | imported by the CLM and INI scripts |
| `copernicusmarine` | downloading from Copernicus Marine |
| `nco` (command line tool) | the Mercator download script merges variables with `ncks`, so **`ncks` must be on your `PATH`** |
| `ecmwf-opendata` | downloading ECMWF open data |
| `eccodes`, `python-eccodes`, `cfgrib` | reading the ECMWF GRIB files |
| `romsutil` | local module, see section 1 |

Check that the tools work:

```bash
python -c "import xroms, xesmf, copernicusmarine, netCDF4; print('ocean python ok')"
python -c "import cfgrib, xarray; from ecmwf.opendata import Client; print('met python ok')"
ncks --version
```

Once your environment works, record the exact versions for reproducibility and commit the file:

```bash
conda env export --no-builds > environment.yml
```

If you want the driver to activate the environment for you (for example under cron), set `CONDA_ENV` and
`CONDA_SH` near the top of `run_gulfofguinea_all.sh`.

---

## 3. Accounts and data sources

### 3.1 Copernicus Marine (ocean, account required)

1. Register for free at <https://marine.copernicus.eu> (use the *Register* link).
2. Log in once on the machine that will run the download:

   ```bash
   copernicusmarine login
   ```

   This stores your credentials in `~/.copernicusmarine/` for later runs. Do this as the same user that
   will run the scripts (including the cron user).
3. For non-interactive systems you can instead set environment variables before running:

   ```bash
   export COPERNICUSMARINE_SERVICE_USERNAME="your_username"
   export COPERNICUSMARINE_SERVICE_PASSWORD="your_password"
   ```

   Never commit credentials to GitHub.

The ROMS grid file and `romsutil.py` are local files.

The datasets downloaded are the global 1/12 degree daily analysis/forecast products:

| Variable(s) | Dataset ID |
|---|---|
| `so` (salinity) | `cmems_mod_glo_phy-so_anfc_0.083deg_P1D-m` |
| `thetao` (potential temperature) | `cmems_mod_glo_phy-thetao_anfc_0.083deg_P1D-m` |
| `uo`, `vo` (currents) | `cmems_mod_glo_phy-cur_anfc_0.083deg_P1D-m` |
| `zos` (sea surface height) | `cmems_mod_glo_phy_anfc_0.083deg_P1D-m` |

Dataset IDs and versions can change. If a download fails with a "dataset not found" error, check the current
catalogue on the Copernicus Marine website (or with `copernicusmarine describe`) and update the `ids` list.
How far back and forward these products reach is set by Copernicus. If you request days outside that range
the download fails.

### 3.2 ECMWF open data (atmosphere, no account)

The IFS HRES real-time open data (0.25 degrees, 3-hourly) is free and needs no account or API key. It is licensed
CC BY 4.0, so keep the attribution that the conversion script writes into the forcing file
(`Contains ECMWF open data ...`). See <https://www.ecmwf.int/en/forecasts/datasets/open-data>.

The variables downloaded are 10 m winds (`10u`, `10v`), 2 m temperature and dewpoint (`2t`, `2d`), mean sea level
pressure (`msl`), net surface solar and thermal radiation (`ssr`, `str`), downward surface thermal radiation
(`strd`) and total precipitation (`tp`).

The `SOURCE` setting in the download script selects where the data comes from: `'ecmwf'` (default, keeps only a few
days), or the mirrors `'aws'`, `'google'` and `'azure'`.

---

## 4. What to change for a new computer or domain

### 4.1 Directories

Every script has hard-coded paths. Change these to match your machine.

| Script | Variable | What it is | Currently set to |
|---|---|---|---|
| `download_mercator_GulfOfGuinea.py` | `outdir` | where the combined daily Mercator files are saved | `/projects/f_omg_1/moa/africa/data/downloads/` |
| `download_mercator_GulfOfGuinea.py` | `tmpdir` | scratch folder for the download | `/projects/f_omg_1/moa/africa/data/temp/` |
| `..._BRY.py` | `datadir` | Mercator files (must equal the Mercator download `outdir`) | `/projects/f_omg_1/moa/africa/data/downloads/` |
| `..._BRY.py` | `outdir` | boundary file and regridding weights are written here | `/projects/f_omg_1/moa/africa/data/bry/` |
| `..._BRY.py` | `L1grdfile` | your ROMS grid file | `/projects/f_omg_1/moa/africa/data/imp_files/grd_GulfOfGuinea_4km.nc` |
| `..._CLM.py` | `datadir`, `outdir`, `L1grdfile` | same roles as above | `.../downloads/`, `.../clm/`, `.../imp_files/grd_GulfOfGuinea_4km.nc` |
| `..._INI.py` | `datadir`, `outdir`, `L1grdfile` | same roles as above | `.../downloads/`, `.../ini/`, `.../imp_files/grd_GulfOfGuinea_4km.nc` |
| `download_ecmwf_opendata_GulfOfGuinea.py` | `outdir` | where the regional ECMWF run files are saved | `/projects/f_omg_1/moa/africa/data/downloads/` |
| `download_ecmwf_opendata_GulfOfGuinea.py` | `tmpdir` | scratch folder for the global GRIB files | `/projects/f_omg_1/moa/africa/data/downloads/tmp/` |
| `convert_ecmwf_to_roms_frc_GulfOfGuinea.py` | `indir` | ECMWF run files (must equal the ECMWF download `outdir`) | `/projects/f_omg_1/moa/africa/data/downloads/` |
| `convert_ecmwf_to_roms_frc_GulfOfGuinea.py` | `outdir` | forcing file is written here | `/projects/f_omg_1/moa/africa/data/blk/` |
| `convert_ecmwf_to_roms_frc_GulfOfGuinea.py` | `ROMS_GRID_FILE` | grid file, only used to warn if the forcing does not cover it | `/projects/f_omg_1/moa/africa/data/imp_files/grd_GulfOfGuinea_4km.nc` |
| `convert_ecmwf_to_roms_frc_GulfOfGuinea.py` | `REF_FRC_FILE` | optional existing forcing file whose lon/lat define the target grid | `None` (native 0.25 degree grid) |
| `run_gulfofguinea_all.sh` | `LOG_ROOT` | where logs go | `logs/` next to the script |

Important details:

- **Trailing slash.** `outdir` and `tmpdir` in the download scripts, and `datadir` in the ocean ROMS scripts, are
  joined to file names by plain string concatenation, so they **must end with `/`**.
- **`datadir` (all ocean ROMS scripts) must be exactly the Mercator download `outdir`**, and **`indir` in the
  conversion script must be exactly the ECMWF download `outdir`**.
- **The Mercator and ECMWF files can share the `downloads/` folder.** Their file names do not overlap, and the
  conversion script only reads `ecmwf_ifs_0p25_GulfOfGuinea_*.nc`.
- **Use dedicated `tmpdir` folders.** The Mercator download script deletes every `*.nc` and `*.tmp` file in its
  `tmpdir` at the start of each day and when it finishes. The ECMWF download script deletes every `*.grib2`, `*.idx`
  and `*.tmp` file in its `tmpdir` when it finishes. Never point either at a folder that holds anything you want
  to keep, and do not make the two share one.
- The Mercator download script does not create `outdir` or `tmpdir`, so create them first. The ECMWF download and
  conversion scripts, and the ocean ROMS scripts, create their own output folders.
- The ECMWF download skips any past run whose file already exists (the latest run is always downloaded again).
  Delete the files in `downloads/` if you want to force a fresh download.
- Example layout:

  ```text
  <your data root>/
  ├── downloads/    # Mercator daily files and ECMWF run files (download outdir, ROMS scripts datadir)
  │   └── tmp/      # ECMWF download scratch (emptied automatically)
  ├── temp/         # Mercator download scratch (emptied automatically)
  ├── bry/          # boundary file + regridding weights
  ├── clm/          # climatology files + regridding weights
  ├── ini/          # initial conditions file + regridding weights
  ├── blk/          # bulk-flux forcing file
  └── imp_files/    # ROMS grid file
  ```

  ```bash
  mkdir -p <your data root>/{downloads/tmp,temp,bry,clm,ini,blk,imp_files}
  ```

**Optional: one setting for all paths.** To avoid editing six files, you can replace the hard-coded paths with a
single environment variable, for example:

```python
root = os.environ.get('GOG_DATA_ROOT', '/projects/f_omg_1/moa/africa/data')
datadir = os.path.join(root, 'downloads') + '/'
outdir  = os.path.join(root, 'bry') + '/'          # 'clm', 'ini' or 'blk' in the other scripts
L1grdfile = os.path.join(root, 'imp_files', 'grd_GulfOfGuinea_4km.nc')
```

and then `export GOG_DATA_ROOT=/your/path` before running.

### 4.2 Time window (edit once, then use the driver)

The driver passes the window through the environment variables `NDAYS_BACK` and `NDAYS_FWD`. In **each of the six
python scripts**, replace the two hard-coded lines with:

```python
ndays_back = int(os.environ.get('NDAYS_BACK', 3))   # use 0 as the default in the Mercator download script
ndays_fwd  = int(os.environ.get('NDAYS_FWD', 2))
```

(`import os` is already present in all of them.) After that you only ever set `-b` and `-f` on the command line.
Running a script directly without the driver uses the defaults in these lines.

Every script computes its dates from `date.today()`. Do not start a run just before midnight, or the download and
the later steps could use different days.

Keep `-b` and `-f` the same between a download step and the step that reads its files. For example, if you run
`-s frc` with a larger `-b` than the earlier `metdl` run used, the conversion finds no data for the extra days and
warns about gaps. The same applies to `bry`, `clm` and `ini` after `download`.

### 4.3 ROMS grid and vertical coordinate (must match your model)

In the BRY, CLM and INI scripts, set these to the values used in your ROMS configuration (`.in` file):

```python
L1theta_s     = 7.0    # surface stretching
L1theta_b     = 2.0    # bottom stretching
L1Tcline      = 250.0  # critical depth
L1N           = 50     # number of vertical levels
L1Vtransform  = 2
L1Vstretching = 4
L1hc          = 250
```

If these differ from your model, the files will load but the vertical levels will be wrong. Keep them identical in all
three scripts. The ECMWF scripts do not use vertical coordinates.

### 4.4 Reference time (must be consistent everywhere)

In the ocean scripts:

```python
reftime = datetime.datetime(2026,1,1)   # "days since 2026-01-01"
```

This sets the time units written into the BRY, CLM and INI files. It must be **the same in all three scripts and
consistent with the time reference in your ROMS input**. The usual choice is January 1st of the forecast year.

The conversion script sets its own reference time automatically, as January 1st of the year of the first day in
the window (`REFTIME`), and writes it into the forcing file as `days since YYYY-01-01`. Check that this matches the
ocean `reftime`. Around New Year the two can differ if you forget to update the ocean scripts, so change the ocean
`reftime` at the start of each year (or set `REFTIME` in the conversion script to the same fixed date).

### 4.5 Domain: the download boxes must cover your ROMS grid

In the Mercator download script:

```python
latmin=-11.0; latmax=8.0
lonmin=-16.0; lonmax=13.5
zmin=-10.0;   zmax=6000.0      # depth range (m)
```

In the ECMWF download script (the box crosses the prime meridian, which the script handles):

```python
latmin = -11.0
latmax = 8.0
lonmin = -16.0
lonmax = 13.5
```

Change these if you move to another region. Each box must extend past every edge of your ROMS grid. For Mercator,
leave at least a few grid cells (about 0.083 degrees each) of margin, otherwise the boundary and corner values will be
extrapolated from the nearest points. For ECMWF, the conversion script prints `Forcing covers ROMS grid: True/False`
when `ROMS_GRID_FILE` is set. If it is `False`, widen the box.

The `latmin/latmax/lonmin/lonmax` values at the top of the BRY script are only used by the optional plotting helper
functions, which are not called in normal runs. You can leave them.

### 4.6 Open boundaries (BRY script only)

```python
bdylist = {'EAST': False, 'WEST': True, 'NORTH': True, 'SOUTH': True}
```

Set `True` for each side of your grid that is an open ocean boundary and `False` for closed (land) sides.
It must agree with the open boundary settings in your ROMS configuration.

### 4.7 Other things you might change

- **Product / dataset IDs** and the Mercator output file name pattern `mercator_GulfOfGuinea_RT_%Y_%m_%d.nc`. If you
  rename the pattern, change it in the download script **and** in all three ocean ROMS scripts.
- **ECMWF file name pattern** `ecmwf_ifs_0p25_GulfOfGuinea_%Y%m%d%H.nc`. If you rename it, change it in the download
  script **and** in the `glob` in the conversion script.
- **Output file names** (`bry_gulfofguinea_...`, `clm_gulfofguinea_...`, `ini_gulfofguinea_...`,
  `GulfOfGuinea_frc_IFS_...`) if you work on another region.
- **Target grid for the forcing.** By default the forcing is on the native 0.25 degree grid cut to the box. Set
  `REF_FRC_FILE` in the conversion script to interpolate (linearly) onto the lon/lat of an existing forcing file.
- **Pressure variable.** `PAIR_VAR = 'msl'` uses mean sea level pressure for `Pair`.
- **NetCDF format.** `NC_FORMAT` in the conversion script is `NETCDF3_64BIT_OFFSET` (use `'NETCDF4'` if your ROMS
  build reads it).

---

## 5. What the scripts do

### 5.1 Ocean

1. **Download.** For each day in the window, downloads salinity, temperature, currents and sea surface height
   separately with `copernicusmarine.subset`, merges them with `ncks -A` into one daily file, and copies it to `outdir`.
2. **Horizontal regridding.** Fills land/missing values in the Mercator fields by nearest-neighbour extrapolation, then
   regrids bilinearly onto the ROMS grid (or onto the three grid rows/columns along each boundary for BRY) with xESMF.
3. **Vertical interpolation.** Interpolates from Mercator depth levels to the ROMS terrain-following levels at each
   unmasked ocean point. This loops in pure Python over grid points, so it can take several minutes per file on
   large grids.
4. **Velocity rotation and averaging.** Rotates east/north velocities to the ROMS grid orientation and computes
   depth-averaged `ubar`/`vbar`.
5. **Write output** into NetCDF files created by `romsutil`.

#### Regridding weight files (important)

The first run computes xESMF weights and saves them in the output folder
(`regrid_mercator_bry_{EAST,WEST,NORTH,SOUTH}.nc`, `regrid_mercator_clm.nc`, `regrid_mercator_ini.nc`). Later runs
re-use them. **Delete these files whenever you change the ROMS grid or the Mercator download box**, otherwise the old
weights will be used silently.

### 5.2 Atmosphere

1. **Download (`metdl`).** The ECMWF server cannot subset by area, so the script downloads the global GRIB for each
   forecast run into `tmpdir`, cuts it to the box, writes one small NetCDF per run, and deletes the GRIB. For every
   run in the window it fetches steps 3, 6, 9 and 12 hours (the short lead part used to build a continuous record).
   For the latest available run it fetches steps 3 to `(ndays_fwd + 1) * 24` hours (the forecast). Runs are 00z and 12z.
2. **Conversion (`frc`).** The conversion script reads all the run files and builds one forcing file:
   - Accumulated fields (`ssr`, `str`, `strd`, `tp`) are de-accumulated within each run (accumulation starts at zero at
     step 0) and divided by the interval, giving W m-2 for the radiation terms and kg m-2 s-1 for rain.
   - For every valid time it takes the most recent run that covers it (the smallest lead time), so the record is
     continuous.
   - Flux values are the mean over the 3 hours ending at the time stamp (the same convention as ERA5 accumulations).
   - Units are converted to ROMS conventions: `Pair` in millibar, `Tair` in Celsius, `Qair` as relative humidity in
     percent (computed from the 2 m temperature and dewpoint), and wind in m s-1.
   - The time axis is 3-hourly because the open data steps are 3-hourly.
3. **Checks.** The conversion script prints the time spacing and warns if the time axis is not uniform (a missing
   run) or if the data end before the requested end date. It stops with an error if any field contains NaNs.

The window covered by the forcing file starts at `today - ndays_back` and ends at the end of the last forecast day.

---

## 6. Outputs and using them in ROMS

Point your ROMS input file at the generated files, for example:

```text
BRYNAME == .../bry/bry_gulfofguinea_Mercator_YYYYMMDD.nc
NUDNAME == .../clm/clm_gulfofguinea_Mercator_YYYY_MM_DD.nc    (one file per day)
ININAME == .../ini/ini_gulfofguinea_Mercator_YYYYMMDD.nc
FRCNAME == .../blk/GulfOfGuinea_frc_IFS_bulkflux_YYYYMMDD.nc
```

`YYYYMMDD` in the BRY, INI and forcing file names is the first day of the window (today minus `-b` days).

The forcing file has the same layout as the ERA5 bulk-flux forcing files used for hindcasts (dimensions `lon`, `lat`,
`time`; variables `Uwind`, `Vwind`, `Pair`, `Tair`, `Qair`, `swrad`, `lwrad_down`, `lwrad`, `rain`), so it can be
used in the same way in a forecast run.

---

## 7. Running automatically (cron example)

```cron
# every day at 02:00 - 3 days back, 2 days forward, all steps
0 2 * * * cd /path/to/this/folder && ./run_gulfofguinea_all.sh -b 3 -f 2 >> cron.log 2>&1
```

Cron has a minimal environment. Set `CONDA_ENV` and `CONDA_SH` in the driver (or export `PATH` yourself) so the right
python and `ncks` are found. The Copernicus login (or the environment variables in section 3.1) must also be
available to the cron user.

The ECMWF download uses the latest run that is available at the time the script runs, so the time you schedule it
decides which run is used. Check ECMWF's publication times and pick a time after the run you want has been released.

---

## 8. Troubleshooting

| Symptom | Likely cause |
|---|---|
| `FileNotFoundError: Missing Mercator files: [...]` | The download did not cover the same window, or `datadir` does not match the download `outdir` (missing trailing slash?). Run the driver with the same `-b`/`-f` for all steps. |
| `ncks: command not found` | NCO is not installed or not on `PATH` (`conda install -c conda-forge nco`). |
| Mercator download asks for a username/password or fails with authentication errors | Run `copernicusmarine login`, or set the `COPERNICUSMARINE_SERVICE_*` variables. |
| `ModuleNotFoundError: romsutil` | Put `romsutil.py` in this folder or on `PYTHONPATH`. |
| `ImportError` for `xesmf`/`esmpy` | Install both from `conda-forge`, not pip. |
| Boundary values look wrong after changing grid or box | Delete old `regrid_mercator_*.nc` weight files. |
| Odd vertical structure in ROMS | `theta_s`, `theta_b`, `Tcline`, `N`, `Vtransform`, `Vstretching` or `hc` do not match your ROMS `.in` file. |
| ROMS reports time out of range | `reftime` differs between the ocean scripts, or differs from the forcing file reference time, or from your ROMS time reference. |
| `ERROR: -f must be <= 5 when metdl/frc run` | The ECMWF open data only reaches 144 hours. Lower `-f`, or run `-s ocean` separately for a longer ocean forecast. |
| `ImportError` or `RuntimeError` about eccodes or cfgrib | `eccodes`, `python-eccodes` and `cfgrib` are not installed in the active environment. Install them from `conda-forge`. |
| ECMWF download prints `!! could not get run ...` | The run is older than the server keeps. Lower `-b`, or set `SOURCE` to `'aws'`, `'google'` or `'azure'` in the download script. |
| `Variables missing from GRIB: [...]` | The download did not return all the requested parameters. Check the `PARAMS` list and the run's log in `logs/run_<timestamp>/metdl.log`. |
| `FileNotFoundError: No input files found in ...` | `indir` in the conversion script does not match the ECMWF download `outdir`, or `metdl` has not run. |
| `RuntimeError: No data inside the requested time window` | `-b` or `-f` differs between `metdl` and `frc`, or the downloaded runs do not cover the window. Rerun both with the same values. |
| `WARNING: time axis is not uniform` | A forecast run is missing in the window. Rerun `metdl` (delete the file for the missing run first). |
| `WARNING: data end at ..., before requested ...` | The latest run did not reach the requested end date. Lower `-f` or rerun when a newer run is available. |
| `Forcing covers ROMS grid: False` | The ECMWF box is smaller than your ROMS grid. Widen `latmin/latmax/lonmin/lonmax` in the ECMWF download script. |

---

## 9. Known issues to fix before first use

These come from reading the current versions of the ocean scripts. Remove this section once they are fixed.

1. **INI script call mismatch.** `downscale_init_file(cfgrd,dsmerc)` is called with two arguments, but the function is
   defined as `downscale_init_file(cfgrd,dsmerc,inifile)`. Pass `inifile` in the call.
2. **INI script overwrites its own output.** It loops over every day in the window but always writes the same
   `inifile`, so the file ends up with the last day instead of the start date. Process only `date_times[0]`.
3. **INI reference time.** It uses `reftime = datetime.datetime(2024,1,1)` while BRY and CLM use 2026. Make all three
   identical (section 4.4).

---

## Credits

Originally created by Elias Hunter (Rutgers), adapted by John Wilkin (2025, 2026) and Becca Horwitz, Cody Benton and Sean Divine (2026).
Mercator data are provided by the E.U. Copernicus Marine Service. Atmospheric data contain ECMWF open data, licensed
CC BY 4.0. Please follow their citation and data-use requirements.

Add a `LICENSE` file before publishing.
