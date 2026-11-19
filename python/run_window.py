"""
run_window.py

One shared definition of the model time window for the Gulf of Guinea
pre-processing scripts (Mercator download/INI/BRY/CLM, ECMWF download/FRC,
rivers, ROMS .in).

The window is defined ONCE, in bash_scripts/window.conf:

      NDAYS_BACK   days of past data before today
      NDAYS_FWD    days of forecast after today
      START_DATE   first day, YYYY-MM-DD   (hindcast; overrides NDAYS_*)
      END_DATE     last day,  YYYY-MM-DD   (the run ends at 00:00 on this day)

The driver scripts source that file and export these as environment
variables; this module reads the environment first and falls back to the
same file, so running a script by hand gives the same window as a full cycle.

  Forecast (rolling) mode - the default
      window = today - NDAYS_BACK  ...  today + NDAYS_FWD

  Hindcast (fixed) mode - used if START_DATE is set

Examples
  python downscale_mercator_to_roms_GulfOfGuinea_BRY.py                # window.conf
  NDAYS_BACK=3 NDAYS_FWD=2 python downscale_mercator_to_roms_GulfOfGuinea_BRY.py
  START_DATE=2026-10-01 END_DATE=2026-11-01 python downscale_mercator_to_roms_GulfOfGuinea_BRY.py
  python run_window.py                                                 # print the window
"""
import os
from datetime import date, datetime, timedelta
from pathlib import Path

# The one file that defines the window (override with WINDOW_CONF)
CONFIG_PATH = Path(os.environ.get(
    'WINDOW_CONF',
    Path(__file__).resolve().parent.parent / 'bash_scripts' / 'window.conf'))

_CONFIG_KEYS = ('NDAYS_BACK', 'NDAYS_FWD', 'START_DATE', 'END_DATE',
                'MAX_DAYS_FWD_MET', 'ECMWF_MODEL', 'ECMWF_RESOL')


def read_config(path=None, keys=_CONFIG_KEYS):
    """Read KEY=value lines from a config file. Returns a dict of strings.

    `keys` limits which names are kept; pass None to keep every key (used by
    site_paths.py for bash_scripts/site.conf).
    """
    path = Path(path) if path else CONFIG_PATH
    values = {}
    if not path.is_file():
        return values
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, _, val = line.partition('=')
        key = key.strip()
        if keys is not None and key not in keys:
            continue
        val = val.split('#')[0].strip().strip('"').strip("'")
        if val:
            values[key] = val
    return values


def setting(name, default=None):
    """One window setting: environment first, then window.conf."""
    val = os.environ.get(name)
    if val not in (None, ''):
        return val
    return read_config().get(name, default)


def get_window():
    """Return (start_date, end_date, mode) as datetime.date objects."""
    cfg = read_config()

    def _get(name):
        val = os.environ.get(name)
        if val not in (None, ''):
            return val
        return cfg.get(name)

    # An explicit NDAYS_* in the environment (a driver's -b/-f) means a rolling
    # window, even when window.conf also holds fixed dates.
    env_ndays = any(os.environ.get(k) not in (None, '')
                    for k in ('NDAYS_BACK', 'NDAYS_FWD'))
    start = None if env_ndays else _get('START_DATE')

    if start:
        end = _get('END_DATE')
        if not end:
            raise SystemExit('END_DATE must be set when START_DATE is set '
                             f'(environment or {CONFIG_PATH})')
        s = datetime.strptime(start, '%Y-%m-%d').date()
        e = datetime.strptime(end, '%Y-%m-%d').date()
        mode = 'hindcast'
    else:
        back, fwd = _get('NDAYS_BACK'), _get('NDAYS_FWD')
        if back is None or fwd is None:
            raise SystemExit(
                'No time window: set NDAYS_BACK and NDAYS_FWD (or START_DATE '
                f'and END_DATE) in {CONFIG_PATH}, or in the environment')
        s = date.today() - timedelta(days=int(back))
        e = date.today() + timedelta(days=int(fwd))
        mode = 'forecast'
    if e < s:
        raise SystemExit(f'Time window ends ({e}) before it starts ({s})')
    return s, e, mode


def reference_time(start):
    """ROMS file time reference: Jan 1 of the start year (as in all input files)."""
    return datetime(start.year, 1, 1)


if __name__ == '__main__':
    s, e, mode = get_window()
    print(f'{mode} window: {s} to {e} ({(e - s).days} days), '
          f'time reference {reference_time(s):%Y-%m-%d} '
          f'[config: {CONFIG_PATH}]')
