#!/bin/bash
#
# Start one Gulf of Guinea ROMS forecast cycle:
#   1. submit the input preparation job  (bash_scripts/job_forecast_prep.sh)
#   2. submit the ROMS job (run/job_gog.sh), which starts only if job 1 succeeds
#
# The window comes from bash_scripts/window.conf (the one place it is set) and
# is fixed when you run this: START = today - NDAYS_BACK, END = today +
# NDAYS_FWD (the run ends at 00:00 on END), or the fixed START_DATE/END_DATE
# if those are set in window.conf.
#
# Usage (from anywhere, on the login node):
#   bash bash_scripts/run_forecast_cycle.sh               # window from window.conf
#   bash bash_scripts/run_forecast_cycle.sh -b 3 -f 2     # override it for this run
#   bash bash_scripts/run_forecast_cycle.sh -n            # show what would be submitted
#
# Watch it:   squeue -u $USER
# Logs:       /projects/f_omg_1/moa/africa/out/forecast/logs/prep.<jobid>.log
#             python/logs/run_<time>/      (one log per preparation step)
#             run/out.slurm.*              (ROMS)
# Output:     /projects/f_omg_1/moa/africa/out/forecast/<START>/

set -euo pipefail

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
while getopts ":b:f:nh" opt; do
    case "$opt" in
        b) WIN_BACK="$OPTARG" ;;
        f) WIN_FWD="$OPTARG" ;;
        n) DRYRUN=1 ;;
        h) sed -n '2,23p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "usage: $0 [-b NDAYS_BACK] [-f NDAYS_FWD] [-n]" >&2; exit 1 ;;
    esac
done

# The window: from bash_scripts/window.conf, unless -b/-f were given. Sets
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
echo "ROMS input file: run/${INFILE}"

if (( DRYRUN )); then
    echo "[dry run] sbatch ${SB_OPTS[*]-} --export=ALL,REPO=${REPO},START_DATE=${START_DATE},END_DATE=${END_DATE} ${REPO}/bash_scripts/job_forecast_prep.sh"
    echo "[dry run] sbatch ${SB_OPTS[*]-} --dependency=afterok:<prep job> --chdir=${REPO}/run ${REPO}/run/job_gog.sh ${INFILE}"
    exit 0
fi

mkdir -p "$LOGDIR"
prep=$(sbatch --parsable ${SB_OPTS[@]+"${SB_OPTS[@]}"} --export=ALL,REPO=${REPO},START_DATE=${START_DATE},END_DATE=${END_DATE} \
       ${REPO}/bash_scripts/job_forecast_prep.sh)
echo "Submitted input preparation job ${prep}  (log: ${LOGDIR}/prep.${prep}.log)"

roms=$(sbatch --parsable ${SB_OPTS[@]+"${SB_OPTS[@]}"} --dependency=afterok:${prep} --kill-on-invalid-dep=yes \
       --job-name=gog_fc_$(date -d "$START_DATE" +%m%d) --chdir=${REPO}/run \
       ${REPO}/run/job_gog.sh ${INFILE})
echo "Submitted ROMS job ${roms}  (starts after ${prep} succeeds; log: run/out.slurm.*.${roms})"
