#!/bin/bash

## Commands commented out with double ##

#SBATCH --kill-on-invalid-dep=yes         # Cancel job on failed dependency
#SBATCH --partition=p_omg_1               # Partition (job queue) for Ocean Modeling Group
#SBATCH --requeue                         # Return job to the queue if preempted
#SBATCH --job-name=gog_becca           # Assign a short name to your job
#SBATCH --nodes=1                         # Number of nodes you require

#SBATCH --ntasks=64                      # Total number of tasks to launch (like -np to mpirun)
#SBATCH --ntasks-per-node=64              # Number of tasks to launch on each node

#SBATCH --cpus-per-task=1                 # Cores per task (>1 if multithread tasks)
#SBATCH --mem=180000                      # Real memory (RAM) required (MB) per node
#SBATCH --time=3-00:00                   # Total run time limit (DD-HH:MM)
#SBATCH --output=out.slurm.%N.%j          # STDOUT output file
#SBATCH --error=err.slurm.%N.%j           # STDERR output file (optional but recommended)
#SBATCH --export=ALL                      # Export you current env to the job env

#SBATCH --mail-type=ALL
#SBATCH --mail-user=bhorwitz@marine.rutgers.edu

## It is important to have --mpi=pmi2 here or ROMS will not run
# ROMS input file: first argument, e.g. "sbatch job_gog.sh roms_gulfofguinea_20261103.in"
# (default roms_gulfofguinea.in). Run from the run/ directory.
umask 002   # new files/folders group-writable, so Becca and Sean can update them (after all #SBATCH lines)
INFILE=${1:-roms_gulfofguinea.in}

# Repo root. Slurm runs a spool copy of this script, so BASH_SOURCE is not
# reliable: try every sensible candidate and keep the first that is a checkout.
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

# ROMS_EXE comes from bash_scripts/site.conf (default ./romsM), so nobody has
# to put their own build path into this shared script.
if REPO=$(find_repo_root); then
    # shellcheck disable=SC1091
    source "${REPO}/bash_scripts/site_env.sh"
fi
ROMS_EXE="${ROMS_EXE:-./romsM}"

if [[ ! -x "$ROMS_EXE" ]]; then
    echo "ERROR: ROMS executable not found or not executable: $ROMS_EXE" >&2
    echo "       Compile it with run/build_roms.sh, or set ROMS_EXE in" >&2
    echo "       bash_scripts/site.conf to a build you already have." >&2
    exit 1
fi

echo "Running ROMS with ${INFILE} on $(date)"
echo "  executable: ${ROMS_EXE}"
srun --mpi=pmi2 "${ROMS_EXE}" ${INFILE}
