#!/usr/bin/env python

import os
import logging

log = logging.getLogger(__name__)


class NoDepotPath(Exception):
    pass


class DepotPathNonExistant(Exception):
    pass


class UnknownVmType(Exception):
    pass


class ImageDepot(object):
    def __init__(self, depot_location):
        self.depot = depot_location
        self.vm_types = {}

        if not self.depot:
            log.warn('No Image Depot was given!')
            raise NoDepotPath('No path to the depot was passed in')
        elif not (self.depot and os.path.exists(self.depot)):
            log.warn('Path for the Image Depot doesn\'t exist')
            raise DepotPathNonExistant('{0} wasn\'t found'.format(self.depot))
        else:
            self.depot = os.path.realpath(self.depot)

            # Find all the VM types that are supported
            for image_type in os.listdir(self.depot):
                # Check if there are any files in the sub-directories
                check = False
                for dpath, dname, dfiles in os.walk(os.path.join(self.depot, image_type)):
                    if dfiles:
                        check = True
                        break

                if check:
                    self.vm_types[image_type] = []
                    version_dir = os.path.join(self.depot, image_type)
                    for image_version in os.listdir(version_dir):
                        self.vm_types[image_type].append(image_version)

    def get_qcow2_image(self, image):
        vm_type, vm_version = image.split('-')

        if vm_type not in self.vm_types:
            raise UnknownVmType('Couldn\'t find an image directory'
                                ' for {0} in {1}'.format(vm_type, self.depot))

        vm_path = ''
        for dpath, dname, dfiles in os.walk(os.path.join(self.depot,vm_type,vm_version)):
            for dfile in dfiles:
                image_found = False
                if dfile.endswith('qcow2'):
                    image_found = True
                    vm_path = '{0}/{1}'.format(dpath, dfile)
                    break

                if image_found:
                    break

        if vm_path:
            return vm_path
        else:
            log.warn('No path with image found')
            return None

    def get_vagrant_image(self, image):
        # TODO: Find Vagrant image and install it into Vagrant
        pass
