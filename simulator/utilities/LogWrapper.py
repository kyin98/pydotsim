#!/usr/bin/env python
# Written by Ken Yin

import logging

def getLogger(name=None):
    """
    Function Name:      getLogger

    Parameter:          name
                         - Name of the logger, If none is given, it will be 
                           the root logger

    Description:        This is a wrapper for logging.getLogger.  If there
                        are no handlers for itself or for the parent logger,
                        the basic configuration will be set with the following
                        format:
                            YYYY-mm-dd HH:MM:SS,NN <log level>:<log name>: <msg>
    """
    log = logging.getLogger(name)

    if (not log.handlers) and (not log.parent.handlers):
        FORMAT = "%(asctime)s:%(levelname)7s:%(name)24s: %(message)s"
        logging.basicConfig(format=FORMAT, level=logging.INFO)

    return log
