#!/usr/bin/env python 
import os
import subprocess
from simulator.builders import BuilderBase
from simulator.utilities.PortResourceCheck import PortResourceCheck
from logging import getLogger

log = getLogger()

base_ports = 6 # This is 1 port for the SSH, monitor, console, http, https, rest
default_vm_port_types = ['serial', 'monitor', '22', '80', '443', '8080']
kvm_options = { 'serial':   '-serial telnet::{0},server,nowait',
                'monitor':  '-monitor telnet::{0},server,nowait',
                'eth0':     '-net user,dnssearch=cumulus.test,vlan=10,net=192.168.0.15/24',
                'fwd_ports':',hostfwd=tcp::{0}-:{1}'}


class KvmBuilder(BuilderBase):
    preference = 10

    def __init__(self, graph):
        self.graph = graph
        self.nodes = []
        self.port_check = PortResourceCheck()
        log.debug('KVM')

    def _construct_vms_(self):
        total_ports = 0
        for node in self.graph.get_nodes():
            if node.get('vm_type'):
                class_vm_type = vm_type_map[node.get('vm_type')]
            else:
                # TODO: Unrecognized VM Type.  Use default type
                class_vm_type = CumulusVmType

            node.set('class_vm_type', class_vm_type)
            ports_needed = len(self.graph.get_interfaces(node.get_name())) + base_ports
            log.debug('{0} needs {1} UDP ports'.format(node.get_name(), ports_needed))
            ports = self.port_check.get_free_ports(ports_needed)
            node.set('udp_ports', ports)
            build_params = { 'ports': ports,
                             'links': node.get('links'),
                             'name': node.get_name() }

            vm_obj = class_vm_type(**build_params)
            node.set('builder', vm_obj)

    def run(self, sim_dir):
        log.debug('Starting KVMs')

    def stop(self, sim_dir):
        log.debug('Stopping KVMs')

    @staticmethod
    def is_builder_supported():
        return True


class DefaultVmType(object):
    def __init__(self, **kwargs):
        self.params = {}
        self.index = 0

        if 'ports' in kwargs:
            self.ports = kwargs.get('ports')
        else:
            self.ports = []

        if 'fwd_ports' in kwargs:
            self.fwd_ports = kwargs.get('fwd_ports')
        else:
            self.fwd_ports = []

        if 'links' in kwargs:
            self.links = kwargs['links']
        else:
            self.links = []

        if 'name' in kwargs:
            self.name = kwargs['name']
        else:
            self.name = 'noname'

        for i, port_type in enumerate(default_vm_port_types):
            self.params[port_type] = self.ports[i]
            self.index = i

        for port in self.fwd_ports:
            if 'fwd_ports' not in self.params:
                self.params['fwd_ports'] = []

            self.index += 1
            self.params['fwd_ports'].append((self.ports[self.index], port))

        # Assign ports to the node's links
        for link in self.links:
            if self.name == link.get_source().split(':')[0]:
                self.index += 1
                link.set('local_port', self.ports[self.index])
            elif self.name == link.get_destination().split(':')[0]:
                self.index += 1
                link.set('remote_port', self.ports[self.index])

    def build_kvm_cmdline(self):
        cmd = ['sudo', '/usr/bin/kvm', '-enable-kvm']

        for port_type in ['serial', 'monitor']:
            cmd.append(kvm_options[port_type].format(self.params[port_type]))

        # Build the eth0 parameters
        fwd_port_str = ""
        for port_type in default_vm_port_types[2:]:
            fwd_port_str += kvm_options['fwd_ports'].format(self.params[port_type], port_type)

        cmd.append(kvm_options['eth0']+fwd_port_str)

        return cmd


class CumulusVmType(DefaultVmType):
    image = 'cumulus-3.7'
    pass


class CiscoVmType(object):
    pass


class AristaVmType(object):
    pass


vm_type_map = { 'cumulus':  CumulusVmType,
                'cisco':    CiscoVmType,
                'arista':   AristaVmType,
                'default':  CumulusVmType }

