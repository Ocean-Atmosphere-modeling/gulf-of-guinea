#!/bin/bash
#
# Batch job: all input files for one Gulf of Guinea forecast cycle.
# Submitted by bash_scripts/run_forecast_cycle.sh, which sets START_DATE and
# END_DATE (do not normally submit this by hand).
#
# Runs python/run_gulfofguinea_forcing_scripts.sh -s all:
#   Mercator download -> BRY -> CLM -> INI -> ECMWF download -> FRC
#   -> rivers -> ROMS .in file (with input checks)
# Compute nodes on Amarel have internet access, so the downloads run here too.

#SBATCH --partition=p_omg_1
#SBATCH --job-name=gog_fc_prep
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64000
#SBATCH --time=04:00:00
#SBATCH --requeue
#SBATCH --output=/projects/f_omg_1/moa/africa/out/forecast/logs/prep.%j.log
#SBATCH --export=ALL

set -euo pipefail

: "${START_DATE:?START_DATE not set (submit with bash_scripts/run_forecast_cycle.sh)}"
: "${END_DATE:?END_DATE not set}"
export START_DATE END_DATE

# The Mercator, river and .in scripts use START_DATE/END_DATE (fixed dates).
# The ECMWF scripts count days from today, so convert the fixed dates to
# NDAYS_BACK/NDAYS_FWD as of the moment this job starts. If the job waited in
# the queue past midnight, both still describe the same window.
today=$(date -d "$(date +%F)" +%s)
NDAYS_BACK=$(( (today - $(date -d "$START_DATE" +%s)) / 86400 ))
NDAYS_FWD=$((  ($(date -d "$END_DATE" +%s) - today) / 86400 ))
if (( NDAYS_FWD < 0 )); then
    echo "ERROR: cycle end $END_DATE is already in the past; resubmit for today" >&2
    exit 1
fi

REPO=/projectsp/f_omg_1/cbenton/gulf-of-guinea
echo "Forecast cycle ${START_DATE} to ${END_DATE} (NDAYS_BACK=${NDAYS_BACK}, NDAYS_FWD=${NDAYS_FWD}) on $(hostname)"
export OMP_NUM_THREADS=${SLURM_CPUS_PER_TASK:-8}

bash ${REPO}/python/run_gulfofguinea_forcing_scripts.sh -b ${NDAYS_BACK} -f ${NDAYS_FWD} -s all
