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
tmpdir='/projects/f_omg_1/moa/africa/data/temp/'

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
#ays=1
#in a real time system you don't want to type in individual dates manually so use this
tstart=date.today()-timedelta(days=5) #data
tend=date.today()+timedelta(days=7) #forecast


#use this when the user wants to specify a fixed date range manually, otherwise comment out
# tstart=datetime(2026, 2, 1)
# tend=datetime(2026,2,29)


# tend=tstart+timedelta(days=2)
#start=date.today()-timedelta(days=0)
#end=date.today()+timedelta(days=3)

days=pd.date_range(tstart,tend)

# END USER SETTINGS FOR DOWNLOAD ----------------------------------------

def main(argv):
    print('MAIN')
    for day in days:
        print(day)

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
        else:
            shutil.copyfile(tmpofilename,ofilename)
            

if __name__ == "__main__":

    
    print('RUNNING')
    main(sys.argv)
    for f in glob.glob(tmpdir+'*.nc'):
        os.remove(f)
    for f in glob.glob(tmpdir+'*.tmp'):
        os.remove(f)
