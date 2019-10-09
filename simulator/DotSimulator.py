#!/usr/bin/env python
# Written by Ken Yin

import os
import pydot
import psutil
import subprocess
import importlib
import pkgutil
import inspect
import apt
import argparse
import random
import string
from simulator.builders import BuilderBase, BuilderSelector
from simulator.utilities.ImageDepot import ImageDepot
from collections import OrderedDict
#from logging import getLogger
import logging
import sys
from simulator.utilities.LogWrapper import getLogger

log = getLogger(__name__)


class DotSimulator(object):
    def __init__(self, **kwargs):
        # Set the simulation directory
        if 'sim_dir' in kwargs:
            self.sim_dir = kwargs['sim_dir']
        else:
            unique_id = "".join(random.SystemRandom().choice(string.ascii_uppercase + string.digits) for _ in range(5))
            if not os.path.exists('/tmp/{0}'.format(os.getlogin())):
                os.mkdir('/tmp/{0}'.format(os.getlogin()))

            self.sim_dir = '/tmp/{0}/{1}-{2}/'.format(os.getlogin(), self.__class__.__name__, unique_id)
            os.mkdir(self.sim_dir)

        # Set the Image Depot directory
        if 'image_depot' in kwargs:
            self.image_depot_dir = kwargs['image_depot']
        else:
            self.image_depot_dir = '/media/psf/image_depot'

        self.image_depot = ImageDepot(self.image_depot_dir)

        # The class inheriting DotSimulator should also be
        # inheriting from DotTopo.  This is where self.graph
        # is defined.
        self.builder = BuilderSelector(self, self.sim_dir, self.image_depot).builder

    def configure(self):
        pass

    def run(self):
        self.builder.run()

    def stop(self):
        self.builder.stop()

    def run_from_cmdline(self):
        parser = argparse.ArgumentParser(description='Start/Stop PyDotSimulator')

        parser.add_argument('--info', action='store_true', help='Display the PyDot topology', default=None)
        parser.add_argument('--start', action='store_true', help='Start the PyDot topology', default=None)
        parser.add_argument('--stop', action='store_true', help='Stop the PyDot topology', default=None)
        parser.add_argument('--loglevel', help='Set the logging level of the output', choices=['DEBUG', 'INFO', 'WARN', 'ERROR'], default='INFO')
        parser.add_argument('--dir', help='Directory that the simulation run/stores info', default=None)
        parser.add_argument('--image-depot', help='Directory that stores all the base VM images', default=None)

        args = parser.parse_args()

        if args.loglevel == 'DEBUG':
            level = logging.DEBUG
        elif args.loglevel == 'ERROR':
            level = logging.ERROR
        elif args.loglevel == 'WARN':
            level = logging.WARN
        else:
            level = logging.INFO

        # Set Logger
        logging.getLogger().setLevel(level)
        FORMAT = "%(asctime)s:%(levelname)7s:%(name)24s: %(message)s" 
        logging.basicConfig(format=FORMAT)

        if args.image_depot:
            if os.path.exists(args.image_depot):
                self.image_depot = args.image_depot
            else:
                log.info('The image depot {0} isn\'t a directory'.format(args.image_depot))
                sys.exit(1)

        if args.info:
            log.info(self.show())

        if args.start and (not args.stop):
            log.debug("Starting Simulation in the directory: {0}".format(self.sim_dir))
            self.run()
        elif args.stop and (not args.start) and args.dir:
            log.debug('Stopping Simultion in {0}'.format(args.dir))
            self.sim_dir = args.dir

            # Check if the simulation directory ends with '/'
            if not self.sim_dir.endswith('/'):
                self.sim_dir += '/'

            self.builder.sim_dir = self.sim_dir
            self.stop()
