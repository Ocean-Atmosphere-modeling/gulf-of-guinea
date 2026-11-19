#!/usr/bin/env bash
#
# run_gulfofguinea_all.sh
#
# Runs the full Gulf of Guinea ROMS pre-processing chain (ocean + atmosphere)
# with ONE shared time window:
#
#   Ocean (Mercator / CMEMS)
#     download  download Mercator daily files
#     bry       build the boundary file (BRY)
#     clm       build the climatology files (CLM, one per day)
#     ini       build the initial conditions file (INI)
#   Atmosphere (ECMWF IFS open data)
#     metdl     download ECMWF open data and subset to the box
#     frc       convert to the ROMS bulk-flux forcing file
#   Rivers and ROMS input
#     riv       GloFAS river forcing (last GloFAS day persisted over the forecast)
#     inp       write the ROMS .in file for this window and check all inputs
#
# The window is defined ONCE in bash_scripts/window.conf and passed to every
# python script through the environment (NDAYS_BACK/NDAYS_FWD, or
# START_DATE/END_DATE for a hindcast), so they can never disagree. The ECMWF
# model and grid (ECMWF_MODEL/ECMWF_RESOL) travel the same way, so the metdl
# and frc steps always use the same files.
#
# Usage:
#   ./run_gulfofguinea_all.sh [-b DAYS_BACK] [-f DAYS_FWD] [-s STEPS]
#                             [-r RESOL] [-m MODEL] [-h]
#
#   -b  days of past data before today      (default: from window.conf)
#   -f  days of forecast after today        (default: from window.conf;
#                                            max MAX_DAYS_FWD_MET when met steps run)
#   -s  comma-separated steps to run        (default: all)
#       step names: download,bry,clm,ini,metdl,frc,riv,inp
#       shortcuts : ocean = download,bry,clm,ini
#                   met   = metdl,frc
#                   all   = everything (ocean, met, riv, inp)
#       Steps always run in the order listed above, whatever order you give.
#   -r  ECMWF grid spacing for metdl/frc     (default: from window.conf)
#       0p25 = 0.25 deg, published from 2024-02-29
#       0p1  = 0.1 deg, published from 2026-10-21, ifs only, ~4.6x the download
#   -m  ECMWF model for metdl/frc            (default: from window.conf)
#       ifs | aifs-single | aifs-ens  (0p1 exists for ifs only)
#   -h  show this help
#
# Examples:
#   ./run_gulfofguinea_all.sh                       # everything, window.conf window
#   ./run_gulfofguinea_all.sh -b 2 -f 5             # everything, 2 back, 5 fwd
#   ./run_gulfofguinea_all.sh -s met                # only the atmospheric forcing
#   ./run_gulfofguinea_all.sh -s ocean              # only the ocean files
#   ./run_gulfofguinea_all.sh -s bry,ini,frc        # pick individual steps
#   ./run_gulfofguinea_all.sh -s met -r 0p1         # atmosphere at 0.1 deg
#
# Note: the real-time ECMWF server keeps only the last ~4 days, so with large
# values of -b the metdl step takes the older runs from the cloud mirror
# instead (SOURCE = 'auto' in the ECMWF download script). The mirror holds
# 0.25 deg open data from 2024-02-29 onward; for anything earlier use ERA5.

set -euo pipefail

umask 002   # new files/folders group-writable, so Becca and Sean can update them

# ----------------------------------------------------------------------------
# USER SETTINGS - edit these for your system
# ----------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Python scripts (relative to SCRIPT_DIR, or give absolute paths)
DOWNLOAD_PY="download_mercator_GulfOfGuinea_analysis.py"
BRY_PY="downscale_mercator_to_roms_GulfOfGuinea_BRY.py"
CLM_PY="downscale_mercator_to_roms_GulfOfGuinea_CLM.py"
INI_PY="downscale_mercator_to_roms_GulfOfGuinea_INI.py"
METDL_PY="download_ecmwf_opendata_GulfOfGuinea.py"
FRC_PY="convert_ecmwf_to_roms_frc_GulfOfGuinea.py"
RIV_PY="make_rivers_GulfOfGuinea.py --download --clobber"   # window from NDAYS_BACK/FWD
INP_PY="make_roms_in.py"

PYTHON="${PYTHON:-python}"

# Conda environment: from bash_scripts/site.conf unless already set
# shellcheck disable=SC1091
source "$(cd "${SCRIPT_DIR}/../bash_scripts" && pwd)/site_env.sh"
CONDA_ENV="${CONDA_ENV:-guinea2}"
CONDA_SH="${CONDA_SH:-$HOME/miniforge3/etc/profile.d/conda.sh}"

# Where logs go
LOG_ROOT="${SCRIPT_DIR}/logs"

# ----------------------------------------------------------------------------
# Defaults and argument parsing
# ----------------------------------------------------------------------------
STEPS="all"

usage() { sed -n '2,/^set -euo/p' "${BASH_SOURCE[0]}" | sed '$d' | sed 's/^# \{0,1\}//'; }

while getopts ":b:f:s:r:m:h" opt; do
    case "$opt" in
        b) WIN_BACK="$OPTARG" ;;
        f) WIN_FWD="$OPTARG" ;;
        s) STEPS="$OPTARG" ;;
        r) ECMWF_RESOL="$OPTARG" ;;
        m) ECMWF_MODEL="$OPTARG" ;;
        h) usage; exit 0 ;;
        :) echo "ERROR: option -$OPTARG needs a value" >&2; exit 1 ;;
        \?) echo "ERROR: unknown option -$OPTARG" >&2; usage; exit 1 ;;
    esac
done

# The window: from bash_scripts/window.conf, unless -b/-f were given. Sets
# WIN_START, WIN_END, WIN_BACK_DAYS, WIN_FWD_DAYS, MAX_DAYS_FWD_MET and exports
# NDAYS_BACK/NDAYS_FWD (or START_DATE/END_DATE) for the python scripts.
# shellcheck disable=SC1091
source "$(cd "${SCRIPT_DIR}/../bash_scripts" && pwd)/window_env.sh"

case "$ECMWF_RESOL" in
    0p25|0p1) ;;
    *) echo "ERROR: -r must be 0p25 or 0p1 (got '$ECMWF_RESOL')" >&2; exit 1 ;;
esac
case "$ECMWF_MODEL" in
    ifs|aifs-single|aifs-ens) ;;
    *) echo "ERROR: -m must be ifs, aifs-single or aifs-ens (got '$ECMWF_MODEL')" >&2; exit 1 ;;
esac
if [[ "$ECMWF_RESOL" == 0p1 && "$ECMWF_MODEL" != ifs ]]; then
    echo "ERROR: 0.1 deg open data exist for model ifs only (got -m $ECMWF_MODEL)" >&2
    exit 1
fi

# Expand shortcuts and validate step names
EXPANDED=""
IFS=',' read -r -a STEP_LIST <<< "$STEPS"
for s in "${STEP_LIST[@]}"; do
    case "$s" in
        all)   EXPANDED+=",download,bry,clm,ini,metdl,frc,riv,inp" ;;
        ocean) EXPANDED+=",download,bry,clm,ini" ;;
        met)   EXPANDED+=",metdl,frc" ;;
        download|bry|clm|ini|metdl|frc|riv|inp) EXPANDED+=",$s" ;;
        *) echo "ERROR: unknown step '$s' (valid: download,bry,clm,ini,metdl,frc,riv,inp,ocean,met,all)" >&2
           exit 1 ;;
    esac
done
STEPS="${EXPANDED#,}"
want() { [[ ",${STEPS}," == *",$1,"* ]]; }

if { want metdl || want frc; } && (( WIN_FWD_DAYS > MAX_DAYS_FWD_MET )); then
    echo "ERROR: -f must be <= ${MAX_DAYS_FWD_MET} when metdl/frc run (ECMWF open data goes to 144 h)" >&2
    echo "       Use '-s ocean' for a longer forecast window on the ocean files only." >&2
    exit 1
fi

# ----------------------------------------------------------------------------
# Environment and logging
# ----------------------------------------------------------------------------
if [[ -n "$CONDA_ENV" ]]; then
    # shellcheck disable=SC1090
    source "$CONDA_SH"
    conda activate "$CONDA_ENV"
fi

RUN_STAMP="$(date +%Y%m%d_%H%M%S)"
LOG_DIR="${LOG_ROOT}/run_${RUN_STAMP}"
mkdir -p "$LOG_DIR"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "${LOG_DIR}/driver.log"; }

run_step() {
    local name="$1" script="$2" args=""
    # allow "script.py --option ..." : first word is the script, the rest are arguments
    args="${script#* }"; [[ "$args" == "$script" ]] && args=""
    script="${script%% *}"
    local path="$script"
    [[ "$path" = /* ]] || path="${SCRIPT_DIR}/${script}"

    if [[ ! -f "$path" ]]; then
        log "ERROR: script not found for step '$name': $path"
        exit 1
    fi

    log "START  ${name}  (${script})"
    local t0=$SECONDS
    # PIPESTATUS so a python failure is not hidden by tee
    set +e
    "$PYTHON" -u "$path" $args 2>&1 | tee "${LOG_DIR}/${name}.log"
    local rc=${PIPESTATUS[0]}
    set -e
    if [[ $rc -ne 0 ]]; then
        log "FAILED ${name} (exit ${rc}) after $((SECONDS - t0))s - see ${LOG_DIR}/${name}.log"
        exit "$rc"
    fi
    log "DONE   ${name} in $((SECONDS - t0))s"
}

# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------
log "Time $(window_describe)"
log "Steps: ${STEPS}"
{ want metdl || want frc; } && log "$(ecmwf_describe)"
log "Logs:  ${LOG_DIR}"

# Ocean
want download && run_step download "$DOWNLOAD_PY"
want bry      && run_step bry      "$BRY_PY"
want clm      && run_step clm      "$CLM_PY"
want ini      && run_step ini      "$INI_PY"
# Atmosphere
want metdl    && run_step metdl    "$METDL_PY"
want frc      && run_step frc      "$FRC_PY"
# Rivers, then the ROMS .in file (checks that every input exists and covers the window)
want riv      && run_step riv      "$RIV_PY"
want inp      && run_step inp      "$INP_PY"

log "All requested steps finished successfully."
