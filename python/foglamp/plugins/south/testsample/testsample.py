# -*- coding: utf-8 -*-

# FOGLAMP_BEGIN
# See: http://foglamp.readthedocs.io/
# FOGLAMP_END

""" Module for testsample async plugin """

import asyncio
import copy
import uuid
import logging
import time
import random
from threading import Timer
from foglamp.common import logger
from foglamp.plugins.common import utils
from foglamp.services.south import exceptions
from foglamp.services.south.ingest import Ingest


__author__ = "Amarendra Kumar Sinha"
__copyright__ = "Copyright (c) 2018 Dianomic Systems"
__license__ = "Apache 2.0"
__version__ = "${VERSION}"


_DEFAULT_CONFIG = {
    'plugin': {
        'description': 'Test Sample',
        'type': 'string',
        'default': 'testsample',
        'readonly': 'true'
    },
    'assetName': {
        'description': 'Name of Asset',
        'type': 'string',
        'default': 'sample',
        'order': '1'
    },
    'noOfAssets': {
        'description': 'No. of assets to generate',
        'type': 'integer',
        'default': '2500',
        'order': '2'
    },
    'dataPointsPerSec': {
        'description': 'Data points per second',
        'type': 'integer',
        'default': '5000',
        'order': '3'
    }
}

_LOGGER = logger.setup(__name__, level=logging.INFO)
_task = None
no_of_assets = 0
asset_srl = 0
cn = 0
cn_time = None


def plugin_info():
    """ Returns information about the plugin.
    Args:
    Returns:
        dict: plugin information
    Raises:
    """
    return {
        'name': 'Test Sample',
        'version': '1.0',
        'mode': 'async',
        'type': 'south',
        'interface': '1.0',
        'config': _DEFAULT_CONFIG
    }


def plugin_init(config):
    """ Initialise the plugin.
    Args:
        config: JSON configuration document for the South plugin configuration category
    Returns:
        data: JSON object to be used in future calls to the plugin
    Raises:
    """
    data = copy.deepcopy(config)
    return data


def plugin_start(handle):
    """ Extracts data from the testsample and returns it in a JSON document as a Python dict.
    Available for async mode only.

    Args:
        handle: handle returned by the plugin initialisation call
    Returns:
        a testsample reading in a JSON document, as a Python dict, if it is available
        None - If no reading is available
    Raises:
        TimeoutError
    """
    global _task, no_of_assets, cn, asset_srl, cn_time
    async def save_data():
        global no_of_assets, cn, asset_srl, cn_time
        try:
            time_stamp = utils.local_timestamp()
            asset_srl = 1 if asset_srl+1 > no_of_assets else asset_srl+1
            data = {
                'asset': "{}_{}".format(handle['assetName']['value'], asset_srl),
                'timestamp': time_stamp,
                'key': str(uuid.uuid4()),
                'readings': {
                    "x": random.random(),
                    "y": random.random(),
                    "z": random.random(),
                }
            }
            await Ingest.add_readings(asset='{}'.format(data['asset']),
                                      timestamp=data['timestamp'], key=data['key'],
                                      readings=data['readings'])
            cn += 1
            if cn == recs:
                _LOGGER.exception(">>>> %s recs in % secs", recs, time.time()-cn_time)
                cn = 0
                cn_time = time.time()
        except RuntimeWarning as ex:
            _LOGGER.exception("TestSample warning: {}".format(str(ex)))
        except (Exception, RuntimeError) as ex:
            _LOGGER.exception("TestSample exception: {}".format(str(ex)))
            raise exceptions.DataRetrievalError(ex)

    def run_task(loop):
        global _task
        global no_of_assets, cn, asset_srl
        asyncio.set_event_loop(loop)
        asyncio.ensure_future(save_data(), loop=loop)
        # Chain next iteration
        _task = Timer(period, run_task, args=(loop, ))
        _task.start()

    try:
        recs = int(handle['dataPointsPerSec']['value'])
        period = round(1.0 / recs, len(str(recs)) + 1)
    except ZeroDivisionError:
        _LOGGER.warning('Data points per second must be greater than 0, defaulting to 1')
        period = 1.0

    no_of_assets = int(handle['noOfAssets']['value'])
    asset_srl = 0
    cn = 0
    cn_time = time.time()

    loop = asyncio.get_event_loop()
    # Start first time
    _task = Timer(period, run_task, args=(loop, ))
    _task.start()

def plugin_reconfigure(handle, new_config):
    """ Reconfigures the plugin

    Args:
        handle: handle returned by the plugin initialisation call
        new_config: JSON object representing the new configuration category for the category
    Returns:
        new_handle: new handle to be used in the future calls
    """
    _LOGGER.info("Old config for testsample plugin {} \n new config {}".format(handle, new_config))
    # Find diff between old config and new config
    diff = utils.get_diff(handle, new_config)
    # Plugin should re-initialize and restart if key configuration is changed
    if 'dataPointsPerSec' in diff or 'assetName' in diff or 'noOfAssets' in diff:
        plugin_shutdown(handle)
        new_handle = plugin_init(new_config)
        new_handle['restart'] = 'yes'
        _LOGGER.info("Restarting testsample plugin due to change in configuration key [{}]".format(', '.join(diff)))
    else:
        new_handle = copy.deepcopy(new_config)
        new_handle['restart'] = 'no'
    return new_handle


def plugin_shutdown(handle):
    """ Shutdowns the plugin doing required cleanup, to be called prior to the South plugin service being shut down.

    Args:
        handle: handle returned by the plugin initialisation call
    Returns:
        plugin shutdown
    """
    global _task
    if _task is not None:
        _task.cancel()
        _task = None
    _LOGGER.info('testsample plugin shut down.')
