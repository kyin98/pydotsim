#!/usr/bin/env python 
# Written by Ken Yin

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
    """
    Class Name:         KvmBuilder
    Description:        This class defines how to build the simulation using KVM/QEMU.
                        The VMs are brought up by using the raw '/usr/bin/kvm' command
                        found in the system.
    """
    preference = 10

    def __init__(self, graph, sim_dir, image_depot):
        self.topology = graph
        self.sim_dir = sim_dir
        self.image_depot = image_depot
        self.nodes = {}
        self.port_check = PortResourceCheck()
        log.debug('KvmBuilder')

    def _construct_vms_(self):
        total_ports = 0
        for node in self.topology.get_nodes():
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
            ports = self.port_check.get_free_ports(ports_needed, sim_dir=self.sim_dir)
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
        """
        Method Name:        run

        Parameters:         None

        Description:        Startup the VM associated with the topology.
                            Then, dump the pydot graph into a YAML file
                            for use by other processes.
        """
        log.debug('Starting KVMs')
        self._construct_vms_()

        for node in self.topology.get_nodes():
            cmds = self.nodes[node.get_name()].build_kvm_cmdline()
            log.debug(" ".join(cmds))
            pid = subprocess.Popen(" ".join(cmds), shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            log.debug('PID for node {0}: {1}'.format(node.get_name(), pid.pid))
            node.set('pid', pid.pid)

        with open('{0}/topo.yaml'.format(self.sim_dir), 'w') as stream:
            yaml.dump(self.topology.graph, stream)

    def stop(self, run_from_cmd_line=True):
        """
        Method Name:        stop

        Parameters:         run_from_cmd_line
                             - Boolean value indicating if the stop was called
                               by a different processes

        Description:        Stop a simulation in a given simulation directory.
                            This directory must contain the 'topo.yaml' file
                            that was created when the method 'run' was called.
        """
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

            if node.get('udp_ports'):
                if run_from_cmd_line:
                    # If 'stop' is called from the command line, then the 'used_ports'
                    # variable won't have any values in it.  So, we need to populate
                    # the variables
                    self.port_check.used_ports += node.get('udp_ports')

                    for link in self.topology.get_links_for_node(node.get_name()):
                        for name in ['local_port', 'remote_port']:
                            port = link.get(name)
                            if port:
                                self.port_check.used_ports.append(port)

                    self.port_check.used_ports = list(set(self.port_check.used_ports))

                self.port_check.release_port(node.get('udp_ports'), sim_dir=self.sim_dir)

    def _kill_child_pid_(self, pid):
        """
        Method Name:        _kill_child_pid_

        Parameters:         pid
                             - psutil.Process object for a specific PID

        Description:        Find the children PIDs for the giev PID and kill
                            it when found.  The parent PIDs should naturally
                            terminate when all the children are killed.
        """
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
    """
    Class Name:     DefaultVmType
    Description:    Base VM class which other VM class types can
                    inherit and overload methods.  This class has
                    been implemented for KVM/QEMU specifically and
                    most likely won't work for other builder types.
    """
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
        """
        Method Name:        create_backer_image

        Parameters:         None

        Description:        Create the QEMU backer image that the simulation will use.
        """
        if not os.path.exists(os.path.join(self.base_sim_dir, self.name)):
            os.makedirs(os.path.join(self.base_sim_dir, self.name))

        cmd = ['sudo', 'qemu-img', 'create', '-b', self.base_image, '-f', 'qcow2',
               '{0}/{1}.qcow2'.format(os.path.join(self.base_sim_dir, self.name), self.name)]

        log.debug('backer cmd: {0}'.format(" ".join(cmd)))
        subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        return '{0}/{1}.qcow2'.format(os.path.join(self.base_sim_dir, self.name), self.name)

    def get_pci_info(self, idx):
        """
        Method Name:        get_pci_info

        Parameters:         idx
                             - The index number of the interface

        Description:        Return a unique PCI slot and multifunction value
                            for a node.  This will be used when creating the
                            interfaces on the KVM command line
        """
        base_pci_slot = 6
        pci_slot = base_pci_slot + (idx/8)
        pci_function = idx % 8
        multifunction = "on" if pci_function == 0 else "off"

        if pci_slot > 31:
            raise NoMorePciSlots('No more PCI slots available to add interfaces')

        return pci_slot, pci_function, multifunction

    def get_eth0_mac(self):
        """
        Method Name:        get_eth0_mac

        Parameters:         None

        Description:        Set the MAC address for 'eth0' based on the 'node_id' since it should
                            be unique
        """
        return "00:0a:00:{0:02x}:{1:02x}:00".format((self.node_id >> 8) & 0xff, self.node_id & 0xff)

    def get_intf_mac(self, intf_id):
        """
        Method Name:        get_intf_mac

        Parameters:         intf_idx
                                - The index for the interface which the MAC address is getting set

        Description:        Set the MAC address for an interface based on the interface index.  The
                            MAC address is based on the 'node id' and 'interface id' since this should
                            yield a unique pair
        """
        return "00:02:00:{0:02x}:{1:02x}:{2:02x}".format((self.node_id >> 8) & 0xff, self.node_id & 0xff, intf_id & 0xff)

    def _build_common_kvm_options_(self):
        """
        Method Name:        _build_common_kvm_options_

        Parameters:         None

        Description:        Build some of the common options that some of the
                            others KVM command line need.
        """
        cmd = ['sudo', '/usr/bin/kvm', '-enable-kvm', '-nographic', 
               '-name {0}'.format(self.name), '-cpu host']

        for port_type in ['serial', 'monitor']:
            cmd.append(kvm_options[port_type].format(self.params[port_type]))

        cmd.append(kvm_options['cores'].format(self.cores))
        cmd.append(kvm_options['ram'].format(self.ram))

        return cmd

    def _build_kvm_intfs_(self):
        """
        Method Name:        _build_kvm_intfs_

        Parameters:         None

        Description:        Builds the KVM command line option for
                            the VM's interfaces using UDP sockets.
        """
        cmd = []

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

    def build_kvm_cmdline(self):
        """
        Method Name:        build_kvm_cmdline

        Parameters:         None

        Description:        This method creates the command line to be used to start this particular
                            node.
        """
        cmd = self._build_common_kvm_options_()
        cmd += self._build_kvm_intfs_()

        # Build the eth0 parameters
        fwd_port_str = ""
        for port_type in default_vm_port_types[2:]:
            fwd_port_str += kvm_options['fwd_ports'].format(self.params[port_type], port_type)

        cmd.append(kvm_options['eth0']+fwd_port_str)
        cmd.append(kvm_options['nic'].format(self.get_eth0_mac()))

        # Create a backer image
        cmd.append(kvm_options['image'].format(self.create_backer_image()))

        return cmd


class CumulusVmType(DefaultVmType):
    """
    Class Name:     CumulusVmType
    Description:    Class for a Cumulus Networks node.
    """
    # Define the default image version to use if one isn't given
    image = 'cumulus-3.7.6'
    pass


class CiscoVmType(DefaultVmType):
    """
    Class Name:     CiscoVmType
    Description:    This class is for a Cisco NXOSV node.  It implements
                    building the KVM command line that is needed to run
                    a NXOSV VM in KVM.
    """
    image = 'cisco_nxosv-7.0.3'

    def __init__(self, **kwargs):
        super(CiscoVmType, self).__init__(**kwargs)
        self.links_format = "-netdev socket,udp={daddr}:{dport},localaddr={saddr}:{sport},id=dev{dev} " + \
                            "-device e1000,addr={slot}.{function}," + \
                            "multifunction={multifunction},netdev=dev{dev},id={name}"
        self.mgmt_intf_format = '-netdev user,net=192.168.0.15/24'

        # Some of the Cisco VMs need more than 4 cores and 8G of RAM to run
        if self.cores < 4:
            self.cores = 4

        if self.ram < 8192:
            self.ram = 8192

    def build_kvm_cmdline(self):
        """
        Method Name:        build_kvm_cmdline

        Parameters:         None

        Description:        This method creates the command line to be used to start the Cisco NXOSV
                            node.  The NXOSV KVM needs to have the options set in a specific order
                            for the VM to come up correctly
        """
        cmd = ['sudo', '/usr/bin/kvm', '-enable-kvm', '-cpu host']

        # Get UEFI BIOS image.  Assuming that the UEFI bios image
        # name is 'bios.bin' and that it is in the same directory
        # as the base image.  Change this if this isn't true.
        img_dir = '/'.join(self.base_image.split('/')[:-1])
        cmd.append('-bios {0}/bios.bin '.format(img_dir))

        for port_type in ['serial', 'monitor']:
            cmd.append(kvm_options[port_type].format(self.params[port_type]))

        # Build the eth0 parameters
        fwd_port_str = ""
        for port_type in default_vm_port_types[2:]:
            fwd_port_str += kvm_options['fwd_ports'].format(self.params[port_type], port_type)

        cmd.append(self.mgmt_intf_format+fwd_port_str+',id=mgmt0')

        # Create backer image
        img_options = '-device ahci,id=ahci0,bus=pci.0,multifunction=on '
        img_options += '-drive file={0},if=none,id=drive-sata-disk0,format=qcow2 '.format(self.create_backer_image())
        img_options += '-device ide-drive,bus=ahci0.0,drive=drive-sata-disk0'

        cmd.append(img_options)

        cmd.append('-nographic')
        cmd.append(kvm_options['cores'].format(self.cores))
        cmd.append(kvm_options['ram'].format(self.ram))

        # Build backend parameters for the mgmt port
        mgmt_str = '-device e1000,netdev=mgmt0,mac={0}'.format(self.get_eth0_mac())
        cmd.append(mgmt_str)

        cmd.append('-name {0}'.format(self.name))

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

            cmd.append(self.links_format.format(**link_params))

        return cmd


class AristaVmType(DefaultVmType):
    """
    Class Name:     AristaVmType
    Description:    This class is for a Arista EOS Lab node.  It implements
                    building the KVM command line that is needed to run
                    an Arista EOS Lab VM in KVM.
    """
    image = 'arista_eos-4.21.3'

    def __init__(self, **kwargs):
        super(AristaVmType, self).__init__(**kwargs)
        self.image = '-hda {0}'

    def build_kvm_cmdline(self):
        """
        Method Name:        build_kvm_cmdline

        Parameters:         None

        Description:        This method creates the command line to be used to start an Arista
                            node.
        """
        cmd = self._build_common_kvm_options_()
        cmd += self._build_kvm_intfs_()

        # Build the eth0 parameters
        fwd_port_str = ""
        for port_type in default_vm_port_types[2:]:
            fwd_port_str += kvm_options['fwd_ports'].format(self.params[port_type], port_type)

        cmd.append(kvm_options['eth0']+fwd_port_str)
        cmd.append(kvm_options['nic'].format(self.get_eth0_mac()))

        # Create a backer image
        cmd.append(self.image.format(self.create_backer_image()))

        return cmd

vm_type_map = { 'cumulus':  CumulusVmType,
                'cisco':    CiscoVmType,
                'arista':   AristaVmType,
                'default':  CumulusVmType }

