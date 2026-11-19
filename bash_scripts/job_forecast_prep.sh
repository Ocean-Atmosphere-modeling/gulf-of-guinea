#!/bin/bash
#
# Batch job: all input files for one Gulf of Guinea forecast cycle.
# Submitted by bash_scripts/run_forecast_cycle.sh, which sets START_DATE and
# END_DATE from bash_scripts/window.conf (do not normally submit this by hand).
#
# Runs python/run_gulfofguinea_forcing_scripts.sh -s all:
#   Mercator download -> BRY -> CLM -> INI -> ECMWF download -> FRC
#   -> rivers -> ROMS .in file (with input checks)
# Compute nodes on Amarel have internet access, so the downloads run here too.

#SBATCH --partition=p_omg_1
#SBATCH --job-name=gog_fc_prep
#SBATCH --nodes=1
#SBATCH --ntasks=64
#SBATCH --ntasks-per-node=64
#SBATCH --cpus-per-task=1
#SBATCH --mem=180000
#SBATCH --time=04:00:00
#SBATCH --requeue
#SBATCH --output=/projects/f_omg_1/moa/africa/out/forecast/logs/prep.%j.log
#SBATCH --export=ALL

set -euo pipefail

umask 002   # new files/folders group-writable, so Becca and Sean can update them

: "${START_DATE:?START_DATE not set (submit with bash_scripts/run_forecast_cycle.sh)}"
: "${END_DATE:?END_DATE not set}"
export START_DATE END_DATE
export START_MODE=${START_MODE:-auto}   # auto | hot | cold, read by make_roms_in.py

# Every python script reads this window through python/run_window.py, so the
# fixed dates are passed straight through - no conversion to day counts, and
# the window does not shift if the job waited in the queue past midnight.
today=$(date -d "$(date +%F)" +%s)
if (( $(date -d "$END_DATE" +%s) < today )); then
    echo "ERROR: cycle end $END_DATE is already in the past; resubmit for today" >&2
    exit 1
fi

# Repo root. Slurm copies a submitted script to its spool directory, so
# BASH_SOURCE is not reliable here: try every sensible candidate and keep the
# first one that really is a checkout (python/run_window.py is the marker).
find_repo_root() {
    local c self
    local -a cands=()
    [[ -n "${REPO:-}" ]] && cands+=("$REPO")
    if [[ -n "${SLURM_JOB_ID:-}" ]] && command -v scontrol >/dev/null 2>&1; then
        self=$(scontrol show job "$SLURM_JOB_ID" --oneliner 2>/dev/null \
               | sed -n 's/.*Command=\([^ ]*\).*/\1/p')
        [[ -n "$self" ]] && cands+=("$(dirname "$(dirname "$self")")")
    fi
    [[ -n "${SLURM_SUBMIT_DIR:-}" ]] && cands+=("$SLURM_SUBMIT_DIR" "$(dirname "$SLURM_SUBMIT_DIR")")
    cands+=("$(cd "$(dirname "${BASH_SOURCE[0]}")/.." 2>/dev/null && pwd)")
    for c in "${cands[@]}"; do
        [[ -n "$c" && -f "$c/python/run_window.py" ]] && { (cd "$c" && pwd); return 0; }
    done
    return 1
}
REPO=$(find_repo_root) || {
    echo "ERROR: cannot find the gulf-of-guinea checkout. Submit from the repo" >&2
    echo "       (or its python/ directory), or sbatch --export=ALL,REPO=/path/to/repo" >&2
    exit 1; }

echo "Forecast cycle ${START_DATE} to ${END_DATE} on $(hostname)"
echo "Repo: ${REPO}"
export OMP_NUM_THREADS=${SLURM_CPUS_PER_TASK:-8}

bash ${REPO}/python/run_gulfofguinea_forcing_scripts.sh -s all
