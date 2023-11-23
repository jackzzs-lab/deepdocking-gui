#!/bin/bash -l

# Create the local env
python3 install.py --phase install_local
# Activate the env
conda activate app-deepdocking-gui 2> conda.out
# Install remote files and create remote env
python3 install.py --phase install_remote
