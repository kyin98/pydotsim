#!/usr/bin/env python

import os
import pydot
import psutil
import subprocess
import importlib
import pkgutil
import inspect
import apt
from simulator.builders import BuilderBase, BuilderSelector
from collections import OrderedDict
from logging import getLogger

log = getLogger()


class DotSimulator(object):
    def __init__(self):
        self.builder = BuilderSelector(iself.graph).builder

    def configure(self):
        pass

    def run(self):
        self.builder.run()

    def stop(self):
        self.builder.stop()
