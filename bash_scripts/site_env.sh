# site_env.sh - load the machine-specific settings for the shell drivers.
#
# Sourced by the drivers; not meant to be run on its own. It reads
# bash_scripts/site.conf (the only file you edit on a new system) and lets the
# environment win over it, the same precedence python/site_paths.py uses:
#
#   environment  >  site.conf
#
# After sourcing, these are set and exported:
#   DATA_ROOT CONDA_ENV CONDA_SH SLURM_PARTITION SLURM_ACCOUNT GRID_FILE
# and LOG_ROOT is derived from DATA_ROOT.

_site_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SITE_CONF="${SITE_CONF:-${_site_dir}/site.conf}"
[[ -f "$SITE_CONF" ]] || { echo "ERROR: site config not found: $SITE_CONF" >&2; exit 1; }

_SITE_KEYS=(DATA_ROOT GRID_FILE CONDA_ENV CONDA_SH SLURM_PARTITION SLURM_ACCOUNT ROMS_EXE OUTPUT_SUFFIX)

# Remember what the environment already said, so the file cannot overwrite it
for _k in "${_SITE_KEYS[@]}"; do
    printf -v "_site_env_${_k}" '%s' "${!_k:-}"
done

# shellcheck disable=SC1090
source "$SITE_CONF"

for _k in "${_SITE_KEYS[@]}"; do
    _v="_site_env_${_k}"
    [[ -n "${!_v:-}" ]] && printf -v "${_k}" '%s' "${!_v}"
done
unset _k _v

: "${DATA_ROOT:?DATA_ROOT not set in ${SITE_CONF}}"
DATA_ROOT="${DATA_ROOT%/}"
CONDA_ENV="${CONDA_ENV:-}"
CONDA_SH="${CONDA_SH:-$HOME/miniforge3/etc/profile.d/conda.sh}"
SLURM_PARTITION="${SLURM_PARTITION:-}"
SLURM_ACCOUNT="${SLURM_ACCOUNT:-}"
GRID_FILE="${GRID_FILE:-${DATA_ROOT}/data/imp_files/grd_GulfOfGuinea_4km.nc}"
ROMS_EXE="${ROMS_EXE:-./romsM}"
LOG_ROOT="${DATA_ROOT}/out/forecast/logs"
export DATA_ROOT GRID_FILE CONDA_ENV CONDA_SH SLURM_PARTITION SLURM_ACCOUNT ROMS_EXE

site_describe() {
    echo "data root ${DATA_ROOT} (from ${SITE_CONF})"
}
