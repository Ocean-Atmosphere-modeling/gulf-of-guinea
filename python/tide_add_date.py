"""
Saves a new copy of a tidal forcing netcdf and adds a zero_phase_date variable

zero_phase_date overrides the TIDE_START value in a roms input file

tide_add_time

Created by Sean Devine 2026/11
"""

import os
import numpy as np
import netCDF4 as nc
from datetime import datetime
import shutil

from run_window import get_window, reference_time
tstart, _, _ = get_window()

#-------------------------------------------------------------------------------------------------------
# Set input tide netcdf
root_tide = '/projects/f_omg_1/moa/africa/data/tides/tid_tpxo_gog_4km_2026.nc'

# Set the desired time or use run_window.py for synchronization

start_time = tstart 
#tide_time = datetime(2026, 1, 1)

# Set the desired output location and name
fname = start_time.strftime('%Y%m%d')
outfile = f'/projects/f_omg_1/moa/africa/data/tides/tid_tpxo_gog_zp_{fname}.nc'

#-------------------------------------------------------------------------------------------------------

def tide_add_time(input_tide, tide_time, outdir):
    nhold = tide_time.strftime('%Y%m%d')
    if not outdir:
        outdir = f'./tid_tpxo_gog_zp_{nhold}.nc'
    shutil.copyfile(input_tide, outdir)
    with nc.Dataset(outfile, mode='r+') as data:
        zp_extant = any(term == 'zero_phase_date' for term in list(data.variables.keys()))

        if not zp_extant:
            zero_phase_date = data.createVariable('zero_phase_date', 'f8')
            zero_phase_date.long_name = 'tidal reference date for zero phase'
            zero_phase_date.units = 'days as %Y%m%d.%f'
            zero_phase_date.C_format = '%13.4f'
            zero_phase_date.FORTRAN_format = '(f13.4)'
            
            print('Creating variable zero_phase_date')
        
        else: 
            print('zero_phase_date extant, rewriting ZPD')

#        tide_format = tide_time.strftime(%Y%m%d.%f)
        tidedate = round(float(tide_time.strftime('%Y%m%d.%f')),4)
        zero_phase_date[:] = tidedate
#    os.chmod(outfile, 0o664)
    #sets file permissions to rw-rw-r--


if __name__ == '__main__':
    tide_add_time(root_tide, start_time, outfile)
