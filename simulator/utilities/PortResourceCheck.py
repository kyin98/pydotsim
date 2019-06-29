#!/usr/bin/env python

import os
import subprocess
import fcntl


class PortResourceCheck(object):
    def __init__(self, start=61001, end=65535):
        # TODO: Temporary hack for testing
        self.free_ports = []
        self.used_ports = []

        for i in range(start, end+1):
            self.free_ports.append(i)

    def get_free_ports(self, num_ports):
        ports = []

        for i in range(num_ports):
            port = self.free_ports.pop(0)
            ports.append(port)
            self.used_ports.append(port)

        return ports

    def release_port(self, ports):
        for port in ports:
            if port in self.used_ports:
                self.used_ports.remove(port)
                self.free_ports.append(port)
