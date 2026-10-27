#!/bin/bash

## Commands commented out with double ##

#SBATCH --kill-on-invalid-dep=yes         # Cancel job on failed dependency
#SBATCH --partition=p_omg_1               # Partition (job queue) for Ocean Modeling Group
#SBATCH --requeue                         # Return job to the queue if preempted
#SBATCH --job-name=gog_test           # Assign a short name to your job
#SBATCH --nodes=2                         # Number of nodes you require

#SBATCH --ntasks=128                      # Total number of tasks to launch (like -np to mpirun)
#SBATCH --ntasks-per-node=64              # Number of tasks to launch on each node

#SBATCH --cpus-per-task=1                 # Cores per task (>1 if multithread tasks)
#SBATCH --mem=180000                      # Real memory (RAM) required (MB) per node
#SBATCH --time=1-00:00                   # Total run time limit (DD-HH:MM)
#SBATCH --output=out.slurm.%N.%j          # STDOUT output file
#SBATCH --error=err.slurm.%N.%j           # STDERR output file (optional but recommended)
#SBATCH --export=ALL                      # Export you current env to the job env

##SBATCH --mail-type=ALL
##SBATCH --mail-user=cb1237@marine.rutgers.edu

## It is important to have --mpi=pmi2 here or ROMS will not run
srun --mpi=pmi2 ./romsM roms_gulfofguinea.in     
