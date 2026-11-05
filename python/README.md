# Gulf of Guinea ROMS pre-processing from Copernicus Marine (Mercator)

Scripts that download daily Mercator (Copernicus Marine, `GLOBAL_ANALYSISFORECAST_PHY_001_024`) ocean fields
and regrid them onto a ROMS grid (`grd_GulfOfGuinea_4km.nc`) to produce:

| Output | Script | File(s) written |
|---|---|---|
| Raw Mercator daily files | `download_mercator_GulfOfGuinea.py` | `mercator_GulfOfGuinea_RT_YYYY_MM_DD.nc` (one per day) |
| Open-boundary conditions | `downscale_mercator_to_roms_GulfOfGuinea_BRY.py` | `bry_gulfofguinea_Mercator_YYYYMMDD.nc` |
| Climatology / nudging files | `downscale_mercator_to_roms_GulfOfGuinea_CLM.py` | `clm_gulfofguinea_Mercator_YYYY_MM_DD.nc` (one per day) |
| Initial conditions | `downscale_mercator_to_roms_GulfOfGuinea_INI.py` | `ini_gulfofguinea_Mercator_YYYYMMDD.nc` |
| Driver for all of the above | `run_gulfofguinea_forecast.sh` | logs in `logs/run_<timestamp>/` |

> The script names above are the names the driver expects. If your files are named differently, edit the
> four `*_PY=` variables at the top of `run_gulfofguinea_forecast.sh`.

All scripts share one time window: **N days back and M days forward of today** (for example 7 back, 2 forward).
The driver sets it for all of them at once.

---

## 1. Quick start

```bash
# 1. create the python environment (section 3)
# 2. register with Copernicus Marine and log in once (section 4)
# 3. edit the directories and grid settings (section 5)
# 4. run everything
chmod +x run_gulfofguinea_forecast.sh
./run_gulfofguinea_forecast.sh -b 7 -f 2
```

Driver options:

```text
-b DAYS_BACK   days of past data before today   (default 7)
-f DAYS_FWD    days of forecast after today     (default 2)
-s STEPS       comma-separated subset of: download,bry,clm,ini   (default all four)
-h             help
```

Examples:

```bash
./run_gulfofguinea_forecast.sh -b 3 -f 5             # 3 days back, 5 forward
./run_gulfofguinea_forecast.sh -s bry,ini            # skip download and clm
```

The steps run in order (download, bry, clm, ini) and the driver stops at the first failure.

---

## 2. What you need before you start

1. A **Copernicus Marine account** (free, section 4).
2. A **ROMS grid NetCDF file** for your domain (standard ROMS grid with `lon_rho`, `lat_rho`, `mask_rho`, `h`,
   `pm`, `pn`, `angle`) such as `grd_GulfOfGuinea_4km.nc`
3. **`romsutil.py`**, the in-house ROMS helper module imported as `import romsutil as rutil`. Included in this repository,
   `create_init_file` and `uv_rot`. 
4. The **s-coordinate settings of your ROMS configuration** (section 5.3), so the output matches your model.
5. Disk space for the daily downloads and output files. Size depends on your domain.

---

## 3. Python environment and dependencies

A conda environment from `conda-forge` is strongly recommended, because `xesmf` depends on `esmpy`, which is
difficult to install with pip. `Homebrew` (https://brew.sh/) can also be used to install esmpy if conda or pip are causing issues. 

```bash
conda create -n gog-roms -c conda-forge python=3.11 \
    numpy scipy pandas xarray dask netcdf4 matplotlib cartopy \
    xesmf esmpy xroms psutil nco
conda activate gog-roms
pip install copernicusmarine
```

| Package | Used for |
|---|---|
| `numpy`, `scipy`, `pandas` | arrays, vertical interpolation (`scipy.interpolate.interp1d`), date ranges |
| `xarray`, `dask` | reading the daily files (`open_mfdataset` needs dask) |
| `netCDF4` | writing into the output files |
| `xesmf`, `esmpy` | horizontal regridding (bilinear, nearest-neighbour extrapolation) |
| `xroms` | ROMS grid handling and depth calculation (also installs `xgcm` and `cf_xarray`) |
| `cartopy`, `matplotlib` | imported by the scripts for optional plotting helpers (not called in normal runs) |
| `psutil` | imported by the CLM and INI scripts |
| `copernicusmarine` | downloading from Copernicus Marine |
| `nco` (command line tool) | the download script merges variables with `ncks`, so **`ncks` must be on your `PATH`** |
| `romsutil` | local module, see section 2 |

Check that the tools work:

```bash
python -c "import xroms, xesmf, copernicusmarine, netCDF4; print('python ok')"
ncks --version
```

Once your environment works, record the exact versions for reproducibility and commit the file:

```bash
conda env export --no-builds > environment.yml
```

If you want the driver to activate the environment for you (for example under cron), set `CONDA_ENV` and
`CONDA_SH` near the top of `run_gulfofguinea_forecast.sh`.

---

## 4. Copernicus Marine account and login

Only one external account is needed.

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

No other accounts or API keys are needed. The ROMS grid file and `romsutil.py` are local files.

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

---

## 5. What to change for a new computer or domain

### 5.1 Directories

Every script has hard-coded paths. Change these to match your machine.

| Script | Variable | What it is | Currently set to |
|---|---|---|---|
| `download_mercator_GulfOfGuinea.py` | `outdir` | where the combined daily Mercator files are saved | `/projects/f_omg_1/moa/africa/data/downloads/` |
| `download_mercator_GulfOfGuinea.py` | `tmpdir` | scratch folder for the download | `/projects/f_omg_1/moa/africa/data/temp/` |
| `..._BRY.py` | `datadir` | Mercator files (must equal the download `outdir`) | `/projects/f_omg_1/moa/africa/data/downloads/` |
| `..._BRY.py` | `outdir` | boundary file and regridding weights are written here | `/projects/f_omg_1/moa/africa/data/bry/` |
| `..._BRY.py` | `L1grdfile` | your ROMS grid file | `/projects/f_omg_1/moa/africa/data/imp_files/grd_GulfOfGuinea_4km.nc` |
| `..._CLM.py` | `datadir`, `outdir`, `L1grdfile` | same roles as above | `.../downloads/`, `.../clm/`, `.../imp_files/grd_GulfOfGuinea_4km.nc` |
| `..._INI.py` | `datadir`, `outdir`, `L1grdfile` | same roles as above | `.../downloads/`, `.../ini/`, `.../imp_files/grd_GulfOfGuinea_4km.nc` |
| `run_gulfofguinea_forecast.sh` | `LOG_ROOT` | where logs go | `logs/` next to the script |

Important details:

- **Trailing slash.** `outdir` and `tmpdir` in the download script, and `datadir` in the other scripts, are joined to
  file names by plain string concatenation, so they **must end with `/`**.
- **`datadir` (all ROMS scripts) must be exactly the download script's `outdir`.**
- **Use a dedicated `tmpdir`.** The download script deletes every `*.nc` and `*.tmp` file in `tmpdir` at the start of each
  day and when it finishes. Never point it at a folder that holds anything you want to keep.
- The download script does not create `outdir` or `tmpdir`, so create them first. The ROMS scripts create their own `outdir`.
- Example layout:

  ```text
  <your data root>/
  ├── downloads/    # Mercator daily files (download outdir, ROMS scripts datadir)
  ├── temp/         # download scratch (emptied automatically)
  ├── bry/          # boundary file + regridding weights
  ├── clm/          # climatology files + regridding weights
  ├── ini/          # initial conditions file + regridding weights
  └── imp_files/    # ROMS grid file
  ```

  ```bash
  mkdir -p <your data root>/{downloads,temp,bry,clm,ini,imp_files}
  ```

**Optional: one setting for all paths.** To avoid editing four files, you can replace the hard-coded paths with a
single environment variable, for example:

```python
root = os.environ.get('GOG_DATA_ROOT', '/projects/f_omg_1/moa/africa/data')
datadir = os.path.join(root, 'downloads') + '/'
outdir  = os.path.join(root, 'bry') + '/'          # 'clm' or 'ini' in the other scripts
L1grdfile = os.path.join(root, 'imp_files', 'grd_GulfOfGuinea_4km.nc')
```

and then `export GOG_DATA_ROOT=/your/path` before running.

### 5.2 Time window (edit once, then use the driver)

The driver passes the window through the environment variables `NDAYS_BACK` and `NDAYS_FWD`. In **each of the four python
scripts**, replace the two hard-coded lines with:

```python
ndays_back = int(os.environ.get('NDAYS_BACK', 7))   # use 0 as the default in the download script
ndays_fwd  = int(os.environ.get('NDAYS_FWD', 2))
```

(`import os` is already present in all of them.) After that you only ever set `-b` and `-f` on the command line.
Running a script directly without the driver uses the defaults in these lines.

Every script computes its dates from `date.today()`. Do not start a run just before midnight, or the download and
the later steps could use different days.

### 5.3 ROMS grid and vertical coordinate (must match your model)

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
three scripts.

### 5.4 Reference time (must be identical everywhere)

```python
reftime = datetime.datetime(2026,1,1)   # "days since 2026-01-01"
```

This sets the time units written into the BRY, CLM and INI files. It must be **the same in all three scripts and
consistent with the time reference in your ROMS input**. The usual choice is January 1st of the forecast year.

### 5.5 Domain: the Mercator download box must cover your ROMS grid

In the download script:

```python
latmin=-11.0; latmax=8.0
lonmin=-16.0; lonmax=13.5
zmin=-10.0;   zmax=6000.0      # depth range (m)
```

Change these if you move to another region. The box must extend past every edge of your ROMS grid by at least a
few Mercator grid cells (about 0.083 degrees each). Otherwise the boundary and corner values will be extrapolated
from the nearest points.

The `latmin/latmax/lonmin/lonmax` values at the top of the BRY script are only used by the optional plotting helper
functions, which are not called in normal runs. You can leave them.

### 5.6 Open boundaries (BRY script only)

```python
bdylist = {'EAST': False, 'WEST': True, 'NORTH': True, 'SOUTH': True}
```

Set `True` for each side of your grid that is an open ocean boundary and `False` for closed (land) sides.
It must agree with the open boundary settings in your ROMS configuration.

### 5.7 Other things you might change

- **Product / dataset IDs** and the output file name pattern `mercator_GulfOfGuinea_RT_%Y_%m_%d.nc`. If you rename
  the pattern, change it in the download script **and** in all three ROMS scripts.
- **Output file names** (`bry_gulfofguinea_...`, `clm_gulfofguinea_...`, `ini_gulfofguinea_...`) if you work on
  another region.

---

## 6. What the scripts do

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

### Regridding weight files (important)

The first run computes xESMF weights and saves them in the output folder
(`regrid_mercator_bry_{EAST,WEST,NORTH,SOUTH}.nc`, `regrid_mercator_clm.nc`, `regrid_mercator_ini.nc`). Later runs
re-use them. **Delete these files whenever you change the ROMS grid or the Mercator download box**, otherwise the old
weights will be used silently.

---

## 7. Outputs and using them in ROMS

Point your ROMS input file at the generated files, for example:

```text
BRYNAME == .../bry/bry_gulfofguinea_Mercator_YYYYMMDD.nc
NUDNAME == .../clm/clm_gulfofguinea_Mercator_YYYY_MM_DD.nc    (one file per day)
ININAME == .../ini/ini_gulfofguinea_Mercator_YYYYMMDD.nc
```

`YYYYMMDD` in the BRY and INI file names is the first day of the window (today minus `-b` days).

---

## 8. Running automatically (cron example)

```cron
# every day at 02:00 - 7 days back, 2 days forward
0 2 * * * cd /path/to/this/folder && ./run_gulfofguinea_forecast.sh -b 7 -f 2 >> cron.log 2>&1
```

Cron has a minimal environment. Set `CONDA_ENV` and `CONDA_SH` in the driver (or export `PATH` yourself) so the right
python and `ncks` are found. The Copernicus login (or the environment variables in section 4) must also be available
to the cron user.

---

## 9. Troubleshooting

| Symptom | Likely cause |
|---|---|
| `FileNotFoundError: Missing Mercator files: [...]` | The download did not cover the same window, or `datadir` does not match the download `outdir` (missing trailing slash?). Run the driver with the same `-b`/`-f` for all steps. |
| `ncks: command not found` | NCO is not installed or not on `PATH` (`conda install -c conda-forge nco`). |
| Download asks for a username/password or fails with authentication errors | Run `copernicusmarine login`, or set the `COPERNICUSMARINE_SERVICE_*` variables. |
| `ModuleNotFoundError: romsutil` | Put `romsutil.py` in this folder or on `PYTHONPATH`. |
| `ImportError` for `xesmf`/`esmpy` | Install both from `conda-forge`, not pip. |
| Boundary values look wrong after changing grid or box | Delete old `regrid_mercator_*.nc` weight files. |
| Odd vertical structure in ROMS | `theta_s`, `theta_b`, `Tcline`, `N`, `Vtransform`, `Vstretching` or `hc` do not match your ROMS `.in` file. |
| ROMS reports time out of range | `reftime` differs between the scripts or from your ROMS time reference. |

---

## 10. Known issues to fix before first use

These come from reading the current versions of the scripts. Remove this section once they are fixed.

1. **INI script call mismatch.** `downscale_init_file(cfgrd,dsmerc)` is called with two arguments, but the function is
   defined as `downscale_init_file(cfgrd,dsmerc,inifile)`. Pass `inifile` in the call.
2. **INI script overwrites its own output.** It loops over every day in the window but always writes the same
   `inifile`, so the file ends up with the last day instead of the start date. Process only `date_times[0]`.
3. **INI reference time.** It uses `reftime = datetime.datetime(2024,1,1)` while BRY and CLM use 2026. Make all three
   identical (section 5.4).

---

## Credits

Originally created by Elias Hunter (Rutgers), adapted by John Wilkin (2025, 2026) and Becca Horwitz (2026).
Mercator data are provided by the E.U. Copernicus Marine Service. Please follow their citation and data-use
requirements.

Add a `LICENSE` file before publishing.
