"""
Creates a tidal harmonic netcdf with unified time.
 
Once created, file will remain functional so long as TIME_REF matches
the given reference time variable. 
 
A separate script is used for setting zero_phase_date, which overwrites
TIDE_START for ease of use in active forecasting.
"""


import os,sys
import xarray as xr
from roms_tools import TidalForcing
from roms_tools import Grid
from datetime import datetime

from run_window import reference_time, get_window
tstart, _, _ = get_window()

# File time reference: Jan 1 of the start year (same as BRY, CLM, rivers, forcing)
# Tidal reference date MUST match TIME_REF in roms input file

reftime = reference_time(tstart)
#reftime = datetime(2026, 1, 1)

gfile='/projects/f_omg_1/moa/africa/data/imp_files/grd_GulfOfGuinea_4km.nc'
outdir='/projects/f_omg_1/moa/africa/data/tides/'
outfile=f'tid_tpxo_gog_4km_{reftime.year}.nc'

# This generates an intermediate ROMS grid file for compatibility with ROMS-TOOLS 
prepared_path = "/projects/f_omg_1/moa/africa/data/tides/temp/grid_for_romstools.nc"
with xr.open_dataset(gfile) as source:
    prepared = source.load()
    prepared.attrs.pop("title", None)
    prepared.to_netcdf(prepared_path)

grid = Grid(filename=prepared_path)

tpxo_path = "/home/std78/roms/tides/DATA/" #Path to the TPXO10 data, stored on home cache to save shared memory 
tpxo_dict = {
    "grid": tpxo_path + "grid_tpxo10v2.nc",
    "h": tpxo_path + "h_tpxo10.v2.nc",
    "u": tpxo_path + "u_tpxo10.v2.nc",
}


# Create A tidal forcing object using the TPXO data. 
tidal_forcing = TidalForcing(
    grid=grid,
    source={"name": "TPXO", "path": tpxo_dict},
    ntides=15,  # Number of constituents to consider <= 15. Default is 10.
    model_reference_date=reftime,  # Model reference date. Default is January 1, 2000.
    use_dask=True,
)

# Save the object's data to a NETCF file.  
tidal_forcing.save(outdir+outfile)
#os.chmod(outdir+outfile, 0o664)

