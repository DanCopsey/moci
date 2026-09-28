#!/usr/bin/env python3
'''
*****************************COPYRIGHT******************************
 (C) Crown copyright 2025 Met Office. All rights reserved.

 Use, duplication or disclosure of this code is subject to the restrictions
 as set forth in the licence. If no licence has been raised with this copy
 of the code, the use, duplication or disclosure of it is strictly
 prohibited. Permission to do so must first be obtained in writing from the
 Met Office Information Asset Owner at the following address:

 Met Office, FitzRoy Road, Exeter, Devon, EX1 3PB, United Kingdom
*****************************COPYRIGHT******************************
NAME
    rivers_def.py

DESCRIPTION
    Definition of the environment variables required for a rivers model
    run
'''

RIVERS_ENVIRONMENT_VARS_INITIAL = {
    'RIVER_EXEC': {},
    'RIVER_LINK': {'default_val': 'river.exe'},
    'RIVER_RUNID': {'default_val':''},
    'PRINT_STATUS': {'default_val': 'PrStatus_Normal'},
    'MODEL_NLIST': {'default_val': 'model_grid.nml'},
    'OUTPUT_NLIST': {'default_val': 'output.nml'},
    'TIME_NLIST': {'default_val': 'timesteps.nml'},
    'COUPLE_NLIST': {'default_val': 'rivers_coupling.nml'},
    'RIV_INIT_NLIST': {'default_val': 'initial_conditions.nml'},
    'ANCILLARIES': {'default_val': 'ancillaries.nml'},
    'RIVER_DATA': {'default_val':'./river_output'},
    'RIVER_NPROC': {'description': 'Number of processors used for rivers'},
    'ROSE_LAUNCHER_PREOPTS_RIVER': {'default_val': '-n 1'},
    'RIVER_START': {'default_val': 'unset'},
}

RIVERS_ENVIRONMENT_VARS_FINAL = {}
