#!/usr/bin/env python 
import os
import subprocess
import yaml
import psutil
from simulator.builders import BuilderBase
from simulator.utilities.PortResourceCheck import PortResourceCheck
from logging import getLogger

log = getLogger(__name__)

base_ports = 6 # This is 1 port for the SSH, monitor, console, http, https, rest
default_vm_port_types = ['serial', 'monitor', '22', '80', '443', '8080']
kvm_options = { 'serial':   '-serial telnet::{0},server,nowait',
                'monitor':  '-monitor telnet::{0},server,nowait',
                'eth0':     '-net user,vlan=10,net=192.168.0.15/24',
                'nic':      '-net nic,vlan=10,macaddr={0},model=virtio',
                'fwd_ports':',hostfwd=tcp::{0}-:{1}',
                'links':    '-netdev socket,udp={daddr}:{dport},localaddr={saddr}:{sport},id=dev{dev} ' + \
                            '-device virtio-net-pci,mac={mac},addr={slot}.{function},multifunction={multifunction},netdev=dev{dev},id={name}',
                'image':    '-drive file={0},if=virtio,werror=report',
                'cores':    '-smp {0}',
                'ram':      '-m {0}'}


class NoMorePciSlots(Exception):
    pass


class NoSimDir(Exception):
    pass


class NoQcow2Image(Exception):
    pass


class KvmBuilder(BuilderBase):
    preference = 10

    def __init__(self, graph, sim_dir, image_depot):
        self.topology = graph
        self.sim_dir = sim_dir
        self.image_depot = image_depot
        self.nodes = {}
        self.port_check = PortResourceCheck()
        log.debug('KvmBuilder')

        if self.topology:
            self._construct_vms_()

    def _construct_vms_(self):
        total_ports = 0
        for node in self.toology.get_nodes():
            if node.get('vm_type'):
                class_vm_type = vm_type_map[node.get('vm_type')]
            else:
                # TODO: Unrecognized VM Type.  Use default type
                class_vm_type = CumulusVmType

            if node.get('image'):
                vm_image = node.get('image')
            else:
                vm_image = class_vm_type.image

            ports_needed = len(self.topology.get_interfaces(node.get_name())) + base_ports
            log.debug('{0} needs {1} UDP ports'.format(node.get_name(), ports_needed))
            ports = self.port_check.get_free_ports(ports_needed)
            node.set('udp_ports', ports)
            build_params = { 'ports': ports,
                             'links': self.topology.get_links_for_node(node.get_name()),
                             'name': node.get_name(),
                             'node_id': node.get('id'),
                             'base_sim_dir': self.sim_dir,
                             'base_image': self.image_depot.get_qcow2_image(vm_image)}

            vm_obj = class_vm_type(**build_params)
            self.nodes[node.get_name()] = vm_obj

    def run(self):
        log.debug('Starting KVMs')
        for node in self.topology.get_nodes():
            cmds = self.nodes[node.get_name()].build_kvm_cmdline()
            log.debug(" ".join(cmds))
            pid = subprocess.Popen(" ".join(cmds), shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            log.debug('PID for node {0}: {1}'.format(node.get_name(), pid.pid))
            node.set('pid', pid.pid)

        with open('{0}/topo.yaml'.format(self.sim_dir), 'w') as stream:
            yaml.dump(self.topology.graph, stream)

    def stop(self):
        log.debug('Stopping KVMs')

        with open('{0}/topo.yaml'.format(self.sim_dir), 'r') as stream:
            topo = yaml.load(stream)

        for node in topo.get_nodes():
            if node.get('pid'):
                try:
                    if isinstance(node.get('pid'), psutil.Process):
                        self._kill_child_pid_(node.get('pid'))
                    elif isinstance(node.get('pid'), int):
                        self._kill_child_pid_(psutil.Process(node.get('pid')))
                    elif isinstance(node.get('pid'), subprocess.Popen):
                        self._kill_child_pid_(psutil.Process(node.get('pid').pid))
                except psutil.NoSuchProcess:
                    log.debug('PID {0} is defunct'.format(node.get('pid')))
                    continue

    def _kill_child_pid_(self, pid):
        if not pid.children():
            log.debug('Killing PID: {0}'.format(pid.pid))
            subprocess.Popen(['sudo', 'kill', '-9', '{0}'.format(pid.pid)], 
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return
        else:
            for c in pid.children():
                self._kill_child_pid_(c)

    @staticmethod
    def is_builder_supported():
        return True


class DefaultVmType(object):
    def __init__(self, **kwargs):
        self.params = {}
        self.index = 0

        if 'base_sim_dir' in kwargs:
            self.base_sim_dir = kwargs.get('base_sim_dir')

            if os.path.exists(self.base_sim_dir) and \
               os.path.isdir(self.base_sim_dir):
                log.debug('Using the base directory of {0}'.format(self.base_sim_dir))
            else:
                raise NoSimDir('There is a problem with the provided directory {0}'.format(self.base_sim_dir))
        else:
            raise NoSimDir('No simulation directory was indicated')

        if 'base_image' in kwargs:
            self.base_image = kwargs.get('base_image')
            if not self.base_image:
                raise NoQcow2Image('The Image depot couldn\'t find an image')
        else:
            raise NoQcow2Image('There was no QCOW2 image found')

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

        if 'node_id' in kwargs:
            self.node_id = kwargs['node_id']
        else:
            self.node_id = 0

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

        if 'cores' in kwargs:
            self.cores = kwargs.get('cores')
        else:
            self.cores = 2

        if 'ram' in kwargs:
            self.ram = kwargs.get('ram')
        else:
            self.ram = 2048

    def create_backer_image(self):
        if not os.path.exists(os.path.join(self.base_sim_dir, self.name)):
            os.makedirs(os.path.join(self.base_sim_dir, self.name))

        cmd = ['sudo', 'qemu-img', 'create', '-b', self.base_image, '-f', 'qcow2',
               '{0}/{1}.qcow2'.format(os.path.join(self.base_sim_dir, self.name), self.name)]

        log.debug('backer cmd: {0}'.format(" ".join(cmd)))
        subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        return '{0}/{1}.qcow2'.format(os.path.join(self.base_sim_dir, self.name), self.name)

    def get_pci_info(self, idx):
        base_pci_slot = 6
        pci_slot = base_pci_slot + (idx/8)
        pci_function = idx % 8
        multifunction = "on" if pci_function == 0 else "off"

        if pci_slot > 31:
            raise NoMorePciSlots('No more PCI slots available to add interfaces')

        return pci_slot, pci_function, multifunction

    def get_eth0_mac(self):
        return "00:0a:00:{0:02x}:{1:02x}:00".format((self.node_id >> 8) & 0xff, self.node_id & 0xff)

    def get_intf_mac(self, intf_id):
        return "00:02:00:{0:02x}:{1:02x}:{2:02x}".format((self.node_id >> 8) & 0xff, self.node_id & 0xff, intf_id & 0xff)

    def build_kvm_cmdline(self):
        cmd = ['sudo', '/usr/bin/kvm', '-enable-kvm', '-nographic', 
               '-name {0}'.format(self.name)]

        for port_type in ['serial', 'monitor']:
            cmd.append(kvm_options[port_type].format(self.params[port_type]))

        # Build the eth0 parameters
        fwd_port_str = ""
        for port_type in default_vm_port_types[2:]:
            fwd_port_str += kvm_options['fwd_ports'].format(self.params[port_type], port_type)

        cmd.append(kvm_options['eth0']+fwd_port_str)
        cmd.append(kvm_options['nic'].format(self.get_eth0_mac()))

        cmd.append(kvm_options['cores'].format(self.cores))
        cmd.append(kvm_options['ram'].format(self.ram))

        # Create a backer image
        #cmd.append(kvm_options['image'].format(self.image))
        cmd.append(kvm_options['image'].format(self.create_backer_image()))

        for i, link in enumerate(self.links):
            slot, func, multifunc = self.get_pci_info(i)

            link_params = {'daddr': '127.0.0.1',
                           'saddr': '127.0.0.1',
                           'mac': self.get_intf_mac(i),
                           'slot': slot,
                           'function': func,
                           'multifunction': multifunc,
                           'dev': i}

            if self.name == link.get_source().split(':')[0]:
                sport = link.get('local_port')
                dport = link.get('remote_port')
                name = link.get_source().split(':')[1]
            elif self.name == link.get_destination().split(':')[0]:
                sport =link.get('remote_port')
                dport = link.get('local_port')
                name = link.get_destination().split(':')[1]

            link_params['sport'] = sport
            link_params['dport'] = dport
            link_params['name'] = name

            cmd.append(kvm_options['links'].format(**link_params))

        return cmd


class CumulusVmType(DefaultVmType):
    image = 'cumulus-3.7.6'
    pass


class CiscoVmType(object):
    pass


class AristaVmType(object):
    pass


vm_type_map = { 'cumulus':  CumulusVmType,
                'cisco':    CiscoVmType,
                'arista':   AristaVmType,
                'default':  CumulusVmType }

