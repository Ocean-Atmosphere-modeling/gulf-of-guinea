#!/usr/bin/env python
#
import os,sys,fnmatch,glob
from shutil import copyfile
from datetime import datetime,timedelta,date
import subprocess,shutil,os,glob
import copernicusmarine as copernicus_marine
import pandas as pd

# USER SETTINGS FOR DOWNLOAD --------------------------------------------

# DIRECTORIES WHERE THE DOWNLOADED MERCATOR DATA IS HELD
outdir='/projects/f_omg_1/moa/africa/data/downloads/'
# Per-user temp folder: this script deletes every .nc in tmpdir when it
# finishes, so a shared folder would let two users delete each other's files
tmpdir=f'/projects/f_omg_1/moa/africa/data/temp_{os.environ.get("USER","user")}/'
os.makedirs(tmpdir, exist_ok=True)

# GULF OF GUINEA BOUNDING BOX -16.0000   13.5000  -11.0000    8.0000
latmin=-11.0
latmax=8.0
lonmin=-16.0
lonmax=13.5
zmin=-10.0;
zmax=6000.0

# PRIMITIVE VARIABLES FOR ROMS PHYSICS
variables=[['so'] ,['thetao'],['uo','vo'],['zos']]
tmpfiles=['TMP_so.nc','TMP_thetao.nc','TMP_uv.nc','TMP_zos.nc']

# CHOOSE THE APPROPRIATE DATASET
ids=['cmems_mod_glo_phy-so_anfc_0.083deg_P1D-m', 
     'cmems_mod_glo_phy-thetao_anfc_0.083deg_P1D-m', 
     'cmems_mod_glo_phy-cur_anfc_0.083deg_P1D-m', 
     'cmems_mod_glo_phy_anfc_0.083deg_P1D-m']

# SET THE TIME RANGE FOR DOWNLOAD

# Time window from the environment (see run_window.py):
#   forecast: NDAYS_BACK / NDAYS_FWD around today (default 3 back, 2 forward)
#   hindcast: START_DATE / END_DATE, e.g. START_DATE=2026-10-01 END_DATE=2026-11-01
from run_window import get_window
tstart, tend, mode = get_window()
print(f'{mode} window: {tstart} to {tend}')

days=pd.date_range(tstart,tend)

# Files for days from (today - REFRESH_DAYS) onward are downloaded again even
# if they exist: those are forecasts/recent analyses that Mercator updates
# every day. Older days are skipped if already downloaded.
refresh_from = date.today() - timedelta(days=int(os.environ.get('REFRESH_DAYS', 1)))

# END USER SETTINGS FOR DOWNLOAD ----------------------------------------

def main(argv):
    print('MAIN')
    for day in days:
        print(day)

        if (os.path.exists(day.strftime(outdir+'mercator_GulfOfGuinea_RT_%Y_%m_%d.nc'))
                and day.date() < refresh_from):
            print('  already downloaded, skipping')
            continue

        for f in glob.glob(tmpdir+'TMP*.nc'):
            os.remove(f)
            
        for ind,variable in enumerate(variables):
            print(tmpfiles[ind])
            print(ids[ind])
            day2=day+timedelta(days=0.5)
            
            print(variable)
            copernicus_marine.subset(
                dataset_id = ids[ind],
                variables = variable,
                minimum_longitude = lonmin,
                maximum_longitude = lonmax,
                minimum_latitude = latmin,
                maximum_latitude = latmax,
                minimum_depth = zmin,
                maximum_depth = zmax,
                start_datetime = day.strftime('%Y-%m-%d %H:%M:%S'),
                end_datetime = day2.strftime('%Y-%m-%d %H:%M:%S'),
                output_filename = tmpfiles[ind],
            #   force_download=True,
            #   overwrite_output_data =True,
            #    dataset_version="202406",
                output_directory = tmpdir,
                )
        
        ofilename = day.strftime(outdir+'mercator_GulfOfGuinea_RT_%Y_%m_%d.nc')
        tmpofilename = day.strftime(tmpdir+'mercator_GulfOfGuinea_RT_%Y_%m_%d.nc')
        print(ofilename)
        
        try:
            print('Copying: '+tmpdir+tmpfiles[0]+' to '+tmpofilename)
            shutil.copyfile(tmpdir+tmpfiles[0], tmpofilename)
    
            
            for tmpfile in tmpfiles[1:]:
                print('Adding: '+tmpdir+tmpfile+' to '+tmpofilename)
                subprocess.check_call(['ncks','-A',tmpdir+tmpfile,tmpofilename])
        except Exception as e:
                # Code to handle other exceptions (if any)
            print(f"An error occurred when combining files via ncks: {e}")
            
            if os.path.exists(tmpofilename):
                print(f'Deleting: {tmpofilename}')
                os.remove(tmpofilename)
        else:
            # Remove first: an existing file may belong to another user (not
            # writable by us), but the shared folder lets group members replace it
            if os.path.exists(ofilename):
                os.remove(ofilename)
            shutil.copyfile(tmpofilename,ofilename)
            os.chmod(ofilename, 0o664)   # group-writable for the other users
            

if __name__ == "__main__":

    
    print('RUNNING')
    main(sys.argv)
    for f in glob.glob(tmpdir+'*.nc'):
        os.remove(f)
    for f in glob.glob(tmpdir+'*.tmp'):
        os.remove(f)
