#!/usr/bin/env bash
#
# run_gulfofguinea_forecast.sh
#
# Runs the Gulf of Guinea ROMS pre-processing chain with ONE shared time window:
#   1. download Mercator (CMEMS) daily files
#   2. build the boundary file   (BRY)
#   3. build the climatology files (CLM, one per day)
#   4. build the initial conditions file (INI)
#
# The window is defined ONCE in bash_scripts/window.conf and passed to every
# python script through the environment (NDAYS_BACK/NDAYS_FWD, or
# START_DATE/END_DATE for a hindcast), so they can never disagree.
#
# Usage:
#   ./run_gulfofguinea_forecast.sh [-b DAYS_BACK] [-f DAYS_FWD] [-s STEPS] [-h]
#
#   -b  days of past data before today      (default: from window.conf)
#   -f  days of forecast after today        (default: from window.conf)
#   -s  comma-separated steps to run        (default: download,bry,clm,ini)
#   -h  show this help
#
# Examples:
#   ./run_gulfofguinea_forecast.sh                    # window from window.conf
#   ./run_gulfofguinea_forecast.sh -b 3 -f 5          # 3 back, 5 forward
#   ./run_gulfofguinea_forecast.sh -b 7 -f 2 -s bry,ini   # skip download and clm

set -euo pipefail

# ----------------------------------------------------------------------------
# USER SETTINGS - edit these for your system
# ----------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Python scripts (relative to SCRIPT_DIR, or give absolute paths)
DOWNLOAD_PY="download_mercator_GulfOfGuinea.py"                 # <-- your download script name
BRY_PY="downscale_mercator_to_roms_GulfOfGuinea_BRY.py"
CLM_PY="downscale_mercator_to_roms_GulfOfGuinea_CLM.py"         # <-- the script that writes clm_*.nc
INI_PY="downscale_mercator_to_roms_GulfOfGuinea_INI.py"

PYTHON="${PYTHON:-python}"

# Conda environment: from bash_scripts/site.conf (leave CONDA_ENV empty there
# to skip activation)
# shellcheck disable=SC1091
source "$(cd "${SCRIPT_DIR}/../bash_scripts" && pwd)/site_env.sh"

# Where logs go
LOG_ROOT="${SCRIPT_DIR}/logs"

# ----------------------------------------------------------------------------
# Defaults and argument parsing
# ----------------------------------------------------------------------------
STEPS="download,bry,clm,ini"

usage() { sed -n '2,/^set -euo/p' "${BASH_SOURCE[0]}" | sed '$d' | sed 's/^# \{0,1\}//'; }

while getopts ":b:f:s:h" opt; do
    case "$opt" in
        b) WIN_BACK="$OPTARG" ;;
        f) WIN_FWD="$OPTARG" ;;
        s) STEPS="$OPTARG" ;;
        h) usage; exit 0 ;;
        :) echo "ERROR: option -$OPTARG needs a value" >&2; exit 1 ;;
        \?) echo "ERROR: unknown option -$OPTARG" >&2; usage; exit 1 ;;
    esac
done

# The window: from bash_scripts/window.conf, unless -b/-f were given. Sets
# WIN_START, WIN_END, WIN_BACK_DAYS, WIN_FWD_DAYS and exports the window for
# the python scripts.
# shellcheck disable=SC1091
source "$(cd "${SCRIPT_DIR}/../bash_scripts" && pwd)/window_env.sh"

# Validate step names
IFS=',' read -r -a STEP_LIST <<< "$STEPS"
for s in "${STEP_LIST[@]}"; do
    case "$s" in
        download|bry|clm|ini) ;;
        *) echo "ERROR: unknown step '$s' (valid: download,bry,clm,ini)" >&2; exit 1 ;;
    esac
done
want() { [[ ",${STEPS}," == *",$1,"* ]]; }

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
    local name="$1" script="$2"
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
    "$PYTHON" -u "$path" 2>&1 | tee "${LOG_DIR}/${name}.log"
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
log "Logs:  ${LOG_DIR}"

want download && run_step download "$DOWNLOAD_PY"
want bry      && run_step bry      "$BRY_PY"
want clm      && run_step clm      "$CLM_PY"
want ini      && run_step ini      "$INI_PY"

log "All requested steps finished successfully."
