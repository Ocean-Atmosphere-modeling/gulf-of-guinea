"""
DOWNSCALE_MERCATOR_TO ROM_INI.py

Adapted from DOWNSCALE_ROMS_OUTPUT.py. Generate and Initial conditions file 
for a ROMS gird from Mercator. 
Created by Elias Hunter, hunter@marine.rutgers.edu, 12/19/2023 
"""
import os,glob
import numpy as np
import xroms
import xarray as xr
import pandas as pd
import xesmf as xe
import cartopy 
import matplotlib.pyplot as plt
import cartopy.feature as cfeature
import datetime,time
from datetime import timedelta,date
import romsutil as rutil
from  scipy.interpolate import interp1d
import netCDF4 as nc
import psutil

import warnings
warnings.filterwarnings("ignore")
# Set relevant inout parameters

proj = cartopy.crs.Mercator(central_longitude=-74)
pc = cartopy.crs.PlateCarree()

# 
#atmin=-3.0
#atmax=53.0
#onmin=-100.0
#onmax=-38.0

# disabling old code ----------------------------
# Set time
#tart_date = datetime.datetime(2024, 5, 7) 

#day=1
#ate_times = [start_date  + timedelta(days=i) for i in range(nday)] 
#eftime=datetime.datetime(2024,1,1)
#units=reftime.strftime('days since %Y-%m-%d')
#time=np.datetime64(reftime.date())

# Encode start date in the output INIFILE name
#nifile=start_date.strftime('ini_gulfofguinea_Mercator_%Y_%m_%d.nc')
#rint(inifile)

# Mercator donor input files
#atadir='/Users/wilkin/Dropbox/_roms-db/coessing/mercator/downloads/'
#egrid_coef_file='regrid_mercator_ini.nc'

# New time keeping copied from BRY script -------

#Set time

reftime=datetime.datetime(2026,1,1)
tunits=reftime.strftime('days since %Y-%m-%d')
rtime=np.datetime64(reftime.date())

# number of days to process - creates a new file for each day
#Set time window for the run
ndays_back = 5   # days of past data (real-time archive)
ndays_fwd  = 7   # days of forecast
 
start_date = date.today() - timedelta(days=ndays_back) #data
tend       = date.today() + timedelta(days=ndays_fwd)  #forecast
 
sdate      = start_date.strftime('%Y%m%d')
date_times = pd.date_range(start_date,tend)   # inclusive of both ends
#Donor grid Info

#Donor inputfiles
datadir='/projects/f_omg_1/moa/africa/data/downloads/'

# Output directory (boundary file and regridding weights are written here)
outdir='/projects/f_omg_1/moa/africa/data/clm/'   # <-- set to your path
os.makedirs(outdir, exist_ok=True)

regrid_coef_file=os.path.join(outdir,'regrid_mercator_clm.nc')

# Receiver Output file << this is now set inside the day loop
#lmfile=f'clm_gulfofguinea_Mercator_{sdate}.nc'

# Output/receiver ROMS Grid 

# roms gridfile 
L1grdfile='/projects/f_omg_1/moa/africa/data/imp_files/grd_GulfOfGuinea_4km.nc'

# roms s-coordinate parameters
L1theta_s=7.0
L1theta_b=2.0
L1Tcline=250.0
L1N=50
L1Vtransform  =2        #vertical transformation equation
L1Vstretching =4        #vertical stretching function
L1hc=250
(s_w_L1,C_w_L1)=rutil.stretching(L1Vstretching,L1theta_s,L1theta_b,L1hc,L1N,1)
(s_r_L1,C_r_L1)=rutil.stretching(L1Vstretching,L1theta_s,L1theta_b,L1hc,L1N,0)

# Output file flags, if True create file
INIflag=True
BRYflag=False



############################################################################
#Main Program
############################################################################

def main():
    ########################################################################
    print('Initializing grids and regridder')
    ########################################################################
    
 # Fail early with a clear message if any daily file (past or forecast) is missing
    filelist=[day.strftime(datadir+'mercator_GulfOfGuinea_RT_%Y_%m_%d.nc') for day in date_times]
    missing=[f for f in filelist if not os.path.exists(f)]
    if missing:
        raise FileNotFoundError(f'Missing Mercator files: {missing}')



    #Getting the mercator grid information
    day=date_times[0]
    #filename = day.strftime(datadir+'mercator_GulfOfGuinea_RA_%Y_%m_%d.nc')
    mfilename = day.strftime(datadir+'mercator_GulfOfGuinea_RT_%Y_%m_%d.nc')
    dsmgrd=xr.open_dataset(mfilename)
    mlat=dsmgrd['latitude']
    mlon=dsmgrd['longitude']
    mdepth=dsmgrd['depth']
    
    
    
    for day in date_times:
        
        print(' ')
        #filename = day.strftime(datadir+'mercator_GulfOfGuinea_RA_%Y_%m_%d.nc')
        mfilename = day.strftime(datadir+'mercator_GulfOfGuinea_RT_%Y_%m_%d.nc')
        print('Reading input data from ...')
        print(mfilename)
        
        cfgrd=xroms.open_netcdf(L1grdfile)
        cfgrd.attrs['sc_r']=L1N
        cfgrd.attrs['sc_w']=L1N+1
        
        dsmerc=xr.open_dataset(mfilename)

    ########################################################################
    #Process donwscaling files
    ########################################################################
        if INIflag:
            start_time=time.time()

            # inifile=day.strftime('clm_gulfofguinea_Mercator_%Y_%m_%d.nc')
            inifile=os.path.join(outdir,day.strftime('clm_gulfofguinea_Mercator_%Y_%m_%d.nc'))
            print(' Output will be to inifile')
            print(' '+inifile)

            downscale_init_file(cfgrd,dsmerc,inifile)
            end_time=time.time()
            elapsed_time = end_time - start_time
            print(f" Initilization file processing time: {elapsed_time} seconds")


def memory_usage():
    process = psutil.Process(os.getpid())
    mem_info = process.memory_info()
    return mem_info.rss / 1024 ** 2  # Memory usage in MB


        
        
def rechunk_eta_xi(ds):
    ds=ds.unify_chunks()   
    ds = ds.chunk({'xi_rho': ds.sizes['xi_rho']})
    ds = ds.chunk({'eta_rho': ds.sizes['eta_rho']})
    ds = ds.chunk({'eta_v': ds.sizes['eta_v']})
    ds = ds.chunk({'xi_u': ds.sizes['xi_u']})
    return ds

def dataset_get_Z(dataout,varnew):



    varnew['zeta']=dataout['zos']
    xromsds_z=varnew.zeta.to_dataset()
    xromsds_z['h']=varnew['h']
    xromsds_z['xi_u']=dataout['xi_u']
    xromsds_z['eta_v']=dataout['eta_v']
        
    xromsds_z['s_w']=('s_w',s_w_L1)
    xromsds_z['Cs_w']=('s_w',C_w_L1)
    xromsds_z['s_rho']=('s_rho',s_r_L1)
    xromsds_z['Cs_r']=('s_rho',C_r_L1)
    xromsds_z.attrs['hc']=L1hc
    xromsds_z['pm']=varnew['pm']
    xromsds_z['pn']=varnew['pn']
    
    (xromsds_z,gridhisL1_z)=xroms.roms_dataset(xromsds_z,Vtransform=L1Vtransform)
    
    

    return xromsds_z       


        
def downscale_init_file(cfgrd,dsmerc,inifile):

    tmp=dsmerc
    mlat=dsmerc['latitude']
    mlon=dsmerc['longitude']
    varnew =cfgrd
    varnew=varnew.rename({'lat_rho':'lat'})
    varnew=varnew.rename({'lon_rho':'lon'})
    
    start_time=time.time()

    dsmerc['zos']= dsmerc['zos'].interpolate_na(dim="longitude", method="nearest",limit=None,fill_value="extrapolate").interpolate_na(dim="latitude", method="nearest",limit=None,fill_value="extrapolate")
    dsmerc['uo']= dsmerc['uo'].interpolate_na(dim="longitude", method="nearest",limit=None,fill_value="extrapolate").interpolate_na(dim="latitude", method="nearest",limit=None,fill_value="extrapolate")
    dsmerc['vo']= dsmerc['vo'].interpolate_na(dim="longitude", method="nearest",limit=None,fill_value="extrapolate").interpolate_na(dim="latitude", method="nearest",limit=None,fill_value="extrapolate")
    dsmerc['so']= dsmerc['so'].interpolate_na(dim="longitude", method="nearest",limit=None,fill_value="extrapolate").interpolate_na(dim="latitude", method="nearest",limit=None,fill_value="extrapolate")
    dsmerc['thetao']= dsmerc['thetao'].interpolate_na(dim="longitude", method="nearest",limit=None,fill_value="extrapolate").interpolate_na(dim="latitude", method="nearest",limit=None,fill_value="extrapolate")
  #  dsmerc['vbar']= dsmerc['vbar'].interpolate_na(dim="longitude", method="nearest",limit=None,fill_value="extrapolate").interpolate_na(dim="latitude", method="nearest",limit=None,fill_value="extrapolate")

    end_time=time.time()
    elapsed_time = end_time - start_time
    print(f' FILL time: {elapsed_time}')
#    varnew=varnew.rename({'mask_rho':'mask'})
    start_time=time.time()
    
    if os.path.exists(regrid_coef_file):
        print(' Re-using weights')
        regridder = xe.Regridder( tmp,varnew, "bilinear",extrap_method="nearest_s2d",filename=regrid_coef_file,reuse_weights=True)  
    else:
        print('Generating weights')
        regridder = xe.Regridder( tmp,varnew, "bilinear",extrap_method="nearest_s2d")
        regridder.to_netcdf(regrid_coef_file)
            

    
    end_time=time.time()
    elapsed_time = end_time - start_time
    print(f' REGRIDDER time: {elapsed_time}')
    
    rutil.create_init_file(inifile,cfgrd,tunits)

    
    print(' RUNNING horizontal regridding')
 
    dataout = regridder(dsmerc,keep_attrs=True)
 
    dataout['xi_u']=varnew['xi_u']
    dataout['eta_v']=varnew['eta_v']
    dataout = dataout.rename({"time": "ocean_time"})
    print(' Preparing for vertical interpolation')
   

    dataout=rechunk_eta_xi(dataout)    
    varnew=rechunk_eta_xi(varnew)
    dataout_z=dataset_get_Z(dataout,varnew)
    
    dim_dict=dataout_z.dims
    
    temp = np.empty((L1N,dim_dict['eta_rho'],dim_dict['xi_rho']))
    temp[:]=0.0
    salt = np.empty((L1N,dim_dict['eta_rho'],dim_dict['xi_rho']))
    salt[:]=0.0
    u_east = np.empty((L1N,dim_dict['eta_rho'],dim_dict['xi_rho']))
    u_east[:]=0.0
    v_north = np.empty((L1N,dim_dict['eta_rho'],dim_dict['xi_rho']))
    v_north[:]=0.0
    
    
    
    print(' Running vertical interpolation, this may take a few minutes')
    
    mask=cfgrd.mask_rho.values
    tmpz=dataout_z.z_rho.values
    tmpz2=dataout['depth']
    temp_I=dataout.thetao.values
    salt_I=dataout.so.values
    u_east_I=dataout.uo.values
    v_north_I=dataout.vo.values
    
    
    start_time=time.time()


    for eta in range(0,dim_dict['eta_rho']):
        for xi in range(0,dim_dict['xi_rho']):
            maskflag=mask[eta,xi]
            if maskflag==0.0:
                continue
            

        #    print('----------------------')
                   
            all_nan = np.all(np.isnan(temp_I[0,:,eta,xi]))
            if ~all_nan:
              #  print('TEMP NAN')
                
                z=-tmpz2.values     
                data=temp_I[0,:,eta,xi]
                Igood=np.where(~np.isnan(data))
                ifun=interp1d(z[Igood],data[Igood],kind='linear',bounds_error=False,fill_value=(data[Igood][-1],data[Igood][0]))
                ntmp=ifun(tmpz[0,:,eta,xi])
                temp[:,eta,xi]=ntmp
                
                
                
            all_nan = np.all(np.isnan(salt_I[0,:,eta,xi]))
            if ~all_nan:
            #    print('Salt NAN')
                z=-tmpz2.values
                data=salt_I[0,:,eta,xi]
                Igood=np.where(~np.isnan(data))
                ifun=interp1d(z[Igood],data[Igood],kind='linear',bounds_error=False,fill_value=(data[Igood][-1],data[Igood][0]))
                ntmp=ifun(tmpz[0,:,eta,xi])
                salt[:,eta,xi]=ntmp
                

            
            all_nan = np.all(np.isnan(u_east_I[0,:,eta,xi]))
            if ~all_nan:
            #    print('U NAN')
                z=-tmpz2.values
                data=u_east_I[0,:,eta,xi]
                Igood=np.where(~np.isnan(data))
                ifun=interp1d(z[Igood],data[Igood],kind='linear',bounds_error=False,fill_value=(data[Igood][-1],data[Igood][0]))
                ntmp=ifun(tmpz[0,:,eta,xi])
                u_east[:,eta,xi]=ntmp
            
            all_nan = np.all(np.isnan(v_north_I[0,:,eta,xi]))
            if ~all_nan:
               # print('V NAN')
                z=-tmpz2.values
                data=v_north_I[0,:,eta,xi]
                Igood=np.where(~np.isnan(data))
                ifun=interp1d(z[Igood],data[Igood],kind='linear',bounds_error=False,fill_value=(data[Igood][-1],data[Igood][0]))
                ntmp=ifun(tmpz[0,:,eta,xi])
                v_north[:,eta,xi]=ntmp        


            
    end_time=time.time()
    elapsed_time = end_time - start_time
    print(f" processing time: {elapsed_time} seconds") 
    eta_rho=dataout['eta_rho'];
    xi_rho=dataout['xi_rho'];


                
            
    # for eta in range(0,dim_dict['eta_rho']):

    #     for xi in range(0,dim_dict['xi_rho']):
    #         maskflag=mask[eta,xi]
    #         if maskflag==0.0:
    #             continue
    #        # print('--------')
            
    #         all_nan = np.all(np.isnan(temp[:,eta,xi]))
    #         if all_nan:
              
    #             tmp=np.squeeze(temp[0,:,:])
    #             real_value_indices = np.argwhere(~np.isnan(tmp))
    #             distances = np.sqrt((real_value_indices[:, 0] - eta)**2 + 
    #                 (real_value_indices[:, 1] - xi)**2)
    #             cI = real_value_indices[np.argmin(distances)]
    #             temp[:,eta,xi]=temp[:,cI[0],cI[1]]
                
    #         #    print([cI[0],cI[1]])
                
    #         all_nan = np.all(np.isnan(salt[:,eta,xi]))
    #         if all_nan:
              
    #             tmp=np.squeeze(salt[0,:,:])
    #             real_value_indices = np.argwhere(~np.isnan(tmp))
    #             distances = np.sqrt((real_value_indices[:, 0] - eta)**2 + 
    #                 (real_value_indices[:, 1] - xi)**2)
    #             cI = real_value_indices[np.argmin(distances)]
    #             salt[:,eta,xi]=salt[:,cI[0],cI[1]]
    #         #    print([cI[0],cI[1]])
              
    #         all_nan = np.all(np.isnan(u_east[:,eta,xi]))
    #         if all_nan:
              
    #             tmp=np.squeeze(u_east[0,:,:])
    #             real_value_indices = np.argwhere(~np.isnan(tmp))
    #             distances = np.sqrt((real_value_indices[:, 0] - eta)**2 + 
    #                 (real_value_indices[:, 1] - xi)**2)
    #             cI = real_value_indices[np.argmin(distances)]
    #             u_east[:,eta,xi]=u_east[:,cI[0],cI[1]]
    #             print([cI[0],cI[1]])
            
                
    #         all_nan = np.all(np.isnan(v_north[:,eta,xi]))
    #         if all_nan:
              
    #             tmp=np.squeeze(v_north[0,:,:])
    #             real_value_indices = np.argwhere(~np.isnan(tmp))
    #             distances = np.sqrt((real_value_indices[:, 0] - eta)**2 + 
    #                 (real_value_indices[:, 1] - xi)**2)
    #             cI = real_value_indices[np.argmin(distances)]
    #             v_north[:,eta,xi]=v_north[:,cI[0],cI[1]]
    #             print([cI[0],cI[1]])
         
        
            
    end_time=time.time()
    elapsed_time = end_time - start_time
    print(f" processing time: {elapsed_time} seconds")

    
    
  #   print('Rotating velocities to receiver grid coordinate system. ')   
    dataout_z['temp']=(('s_rho', 'eta_rho', 'xi_rho'),temp)
    dataout_z['salt']=(('s_rho', 'eta_rho', 'xi_rho'),salt) 
    dataout_z['u_eastward']=(('s_rho', 'eta_rho', 'xi_rho'),u_east) 
    dataout_z['v_northward']=(('s_rho', 'eta_rho', 'xi_rho'),v_north) 
  #   dataout_z['vbar_northward']=xromqckL1['vbar_northward']
  #   dataout_z['ubar_eastward']=xromqckL1['ubar_eastward']
    dataout_z['zeta']=dataout_z['zeta'].fillna(0)
    dataout_z=dataout_z.squeeze(dim="ocean_time") 
    (dataout_z,gridout)=xroms.roms_dataset(dataout_z,Vtransform=L1Vtransform)
        

    uv=rutil.uv_rot(dataout_z.u_eastward, dataout_z.v_northward, gridout,cfgrd.angle,reverse=True)
    ruhis=uv[0]
    rvhis=uv[1]
    dataout_z=xr.merge([dataout_z,ruhis,rvhis])
    dataout_z.load()
    ubar=dataout_z.u.xroms.gridmean(gridout,"Z")
    vbar=dataout_z.v.xroms.gridmean(gridout,"Z")


    print('  Writing initialization data to file '+inifile)
    ncid = nc.Dataset(inifile, "r+", format="NETCDF4")
    
    t=dsmerc.time.values
    timeout=(t-np.datetime64(rtime)) / np.timedelta64(1, 'D')
    ncid.variables['ocean_time'][:]=timeout

    ncid.variables['ubar'][0,:,:]=ubar.values[:,:]
    ncid.variables['vbar'][0,:,:]=vbar.values[:,:]
    ncid.variables['zeta'][0,:,:]=dataout['zos'].values[:,:]
    ncid.variables['u'][0,:,:,:]=dataout_z.u.values[:,:,:]
    ncid.variables['v'][0,:,:,:]=dataout_z.v.values[:,:,:]
    ncid.variables['salt'][0,:,:,:]=salt
    ncid.variables['temp'][0,:,:,:]=temp
    ncid.variables['Vtransform'][:]=L1Vtransform
    ncid.variables['Vstretching'][:]=L1Vstretching
    ncid.variables['theta_b'][:]=L1theta_b
    ncid.variables['theta_s'][:]=L1theta_s
    ncid.variables['Tcline'][:]=L1Tcline
    ncid.variables['hc'][:]=L1hc
    
    ncid.sync()
    ncid.close()

def plot_2D_LL(lon,lat,var):
    fig = plt.figure(figsize=(10,6))
    ax = fig.add_subplot(1,1,1,projection=proj)
    gl = ax.gridlines(draw_labels=True, x_inline=False, y_inline=False)
    gl.top_labels = False
    gl.right_labels = False
    ax.coastlines(resolution='50m')

    ax.set_extent([lonmin, lonmax, latmin,latmax])
    
    
    pcid=ax.pcolormesh(lon,lat,var,transform=pc)
    colorbar = plt.colorbar(pcid)
    plt.show()
    
def plot_points_LL(lon,lat,var):
    fig = plt.figure(figsize=(10,6))
    ax = fig.add_subplot(1,1,1,projection=proj)
    gl = ax.gridlines(draw_labels=True, x_inline=False, y_inline=False)
    gl.top_labels = False
    gl.right_labels = False
    ax.coastlines(resolution='50m')

    ax.set_extent([lonmin, lonmax, latmin,latmax])
        
        
    pcid=ax.scatter(lon,lat,c=var,s=20,transform=pc,marker='o',vmin=0,vmax=30)
    colorbar = plt.colorbar(pcid)
    plt.show()
    
    
    
    
if __name__ == "__main__":
    print('Running Downscale')
    main()
    
    print('Finished Downscale')
