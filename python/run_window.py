"""
run_window.py

One shared definition of the model time window for the Gulf of Guinea
pre-processing scripts (Mercator download/INI/BRY/CLM, rivers, ROMS .in).

Set by environment variables, so a driver script can give every step the
same window:

  Forecast (rolling) mode - the default
      NDAYS_BACK   days of past data before today   (default 3)
      NDAYS_FWD    days of forecast after today      (default 2)
      -> window = today - NDAYS_BACK  ...  today + NDAYS_FWD

  Hindcast (fixed) mode - used if START_DATE is set
      START_DATE   first day, YYYY-MM-DD
      END_DATE     last day,  YYYY-MM-DD (the run ends at 00:00 on this day)

Examples
  NDAYS_BACK=3 NDAYS_FWD=2 python downscale_mercator_to_roms_GulfOfGuinea_BRY.py
  START_DATE=2026-10-01 END_DATE=2026-11-01 python downscale_mercator_to_roms_GulfOfGuinea_BRY.py
"""
import os
from datetime import date, datetime, timedelta

DEFAULT_BACK = 3
DEFAULT_FWD = 2


def get_window():
    """Return (start_date, end_date, mode) as datetime.date objects."""
    start = os.environ.get('START_DATE')
    if start:
        end = os.environ.get('END_DATE')
        if not end:
            raise SystemExit('END_DATE must be set when START_DATE is set')
        s = datetime.strptime(start, '%Y-%m-%d').date()
        e = datetime.strptime(end, '%Y-%m-%d').date()
        mode = 'hindcast'
    else:
        back = int(os.environ.get('NDAYS_BACK', DEFAULT_BACK))
        fwd = int(os.environ.get('NDAYS_FWD', DEFAULT_FWD))
        s = date.today() - timedelta(days=back)
        e = date.today() + timedelta(days=fwd)
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
          f'time reference {reference_time(s):%Y-%m-%d}')
