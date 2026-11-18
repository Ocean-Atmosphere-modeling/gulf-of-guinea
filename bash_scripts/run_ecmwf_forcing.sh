#!/bin/bash
#
# Download ECMWF IFS open data and convert it to a ROMS bulk-flux forcing file
# for the Gulf of Guinea, over the window set in bash_scripts/window.conf.
#
# Run on the LOGIN node (the download needs internet access):
#
#   bash bash_scripts/run_ecmwf_forcing.sh               # window from window.conf
#   bash bash_scripts/run_ecmwf_forcing.sh 2026-10-01    # or start from this date
#                                                        # (through today + NDAYS_FWD)
#
# Scripts needed (in python/):
#   download_ecmwf_opendata_GulfOfGuinea.py   (set SOURCE = 'aws' for past dates)
#   convert_ecmwf_to_roms_frc_GulfOfGuinea.py
#
# Output: /projects/f_omg_1/moa/africa/data/blk/GulfOfGuinea_frc_IFS_bulkflux_<YYYYMMDD>.nc

set -e                                    # stop if a step fails

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# The window comes from bash_scripts/window.conf. An optional first argument
# gives a start date instead, counted back from today (NDAYS_FWD stays as set
# in window.conf).
if [ -n "${1:-}" ]; then
    arg_back=$(( ( $(date -d "$(date +%F)" +%s) - $(date -d "$1" +%s) ) / 86400 ))
    if [ "$arg_back" -lt 0 ]; then
        echo "start date $1 is in the future"; exit 1
    fi
    WIN_BACK="$arg_back"
fi

# Sets WIN_START, WIN_END, WIN_FWD_DAYS, MAX_DAYS_FWD_MET and exports the
# window for the python scripts.
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/window_env.sh"

(( WIN_FWD_DAYS <= MAX_DAYS_FWD_MET )) || {
    echo "forecast days (${WIN_FWD_DAYS}) must be <= ${MAX_DAYS_FWD_MET} (ECMWF open data goes to 144 h)" >&2
    exit 1; }

echo "Forcing $(window_describe)"
START_DATE_FILE="$WIN_START"

# Python environment: may have to change depending on your setup
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/site_env.sh"
# shellcheck disable=SC1090
source "${CONDA_SH:-$HOME/miniforge3/etc/profile.d/conda.sh}"
conda activate "${CONDA_ENV:-guinea2}"

cd "$(dirname "${BASH_SOURCE[0]}")/../python"

echo "=== Download ECMWF open data  $(date)"
python -u download_ecmwf_opendata_GulfOfGuinea.py

echo "=== Convert to ROMS forcing   $(date)"
python -u convert_ecmwf_to_roms_frc_GulfOfGuinea.py

echo "=== done $(date)"
ls -lh /projects/f_omg_1/moa/africa/data/blk/GulfOfGuinea_frc_IFS_bulkflux_$(date -d "$START_DATE_FILE" +%Y%m%d).nc
