#!/usr/bin/env python
"""
make_roms_in.py

Write the ROMS input file for one Gulf of Guinea run (a forecast cycle or a
hindcast) from the base file run/roms_gulfofguinea.in, filling in the
settings that change each cycle:

  TIME_REF, DSTART, NTIMES                  from the time window
  (FRCNAME follows ECMWF_MODEL/ECMWF_RESOL, so the .in points at the
   forcing for the grid you ran the frc step at; ifs/0p25 falls back to the
   older untagged name when no tagged file exists)
  ININAME, BRYNAME, CLMNAME (1 per day),    the input files made for this
  FRCNAME/NFFILES, SSFNAME                  window by the pre-processing scripts
  RSTNAME, HISNAME, QCKNAME, AVGNAME,       per-cycle output folder and names
  DIANAME

Everything else (grid, nudging, tides, physics, tiling, output frequency) is
taken unchanged from the base file, so edit the base file for those.

It also checks that every input file exists and covers the window, so a
missing or bad file is caught here and not 15 s into the ROMS job.

The time window comes from the environment like the other scripts
(NDAYS_BACK/NDAYS_FWD, or START_DATE/END_DATE; see run_window.py), or from
--start/--end.

Examples
  NDAYS_BACK=3 NDAYS_FWD=2 python make_roms_in.py
  python make_roms_in.py --start 2026-10-01 --end 2026-11-01
  -> run/roms_gulfofguinea_20261103.in   (named by the start date)
"""
import os
import re
import sys
import argparse
import glob
from datetime import date, datetime, timedelta

import numpy as np
import netCDF4 as nc
import cftime

HERE = os.path.dirname(os.path.abspath(__file__))

# The ECMWF model and grid the frc step used, so FRCNAME points at the
# matching forcing file (bash_scripts/window.conf, or ECMWF_MODEL/ECMWF_RESOL
# in the environment).
from run_window import setting
from site_paths import INP, BLK, OUT_FORECAST, OUTPUT_SUFFIX
ECMWF_MODEL = setting('ECMWF_MODEL', 'ifs')
ECMWF_RESOL = setting('ECMWF_RESOL', '0p25')

# USER SETTINGS -------------------------------------------------------------
base_in = os.path.join(HERE, '..', 'run', 'roms_gulfofguinea.in')
run_dir = os.path.join(HERE, '..', 'run')        # where the new .in is written

inp = INP
blk = BLK
out_root = OUT_FORECAST

def frc_name(S, E):
    """Forcing file for a window from S to E.

    convert_ecmwf_to_roms_frc_GulfOfGuinea.py tags the name with the model, the
    grid and both dates. Files written by earlier versions are missing one tag
    or the other, so try those names too before giving up.
    """
    tag = f'{ECMWF_MODEL.upper()}_{ECMWF_RESOL}'
    current = f'GulfOfGuinea_frc_{tag}_bulkflux_{S:%Y%m%d}_{E:%Y%m%d}.nc'
    older = [f'GulfOfGuinea_frc_{tag}_bulkflux_{S:%Y%m%d}.nc']
    # Untagged names may only be used for ifs at 0.25 deg: every untagged file
    # was written by the older code, which produced nothing else. Falling back
    # for another grid would quietly hand ROMS a 0.25 deg forcing.
    if (ECMWF_MODEL, ECMWF_RESOL) == ('ifs', '0p25'):
        older += [f'GulfOfGuinea_frc_IFS_bulkflux_{S:%Y%m%d}_{E:%Y%m%d}.nc',
                  f'GulfOfGuinea_frc_IFS_bulkflux_{S:%Y%m%d}.nc']
    if not os.path.exists(blk + current):
        for name in older:
            if os.path.exists(blk + name):
                print(f'  forcing: {current} not found, using older {name}')
                return name
    return current


# Input file names for a window starting on S (date) and ending on E
def input_files(S, E):
    days = [S + timedelta(days=k) for k in range((E - S).days + 1)]
    return {
        'ININAME': inp + f'ini/ini_gulfofguinea_Mercator_{S:%Y%m%d}.nc',
        'BRYNAME': inp + f'bry/bry_gulfofguinea_Mercator_{S:%Y%m%d}.nc',
        'CLMNAME': [inp + f'clm/clm_gulfofguinea_Mercator_{d:%Y_%m_%d}.nc' for d in days],
        'FRCNAME': blk + frc_name(S, E),
        'SSFNAME': inp + f'riv/riv_gulfofguinea_{S:%Y%m%d}_{E:%Y%m%d}_v2.nc',
    }

OUTPUT_KEYS = {'RSTNAME': 'rst', 'HISNAME': 'his', 'QCKNAME': 'qck',
               'AVGNAME': 'avg', 'DIANAME': 'dia'}

# One fixed model clock for every run (spin-up and all forecast cycles), so a
# cycle can start from a history snapshot written by an earlier run.
TIME_REF = date(2026, 1, 1)

# How a run starts (--start-mode, or START_MODE in the environment):
#   auto  hot start if an earlier run saved a snapshot at the start time,
#         otherwise cold start (default)
#   hot   hot start only; error if no snapshot is found
#   cold  cold start from the Mercator INI file
#
# Cold start: DSTART = run start, so RAMP_TIDES ramps the tides up from zero
#   (tanh: 76% after 1 day, 96% after 2, 99.5% after 3).
# Hot start:  DSTART = TIME_REF, months before the start, so the tides are at
#   full strength (the ramp only acts in the first days after DSTART). ROMS
#   numbers output files by time step counted from DSTART, so hot-start file
#   numbers are the day of the year, e.g. his_gog_20261116_0320.nc = Nov 16.
# END USER SETTINGS ---------------------------------------------------------


def find_entry(lines, key):
    """Index range [i0, i1) of an active 'KEY == value' entry, including
    continuation lines (ending in | or \\). Errors if not exactly one."""
    pat = re.compile(rf'^\s*{re.escape(key)}\s*==?(?!=)')
    pat2 = re.compile(rf'^\s*{re.escape(key)}\s*==')
    hits = [i for i, l in enumerate(lines) if pat.match(l) or pat2.match(l)]
    if len(hits) != 1:
        raise SystemExit(f'{key}: found {len(hits)} active entries in {base_in}, expected 1')
    i0 = i1 = hits[0]
    while lines[i1].split('!')[0].rstrip().endswith(('|', '\\')):
        i1 += 1
    return i0, i1 + 1


def set_entry(lines, key, value, comment=''):
    """Replace KEY's value (str, or list of file names for a | list)."""
    i0, i1 = find_entry(lines, key)
    m = re.match(rf'^(\s*{re.escape(key)}\s*)(==|=)', lines[i0])
    lead, op = m.group(1), m.group(2)
    if isinstance(value, list):
        pad = ' ' * (len(lead) + len(op) + 1)
        new = [f'{lead}{op} {value[0]}' + (' |' if len(value) > 1 else '')]
        new += [f'{pad}{v}' + (' |' if k < len(value) - 1 else '')
                for k, v in enumerate(value[1:], start=1)]
    else:
        new = [f'{lead}{op} {value}' + (f'      ! {comment}' if comment else '')]
    lines[i0:i1] = [l + '\n' for l in new]


def get_value(lines, key):
    i0, _ = find_entry(lines, key)
    return lines[i0].split('!')[0].split('=')[-1].strip()


# --- hot start --------------------------------------------------------------
def find_hot_start(S):
    """Newest history snapshot at exactly 00:00 on S, written by an earlier run
    on the fixed TIME_REF clock (runs made before the fixed clock, e.g. the
    early cold-start cycles, are not used). Returns the file path or None."""
    want = datetime(S.year, S.month, S.day)
    ref = f'seconds since {TIME_REF:%Y-%m-%d}'
    found = []
    for f in glob.glob(os.path.join(out_root, '*', 'his_*.nc')):
        run_start = os.path.basename(os.path.dirname(f))
        if run_start >= f'{S:%Y%m%d}':        # only runs that started before S
            continue
        try:
            with nc.Dataset(f) as d:
                v = d['ocean_time']
                if not v.units.startswith(ref) or v.shape[0] < 1:
                    continue
                t = cftime.num2date(v[:], v.units)
        except Exception:
            continue                          # incomplete or unreadable file
        for k, x in enumerate(t):
            if datetime(x.year, x.month, x.day, x.hour, x.minute) == want:
                found.append((run_start, f, k))
    if not found:
        return None
    found.sort()                              # newest run that reached S wins
    run_start, f, k = found[-1]
    if k != 0:                                # ROMS reads record 1 of ININAME
        print(f'  skipping {f}: snapshot at {S} is record {k + 1}, not 1')
        return None
    return f


# --- input checks ----------------------------------------------------------
def nc_times(fname, tvar):
    with nc.Dataset(fname) as d:
        v = d[tvar]
        t = np.ma.compressed(v[:])
        if t.size == 0:
            return []
        cal = getattr(v, 'calendar', 'standard')
        return [datetime(x.year, x.month, x.day, x.hour, x.minute)
                for x in cftime.num2date(t, v.units, calendar=cal)]


def check_inputs(files, S, E):
    t0, t1 = datetime(S.year, S.month, S.day), datetime(E.year, E.month, E.day)
    problems = []

    def need(fname, tvar, what):
        if not os.path.exists(fname):
            problems.append(f'MISSING   {what}: {fname}')
            return None
        try:
            t = nc_times(fname, tvar)
        except Exception as e:
            problems.append(f'UNREADABLE {what}: {fname} ({e})')
            return None
        if not t:
            problems.append(f'EMPTY     {what} (no time records): {fname}')
            return None
        return t

    t = need(files['ININAME'], 'ocean_time', 'INI')
    if t and t[0] != t0:
        problems.append(f'BAD TIME  INI is {t[0]}, run starts {t0}')
    for key, tvar, what in [('BRYNAME', 'bry_time', 'BRY'), ('FRCNAME', 'time', 'FRC'),
                            ('SSFNAME', 'river_time', 'rivers')]:
        t = need(files[key], tvar, what)
        if t and (min(t) > t0 or max(t) < t1):
            problems.append(f'COVERAGE  {what} spans {min(t)} to {max(t)}, '
                            f'run needs {t0} to {t1}: {files[key]}')
    for f in files['CLMNAME']:
        t = need(f, 'ocean_time', 'CLM')
        if t and len(t) != 1:
            problems.append(f'BAD CLM   {len(t)} records (expected 1): {f}')
    return problems


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--start', help='first day YYYY-MM-DD (default: from environment)')
    p.add_argument('--end', help='last day YYYY-MM-DD; the run ends at 00:00 on it')
    p.add_argument('--base', default=base_in, help='base ROMS .in file')
    p.add_argument('--out', help='output .in file (default run/roms_gulfofguinea_<start>.in)')
    p.add_argument('--no-check', action='store_true', help='skip the input file checks')
    p.add_argument('--start-mode', choices=['auto', 'hot', 'cold'],
                   default=os.environ.get('START_MODE', 'auto'),
                   help='auto (default): hot start if an earlier snapshot exists; '
                        'hot: require one; cold: start from the Mercator INI')
    a = p.parse_args()

    if a.start and a.end:
        S = datetime.strptime(a.start, '%Y-%m-%d').date()
        E = datetime.strptime(a.end, '%Y-%m-%d').date()
        mode = 'given'
    elif a.start or a.end:
        p.error('give both --start and --end')
    else:
        sys.path.insert(0, HERE)
        from run_window import get_window
        S, E, mode = get_window()
    ndays = (E - S).days
    if ndays < 1:
        raise SystemExit(f'Window {S} to {E} is shorter than one day')

    lines = open(a.base).readlines()
    dt = float(get_value(lines, 'DT').replace('d', 'e').replace('D', 'e'))
    ntimes = int(round(ndays * 86400 / dt))

    files = input_files(S, E)
    # OUTPUT_SUFFIX (bash_scripts/site.conf) keeps two people who run the same
    # start date from writing into the same folder; the file names inside are
    # unchanged, so anything that reads them still works.
    outdir = os.path.join(out_root, f'{S:%Y%m%d}{OUTPUT_SUFFIX}')
    tag = f'gog_{S:%Y%m%d}'

    # Hot or cold start
    hot = None if a.start_mode == 'cold' else find_hot_start(S)
    if a.start_mode == 'hot' and hot is None:
        raise SystemExit(f'--start-mode hot: no earlier snapshot at {S} 00:00 in {out_root}')
    if hot:
        files['ININAME'] = hot
        dstart = 0.0                              # = TIME_REF: no tide ramp
        how = f'HOT start from {hot}'
    else:
        dstart = float((S - TIME_REF).days)       # = run start: tides ramp up
        how = 'COLD start from the Mercator INI (tides ramped up over ~3 days)'
        if a.start_mode == 'auto':
            how += f'; no earlier snapshot at {S} 00:00 was found'

    # Time: one fixed clock (TIME_REF) for all runs
    set_entry(lines, 'TIME_REF', f'{TIME_REF:%Y%m%d}.0d0', 'yyyymmdd.dd (fixed for all runs)')
    set_entry(lines, 'DSTART', f'{dstart:.1f}d0',
              'days since TIME_REF; = run start for a cold start (ramps tides)')
    set_entry(lines, 'NTIMES', str(ntimes), f'{ndays} days: {S} 00:00 to {E} 00:00')
    # Inputs
    set_entry(lines, 'ININAME', files['ININAME'])
    set_entry(lines, 'BRYNAME', files['BRYNAME'])
    set_entry(lines, 'NCLMFILES', '1', 'one climatology set, split into daily files')
    set_entry(lines, 'CLMNAME', files['CLMNAME'])
    set_entry(lines, 'NFFILES', '1', 'number of unique forcing files')
    set_entry(lines, 'FRCNAME', files['FRCNAME'])
    set_entry(lines, 'SSFNAME', files['SSFNAME'])
    # Outputs
    for key, pre in OUTPUT_KEYS.items():
        set_entry(lines, key, os.path.join(outdir, f'{pre}_{tag}.nc'))

    fname = a.out or os.path.join(run_dir, f'roms_gulfofguinea_{S:%Y%m%d}.in')
    with open(fname, 'w') as f:
        f.writelines(lines)
    os.makedirs(outdir, exist_ok=True)

    print(f'{mode} window: {S} to {E} ({ndays} days, NTIMES={ntimes}, DT={dt:g} s)')
    print(how)
    print(f'Wrote {os.path.normpath(fname)}')
    print(f'Output folder {outdir}')

    if a.no_check:
        return
    problems = check_inputs(files, S, E)
    if problems:
        print('\nINPUT PROBLEMS - ROMS would fail:')
        for m in problems:
            print('  ' + m)
        sys.exit(1)
    print(f'All inputs found and cover {S} to {E} '
          f'(INI, BRY, {len(files["CLMNAME"])} CLM, FRC, rivers)')


if __name__ == '__main__':
    main()
