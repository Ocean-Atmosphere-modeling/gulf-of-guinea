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
#
# The window is passed to every python script through the environment
# variables NDAYS_BACK and NDAYS_FWD, so they can never disagree.
#
# Usage:
#   ./run_gulfofguinea_all.sh [-b DAYS_BACK] [-f DAYS_FWD] [-s STEPS] [-h]
#
#   -b  days of past data before today      (default: 3)
#   -f  days of forecast after today        (default: 2, max 5 when met steps run)
#   -s  comma-separated steps to run        (default: all)
#       step names: download,bry,clm,ini,metdl,frc
#       shortcuts : ocean = download,bry,clm,ini
#                   met   = metdl,frc
#                   all   = everything
#       Steps always run in the order listed above, whatever order you give.
#   -h  show this help
#
# Examples:
#   ./run_gulfofguinea_all.sh                       # everything, 3 back, 2 fwd
#   ./run_gulfofguinea_all.sh -b 2 -f 5             # everything, 2 back, 5 fwd
#   ./run_gulfofguinea_all.sh -s met                # only the atmospheric forcing
#   ./run_gulfofguinea_all.sh -s ocean              # only the ocean files
#   ./run_gulfofguinea_all.sh -s bry,ini,frc        # pick individual steps
#
# Note: the ECMWF open data server keeps only a few days of history, so large
# values of -b will fail in the metdl step unless SOURCE is set to 'aws',
# 'google' or 'azure' in the ECMWF download script. If you need a long window
# for the ocean files only, run the ocean and met steps separately.

set -euo pipefail

# ----------------------------------------------------------------------------
# USER SETTINGS - edit these for your system
# ----------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Python scripts (relative to SCRIPT_DIR, or give absolute paths)
DOWNLOAD_PY="download_mercator_GulfOfGuinea.py"
BRY_PY="downscale_mercator_to_roms_GulfOfGuinea_BRY.py"
CLM_PY="downscale_mercator_to_roms_GulfOfGuinea_CLM.py"
INI_PY="downscale_mercator_to_roms_GulfOfGuinea_INI.py"
METDL_PY="download_ecmwf_opendata_GulfOfGuinea.py"
FRC_PY="convert_ecmwf_to_roms_frc_GulfOfGuinea.py"

PYTHON="${PYTHON:-python}"

# Optional: conda environment to activate (leave empty to skip)
CONDA_ENV=""            # e.g. "roms-env"
CONDA_SH=""             # e.g. "$HOME/miniconda3/etc/profile.d/conda.sh"

# Where logs go
LOG_ROOT="${SCRIPT_DIR}/logs"

# ----------------------------------------------------------------------------
# Defaults and argument parsing
# ----------------------------------------------------------------------------
DAYS_BACK=3
DAYS_FWD=2
STEPS="all"
MAX_DAYS_FWD_MET=5      # ECMWF open data goes to 144 h: (fwd+1)*24 <= 144

usage() { sed -n '2,/^set -euo/p' "${BASH_SOURCE[0]}" | sed '$d' | sed 's/^# \{0,1\}//'; }

while getopts ":b:f:s:h" opt; do
    case "$opt" in
        b) DAYS_BACK="$OPTARG" ;;
        f) DAYS_FWD="$OPTARG" ;;
        s) STEPS="$OPTARG" ;;
        h) usage; exit 0 ;;
        :) echo "ERROR: option -$OPTARG needs a value" >&2; exit 1 ;;
        \?) echo "ERROR: unknown option -$OPTARG" >&2; usage; exit 1 ;;
    esac
done

is_nonneg_int() { [[ "$1" =~ ^[0-9]+$ ]]; }
if ! is_nonneg_int "$DAYS_BACK" || ! is_nonneg_int "$DAYS_FWD"; then
    echo "ERROR: -b and -f must be non-negative integers (got b='$DAYS_BACK', f='$DAYS_FWD')" >&2
    exit 1
fi

# Expand shortcuts and validate step names
EXPANDED=""
IFS=',' read -r -a STEP_LIST <<< "$STEPS"
for s in "${STEP_LIST[@]}"; do
    case "$s" in
        all)   EXPANDED+=",download,bry,clm,ini,metdl,frc" ;;
        ocean) EXPANDED+=",download,bry,clm,ini" ;;
        met)   EXPANDED+=",metdl,frc" ;;
        download|bry|clm|ini|metdl|frc) EXPANDED+=",$s" ;;
        *) echo "ERROR: unknown step '$s' (valid: download,bry,clm,ini,metdl,frc,ocean,met,all)" >&2
           exit 1 ;;
    esac
done
STEPS="${EXPANDED#,}"
want() { [[ ",${STEPS}," == *",$1,"* ]]; }

if { want metdl || want frc; } && (( DAYS_FWD > MAX_DAYS_FWD_MET )); then
    echo "ERROR: -f must be <= ${MAX_DAYS_FWD_MET} when metdl/frc run (ECMWF open data goes to 144 h)" >&2
    echo "       Use '-s ocean' for a longer forecast window on the ocean files only." >&2
    exit 1
fi

# The python scripts read these (see the os.environ lines in each script)
export NDAYS_BACK="$DAYS_BACK"
export NDAYS_FWD="$DAYS_FWD"

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
log "Time window: ${DAYS_BACK} day(s) back, ${DAYS_FWD} day(s) forward (relative to $(date +%Y-%m-%d))"
log "Steps: ${STEPS}"
log "Logs:  ${LOG_DIR}"

# Ocean
want download && run_step download "$DOWNLOAD_PY"
want bry      && run_step bry      "$BRY_PY"
want clm      && run_step clm      "$CLM_PY"
want ini      && run_step ini      "$INI_PY"
# Atmosphere
want metdl    && run_step metdl    "$METDL_PY"
want frc      && run_step frc      "$FRC_PY"

log "All requested steps finished successfully."
