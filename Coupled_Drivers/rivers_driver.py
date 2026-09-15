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
    rivers_driver.py

DESCRIPTION
    Driver for the JULES river standalone model, called from link_drivers.
'''

import os
import sys
import re
import pathlib
import common
import error
import time
import dr_env_lib.rivers_def
import dr_env_lib.env_lib
try:
    import f90nml
except ImportError:
    pass


def _load_environment_variables(river_envar):
    '''
    Load the river environment variables required for the model run into the
    river_envar container
    '''
    # Load the river namelist environment variable
    river_envar = dr_env_lib.env_lib.load_envar_from_definition(
        river_envar, dr_env_lib.rivers_def.RIVERS_ENVIRONMENT_VARS_INITIAL)

    return river_envar


def _setup_dates(common_envar):
    '''
    Setup the dates for the JULES river model run
    '''
    calendar = common_envar['CALENDAR']

    sys.stdout.write('[INFO] River calendar= %s ' % calendar)
    if calendar not in ('360day', '365day', 'gregorian'):
        sys.stderr.write('[FAIL] Calendar type %s not recognised\n' %
                         calendar)
        sys.exit(error.INVALID_EVAR_ERROR)

    # Find the start and end times in the right format
    task_start = common_envar['TASKSTART'].split(',')
    task_length = common_envar['TASKLENGTH'].split(',')

    start_date = '%s%s%sT%s%sZ' % (task_start[0].zfill(4),
                                   task_start[1].zfill(2),
                                   task_start[2].zfill(2),
                                   task_start[3].zfill(2),
                                   task_start[4].zfill(2))
    format_date = '%Y-%m-%d %H:%M:%S'
    length_date = 'P%sY%sM%sDT%sH%sM' % (task_length[0], task_length[1],
                                         task_length[2], task_length[3],
                                         task_length[4])

    start_cmd = ['isodatetime', '%s' % start_date, '-f', '%s' % format_date]
    end_cmd = ['isodatetime', '%s' % start_date, '-f', '%s' % format_date,
               '-s', '%s' % length_date, '--calendar', '%s' % calendar]

    _, run_start = common.exec_subproc(start_cmd)
    _, run_end = common.exec_subproc(end_cmd)

    return run_start.strip(), run_end.strip()


def _update_river_nl(common_envar, river_envar, run_start, run_end):
    '''
    Check that the JULES river namelist files exist, update
    the start and end dates, and create the output directory
    '''
    # Check that the namelist files exist
    output_nl = river_envar['OUTPUT_NLIST']
    time_nl = river_envar['TIME_NLIST']
    riv_init_nl = river_envar['RIV_INIT_NLIST']
    ancillaries_nl = river_envar['ANCILLARIES']

    if not os.path.isfile(output_nl):
        sys.stderr.write('[FAIL] Can not find the river namelist file %s\n' %
                         output_nl)
        sys.exit(error.MISSING_DRIVER_FILE_ERROR)
    if not os.path.isfile(time_nl):
        sys.stderr.write('[FAIL] Can not find the river namelist file %s\n' %
                         time_nl)
        sys.exit(error.MISSING_DRIVER_FILE_ERROR)

    # If the run ID has been overridden for the rivers code, the use
    # that value. Otherwise use the standard RUNID.
    if river_envar['RIVER_RUNID'] == '':
       run_id = common_envar['RUNID']+'r'
    else:
       run_id = river_envar['RIVER_RUNID']+'r'

    # We need to ensure the date is included in all
    # "profile_name" entries
    mod_timenl = common.ModNamelist(time_nl)
    mod_timenl.var_val('main_run_start', run_start)
    mod_timenl.var_val('main_run_end', run_end)
    mod_timenl.replace()

    # We don't want to initialise river storage from ancillary file for a CRUN
    # This means reducing nvars by one and shrinking all associated lists by one
    if common_envar['CONTINUE'] == 'true':
        mod_ancilsnl = common.ModNamelist(ancillaries_nl)
        mod_ancilsnl.var_val('nvars', 3)
        mod_ancilsnl.var_val('use_file', '.true.,.true.,.true.')
        mod_ancilsnl.var_val('var', "'direction','sequence','rivers_outflow_number'")
        mod_ancilsnl.var_val('var_name', "'river_routing_direction','river_routing_sequence','river_number'")
        mod_ancilsnl.var_val('is_climatology', '.false.,.false.,.false.')
        mod_ancilsnl.var_delete('const_val')
        mod_ancilsnl.replace()

    # River dumps have their own peculiar naming convention.
    # The .0. part is a temporary solution pending clarification of whether
    # JULES can be made to use YYYYMMDDhhmmss in the dump name. It assumes
    # all dumps start from midnight which is not a good thing to assume
    start_yyyymmdd = str(run_start[:4]) + str(run_start[5:7]) + str(run_start[8:10])
    end_yyyymmdd = str(run_end[:4]) + str(run_end[5:7]) + str(run_end[8:10])
    latest_river_dump = river_envar['RIVER_DATA'] + '/' + run_id + '.dump.' + \
                        start_yyyymmdd + '.0.nc'

    if common_envar['CONTINUE'] == 'false':
       # This is a new run so we just stick with whatever dump or
       # other initialisation method is provided in the namelists
       sys.stdout.write('[INFO] River running from existing restart data or ancil\n')

       # If we have an old river history data directory from a previous run
       # then rename it.
       direc = river_envar['RIVER_DATA']
       if os.path.isdir(direc) and (direc not in ('./', '.')):
          sys.stdout.write('[INFO] directory is %s\n' % direc)
          sys.stdout.write('[INFO] This is a New Run. Renaming old RIVER'
                           ' history directory\n')
          os.rename(direc, '%s.%s' % (direc, time.strftime("%Y%m%d%H%M")))
          os.makedirs(direc)

    elif os.path.isfile(latest_river_dump):
       # This is a CRUN so we update the namelist to point at the most
       # recent restart file.
       mod_rivinitnl = common.ModNamelist(riv_init_nl)

       mod_rivinitnl.var_val('file',latest_river_dump)

       # Ensure we're set to use a restart file
       l_restart='.true.'
       mod_rivinitnl.var_val('dump_file', l_restart)

       # Set the number of initialised variables to zero so that it loads all the variables from the dump
       mod_rivinitnl.var_val('nvars', 0)

       mod_rivinitnl.replace()
    else:
        sys.stderr.write('[FAIL] No restart data available for rivers in '
                         ':\n  %s\n' % latest_river_dump)
        sys.exit(error.MISSING_MODEL_FILE_ERROR)

    # Set up specific filename details for any expected diagnostic files.
    filestub_drive_rivers='drive_rivers-only.' + start_yyyymmdd + \
                                                            '_' + end_yyyymmdd
    filestub_rivers='rivers.' + start_yyyymmdd + '_' + end_yyyymmdd

    mod_outputnl = common.ModNamelist(output_nl)

    # Update the start and end dates
    mod_outputnl.var_val('output_start', run_start)
    mod_outputnl.var_val('output_end', run_end)

    # Update the run id
    mod_outputnl.var_val('run_id', run_id)

    # Update the output diagnostic file names
    mod_outputnl.var_val_conditional(
           'profile_name', [[lambda x: 'drive_rivers' in x, filestub_drive_rivers],
                            [lambda x: 'rivers' in x and 'drive' not in x, filestub_rivers]])

    mod_outputnl.replace()

    # Create the output directory, do not rely on f90nml
    rcode, val = common.exec_subproc(['grep', 'output_dir', output_nl])
    if rcode == 0:
        try:
            output_dir = re.findall(r'[\"\'](.*?)[\"\']', val)[0].rstrip('/')
            pathlib.Path(output_dir).mkdir(parents=True, exist_ok=True)
        except IndexError:
            # No path found
            pass


def _setup_executable(common_envar):
    '''
    Setup the environment and any files required by the executable
    '''
    # Create the environment variable container
    river_envar = dr_env_lib.env_lib.LoadEnvar()
    # Load the environment variables required
    river_envar = _load_environment_variables(river_envar)

    # Link the river executable
    common.remove_file(river_envar['RIVER_LINK'])
    os.symlink(river_envar['RIVER_EXEC'],
               river_envar['RIVER_LINK'])

    # Setup date variables
    run_start, run_end = _setup_dates(common_envar)

    # Update the river namelists
    _update_river_nl(common_envar, river_envar, run_start, run_end)

    return river_envar


def _set_launcher_command(river_envar):
    '''
    Setup the launcher command for the executable
    '''
    launch_cmd = river_envar['ROSE_LAUNCHER_PREOPTS_RIVER']

    launch_cmd = '%s ./%s' % \
        (river_envar['ROSE_LAUNCHER_PREOPTS_RIVER'],
         river_envar['RIVER_LINK'])

    # Put in quotes to allow this environment variable to be exported as it
    # contains (or can contain) spaces
    river_envar['ROSE_LAUNCHER_PREOPTS_RIVER'] = "'%s'" % \
        river_envar['ROSE_LAUNCHER_PREOPTS_RIVER']
    return launch_cmd


def _get_river_resol(river_nl_file, run_info):
    '''
    Determine the JULES river resolution.
    This function is only used when creating the namcouple at run time.
    '''

    # Check if the namelist file exists
    if not os.path.isfile(river_nl_file):
        sys.stderr.write('[FAIL] Can not find the river namelist file %s\n' %
                         river_nl_file)
        sys.exit(error.MISSING_DRIVER_FILE_ERROR)

    # Read in the resolution of JULES river
    river_nml = f90nml.read(river_nl_file)

    # Check the required entries exist
    if 'jules_input_grid' not in river_nml:
        sys.stderr.write('[FAIL] jules_input_grid not found in %s\n' %
                         river_nl_file)
        sys.exit(error.MISSING_RIVER_RESOL_NML)
    if 'nx' not in river_nml['jules_input_grid'] or \
       'ny' not in river_nml['jules_input_grid']:
        sys.stderr.write('[FAIL] nx or ny are missing from namelist'
                         'jules_input_grid in %s\n' % river_nl_file)
        sys.exit(error.MISSING_RIVER_RESOL)

    # Store the ocean resolution
    run_info['RIV_resol'] = [river_nml['jules_input_grid']['nx'],
                             river_nml['jules_input_grid']['ny']]

    return run_info


def _sent_coupling_fields(river_envar, run_info):
    '''
    Write the coupling fields sent from JULES river into model_snd_list.
    This function is only used when creating the namcouple at run time.
    '''
    from write_namcouple import add_to_cpl_list

    # Check that file specifying the coupling fields sent from
    # JULES river is present
    if not os.path.exists('OASIS_RIV_SEND'):
        sys.stderr.write('[FAIL] OASIS_RIV_SEND is missing.\n')
        sys.exit(error.MISSING_OASIS_RIV_SEND)

    # Add toyatm to our list of executables
    if not 'exec_list' in run_info:
        run_info['exec_list'] = []
    run_info['exec_list'].append('toyriv')

    # Determine the ocean resolution
    run_info = _get_river_resol(river_envar['MODEL_NLIST'], run_info)

    # If using the default coupling option, we'll need to read the
    # JULES river namelist later
    river_nl = river_envar['COUPLE_NLIST']
    if not os.path.isfile(river_nl):
        sys.stderr.write('[FAIL] Can not find the river namelist file %s\n' %
                         river_nl)
        sys.exit(error.MISSING_DRIVER_FILE_ERROR)
    run_info['river_nl'] = river_nl

    # Read the namelist
    oasis_nml = f90nml.read('OASIS_RIV_SEND')

    # Check we have the expected information
    if 'oasis_riv_send_nml' not in oasis_nml:
        sys.stderr.write('[FAIL] namelist oasis_riv_send_nml is '
                         'missing from OASIS_RIV_SEND.\n')
        sys.exit(error.MISSING_OASIS_RIV_SEND_NML)
    if 'oasis_riv_send' not in oasis_nml['oasis_riv_send_nml']:
        sys.stderr.write('[FAIL] entry oasis_riv_send is missing '
                         'from namelist oasis_riv_send_nml in '
                         'OASIS_RIV_SEND.\n')
        sys.exit(error.MISSING_OASIS_RIV_SEND)

    # Create a list of fields sent from RIV
    model_snd_list = add_to_cpl_list(
        'RIV', False, 0, oasis_nml['oasis_riv_send_nml']['oasis_riv_send']
    )

    return run_info, model_snd_list

def _finalize_executable():
    '''
    Finalize the JULES river run, copy the river namelists to
    the restart directory for the next cycle, update standard out,
    and ensure that no errors have been found in the river execution.
    '''
    sys.stdout.write('[INFO] finalizing JULES river')
    sys.stdout.write('[INFO] running finalize in %s' % os.getcwd())

    # The JULES river output is written by default to the standard output

    # JULES river does not produce a restart file yet

def run_driver(common_env, mode, run_info):
    '''
    Run the driver, and return an instance of common.LoadEnvar and as string
    containing the launcher command for the JULES river model
    '''
    if mode == 'run_driver':
        exe_envar = _setup_executable(common_env)
        launch_cmd = _set_launcher_command(exe_envar)
        if run_info['l_namcouple']:
            model_snd_list = None
        else:
            run_info, model_snd_list = \
                _sent_coupling_fields(exe_envar, run_info)
    elif mode == 'finalize':
        _finalize_executable()
        exe_envar = None
        launch_cmd = None
        model_snd_list = None
    return exe_envar, launch_cmd, run_info, model_snd_list
