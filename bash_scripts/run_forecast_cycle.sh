#!/bin/bash
#
# Start one Gulf of Guinea ROMS forecast cycle:
#   1. submit the input preparation job  (bash_scripts/job_forecast_prep.sh)
#   2. submit the ROMS job (run/job_gog.sh), which starts only if job 1 succeeds
#
# The window comes from bash_scripts/window.conf (the one place it is set) and
# is fixed when you run this: START = today - NDAYS_BACK (or -s/-b), END =
# today + NDAYS_FWD (the run ends at 00:00 on END), or the fixed
# START_DATE/END_DATE if those are set in window.conf.
#
# Start: by default each cycle HOT starts from the previous run's history
# snapshot at START (no tide ramp). If none exists it COLD starts from the
# Mercator INI with the tides ramped up (see python/make_roms_in.py).
#
# Usage (from anywhere, on the login node):
#   bash bash_scripts/run_forecast_cycle.sh               # window from window.conf
#   bash bash_scripts/run_forecast_cycle.sh -b 3 -f 2     # override it for this run
#   bash bash_scripts/run_forecast_cycle.sh -s 2026-11-01 -c   # spin-up: cold start Nov 1
#   bash bash_scripts/run_forecast_cycle.sh -n            # show what would be submitted
#
#   -b N           days of past data before today
#   -f N           forecast days after today
#   -s YYYY-MM-DD  fixed start date (instead of -b)
#   -c             force a cold start (Mercator INI, tides ramped)
#   -H             require a hot start (fail if no earlier snapshot)
#   -n             dry run: print the sbatch commands, submit nothing
#
# Watch it:   squeue -u $USER
# Logs:       $DATA_ROOT/out/forecast/logs/prep.<jobid>.log
#             python/logs/run_<time>/      (one log per preparation step)
#             run/out.slurm.*              (ROMS)
# Output:     $DATA_ROOT/out/forecast/<START><OUTPUT_SUFFIX>/
# DATA_ROOT and OUTPUT_SUFFIX are set in bash_scripts/site.conf.

set -euo pipefail

umask 002   # new files/folders group-writable, so colleagues can update them

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(dirname "$SCRIPT_DIR")"
# Machine-specific settings (DATA_ROOT, SLURM_PARTITION, SLURM_ACCOUNT)
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/site_env.sh"
LOGDIR="${LOG_ROOT}"

# Passed on the sbatch command line, overriding the #SBATCH defaults in the
# job scripts (Slurm reads those before the script runs, so they cannot come
# from a config file).
SB_OPTS=()
[[ -n "${SLURM_PARTITION:-}" ]] && SB_OPTS+=(--partition="${SLURM_PARTITION}")
[[ -n "${SLURM_ACCOUNT:-}" ]] && SB_OPTS+=(--account="${SLURM_ACCOUNT}")

DRYRUN=0
START_OPT=""
START_MODE=auto
while getopts ":b:f:s:cHnh" opt; do
    case "$opt" in
        b) WIN_BACK="$OPTARG" ;;
        f) WIN_FWD="$OPTARG" ;;
        s) START_OPT="$OPTARG" ;;
        c) START_MODE=cold ;;
        H) START_MODE=hot ;;
        n) DRYRUN=1 ;;
        h) sed -n '2,34p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "usage: $0 [-b NDAYS_BACK | -s START] [-f NDAYS_FWD] [-c|-H] [-n]" >&2; exit 1 ;;
    esac
done

# -s gives a fixed start date: turn it into "days back from today", which is
# what window.conf and window_env.sh work in.
if [[ -n "$START_OPT" ]]; then
    date -d "$START_OPT" >/dev/null 2>&1 || { echo "-s: bad date '$START_OPT'" >&2; exit 1; }
    back=$(( ( $(date -d "$(date +%F)" +%s) - $(date -d "$START_OPT" +%s) ) / 86400 ))
    (( back >= 0 )) || { echo "-s: start date is in the future" >&2; exit 1; }
    WIN_BACK="$back"
fi

# The window: from bash_scripts/window.conf, unless -b/-f/-s were given. Sets
# WIN_START, WIN_END, WIN_BACK_DAYS, WIN_FWD_DAYS, MAX_DAYS_FWD_MET.
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/window_env.sh"

(( WIN_FWD_DAYS <= MAX_DAYS_FWD_MET )) || {
    echo "forecast days (${WIN_FWD_DAYS}) must be <= ${MAX_DAYS_FWD_MET} (ECMWF open data goes to 144 h)" >&2
    exit 1; }

START_DATE="$WIN_START"
END_DATE="$WIN_END"
INFILE=roms_gulfofguinea_$(date -d "$START_DATE" +%Y%m%d).in

echo "Cycle: $(window_describe)"
echo "Start mode: ${START_MODE}   ROMS input file: run/${INFILE}"

EXPORTS="ALL,REPO=${REPO},START_DATE=${START_DATE},END_DATE=${END_DATE},START_MODE=${START_MODE}"

if (( DRYRUN )); then
    echo "[dry run] sbatch ${SB_OPTS[*]-} --export=${EXPORTS} ${REPO}/bash_scripts/job_forecast_prep.sh"
    echo "[dry run] sbatch ${SB_OPTS[*]-} --dependency=afterok:<prep job> --chdir=${REPO}/run ${REPO}/run/job_gog.sh ${INFILE}"
    exit 0
fi

mkdir -p "$LOGDIR"
prep=$(sbatch --parsable ${SB_OPTS[@]+"${SB_OPTS[@]}"} --export="${EXPORTS}" \
       ${REPO}/bash_scripts/job_forecast_prep.sh)
echo "Submitted input preparation job ${prep}  (log: ${LOGDIR}/prep.${prep}.log)"

roms=$(sbatch --parsable ${SB_OPTS[@]+"${SB_OPTS[@]}"} --dependency=afterok:${prep} --kill-on-invalid-dep=yes \
       --job-name=gog_fc_$(date -d "$START_DATE" +%m%d) --chdir=${REPO}/run \
       ${REPO}/run/job_gog.sh ${INFILE})
echo "Submitted ROMS job ${roms}  (starts after ${prep} succeeds; log: run/out.slurm.*.${roms})"
