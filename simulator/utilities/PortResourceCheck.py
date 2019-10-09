#!/usr/bin/env python
# Written by Ken Yin

import os
import subprocess
import fcntl
import logging
import socket
import logging
from simulator.utilities.LogWrapper import getLogger

log = getLogger(__name__)


class PortResourceCheck(object):
    def __init__(self, start=61001, end=65535, directory='/tmp/port_check'):
        self.free_ports = []
        self.used_ports = []

        self.directory = directory
        if not os.path.exists(self.directory):
            log.debug('Creating the directory, {0}, since it didn\'t exist'.format(self.directory))
            os.mkdir(self.directory)
            rv, fp = self.lock_dir(self.directory)

            if rv:
                # Lock for the directory acquired
                for i in range(start, end+1):
                    if self.check_udp_state(i):
                        lock_acquired, fd = self.lock_file("{0}/{1}".format(self.directory, i))
                        if lock_acquired:
                            fd.write('')
                            self.unlock_file(fd)

                            # Add port into the free_ports list
                            self.free_ports.append(i)
                            fd.close()

                self.unlock_dir(fp)
        else:
            # Read all files and find ones that are empty
            for root, dirs, files in os.walk(self.directory):
                for i in files:
                    with open("{0}/{1}".format(root, i), 'r') as f:
                        if not f.read():
                            self.free_ports.append(int(i))

        # Sort the ports
        self.free_ports = sorted(self.free_ports)

    def check_udp_state(self, port):
        u = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        return u.connect_ex(('127.0.0.1', port)) == 0

    def lock_file(self, file_name, op_type='w'):
        fp = open(file_name, op_type)
        try:
            fcntl.lockf(fp, fcntl.LOCK_EX|fcntl.LOCK_NB)
        except IOError as e:
            fp.close()
            return False, -1
        else:
            return True, fp

    def unlock_file(self, fp):
        fcntl.lockf(fp, fcntl.LOCK_UN)
        fp.close()

    def lock_dir(self, directory):
        fp = os.open(directory, os.O_RDONLY)

        try:
            fcntl.flock(fp, fcntl.LOCK_EX|fcntl.LOCK_NB)
        except IOError as e:
            fp.close()
            return False, -1
        else:
            return True, fp

    def unlock_dir(self, dir_fp):
        fcntl.flock(dir_fp, fcntl.LOCK_UN)
        os.close(dir_fp)

    def get_free_ports(self, num_ports, sim_dir=None):
        ports = []

        while len(ports) < num_ports:
            try:
                port = self.free_ports.pop(0)
            except IndexError as e:
                break

            rv, fp = self.lock_file('{0}/{1}'.format(self.directory, port))
            if rv and sim_dir:
                fp.write('{0}'.format(sim_dir))
                self.unlock_file(fp)
                ports.append(port)

                if port not in self.used_ports:
                    self.used_ports.append(port)

        return ports

    def release_port(self, ports, sim_dir=None):
        for port in ports:
            if port in self.used_ports:
                with open('{0}/{1}'.format(self.directory, port), 'r') as fp:
                    if sim_dir:
                        sim_info = fp.read().strip()

                        if sim_info == sim_dir:
                            # This simulation is the owner of the UDP port since it
                            # has the correct sim_info in it
                            rv, fd = self.lock_file('{0}/{1}'.format(self.directory, port))
                            if rv:
                                fd.write('')
                                self.unlock_file(fd)
                                self.used_ports.remove(port)
                                self.free_ports.append(port)
