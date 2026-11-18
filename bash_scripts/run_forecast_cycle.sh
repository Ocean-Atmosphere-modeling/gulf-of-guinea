#!/bin/bash
#
# Start one Gulf of Guinea ROMS forecast cycle:
#   1. submit the input preparation job  (bash_scripts/job_forecast_prep.sh)
#   2. submit the ROMS job (run/job_gog.sh), which starts only if job 1 succeeds
#
# The window is fixed when you run this: START = today - DAYS_BACK (or -s),
# END = today + DAYS_FWD (the run ends at 00:00 on END).
#
# Start: by default each cycle HOT starts from the previous run's history
# snapshot at START (no tide ramp). If none exists it COLD starts from the
# Mercator INI with the tides ramped up (see python/make_roms_in.py).
#
# Usage (from anywhere, on the login node):
#   bash bash_scripts/run_forecast_cycle.sh               # daily cycle: 3 days back, 2 forward
#   bash bash_scripts/run_forecast_cycle.sh -b 3 -f 2
#   bash bash_scripts/run_forecast_cycle.sh -s 2026-11-01 -c   # spin-up: cold start Nov 1 -> today+2
#   bash bash_scripts/run_forecast_cycle.sh -n            # show what would be submitted
#
#   -s YYYY-MM-DD  fixed start date (instead of -b)
#   -c             force a cold start (Mercator INI, tides ramped)
#   -H             require a hot start (fail if no earlier snapshot)
#
# Watch it:   squeue -u $USER
# Logs:       /projects/f_omg_1/moa/africa/out/forecast/logs/prep.<jobid>.log
#             python/logs/run_<time>/      (one log per preparation step)
#             run/out.slurm.*              (ROMS)
# Output:     /projects/f_omg_1/moa/africa/out/forecast/<START>/

set -euo pipefail

umask 002   # new files/folders group-writable, so Becca and Sean can update them

REPO=/projectsp/f_omg_1/cbenton/gulf-of-guinea
LOGDIR=/projects/f_omg_1/moa/africa/out/forecast/logs

DAYS_BACK=3
DAYS_FWD=2
DRYRUN=0
START_OPT=""
START_MODE=auto
while getopts ":b:f:s:cHnh" opt; do
    case "$opt" in
        b) DAYS_BACK="$OPTARG" ;;
        f) DAYS_FWD="$OPTARG" ;;
        s) START_OPT="$OPTARG" ;;
        c) START_MODE=cold ;;
        H) START_MODE=hot ;;
        n) DRYRUN=1 ;;
        h) sed -n '2,30p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "usage: $0 [-b DAYS_BACK | -s START] [-f DAYS_FWD] [-c|-H] [-n]" >&2; exit 1 ;;
    esac
done
if [[ -n "$START_OPT" ]]; then
    date -d "$START_OPT" >/dev/null 2>&1 || { echo "-s: bad date '$START_OPT'" >&2; exit 1; }
    DAYS_BACK=$(( ( $(date -d "$(date +%F)" +%s) - $(date -d "$START_OPT" +%s) ) / 86400 ))
    (( DAYS_BACK >= 0 )) || { echo "-s: start date is in the future" >&2; exit 1; }
fi
[[ "$DAYS_BACK" =~ ^[0-9]+$ && "$DAYS_FWD" =~ ^[0-9]+$ ]] || { echo "-b/-f must be whole numbers" >&2; exit 1; }
(( DAYS_BACK + DAYS_FWD >= 1 )) || { echo "window must be at least 1 day" >&2; exit 1; }
(( DAYS_FWD <= 5 )) || { echo "-f must be <= 5 (ECMWF open data goes to 144 h)" >&2; exit 1; }

START_DATE=$(date -d "-${DAYS_BACK} days" +%F)
END_DATE=$(date -d "+${DAYS_FWD} days" +%F)
INFILE=roms_gulfofguinea_$(date -d "$START_DATE" +%Y%m%d).in

echo "Cycle: ${START_DATE} 00:00 to ${END_DATE} 00:00  (${DAYS_BACK} days back, ${DAYS_FWD} forward)"
echo "Start mode: ${START_MODE}   ROMS input file: run/${INFILE}"

if (( DRYRUN )); then
    echo "[dry run] sbatch --export=ALL,START_DATE=${START_DATE},END_DATE=${END_DATE},START_MODE=${START_MODE} ${REPO}/bash_scripts/job_forecast_prep.sh"
    echo "[dry run] sbatch --dependency=afterok:<prep job> --chdir=${REPO}/run ${REPO}/run/job_gog.sh ${INFILE}"
    exit 0
fi

mkdir -p "$LOGDIR"
prep=$(sbatch --parsable --export=ALL,START_DATE=${START_DATE},END_DATE=${END_DATE},START_MODE=${START_MODE} \
       ${REPO}/bash_scripts/job_forecast_prep.sh)
echo "Submitted input preparation job ${prep}  (log: ${LOGDIR}/prep.${prep}.log)"

roms=$(sbatch --parsable --dependency=afterok:${prep} --kill-on-invalid-dep=yes \
       --job-name=gog_fc_$(date -d "$START_DATE" +%m%d) --chdir=${REPO}/run \
       ${REPO}/run/job_gog.sh ${INFILE})
echo "Submitted ROMS job ${roms}  (starts after ${prep} succeeds; log: run/out.slurm.*.${roms})"
