# Running the Gulf of Guinea ocean forecast

This guide takes you from a fresh computer to a working ocean forecast for the
Gulf of Guinea. It assumes you can open a terminal and copy commands. It does
**not** assume you have run an ocean model before.

If a word is new to you, check the [glossary](#2-words-you-will-meet) in
section 2. Terms are explained the first time they appear.

**Contents**

Background

1. [What this does](#1-what-this-does)
2. [Words you will meet](#2-words-you-will-meet)
3. [What it costs: disk, internet, time](#3-what-it-costs-disk-internet-time)
4. [Can I run this on my computer?](#4-can-i-run-this-on-my-computer)

Setting up, in order

5. [The whole setup at a glance](#5-the-whole-setup-at-a-glance)
6. [Step 1 — Create your accounts](#6-step-1--create-your-accounts)
7. [Step 2 — Get the code and install the packages](#7-step-2--get-the-code-and-install-the-packages)
8. [Step 3 — Obtain the four fixed files](#8-step-3--obtain-the-four-fixed-files)
9. [Step 4 — Create the folders](#9-step-4--create-the-folders)
10. [Step 5 — Set the paths in site.conf](#10-step-5--set-the-paths-in-siteconf)
11. [Step 6 — Choose the dates in window.conf](#11-step-6--choose-the-dates-in-windowconf)
12. [Step 7 — Compile ROMS](#12-step-7--compile-roms)

Running

13. [Which script to run, in what order](#13-which-script-to-run-in-what-order)
14. [Where your log files are](#14-where-your-log-files-are)
15. [Sharing the system with colleagues](#15-sharing-the-system-with-colleagues)
16. [How to know it worked](#16-how-to-know-it-worked)
17. [What each step actually does](#17-what-each-step-actually-does)

Help

18. [When something goes wrong](#18-when-something-goes-wrong)
19. [Reference tables](#19-reference-tables)
20. [Credit where it is due](#20-credit-where-it-is-due)

---

## 1. What this does

A **numerical ocean model** solves the equations of fluid motion on a grid of
points covering a piece of ocean. This repository runs one for the Gulf of
Guinea, on a grid with about 4 km between neighbouring points.

A model cannot run on its own. You must tell it three things:

1. **Where it starts.** The temperature, salinity, currents and sea level everywhere in the region on day one. This is the *initial condition*.
2. **What happens at the edges.** The Gulf of Guinea is not a closed basin, so water flows in and out across the open sides of the grid. These are the *boundary conditions*, and they come from a global ocean model.
3. **What the atmosphere is doing.** Wind pushes the sea surface, sunlight warms it, rain and evaporation change its saltiness. This is the *surface forcing*, and it comes from a weather forecast.

The scripts here fetch those three ingredients from public data services, put
them on the model's own grid, write the model's settings file, and run the
model. The result is a forecast of currents, temperature, salinity and sea
level for the next few days.

The work was developed to support the Coastal Ocean Environment Summer Schools
in Nigeria and Ghana.

---

## 2. Words you will meet

| Word | What it means here |
|------|--------------------|
| **ROMS** | Regional Ocean Modeling System, the model program itself. Free and open source. You compile it once. |
| **grid** | The mesh of points the model computes on. Ours covers roughly 16°W–13.5°E and 11°S–8°N at 4 km spacing. |
| **forcing** | Data pushed into the model from outside — here, wind, heat and rain from a weather forecast. |
| **initial condition (INI)** | The ocean state on the first day of the run. |
| **boundary condition (BRY)** | The ocean state at the open edges of the grid, for every day of the run. |
| **climatology (CLM)** | Here, the global ocean model's fields interpolated onto our grid for every day, used for nudging the interior. |
| **nudging** | Gently pulling the model back toward the global fields, so it does not drift away from reality. |
| **forecast** | A run covering dates that include the future. |
| **hindcast** | A run covering dates entirely in the past, to study something that already happened. |
| **Mercator / CMEMS** | The European global ocean analysis. Our source for ocean temperature, salinity, currents and sea level. |
| **ECMWF / IFS** | The European weather centre and its forecast model. Our source for atmospheric forcing. |
| **GloFAS** | A global river discharge dataset. Our source for river inflow. |
| **NetCDF (`.nc`)** | The standard file format for this kind of gridded data. |
| **GRIB** | The format weather centres use. The scripts convert it to NetCDF for you. |
| **conda** | A tool that installs scientific Python packages without needing administrator rights. |
| **HPC cluster** | A shared multi-computer system you submit jobs to instead of running them directly. |
| **Slurm** | The program that manages those jobs. You will see `sbatch` (submit) and `squeue` (check). |
| **job script** | A shell script with `#SBATCH` lines at the top telling Slurm what resources it needs. |
| **login node** | The computer you land on when you connect to a cluster. Fine for downloads and small work; not for heavy computation. |
| **window** | The span of dates a run covers, e.g. three days back to two days ahead. |

---

## 3. What it costs: disk, internet, time

These are measured from real runs of this configuration, not estimates. Knowing
them in advance matters if disk space or bandwidth is limited.

**Disk space, for one five-day cycle**

| What | Size |
|------|------|
| Fixed files you obtain once (grid, nudging, tides, river template) | **630 MB** |
| Global ocean files downloaded, one per day | 65 MB each → ~390 MB |
| Weather files kept after trimming to our region | 0.5 MB per forecast run at 0.25° (2.4 MB at 0.1°) |
| Surface forcing file | 16 MB (a 31-day hindcast gives 98 MB) |
| Initial condition | 464 MB |
| Boundary conditions | 47 MB |
| Climatology, one file per day | 464 MB each → ~2.8 GB |
| River file | 0.2 MB |
| **Model output** | **7.4 GB** |
| **Total per cycle** | **about 11 GB** |

**Internet traffic, for one five-day cycle:** roughly **0.5 GB**. The ocean
files dominate. The weather files are trimmed to our region *after* download,
so each forecast run pulls about 17 MB at 0.25° even though only 0.5 MB is
kept. At 0.1° that download is about 4.6 times larger.

**Time** (measured on one compute node using 8 processor cores):

| Step | Time |
|------|------|
| Download global ocean files | 168 s |
| Boundary conditions | 104 s |
| Climatology | 405 s |
| Initial condition | 109 s |
| Download weather data | 2–31 s |
| Convert weather to forcing | 7–8 s |
| River file | 3 s |
| Write the model settings file | under 1 s |
| **All preparation** | **about 13 minutes** |
| The model run itself | 22 minutes on 64 cores, in the one run we have timed |

Treat that last number as a rough guide only: it depends on how many days you
simulate and how many cores you use. Time your own first run, then set the job
time limits from what you measure.

---

## 4. Can I run this on my computer?

**The preparation steps:** yes, on an ordinary computer with internet access.
They are plain Python. You need enough disk space (section 3) and patience for
the downloads.

A caution about memory: the supplied job scripts request 64 GB of RAM for the
preparation work. That is a generous request for a shared cluster, not a
measured requirement — we have not measured the true peak. If your machine has
less, start with a one-day window (`NDAYS_BACK=0`, `NDAYS_FWD=0`, see section 11)
and watch whether it completes before trying longer windows.

**The model run itself:** this needs real computing power. The configuration
here is set up for 64 processor cores. On fewer cores it will still run, but
slower; you change the core count in `run/job_gog.sh` and the matching tiling
settings in `run/roms_gulfofguinea.in`. Running a multi-day forecast on a laptop
is not realistic.

**If you have no cluster at all**, you can still do useful work:

1. Run only the atmospheric steps (section 13.3). They take minutes and little disk, and they produce a real forcing file you can inspect and plot.
2. Run the ocean download and the boundary/initial condition steps for a one-day window, to learn the data formats.
3. Use the repository as a reference for building your own configuration on whatever machine you do have.

**Slurm is not required** for anything except the model run and the batch
preparation. Every step can be run directly from the command line (section
13.2), which is also the easier way to learn what each one does.

---

## 5. The whole setup at a glance

Seven steps, in this order. Each has its own section below with the exact
commands and a way to check it worked. Do them in order — later steps depend on
earlier ones.

| # | Step | You will type | How you know it worked |
|---|------|---------------|------------------------|
| 1 | Create two free accounts | `copernicusmarine login` | the login command reports success |
| 2 | Get the code, install packages | `git clone …`, `conda env create -f environment.yml` | `conda activate gulfofguinea` works |
| 3 | Obtain the four fixed files | copy them into `data/imp_files/` | `ls` shows 4 files, ~630 MB |
| 4 | Create the folders | `mkdir -p …` | `ls $DATA_ROOT` shows `data`, `inp`, `out` |
| 5 | Set the paths | edit `bash_scripts/site.conf` | `python python/site_paths.py` prints your paths |
| 6 | Choose the dates | edit `bash_scripts/window.conf` | `python python/run_window.py` prints your dates |
| 7 | Compile the model (only if you will run it) | `./build_roms.sh -j 8` | `run/romsM` exists |

Then go to [section 13](#13-which-script-to-run-in-what-order) to run it.

Only two files ever need editing for a new machine: `site.conf` (step 5) and
`window.conf` (step 6). You do not edit any Python script.

---

## 6. Step 1 — Create your accounts

Two free accounts. Neither takes long, and the weather data needs none at all.

**Copernicus Marine — for the ocean data (required).** Register at
<https://data.marine.copernicus.eu>. Then, after step 2 has installed the
software, run this once:

```bash
copernicusmarine login
```

It saves your details to `~/.copernicusmarine/.copernicusmarine-credentials`.
If you prefer not to store a password file, set the environment variables
`COPERNICUSMARINE_SERVICE_USERNAME` and `COPERNICUSMARINE_SERVICE_PASSWORD`
instead.

**CEMS Early Warning Data Store — for the rivers.** Register at
<https://ewds.climate.copernicus.eu>, navigate to your home directory, then create the file `nano ~/.cdsapirc` with
exactly two lines copy and pasted from your cds profile:

```
url: https://ewds.climate.copernicus.eu/api
key: <your API token>
```

You must accept **two** separate things before your first download, and the
error messages for them look almost identical:

1. **Terms of use of the CEMS Early Warning Data Store** — the site-wide policy, accepted once for the whole service, at <https://ewds.climate.copernicus.eu/licences/terms-of-use-cems> (log in first). It is revised from time to time; a new revision must be accepted again.
2. **CEMS-FLOODS datasets licence** — the dataset licence, at <https://ewds.climate.copernicus.eu/datasets/cems-glofas-historical?tab=download> under **Terms of use**. This one covers every GloFAS dataset.

Accepting the dataset licence does not accept the site policy, which is why a
download can fail with `403 Forbidden` even after you have ticked the licence on
the dataset page. List what your account has already accepted with:

```bash
key=$(awk '/^key:/{print $2}' ~/.cdsapirc)     # or your CDSAPI_KEY
curl -sL -H "PRIVATE-TOKEN: $key"   https://ewds.climate.copernicus.eu/api/profiles/v1/account/licences
```

Note that this is the Early Warning Data Store (`ewds.climate.copernicus.eu`),
**not** the Climate Data Store (`cds.climate.copernicus.eu`). They are separate
services with separate accounts and tokens, which is why the `url:` line above
points at `ewds`. A Climate Data Store token will not work here.

Each service issues its **own** token, even though you sign in with the same
ECMWF account. If you already use the Climate Data Store for other work, keep
that `~/.cdsapirc` and point this pipeline at the Early Warning Data Store with
environment variables instead of editing the file:

```bash
export CDSAPI_URL=https://ewds.climate.copernicus.eu/api
export CDSAPI_KEY=<your EWDS token>
```

To check which service a token belongs to:

```bash
python -c "import cdsapi; cdsapi.Client().client.check_authentication(); print('token valid for', __import__('os').environ.get('CDSAPI_URL','the url in ~/.cdsapirc'))"
```

Skip this account entirely if you already have a GloFAS file: pass it with
`--glofas-file` instead.

**Check it worked:** `copernicusmarine login` prints a success message, and
`cat ~/.cdsapirc` shows your two lines.

**Common mistake:** committing these credentials to git. They live in your *home
directory*, never in the repository.

---

## 7. Step 2 — Get the code and install the packages

If you do not have conda, install [Miniforge](https://github.com/conda-forge/miniforge)
first — it needs no administrator rights.

```bash
git clone https://github.com/Ocean-Atmosphere-modeling/gulf-of-guinea.git
cd gulf-of-guinea
conda env create -f environment.yml
conda activate gulfofguinea
```

The third command reads `environment.yml` and installs everything the scripts
need. It takes several minutes and downloads a few hundred MB:

| Packages | Why they are needed |
|----------|---------------------|
| xarray, numpy, pandas, dask, netCDF4 | reading, writing and handling gridded data |
| xesmf, esmpy, xroms | putting global data onto the model's grid |
| cfgrib, eccodes, python-eccodes | reading the weather centre's GRIB files |
| copernicusmarine | talking to the Copernicus Marine service |
| ecmwf-opendata | fetching ECMWF forecasts |
| matplotlib, cartopy | plotting, if you want it |

One package is left out on purpose, because only the river step needs it:

```bash
pip install cdsapi        # only if you will download GloFAS yourself
```

**Check it worked:**

```bash
conda activate gulfofguinea
python -c "import xarray, xesmf, cfgrib, copernicusmarine; print('packages OK')"
```

**Common mistakes:** installing cfgrib or eccodes with `pip` instead of conda,
which usually produces confusing GRIB errors later; and forgetting
`conda activate gulfofguinea` in a new terminal, which makes the scripts fail
with `ModuleNotFoundError`.

**Note the environment name.** `environment.yml` creates an environment called
`gulfofguinea`. Whatever name you use, put the same name in `site.conf` at step
5, so the job scripts activate the right one.

---

## 8. Step 3 — Obtain the four fixed files

Four files describe this particular model configuration. They are too large for
git, so they are **not** in the repository. Ask the maintainers for them, or
build equivalents for your own region.

| File | Size | What it is |
|------|------|------------|
| `grd_GulfOfGuinea_4km.nc` | 70 MB | the grid: where each point is, how deep the sea is, which points are land |
| `nud_gulfofguinea_Nf15.nc` | 430 MB | how strongly to nudge the model toward the global fields, point by point |
| `tid_tpxo_GulfOfGuinea_4km.nc` | 127 MB | the tides at the open boundaries |
| `riv_gulfofguinea_2024_v2.nc` | 2.1 MB | a river file used as a template and as a fallback |

They all go in one place, which you create in step 4:
`<your data root>/data/imp_files/`.

Two related files **are** in the repository, because they are small and
text-based: `imp_files/nudgcoef.cdl` and `imp_files/nudgcoef_gulfofguinea.m`,
which regenerate the nudging file.

**Check it worked:** `ls -lh $DATA_ROOT/data/imp_files/` lists four `.nc` files
totalling about 630 MB.

---

## 9. Step 4 — Create the folders

Pick one directory with at least ~15 GB free for a first cycle (see section 3).
This is your **data root**. Create the structure inside it:

```bash
export DATA_ROOT=/path/you/choose          # edit this line

mkdir -p $DATA_ROOT/data/{downloads,blk,glofas,imp_files,bry,clm,ini}
mkdir -p $DATA_ROOT/inp/{ini,bry,clm,riv}
mkdir -p $DATA_ROOT/out/forecast/logs
```

What each folder is for:

| Folder | Contents |
|--------|----------|
| `data/downloads/` | ocean and weather files exactly as downloaded |
| `data/blk/` | the surface forcing file the model reads |
| `data/glofas/` | river discharge downloads |
| `data/imp_files/` | the four fixed files from step 3 |
| `data/bry/`, `data/clm/`, `data/ini/` | saved interpolation weights — **not** model inputs, just a speed-up |
| `inp/ini/`, `inp/bry/`, `inp/clm/`, `inp/riv/` | the model input files the scripts produce |
| `out/forecast/<date>_<user>/` | model output, one folder per run (see below) |
| `out/forecast/logs/` | logs from the preparation job |

That naming split catches people out, so it is worth repeating: `data/bry` holds
interpolation weights, while `inp/bry` holds the boundary condition the model
actually reads.

**Check it worked:**

```bash
ls $DATA_ROOT                 # expect: data  inp  out
ls $DATA_ROOT/data            # expect: blk  bry  clm  downloads  glofas  imp_files  ini
ls $DATA_ROOT/inp             # expect: bry  clm  ini  riv
df -h $DATA_ROOT              # check the free space
```

**Why the output folder carries your user name.** The folder is named after the
cycle's start date. On a shared data tree that is not enough: if two people run
the same start date, the second run overwrites the first one's output, because
the files inside are named only by date too. `OUTPUT_SUFFIX` in `site.conf`
(default `_$USER`) gives each person their own folder. Set it empty there, or
for one run with `OUTPUT_SUFFIX= …`, to get the bare date back.

**Note:** `export DATA_ROOT=…` only lasts for the current terminal. It is used
here to shorten the commands; the scripts themselves get the path from
`site.conf` in step 5, not from this variable.

**On a shared system, check you can write to every folder now** — not after a
job fails. Section 15 covers sharing a data tree with colleagues in full. If colleagues created some of these folders, they may be readable by
you but not writable, and a job that cannot write its output is killed with no
log at all. Section 14.4 has a one-line loop that checks all of them.

---

## 10. Step 5 — Set the paths in site.conf

This is the step that moves the pipeline to a new machine. Open
`bash_scripts/site.conf` in a text editor and set six values:

```bash
DATA_ROOT=/path/you/choose                      # the folder from step 4
#GRID_FILE=/path/to/grd_GulfOfGuinea_4km.nc     # only if the grid is NOT in data/imp_files
CONDA_ENV=gulfofguinea                          # the environment name from step 2
CONDA_SH=$HOME/miniforge3/etc/profile.d/conda.sh
SLURM_PARTITION=p_omg_1                         # your cluster's queue name
SLURM_ACCOUNT=                                  # leave empty if your cluster does not need one
```

| Setting | What to put |
|---------|-------------|
| `DATA_ROOT` | the directory you created in step 4 |
| `GRID_FILE` | leave commented out unless your grid lives outside `data/imp_files/` |
| `CONDA_ENV` | the environment name from step 2 |
| `CONDA_SH` | path to `conda.sh`; find it with `ls $(conda info --base)/etc/profile.d/conda.sh` |
| `SLURM_PARTITION` | your cluster's queue; ask your administrator or run `sinfo` |
| `SLURM_ACCOUNT` | your allocation, if the cluster requires one; otherwise empty |
| `OUTPUT_SUFFIX` | appended to each cycle's output folder; `_$USER` keeps your runs separate from your colleagues' |
| `ROMS_EXE` | the compiled model to launch; `./romsM` is the one `build_roms.sh` makes in `run/`. Point it at an existing build to skip compiling |

Every folder from step 4 is worked out from `DATA_ROOT`. Both the shell scripts
and the Python scripts read this one file, so they cannot disagree.

**Check it worked — do not skip this:**

```bash
python python/site_paths.py
```

It prints every path the scripts will use. Read the list and confirm the paths
are the ones you created. This takes seconds and saves hours.

**Three settings live elsewhere**, because the cluster's job scheduler reads
them before your script starts, so a configuration file cannot reach them. Edit
them directly in `bash_scripts/job_forecast_prep.sh`,
`bash_scripts/job_downscale.sh` and `run/job_gog.sh`:

1. `#SBATCH --mem` and `#SBATCH --time` — memory and wall-clock time to request.
2. `#SBATCH --ntasks` — how many processor cores (64 in `run/job_gog.sh`).
3. `#SBATCH --mail-user` — put your own address, or delete the line.

---

## 11. Step 6 — Choose the dates in window.conf

Open `bash_scripts/window.conf`:

```bash
NDAYS_BACK=3        # start this many days before today
NDAYS_FWD=2         # end this many days after today
#START_DATE=2026-10-01    # uncomment BOTH lines for fixed dates (a hindcast)
#END_DATE=2026-11-01
MAX_DAYS_FWD_MET=5  # safety limit: the open weather forecast only reaches 144 hours
ECMWF_MODEL=ifs     # which weather model
ECMWF_RESOL=0p25    # 0p25 = 0.25°, or 0p1 = 0.1° (finer, bigger downloads)
```

With the values above, a run started today covers three days of the recent past
plus two days ahead. The past part matters: it lets the ocean model settle down
before the forecast period begins.

**For your very first run, use a one-day window** — it is quick, small, and
proves your accounts and folders are right:

```bash
NDAYS_BACK=0
NDAYS_FWD=0
```

**Check it worked:**

```bash
python python/run_window.py
# forecast window: 2026-11-09 to 2026-11-14 (5 days), time reference 2026-01-01
```

Three rules worth knowing:

1. Each extra day costs about 65 MB of download and 464 MB of climatology on disk.
2. `NDAYS_FWD` cannot exceed 5 while the weather steps run, because the open forecast stops at 144 hours.
3. For a hindcast, set `START_DATE` and `END_DATE`. The finer 0.1° weather data exists only from 2026-10-21 onward, so earlier hindcasts need `ECMWF_RESOL=0p25` (from 2024-02-29) or another source such as ERA5.

---

## 12. Step 7 — Compile ROMS

Skip this step if you only want to prepare input files and not run the model.

You need a Fortran compiler, an MPI library and the NetCDF libraries. The build
script is written for the Intel compiler (`FORT=ifx`); for gfortran, change that
line in `run/build_roms.sh`.

The ROMS source code is not included here. Clone it into the empty `roms/`
folder, then compile:

```bash
git clone https://github.com/myroms/roms.git roms
cd run
./build_roms.sh -j 8          # -j 8 compiles using 8 cores
cd ..
```

**Check it worked:** `ls -lh run/romsM` shows the compiled program.

**Already have a build elsewhere?** You can skip this step. Set `ROMS_EXE` in
`bash_scripts/site.conf` to that executable and `run/job_gog.sh` will use it:

```bash
ROMS_EXE=/path/to/another/checkout/romsM
```

Check first that it was built for this configuration — compare the `*.h` file
used for that build with `run/gulfofguinea.h`; if they differ, the compiled
physics does not match what this repository expects. The job refuses to start,
with a clear message, if the path does not exist or is not executable.

**On a cluster that provides ROMS as a module**, `module load roms/<version>`
before building lets the script find the source itself.

---

## 13. Which script to run, in what order

The eight preparation steps must happen in a fixed order, because each uses what
the previous ones produced:

```
download  →  bry  →  clm  →  ini  →  metdl  →  frc  →  riv  →  inp  →  ROMS
└─ ocean data ─────────────┘  └─ weather ──┘   └ rivers ┘  └ settings ┘
```

**You do not have to remember that order.** The runner scripts apply it for you,
whatever order you ask for the steps in. Pick one of the three ways below.

### 13.1 The simple way: one command, on a cluster

```bash
bash bash_scripts/run_forecast_cycle.sh -n     # 1. see what would happen; changes nothing
bash bash_scripts/run_forecast_cycle.sh        # 2. really submit
```

Always run with `-n` first and read what it prints: the dates, the settings file
it will create, and the two jobs it will submit.

This one command submits two jobs in the right order and makes the second depend
on the first, so a failed download cannot produce a nonsense forecast:

| Order | Job | What it does |
|-------|-----|--------------|
| 1st | `bash_scripts/job_forecast_prep.sh` | all eight preparation steps |
| 2nd | `run/job_gog.sh` | the model, started only if the first job succeeded |

You never run those two job scripts by hand in normal use —
`run_forecast_cycle.sh` submits them for you. Watch progress with:

```bash
squeue -u $USER                                          # waiting or running?
tail -f $DATA_ROOT/out/forecast/logs/prep.<jobid>.log    # preparation
tail -f run/out.slurm.*                                  # the model
```

Section 14 explains where each of those files comes from, and what to do when
one of them does not exist.

If `squeue` shows `PENDING` with a reason like `ReqNodeNotAvail, Reserved for
maintenance`, the cluster is unavailable, not broken. Check with
`scontrol show reservation` and wait.

### 13.2 The learning way: one step at a time, no cluster needed

This is the better way to understand the pipeline. Run the steps yourself, in
this order:

```bash
# start small: one day, one step
bash python/run_gulfofguinea_forcing_scripts.sh -b 0 -f 0 -s download

# then the rest of the ocean side
bash python/run_gulfofguinea_forcing_scripts.sh -s bry
bash python/run_gulfofguinea_forcing_scripts.sh -s clm
bash python/run_gulfofguinea_forcing_scripts.sh -s ini

# then the weather side
bash python/run_gulfofguinea_forcing_scripts.sh -s metdl
bash python/run_gulfofguinea_forcing_scripts.sh -s frc

# then rivers and the model settings file
bash python/run_gulfofguinea_forcing_scripts.sh -s riv
bash python/run_gulfofguinea_forcing_scripts.sh -s inp
```

Or in groups, which is what most people use day to day:

```bash
bash python/run_gulfofguinea_forcing_scripts.sh -s ocean      # download, bry, clm, ini
bash python/run_gulfofguinea_forcing_scripts.sh -s met        # metdl, frc
bash python/run_gulfofguinea_forcing_scripts.sh -s all        # all eight, in order
bash python/run_gulfofguinea_forcing_scripts.sh -s met -r 0p1 # weather at 0.1°
```

The step names are `download`, `bry`, `clm`, `ini`, `metdl`, `frc`, `riv` and
`inp`. The shortcuts are `ocean`, `met` and `all`. Every step writes its own log
under `python/logs/run_<timestamp>/`, and the chain stops at the first failure.

### 13.3 The light way: atmosphere only, on an ordinary computer

The smallest useful thing you can do — minutes, and well under 100 MB:

```bash
bash bash_scripts/run_ecmwf_forcing.sh                # dates from window.conf
bash bash_scripts/run_ecmwf_forcing.sh 2026-10-01     # or start from a given date
```

### 13.4 Running the model separately

If the input files already exist and you only want the model:

```bash
python python/make_roms_in.py        # writes run/roms_gulfofguinea_<START>.in
cd run
sbatch job_gog.sh roms_gulfofguinea_<START>.in
```

`make_roms_in.py` checks that every input file exists and covers your dates
before writing. A missing file is reported here in seconds, instead of crashing
the model later.

**Do not edit `run/roms_gulfofguinea.in` to set up a run.** There are two files
and they have different jobs:

| File | What it is | Do you edit it? |
|------|-----------|-----------------|
| `run/roms_gulfofguinea.in` | the template, holding the physics, grid, tides, nudging, tiling and output settings that stay the same from run to run | only to change the science |
| `run/roms_gulfofguinea_<START>.in` | written fresh by `make_roms_in.py` for one specific run: the dates, the number of time steps, and the name of every input file | never — it is regenerated each cycle |

So leaving the template untouched is correct. Just remember to pass the
generated file to the model: `sbatch job_gog.sh roms_gulfofguinea_<START>.in`.
Running `sbatch job_gog.sh` with no argument falls back to the template, which
has no dates filled in and will not give you the run you wanted.

### 13.5 Every script, and when you use it

| Script | You run it | When |
|--------|-----------|------|
| `bash_scripts/run_forecast_cycle.sh` | yes | the normal way to run a whole cycle |
| `python/run_gulfofguinea_forcing_scripts.sh` | yes | to run steps yourself, with or without a cluster |
| `bash_scripts/run_ecmwf_forcing.sh` | yes | weather steps only |
| `bash_scripts/job_downscale.sh` | sometimes | `ini`, `bry`, `clm` on a compute node, when the ocean data is already downloaded: `cd python && sbatch ../bash_scripts/job_downscale.sh` |
| `run/build_roms.sh` | once | to compile the model (step 7) |
| `bash_scripts/job_forecast_prep.sh` | no | submitted for you by `run_forecast_cycle.sh` |
| `run/job_gog.sh` | rarely | submitted for you; by hand only as in 13.4 |
| `bash_scripts/site_env.sh`, `window_env.sh` | no | helper files the other scripts read |

---

## 14. Where your log files are

Every run writes logs. Knowing which file to open — and what it means when the
file does not exist — is the difference between a five-minute fix and a lost
afternoon.

### 14.1 The three kinds of log

| What ran | Log file | Set by |
|----------|----------|--------|
| The preparation job on a cluster | `$DATA_ROOT/out/forecast/logs/prep.<jobid>.log` | `#SBATCH --output` in `bash_scripts/job_forecast_prep.sh` |
| Each individual step | `python/logs/run_<timestamp>/<step>.log`, plus `driver.log` for the summary | the step runner, inside the repository |
| The model (ROMS) | `out.slurm.<node>.<jobid>` and `err.slurm.<node>.<jobid>` | `#SBATCH --output` / `--error` in `run/job_gog.sh` |

Two things about the model's logs surprise people:

1. Their paths are **relative**, so they appear in whatever directory the job started in. `run_forecast_cycle.sh` submits with `--chdir=<repo>/run`, so look in `run/`. If you submitted by hand from somewhere else, they are in that directory instead.
2. `.gitignore` lists `out.slurm.*` and `err.slurm.*`, so `git status` will never show them. They are on disk even though git ignores them.

### 14.2 Finding the log for a job you already ran

```bash
squeue -u $USER                     # jobs waiting or running, with their IDs
sacct -u $USER --starttime now-2days \
      --format=JobID%14,JobName%20,Submit,State,Elapsed,ExitCode,WorkDir%50 -X
```

`sacct` shows finished jobs too, which `squeue` does not. Once you have the job
ID, the preparation log is `…/logs/prep.<jobid>.log`, and the model logs end in
`.<jobid>`. To see the exact command that submitted a job:

```bash
sacct -j <jobid> --format=JobID%14,SubmitLine%150
```

### 14.3 When there is no log file at all

If `sacct` shows the job as `FAILED` after only a few seconds and **no log file
was created anywhere**, the job died before your script started running. The log
is missing because writing the log was the thing that failed.

The usual signature looks like this:

```
JobID          JobName      State     Elapsed  ExitCode
63887078       gog_fc_prep  FAILED   00:00:15  0:53
63887078.batch batch        CANCELLED          0:53
```

Three causes, in order of likelihood:

1. **The log directory is not writable by you.** Common on shared systems: a colleague created the folder, and the group has read and execute permission but not write. Slurm cannot create the output file, so it kills the job.
2. **The log directory does not exist.** Slurm will not create it for you.
3. **An invalid `#SBATCH` option**, such as a partition or account name your cluster does not recognise.

Test the first two directly — this is the single most useful command in this
section:

```bash
touch $DATA_ROOT/out/forecast/logs/_writetest && \
  echo "writable" && rm $DATA_ROOT/out/forecast/logs/_writetest
```

If that prints `Permission denied`, you have found the problem.

### 14.4 Checking every folder at once on a shared system

The preparation steps write into many folders. If even one of them is not
writable by you, the chain fails partway through. Check them all before you run
anything:

```bash
for p in data/downloads data/blk data/glofas data/imp_files \
         data/bry data/clm data/ini \
         inp/ini inp/bry inp/clm inp/riv out/forecast out/forecast/logs; do
  if touch $DATA_ROOT/$p/._wt 2>/dev/null; then
    rm -f $DATA_ROOT/$p/._wt; printf '%-22s writable\n' "$p"
  else
    printf '%-22s NOT WRITABLE  (%s)\n' "$p" "$(stat -c '%U %A' $DATA_ROOT/$p 2>/dev/null)"
  fi
done
```

A folder that belongs to a colleague and shows `drwxr-sr-x` has no `w` in the
middle group of letters, which means the group cannot write to it. Ask that
person, or your system administrator, to run:

```bash
chmod g+w <folder>        # only the folder's owner or an administrator can do this
```

The folders already carry the group's setgid bit (the `s` in the listing), so
files created inside them stay in the shared group.

Two details worth asking for at the same time, so you do not have to go back a
second time:

1. **The files inside need it too.** Permission on the folder lets you create and delete files; permission on each *file* is what lets you overwrite it. Files written with the default settings are `-rw-r--r--`, which the group cannot overwrite. The owner fixes them with `chmod -R g+w <folder>`.
2. **Set `umask 002` before running.** Otherwise every new file is created group-read-only again and the problem comes back next week. Anyone sharing the data tree should put `umask 002` in their `~/.bashrc`, or at least run it before starting a cycle.

A quick way to see whether this will bite you:

```bash
find $DATA_ROOT/inp $DATA_ROOT/out -type f ! -perm -g=w | head
```

Any file listed cannot be overwritten by anyone except its owner.

**If you cannot get write permission**, you do not have to wait. Point
`DATA_ROOT` in `site.conf` at a directory you own, create the folders there
(section 9), and link the four fixed files instead of copying them:

```bash
ln -s /shared/path/data/imp_files/*.nc $DATA_ROOT/data/imp_files/
```

Symbolic links cost no disk space, and you only need to read those files.

### 14.5 A missing second job

`run_forecast_cycle.sh` prints **two** job IDs: the preparation job, then the
model job that depends on it. If you only saw one, the second `sbatch` was
rejected, and that error appeared in your terminal rather than in any log file.
Use `sacct` to check whether a model job exists at all before hunting for its
output.

---

## 15. Sharing the system with colleagues

Everything in this section comes from problems that actually happened on this
setup. If you are the only person using your data tree, you can skip it.

The pipeline was built around **one shared data tree**: the ocean downloads, the
regridded inputs and the model output all live under a single `DATA_ROOT` that
several people can use. That saves a great deal of disk, and it means your
colleague's downloads save you a download. It also means you can stand on each
other's toes in three specific ways.

### 15.1 Folders your colleagues created

Whoever creates a folder owns it, and by default the group can read it but not
write to it. The first person to run a step creates the folder; everyone else
then fails. Worse, the failure can be invisible: if Slurm cannot create the log
file, the job is killed before your script runs and there is no log to read
(section 14.3).

Check every folder before your first run, with the loop in section 14.4. Ask the
owner to run `chmod -R g+w <folder>` on anything that comes back as not
writable — the `-R` matters, because folder permission controls who can create
files while each *file's* permission controls who can overwrite it.

Then make sure everyone sharing the tree sets `umask 002` in their `~/.bashrc`,
so the files they create from then on stay group-writable. Without that, the
problem comes back with every new file.

### 15.2 Two people, one start date

Model output goes to `out/forecast/<START_DATE><OUTPUT_SUFFIX>/`. If two people
run the same start date with no suffix, the second run writes over the first
one's output — and because permissions are now group-writable, nothing stops it.

`OUTPUT_SUFFIX=_$USER` in `site.conf` (the default) gives each person their own
folder, which solves it. Before submitting, it still costs nothing to look:

```bash
ls -ld $DATA_ROOT/out/forecast/*/      # who already ran which dates
squeue -p <your partition>             # what is running right now, for everyone
```

Remember that `squeue -p` shows every user's jobs, not only yours. Use
`squeue -u $USER` for your own.

### 15.3 Files you share whether you mean to or not

| What | Shared? | What happens if two people run at once |
|------|---------|----------------------------------------|
| Ocean and weather downloads | yes | harmless: files are skipped if already present, and re-downloaded only when stale |
| Scratch folders for raw GRIB | no | per user and per grid, so cleanup never touches anyone else's files |
| Regridded inputs in `inp/` | yes | the second run overwrites the first with an equivalent file; harmless for the same dates, confusing for different settings |
| Forcing files in `blk/` | by model and grid | a 0.25° and a 0.1° run do not collide, but two 0.25° runs of the same date do |
| Model output in `out/forecast/` | separated by `OUTPUT_SUFFIX` | with the suffix, never; without it, silent overwriting |

### 15.4 A short check before you submit

```bash
python python/site_paths.py            # are my paths what I think they are?
python python/run_window.py            # which dates am I about to run?
squeue -u $USER                        # am I already running something?
ls -ld $DATA_ROOT/out/forecast/*/      # has someone run this date already?
bash bash_scripts/run_forecast_cycle.sh -n    # what exactly would be submitted?
```

Five commands, a few seconds, and they catch nearly every problem in this
section before it reaches the queue.

---

## 16. How to know it worked

After the preparation steps, check that the files exist and look sensible:

```bash
ls -lh $DATA_ROOT/inp/ini $DATA_ROOT/inp/bry $DATA_ROOT/inp/clm $DATA_ROOT/data/blk
ncdump -h $DATA_ROOT/data/blk/GulfOfGuinea_frc_IFS_0p25_bulkflux_*.nc | head -40
```

Signs that things are right:

1. There is one climatology file per day of your window, each about 464 MB.
2. The forcing file covers your dates — the conversion step prints its time range and reports whether it covers the model grid.
3. `python python/make_roms_in.py` runs without complaining, and the `.in` file it writes names files that all exist.
4. The model's log (`run/out.slurm.*`) keeps printing time steps and does not stop early.

Signs of trouble: a climatology file much smaller than its neighbours, a time
range that does not reach the end of your window, or a step that finishes
suspiciously fast. All three usually mean an incomplete download; delete the
suspect file and run the step again.

---

## 17. What each step actually does

Read this once and the scripts stop being a black box.

1. **`download`** asks Copernicus Marine for one file per day covering our region: temperature, salinity, the two horizontal current components and sea surface height, on the global 1/12° grid. Files for the last day or two are fetched again each time, because the analysis is updated daily.
2. **`bry`** reads those files and interpolates them onto the edges of our grid, then writes the boundary conditions. The model will read this to know what flows in and out.
3. **`clm`** does the same interpolation for the whole interior, one file per day. The model nudges gently toward these fields so it does not drift.
4. **`ini`** writes the single snapshot the model starts from, built the same way, for the first day of the window.
5. **`metdl`** downloads ECMWF open weather forecasts. For each forecast run it takes the global file, cuts out our region, and saves a small NetCDF. Several runs are stitched together so the record is continuous.
6. **`frc`** converts those weather files into the form the model expects: wind, air temperature, humidity, pressure, radiation and rainfall, with the accumulated quantities turned into rates. It checks that the result covers the whole model grid.
7. **`riv`** turns GloFAS river discharge into point sources for seven rivers — Volta, Niger, Cross, Sanaga, Ogooué, Kouilou-Niari and Congo. GloFAS lags real time, so the last available day is repeated across the forecast, with a warning when that happens.
8. **`inp`** writes the model's settings file: the dates, the number of time steps, and the names of every input file. It validates them all first.

Then ROMS runs, reading those files and writing output into
`out/forecast/<start date>/`.

---

## 18. When something goes wrong

| What you see | What it means and what to do |
|--------------|------------------------------|
| `No time window: set NDAYS_BACK and NDAYS_FWD …` | `window.conf` is missing or empty. See section 11. |
| `DATA_ROOT is not set` | `site.conf` is missing or empty. See section 10. |
| `ERROR: site config not found` | The file was moved or renamed. It belongs at `bash_scripts/site.conf`. |
| `ECMWF open data for ifs at 0p1 start 2026-10-21 …` | You asked for finer weather data from before it existed. Use `ECMWF_RESOL=0p25`, or ERA5 for dates before 2024-02-29. |
| `-f must be <= 5 …` | The open weather forecast only reaches 144 hours. Shorten `NDAYS_FWD`, or run `-s ocean` for a longer ocean-only window. |
| `No input files matching ecmwf_… in …` | The weather download and the conversion were run with different model or resolution settings. Set them in `window.conf` so both steps agree. |
| `INPUT PROBLEMS - ROMS would fail: COVERAGE FRC spans … run needs …` | The weather forcing is shorter than your run window, usually because the long forecast steps were never downloaded. Re-run `-s metdl,frc,inp`. `make_roms_in.py` catches this before ROMS starts, so nothing is wasted. |
| `make_roms_in.py` says the forcing file is missing | The `frc` step has not run for the resolution you have now selected. Run it, or switch `ECMWF_RESOL` back. |
| `cdsapi is not installed` | `pip install cdsapi`, then create `~/.cdsapirc` as in section 6. |
| `error: give --glofas-file or --download` | `make_rivers_GulfOfGuinea.py` will not guess where its river data comes from. Use `--download --clobber` (as the step runner does), or point it at a file you already have with `--glofas-file`. |
| `403 Client Error: Forbidden` while downloading GloFAS, with no further detail | Your token is for the Climate Data Store, not the Early Warning Data Store. They are separate services with separate tokens — see section 6. |
| `403 … user didn't accept all required site policies` | The message names what is missing, usually `Terms of use of the CEMS Early Warning Data Store`. Open the URL it prints, log in, and accept. This is separate from the dataset licence — see section 6. |
| Copernicus Marine refuses to authenticate | Run `copernicusmarine login` again. Check the credentials file is readable. |
| Errors mentioning GRIB or missing variables | cfgrib and eccodes do not match. Reinstall both from conda-forge, not pip. |
| `cannot find the gulf-of-guinea checkout` | Submit from inside the repository (or its `python/` folder), or add `--export=ALL,REPO=/path/to/repo` to your `sbatch` command. |
| `execve(): …/romsM: No such file or directory`, repeated once per core | The model was never compiled. Do section 12, or set `ROMS_EXE` in `site.conf` to a build you already have. |
| `ERROR: ROMS executable not found or not executable` | `ROMS_EXE` points somewhere wrong. Check the path, and that the file has execute permission. |
| Job sits as `PENDING / ReqNodeNotAvail` | The cluster is in maintenance. `scontrol show reservation` tells you until when. |
| A download fails part-way | Run the step again. Completed files are skipped, so it resumes rather than starting over. |
| A colleague's model output disappeared | Two runs used the same start date and wrote to the same output folder. Check `OUTPUT_SUFFIX` is set in `site.conf` — see section 15.2. |
| Job `FAILED` after a few seconds, no log file anywhere | Slurm could not create its output file. Almost always the log directory is not writable by you — see section 14.3. |
| `Permission denied` writing to `inp/…`, `out/…` or `data/…` | A colleague owns that folder and the group cannot write. Ask them for `chmod g+w`, or set `DATA_ROOT` to a directory you own — see section 14.4. |
| `run_forecast_cycle.sh` printed only one job ID | The model job was rejected at submission. The error is in your terminal, not in a log — see section 14.5. |
| Everything is too slow or too large | Shrink the window (`-b 0 -f 1`), or run `-s met` only. Section 3 shows what each extra day costs. |

---

## 19. Reference tables

### 19.1 The pipeline

| Step | Script in `python/` | Produces |
|------|--------------------|----------|
| `download` | `download_mercator_GulfOfGuinea_analysis.py` | `data/downloads/mercator_GulfOfGuinea_RT_YYYY_MM_DD.nc` |
| `bry` | `downscale_mercator_to_roms_GulfOfGuinea_BRY.py` | `inp/bry/` |
| `clm` | `downscale_mercator_to_roms_GulfOfGuinea_CLM.py` | `inp/clm/`, one file per day |
| `ini` | `downscale_mercator_to_roms_GulfOfGuinea_INI.py` | `inp/ini/` |
| `metdl` | `download_ecmwf_opendata_GulfOfGuinea.py` | `data/downloads/ecmwf_<model>_<resol>_GulfOfGuinea_YYYYMMDDHH.nc` |
| `frc` | `convert_ecmwf_to_roms_frc_GulfOfGuinea.py` | `data/blk/GulfOfGuinea_frc_<MODEL>_<resol>_bulkflux_YYYYMMDD.nc` |
| `riv` | `make_rivers_GulfOfGuinea.py` | `inp/riv/` |
| `inp` | `make_roms_in.py` | `run/roms_gulfofguinea_YYYYMMDD.in` |

`python/romsutil.py` holds shared helper code and is not run directly.
`python/N/` contains a fixed-date reanalysis downloader that is not part of this
pipeline.

### 19.2 The driver scripts

| Script | Where it runs | What it does |
|--------|---------------|--------------|
| `bash_scripts/run_forecast_cycle.sh` | login node | submits the whole cycle |
| `bash_scripts/job_forecast_prep.sh` | compute node | runs all eight preparation steps |
| `bash_scripts/job_downscale.sh` | compute node | `ini`, `bry`, `clm` only |
| `bash_scripts/run_ecmwf_forcing.sh` | login node or laptop | `metdl` and `frc` only |
| `python/run_gulfofguinea_forcing_scripts.sh` | anywhere | the step runner; `-s` chooses steps |
| `run/build_roms.sh` | login node | compiles ROMS |
| `run/job_gog.sh` | compute node | runs the model |

### 19.3 Weather data availability

Measured on 2026-11-12 by asking each source for individual forecast runs:

| Source | Data | Available |
|--------|------|-----------|
| `data.ecmwf.int` (live service) | 0.25° and 0.1° | the last ~4 days only |
| Google and AWS mirrors | 0.25° (`ifs/0p25`) | 2024-02-29 to today |
| Google and AWS mirrors | 0.1° (`ifs/0p1`) | 2026-10-21 to today |
| Google and AWS mirrors | 0.4° (`0p4-beta`, retired) | 2023-07-15 to 2024-02-28 |

You do not choose between these. The download script takes each forecast run
from the live service while it is still there and from the mirror once it is
older, and stops with a clear message if you ask for dates before the data
exists. Re-check any of these dates yourself with:

```bash
curl -I https://storage.googleapis.com/ecmwf-open-data/YYYYMMDD/00z/ifs/0p25/oper/YYYYMMDD000000-0h-oper-fc.index
```

A response of `200` means that run is available; `404` means it is not.

### 19.4 Grid spacing choices

| Setting | Points over our region | Available from | Notes |
|---------|-----------------------|----------------|-------|
| `0p25` | 77 × 119 | 2024-02-29 | the default; a good starting point |
| `0p1` | 190 × 295 | 2026-10-21 | finer winds, about 4.6× the download, `ifs` model only |

The model name and grid spacing appear in every file name and scratch folder, so
the two grids never mix and `make_roms_in.py` points the model at whichever you
selected:

| What | 0.25° | 0.1° |
|------|-------|------|
| downloaded run | `downloads/ecmwf_ifs_0p25_GulfOfGuinea_<YYYYMMDDHH>.nc` | `…ecmwf_ifs_0p1_GulfOfGuinea_<YYYYMMDDHH>.nc` |
| forcing for the model | `blk/GulfOfGuinea_frc_IFS_0p25_bulkflux_<YYYYMMDD>.nc` | `…_IFS_0p1_bulkflux_<YYYYMMDD>.nc` |
| scratch folder | `downloads/tmp_ifs_0p25_<user>/` | `downloads/tmp_ifs_0p1_<user>/` |
| temporary GRIB | `TMP_ifs_0p25_<YYYYMMDDHH>.grib2` | `TMP_ifs_0p1_<YYYYMMDDHH>.grib2` |

The scratch folders are separate by design, not just for tidiness: the download
step deletes every temporary file in *its own* scratch folder when it finishes,
so a shared folder would let a run that is finishing wipe the downloads of one
still in progress. They are also per user, for the same reason.

### 19.5 Settings summary

| File | Holds | Typical reason to edit |
|------|-------|------------------------|
| `bash_scripts/site.conf` | where things are: `DATA_ROOT`, conda, Slurm queue | moving to a new computer |
| `bash_scripts/window.conf` | what to run: dates, weather model and grid | every new forecast or hindcast |
| `run/roms_gulfofguinea.in` | the model's physics, tiling and output settings | changing the science |
| `run/job_gog.sh` | cores, memory, time limit for the model run | matching your machine |

---

## 20. Credit where it is due

ECMWF open data are published under CC BY 4.0: credit ECMWF when you use or
share them. Copernicus Marine and CEMS/GloFAS have their own terms — cite them
as those services ask. ROMS is developed by the ROMS group and is free to use
under its own licence.

If you use this configuration in work you publish, please also credit the people
who built it, listed in the repository's commit history and `LICENSE`.
