#!/bin/bash
#
# Make the ROMS INI, BRY and CLM files from downloaded Mercator data on a compute node.
# Run the Mercator download first (on the login node), then submit from the
# repo's python/ directory:
#
# For example: cd /path/to/gulf-of-guinea/python
# Command to run:   sbatch ../bash_scripts/job_downscale.sh
# The repo is found from the directory you submit from, so no path is hardcoded.
#
# Scripts needed are the following
#  downscale_mercator_to_roms_GulfOfGuinea_INI.py
#  downscale_mercator_to_roms_GulfOfGuinea_BRY.py
#  downscale_mercator_to_roms_GulfOfGuinea_CLM.py
#
# Check progress with:  squeue -u $USER   and   tail -f downscale.<jobid>.log

#SBATCH --partition=p_omg_1               # Ocean Modeling Group partition
#SBATCH --job-name=gog_downscale
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8                 # threads for numpy/xesmf
#SBATCH --mem=64000                       # MB
#SBATCH --time=12:00:00                   # HH:MM:SS
#SBATCH --requeue                         # back in the queue if preempted
#SBATCH --output=downscale.%j.log         # stdout and stderr together
#SBATCH --export=ALL

set -e                                    # stop if a step fails

umask 002   # new files/folders group-writable, so colleagues can update them

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

# Python environment: May have to change depending on your setup
# shellcheck disable=SC1091
source "${REPO}/bash_scripts/site_env.sh"
# shellcheck disable=SC1090
source "${CONDA_SH:-$HOME/miniforge3/etc/profile.d/conda.sh}"
conda activate "${CONDA_ENV:-guinea2}"
export OMP_NUM_THREADS=${SLURM_CPUS_PER_TASK}

echo "Repo: ${REPO}"
cd "${REPO}/python"                       # romsutil.py lives here

echo "=== INI  $(date)"
python -u downscale_mercator_to_roms_GulfOfGuinea_INI.py

echo "=== BRY  $(date)"
python -u downscale_mercator_to_roms_GulfOfGuinea_BRY.py

echo "=== CLM  $(date)"
python -u downscale_mercator_to_roms_GulfOfGuinea_CLM.py

echo "=== done $(date)"
