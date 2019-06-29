#!/usr/bin/env python

import os
import pkgutil
import inspect
import apt
import subprocess
import importlib


class NoBuildersSupported(Exception):
    pass


class BuilderBase(object):
    """
    Class:          BuilderBase
    Description:    All VM builder classes should inherit from this
                    base class.  However, this class should never be
                    instantiated itself.
    """
    # The preference will be used to determine which builder sub-class
    # to choose
    preference=100

    @staticmethod
    def is_builder_supported(self):
        raise NotImplemented('"is_builder_supported" wasn\'t implemented!')


class BuilderSelector(object):
    """
    Class:          BuildSelector
    Description:    This class will go through all of the supported VM builders
                    and determine which one it will use on the current system.
                    The VM builder that has the lowest prefernce and is supported
                    will be the one that is chosen.
    """
    def __init__(self, graph):
        self.graph = graph

        current_path = os.path.dirname(os.path.realpath(__file__))
        imp_mod = importlib.import_module

        # Get all of the user defined modules for the underlying
        # simulation support
        sim_blocks = [imp_mod('simulator.builders.{0}'.format(modname)) for _, modname, _
                      in pkgutil.iter_modules([current_path])
                      if not modname.startswith('_')]

        builders = []
        for builder_mod in sim_blocks:
            #builders = [builder for _, builder in inspect.getmembers(builder_mod)
            #            if isinstance(builder, type) and builder != BuilderBase
            #            and issubclass(builder, BuilderBase)]

            for _, builder in inspect.getmembers(builder_mod):
                if isinstance(builder, type) and (builder != BuilderBase) and \
                   issubclass(builder, BuilderBase):
                    builders.append(builder)

        preference_check = apt.apt_pkg.version_compare

        # Pick the builder with the lowest preference
        builders.sort(preference_check, key=lambda _builder: _builder.preference)

        for builder in builders:
            if builder.is_builder_supported():
                self.builder = builder(self.graph)
                break
        else:
            raise NoBuildersSupported('Couldn\'t find any builders that are '
                                      'supported on this device')
