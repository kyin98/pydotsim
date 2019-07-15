#!/usr/bin/env python

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
from simulator.builders import BuilderBase, BuilderSelector
fro simulator.utilities.ImageDepot import ImageDepot
from collections import OrderedDict
from logging import getLogger

log = getLogger(__name__)


class DotSimulator(object):
    def __init__(self, **kwargs):
        # Set the simulation directory
        if 'sim_dir' in kwargs:
            self.sim_dir = kwargs['sim_dir']
        else:
            unique_id = "".join(random.SystemRandom().choice(string.ascii_uppercase + string.digits) for _ in range(5))
            self.sim_dir = '/tmp/{0}/{1}-{2}/'.format(os.getusername(), self.__class__.__name__, unique_id)

        # Set the Image Depot directory
        if 'image_depot' in kwargs:
            self.image_depot_dir = kwargs['image_depot']
        else:
            self.image_depot_dir = '/media/psf/image_depot'

        self.image_depot = ImageDepot(self.image_depot_dir)

        # The class inheriting DotSimulator should also be
        # inheriting from DotTopo.  This is where self.graph
        # is defined.
        self.builder = BuilderSelector(self.graph, self.sim_dir, self.image_depot).builder

    def configure(self):
        pass

    def run(self):
        self.builder.run()

    def stop(self):
        self.builder.stop()

    def run_from_cmdline(self):
        pass
