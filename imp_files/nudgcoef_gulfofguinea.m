% Create boundary nudging coefficients file 
%
% John Wilkin - Nov 2024
%
% See d_nudgcoef.m in myroms MATLAB tools for information

% Grid file
GridFile = 'GulfOfGuinea_4km.nc';

% Initial conditions file (for s-coordinate parameters)
InitialConditionsFile = ['../mercator/IC_BC/' ...
  'ini_gulfofguinea_Mercator_2024_06_01.nc'];

% Output file
Nscale = 15; % roughly 7 coarse grid cells
NudgFile = "nud_gulfofguinea_Nf"+int2str(Nscale)+".nc"; % Nf width of zone

% Create an empty nudging coefficients file
% NOTE - the template CDL file has to exist with the correct DIMENSIONS
if ~exist(NudgFile,'file')
  unixstr = "ncgen -b -o "+NudgFile+ " nudgcoef.cdl";
  disp("An empty NUDGING file must be created with ..."+newline+unixstr)
  unixstr = "/opt/local/bin/"+unixstr;
  disp(" creating the empty file now")
  unix(unixstr)
end

% Grid
g = roms_get_grid(GridFile,InitialConditionsFile);
ncwrite(NudgFile,'spherical',1)
ncwrite(NudgFile,'lon_rho',g.lon_rho')
ncwrite(NudgFile,'lat_rho',g.lat_rho')

% Create nudging coefficients by pseudo diffusion from the open boundary
% perimeter. This avoids nudging in bays close to a masked boundary.

% Units values on edge of zero scratch arrays
wrk = zeros(size(g.h));
wrk(:,[1 end]) = g.mask_rho(:,[1 end]);
wrk([1 end],:) = g.mask_rho([1 end],:);
wrk = wrk([1 1:end end],[1 1:end end]); % pad

% Diffuse boundary value into interior
for k=1:Nscale^2
  k
  tmp = conv2(wrk,ones([3 3])/9,'same');
  % take max or perimeter values will decrease due to zero padding in
  % the conv2 operation
  wrk = max(tmp,wrk);
  % enforce zero on north boundary
  % wrk(end,:) = 0;
end

% Extract the rho point grid subset
wrk = wrk(2:(end-1),2:(end-1));

% Force interior points to have exactly zero nudging in the hope this 
% will allow the file to compress well in netcdf-4
% nought = wrk(Nfilt^2+1,Nfilt^2+1);
nought = eps('single');
wrk(wrk<=nought) = 0;

% Normalize to be sure range is 0 to 1
wrk = wrk/max(wrk(:));

% 2D and 3D nudging coefficients
wrk = wrk.*g.mask_rho;
nudg2D = wrk';
nudg3D = repmat(nudg2D,[1 1 g.N]);

% ROMS time step parameters
dt = 72; % model time steps in seconds
ndtfast = 30; % fast time step factor from roms.in

% Set nudging time scales
% 
% 3D (slow time step) variables
dtdays = 72/86400;       % days
gamma3D = 1/(10*dtdays); % stiff nudging of 10*dt at the perimeter

% 2D (fast time step) should be even less because the 
% nudging is applied on every fast time step
% though in my experience nudging the 2D solution is not advised
% because it will work against Chapman/Flather
gamma2D = 1/(10*(dtdays/ndtfast));

ncwrite(NudgFile,'M2_NudgeCoef',gamma2D*nudg2D)
ncwrite(NudgFile,'M3_NudgeCoef',gamma3D*nudg3D)
ncwrite(NudgFile,'temp_NudgeCoef',gamma3D*nudg3D)
ncwrite(NudgFile,'salt_NudgeCoef',gamma3D*nudg3D)

ncwriteatt(NudgFile,'/','grd_file',GridFile)
comment = "Created by J. Wilkin "+datestr(now,'yyyy-mm-dd')+...
  " for "+g.grd_file+" using "+which(mfilename);
disp(comment)
ncwriteatt(NudgFile,'/','history',comment)
comment = "Using very stiff perimeter 3D nudging time scale of " ...
  +num2str(1/(dtdays*gamma3D))+" times delta-t "...
  +"and M2/2D time scale further reduced by NDTFAST";
ncwriteatt(NudgFile,'/','comment1',comment)
if ~exist('title','var')
  title = 'Gulf of Guinea 4-km model downscale of Mercator for COESSING';
end
ncwriteatt(NudgFile,'/','title',title)
