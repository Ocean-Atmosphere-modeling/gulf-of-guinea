#!/bin/bash
#
# Make the ROMS INI, BRY and CLM files from downloaded Mercator data on a compute node.
# Run the Mercator download first (on the login node), then submit from the
# repo's python/ directory:
#
# For example: cd /projectsp/f_omg_1/cbenton/gulf-of-guinea/python
# Command to run:   sbatch ../bash_scripts/job_downscale.sh
#
# Scripts needed are the following
#  downscale_mercator_to_roms_GulfOfGuinea_INI.py
#  downscale_mercator_to_roms_GulfOfGuinea_BRY.py
#  downscale_mercator_to_roms_GulfOfGuinea_CLM.py
#
# Check progress with:  squeue -u $USER   and   tail -f downscale.<jobid>.log

#SBATCH --partition=p_omg_1               # Ocean Modeling Group partition
#SBATCH --job-name=gog_downscale
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8                 # threads for numpy/xesmf
#SBATCH --mem=64000                       # MB
#SBATCH --time=12:00:00                   # HH:MM:SS
#SBATCH --requeue                         # back in the queue if preempted
#SBATCH --output=downscale.%j.log         # stdout and stderr together
#SBATCH --export=ALL

set -e                                    # stop if a step fails

# Python environment: May have to change depending on your setup
source ~/miniforge3/etc/profile.d/conda.sh
conda activate guinea2
export OMP_NUM_THREADS=${SLURM_CPUS_PER_TASK}

cd /projectsp/f_omg_1/cbenton/gulf-of-guinea/python   # romsutil.py lives here

echo "=== INI  $(date)"
python -u downscale_mercator_to_roms_GulfOfGuinea_INI.py

echo "=== BRY  $(date)"
python -u downscale_mercator_to_roms_GulfOfGuinea_BRY.py

echo "=== CLM  $(date)"
python -u downscale_mercator_to_roms_GulfOfGuinea_CLM.py

echo "=== done $(date)"
