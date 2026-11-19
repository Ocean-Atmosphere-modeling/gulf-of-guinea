"""
site_paths.py

Every directory the Gulf of Guinea scripts read or write, derived from one
setting: DATA_ROOT in bash_scripts/site.conf (or the DATA_ROOT environment
variable, which wins). Moving to a new system means editing that one file.

Use it like:

    from site_paths import DOWNLOADS, BLK, GRID_FILE

Directory names keep their trailing slash, so `DOWNLOADS + 'file.nc'` works.
"""
import os
from pathlib import Path

from run_window import read_config

# The one file that defines machine-specific settings (override with SITE_CONF)
SITE_CONF = Path(os.environ.get(
    'SITE_CONF',
    Path(__file__).resolve().parent.parent / 'bash_scripts' / 'site.conf'))

_cfg = read_config(SITE_CONF, keys=None)


def setting(name, default=None):
    """One site setting: environment first, then site.conf. $HOME and ~ expand."""
    val = os.environ.get(name)
    if val in (None, ''):
        val = _cfg.get(name, default)
    if isinstance(val, str):
        val = os.path.expanduser(os.path.expandvars(val))
    return val


DATA_ROOT = setting('DATA_ROOT')
if not DATA_ROOT:
    raise SystemExit(
        f'DATA_ROOT is not set: edit {SITE_CONF} (or export DATA_ROOT)')
DATA_ROOT = DATA_ROOT.rstrip('/')

# Raw and intermediate data
DATA        = f'{DATA_ROOT}/data/'
DOWNLOADS   = f'{DATA}downloads/'      # Mercator and ECMWF files as downloaded
BLK         = f'{DATA}blk/'            # ROMS bulk-flux forcing
GLOFAS      = f'{DATA}glofas/'         # GloFAS river discharge
IMP_FILES   = f'{DATA}imp_files/'      # static inputs (grid, nudging, tides)

# Cached regridding weights (one folder per product, not ROMS inputs)
WEIGHTS_INI = f'{DATA}ini/'
WEIGHTS_BRY = f'{DATA}bry/'
WEIGHTS_CLM = f'{DATA}clm/'

# ROMS input files produced by the pre-processing steps
INP         = f'{DATA_ROOT}/inp/'
INP_INI     = f'{INP}ini/'
INP_BRY     = f'{INP}bry/'
INP_CLM     = f'{INP}clm/'
INP_RIV     = f'{INP}riv/'

# ROMS output, one folder per cycle, plus the preparation-job logs
OUT_FORECAST = f'{DATA_ROOT}/out/forecast/'
LOG_ROOT     = f'{OUT_FORECAST}logs/'

# The model grid
GRID_FILE = setting('GRID_FILE') or f'{IMP_FILES}grd_GulfOfGuinea_4km.nc'

# Appended to the per-cycle output folder name, so two people running the same
# start date do not write into the same folder. Empty means a bare date, which
# is what happened before this setting existed.
# An empty value normally means "not set" and falls back to the file, but here
# an explicitly exported empty string is a deliberate "no suffix", so check for
# the variable's presence rather than its truth.
if 'OUTPUT_SUFFIX' in os.environ:
    _suffix = os.path.expandvars(os.environ['OUTPUT_SUFFIX'])
else:
    _suffix = setting('OUTPUT_SUFFIX', '') or ''
OUTPUT_SUFFIX = _suffix.strip().replace('/', '')


def user_tmp(parent, prefix='tmp'):
    """Per-user scratch folder inside `parent`, so simultaneous runs by two
    people do not delete each other's temporary files. The caller makes it."""
    return f'{parent}{prefix}_{os.environ.get("USER", "user")}/'


if __name__ == '__main__':
    print(f'site config: {SITE_CONF}')
    print(f'  {"OUTPUT_SUFFIX":13s} {OUTPUT_SUFFIX!r}')
    for name in ('DATA_ROOT', 'DOWNLOADS', 'BLK', 'GLOFAS', 'IMP_FILES',
                 'WEIGHTS_INI', 'WEIGHTS_BRY', 'WEIGHTS_CLM', 'INP_INI',
                 'INP_BRY', 'INP_CLM', 'INP_RIV', 'OUT_FORECAST', 'LOG_ROOT',
                 'GRID_FILE'):
        print(f'  {name:13s} {globals()[name]}')
    print(f'  {"user_tmp":13s} {user_tmp(DOWNLOADS)}')
