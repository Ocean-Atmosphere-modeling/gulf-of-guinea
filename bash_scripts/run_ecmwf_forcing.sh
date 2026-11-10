#!/bin/bash
#
# Download ECMWF IFS open data and convert it to a ROMS bulk-flux forcing file
# for the Gulf of Guinea, covering START_DATE through today (+ NDAYS_FWD days).
#
# Run on the LOGIN node (the download needs internet access):
#
#   cd /projectsp/f_omg_1/cbenton/gulf-of-guinea
#   bash bash_scripts/run_ecmwf_forcing.sh               # uses START_DATE below
#   bash bash_scripts/run_ecmwf_forcing.sh 2026-10-01    # or give a start date
#
# Scripts needed (in python/):
#   download_ecmwf_opendata_GulfOfGuinea.py   (set SOURCE = 'aws' for past dates)
#   convert_ecmwf_to_roms_frc_GulfOfGuinea.py
#
# Output: /projects/f_omg_1/moa/africa/data/blk/GulfOfGuinea_frc_IFS_bulkflux_<YYYYMMDD>.nc

set -e                                    # stop if a step fails

# USER SETTINGS ---------------------------------------------------------
START_DATE=${1:-2026-10-01}               # first day of the run (YYYY-MM-DD)
NDAYS_FWD=0                               # forecast days past today (0 for a hindcast)
# -----------------------------------------------------------------------

# Days from START_DATE to today; both python scripts read NDAYS_BACK/NDAYS_FWD
NDAYS_BACK=$(( ( $(date -d "$(date +%F)" +%s) - $(date -d "$START_DATE" +%s) ) / 86400 ))
if [ "$NDAYS_BACK" -lt 0 ]; then
    echo "START_DATE $START_DATE is in the future"; exit 1
fi
export NDAYS_BACK NDAYS_FWD
echo "Forcing window: $START_DATE to $(date -d "+${NDAYS_FWD} days" +%F)  (NDAYS_BACK=$NDAYS_BACK, NDAYS_FWD=$NDAYS_FWD)"

# Python environment: may have to change depending on your setup
source ~/miniforge3/etc/profile.d/conda.sh
conda activate guinea2

cd "$(dirname "${BASH_SOURCE[0]}")/../python"

echo "=== Download ECMWF open data  $(date)"
python -u download_ecmwf_opendata_GulfOfGuinea.py

echo "=== Convert to ROMS forcing   $(date)"
python -u convert_ecmwf_to_roms_frc_GulfOfGuinea.py

echo "=== done $(date)"
ls -lh /projects/f_omg_1/moa/africa/data/blk/GulfOfGuinea_frc_IFS_bulkflux_$(date -d "$START_DATE" +%Y%m%d).nc
