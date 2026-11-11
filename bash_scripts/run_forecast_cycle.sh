#!/bin/bash
#
# Start one Gulf of Guinea ROMS forecast cycle:
#   1. submit the input preparation job  (bash_scripts/job_forecast_prep.sh)
#   2. submit the ROMS job (run/job_gog.sh), which starts only if job 1 succeeds
#
# The window is fixed when you run this: START = today - DAYS_BACK,
# END = today + DAYS_FWD (the run ends at 00:00 on END).
#
# Usage (from anywhere, on the login node):
#   bash bash_scripts/run_forecast_cycle.sh               # 3 days back, 2 forward
#   bash bash_scripts/run_forecast_cycle.sh -b 3 -f 2
#   bash bash_scripts/run_forecast_cycle.sh -n            # show what would be submitted
#
# Watch it:   squeue -u $USER
# Logs:       /projects/f_omg_1/moa/africa/out/forecast/logs/prep.<jobid>.log
#             python/logs/run_<time>/      (one log per preparation step)
#             run/out.slurm.*              (ROMS)
# Output:     /projects/f_omg_1/moa/africa/out/forecast/<START>/

set -euo pipefail

REPO=/projectsp/f_omg_1/cbenton/gulf-of-guinea
LOGDIR=/projects/f_omg_1/moa/africa/out/forecast/logs

DAYS_BACK=3
DAYS_FWD=2
DRYRUN=0
while getopts ":b:f:nh" opt; do
    case "$opt" in
        b) DAYS_BACK="$OPTARG" ;;
        f) DAYS_FWD="$OPTARG" ;;
        n) DRYRUN=1 ;;
        h) sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "usage: $0 [-b DAYS_BACK] [-f DAYS_FWD] [-n]" >&2; exit 1 ;;
    esac
done
[[ "$DAYS_BACK" =~ ^[0-9]+$ && "$DAYS_FWD" =~ ^[0-9]+$ ]] || { echo "-b/-f must be whole numbers" >&2; exit 1; }
(( DAYS_BACK + DAYS_FWD >= 1 )) || { echo "window must be at least 1 day" >&2; exit 1; }
(( DAYS_FWD <= 5 )) || { echo "-f must be <= 5 (ECMWF open data goes to 144 h)" >&2; exit 1; }

START_DATE=$(date -d "-${DAYS_BACK} days" +%F)
END_DATE=$(date -d "+${DAYS_FWD} days" +%F)
INFILE=roms_gulfofguinea_$(date -d "$START_DATE" +%Y%m%d).in

echo "Cycle: ${START_DATE} 00:00 to ${END_DATE} 00:00  (${DAYS_BACK} days back, ${DAYS_FWD} forward)"
echo "ROMS input file: run/${INFILE}"

if (( DRYRUN )); then
    echo "[dry run] sbatch --export=ALL,START_DATE=${START_DATE},END_DATE=${END_DATE} ${REPO}/bash_scripts/job_forecast_prep.sh"
    echo "[dry run] sbatch --dependency=afterok:<prep job> --chdir=${REPO}/run ${REPO}/run/job_gog.sh ${INFILE}"
    exit 0
fi

mkdir -p "$LOGDIR"
prep=$(sbatch --parsable --export=ALL,START_DATE=${START_DATE},END_DATE=${END_DATE} \
       ${REPO}/bash_scripts/job_forecast_prep.sh)
echo "Submitted input preparation job ${prep}  (log: ${LOGDIR}/prep.${prep}.log)"

roms=$(sbatch --parsable --dependency=afterok:${prep} --kill-on-invalid-dep=yes \
       --job-name=gog_fc_$(date -d "$START_DATE" +%m%d) --chdir=${REPO}/run \
       ${REPO}/run/job_gog.sh ${INFILE})
echo "Submitted ROMS job ${roms}  (starts after ${prep} succeeds; log: run/out.slurm.*.${roms})"
