from util_functions import lerp, seconds_to_datetime, datetime_string_to_seconds
import builtins as __builtin__
import pandas as pd
import numpy as np
import argparse
import glob
import time
import os

try:
    import __builtin__
except ImportError:
    # Python 3
    import builtins as __builtin__
    
# For debugging purposes only:
def print(*args, **kwargs):
    __builtin__.print('\t simple_jobs: ', end="")
    return __builtin__.print(*args, **kwargs)

START_TIME = time.time()

parser = argparse.ArgumentParser()
parser.add_argument('-n_it','--iteration_no',required=True)
parser.add_argument('-file_path','--file_path',required=True)
parser.add_argument('-nhp','--number_of_hyp',required=True)
parser.add_argument('-titr','--total_iterations',required=True)

# adding parameter for where to save all the data to:
parser.add_argument('-save', '--save_path', required=False, default=None)

# allowing for variable number of molecules to test and validate from:
parser.add_argument('-n_mol', '--number_mol', required=False, default=1000000)
parser.add_argument('-pfm', '--percent_first_mols', required=False, default=1)  # these two inputs must be percentages (e.g. 100 for 100%)
parser.add_argument('-plm', '--percent_last_mols', required=False, default=0.01)

# Flag for switching between functions that determine how many mols to be left at the end of iteration 
#   if not provided it defaults to a linear dec
funct_flags = parser.add_mutually_exclusive_group(required=False)
funct_flags.add_argument('-expdec', '--exponential_dec', required=False, default=-1) # must pass in the base number
funct_flags.add_argument('-polydec', '--polynomial_dec', required=False, default=-1) # You must also pass in to what power for this flag

# This determines whether or not you want to choose a continuous range of hyperparameters
parser.add_argument('-chp', '--continuous_hyperparameters', required=False, default=False, type=bool)

io_args, extra_args = parser.parse_known_args()
n_it = int(io_args.iteration_no)
nhp = int(io_args.number_of_hyp)
titr = int(io_args.total_iterations)

num_molec = int(io_args.number_mol)
percent_first_mols = float(io_args.percent_first_mols)
percent_last_mols = float(io_args.percent_last_mols)

exponential_dec = int(io_args.exponential_dec)
polynomial_dec = int(io_args.polynomial_dec)

dynamic_hyperparameters = io_args.continuous_hyperparameters

PROJECT_PATH = io_args.file_path   # Now == file_path/protein
SAVE_PATH = io_args.save_path
# if no save path is provided we just save it in the same location as the data
if SAVE_PATH is None: SAVE_PATH = PROJECT_PATH

assert percent_first_mols < 100, "Percent_first_mols must be less than 100% for progress on the first iteration."
assert percent_last_mols < percent_first_mols, "Percent_last molecs must be less than percent_first_molecs."

# sums the first column (the size of our dataset)
t_mol = pd.read_csv(PROJECT_PATH+'/Mol_ct_file.csv',header=None)[[0]].sum()[0] # num of compounds in each file is mol_ct_file


"""
Hyperparameter information:
------------------------------------------------------------------------------------------------------------------------
Note that we have 7 hyperparameters that we can tune. 

1. num_units (number of neurons per layer)
2. dropout (dropout per layer)
3. learn_rate (model's learning rate)
4. bin_array (number of deep layers for model)
5. wt (class weight for training)
6. bs (batch size for training)
7. oss (over sample size for training)

Since the models are going to be a combination of these values, we have:
    * Let Hyperparameter Name = len(Hyperparameter Name) for simplicity:
        - Number of models = num_units * dropout * learn_rate * bin_array * wt * bs * oss

Since we have a number of hyperparameter predefined, we should create a range given the passed number of HPs
------------------------------------------------------------------------------------------------------------------------
"""

# Changes the way we create our hyperparameters
cummulative = 0.25 * n_it
if dynamic_hyperparameters:

    # len(num_units) <= num_values_per_hyperparameters
    num_values_per_hyperparameters = round(nhp ** (1/7))

    # Define ranges of hyperparameters
    unit_range = [100, 2000]
    dropout_range = [0.2, 0.5]
    learn_rate_range = [0.0001, 0.0001]
    bin_array_range = [2, 3]
    wt_range = [2, 3]
    bs_range = [128, 256]
    oss_range = [5, 20]

else:
    # Use predefined ranges/values
    num_units = [(900, 1150), (1150, 1400)]
    dropout = [(0.6, 0.75), (0.75, 0.9)]
    learn_rate = [(0.00014, 0.00020)]
    bin_array = [2, 3]
    wt = [(2.20, 5.0)]

    if nhp < 144:
        bs = [256]
    else:
        bs = [128, 256]

    if nhp < 48:
        oss = [(10, 20), (20, 30), (30, 40)]
    elif nhp < 72:
        oss = [5, 10]
    else:
        oss = [5, 10, 20]

# Precalculate the number of models
import random
number_of_models = len(num_units) * len(dropout) * len(learn_rate) * len(bin_array) * len(wt) * len(bs) * len(oss)
print("Number of models:", number_of_models)

try:
    os.mkdir(SAVE_PATH+'/iteration_'+str(n_it)+'/simple_job')
except OSError: # catching file exists error
    pass

# Clearing up space from previous iteration
for f in glob.glob(SAVE_PATH+'/iteration_'+str(n_it)+'/simple_job/*'):
    os.remove(f)

# getting the list of scores from the validation labels
scores_val = pd.read_csv(PROJECT_PATH+"/iteration_1/validation_labels.txt", header=[0]).iloc[:,0].to_numpy()

# Default is 1% and 0.01% for pfm and plm respectfully.
first_mols = int((percent_first_mols/100) * len(scores_val))
last_mols =  int((percent_last_mols/100) * len(scores_val))

if n_it==1:
    # 'good_mol' is the number of top scoring molecules to save at the end of the iteration
    good_mol = first_mols
else:
    if exponential_dec != -1:
        good_mol = int() #TODO: create functions for these
    elif polynomial_dec != -1:
        good_mol = int()
    else:
        good_mol = int(((last_mols-first_mols)*n_it + titr*first_mols-last_mols)/(titr-1))     # linear decrease as iterations increase

# needs at least 10 hits for this to even work so we set it higher
good_mol = good_mol if good_mol > 50 else 50
assert good_mol < len(scores_val), "good mol must be less than total mols"

# calculating threshold using percentile:
percent_good_mol = 100 * good_mol/len(scores_val)
cf_start = np.percentile(scores_val, percent_good_mol)
print("Calculating using percentile ({:.4}%):".format(percent_good_mol))
print('Threshold (cutoff):', cf_start)
print('Molec under thresh:', len(scores_val[scores_val<cf_start]))
print('Goal molec:', good_mol)
print('Total molec:', len(scores_val))

all_hyperparas = []
for o in oss:   # Over Sample Size
    for batch in bs:
        for nu in num_units:
            for do in dropout:
                for lr in learn_rate:
                    for ba in bin_array:
                        for w in wt:    # Weight
                            # We now create a random search between two values and add them to a list of hps
                            hypers = []
                            # Look at each hp
                            for hp in [o,batch,nu,do,lr,ba,w,cf_start]:
                                # If it is a tuple, then we have a range of values
                                if type(hp) is tuple:
                                    min_val = hp[0]
                                    max_val = hp[1]
                                    # Check if it is floats and use uniform
                                    if type(min_val) is float and type(max_val) is float:
                                        hypers.append(random.uniform(min_val, max_val))
                                    elif type(min_val) is int and type(max_val) is int:
                                        hypers.append(random.randint(min_val, max_val))
                                else:
                                    hypers.append(hp)

                            # print the params for debugging
                            print("HP:", hypers)
                            all_hyperparas.append(hypers)

print('Total Hyperparameters:', len(all_hyperparas))
# Creating all the jobs for each hyperparameter combination:

other_args = ' '.join(extra_args) + ' -n_it {} -t_mol {} --data_path {} --save_path {} -n_mol {}'.format(n_it, t_mol, PROJECT_PATH, SAVE_PATH, num_molec)
print("Args:", other_args)
for i in range(len(all_hyperparas)):
    model_number = i + 1
    with open(SAVE_PATH+'/iteration_'+str(n_it)+'/simple_job/simple_job_'+str(model_number)+'.sh', 'w') as ref:
        ref.write('#!/bin/bash\n')
        ref.write('#SBATCH --ntasks=1\n')
        ref.write('#SBATCH --gres=gpu:1\n')
        ref.write('#SBATCH --cpus-per-task=1\n')
        ref.write('#SBATCH --job-name=phase_4\n')
        ref.write('#SBATCH --mem=0               # memory per node\n')
        ref.write("#SBATCH --output=slurm-phase_4-%x.%j.out\n")
        ref.write("#SBATCH --error=slurm-phase_4-%x.%j.err\n")
        ref.write('\n')
        ref.write("echo Partition: $SLURM_JOB_PARTITION \n")

        cwd = os.getcwd()
        ref.write('cd {}\n'.format(cwd))
        ref.write('source ~/.bashrc\n')
        ref.write('source activation_script.sh\n')
        hyp_args = '-os {} -bs {} -num_units {} -dropout {} -learn_rate {} -bin_array {} -wt {} -cf {}'.format(*all_hyperparas[i])
        ref.write('python -u progressive_docking.py ' + hyp_args + ' ' + other_args + ' --model_number ' + str(model_number))
        ref.write("\n echo complete")


print('Runtime:', time.time() - START_TIME)
