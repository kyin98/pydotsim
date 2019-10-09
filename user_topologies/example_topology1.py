#!/usr/bin/env python
from simulator.DotTopo import DotTopo
from simulator.DotSimulator import DotSimulator

# Define a PyDot string to pass in as a parameter
topo_str = """graph G {
r1 [label=swp1];
r2 [label=eth1_1];
r1:swp1 -- r2:eth1_1  [];
}
"""


class TestDynamic(DotTopo, DotSimulator):
    def __init__(self):
        DotTopo.__init__(self, graph=topo_str)
        DotSimulator.__init__(self, image_depot='<PATH for your image repo>')

        # Modifying the PyDot graph that was passed into the instance
        # Change some of the properties for node 'r2'
        r2 = self.get_node_from_name('r2')
        r2.set('vm_type', 'arista')

        # Add a new node 'r3' which is an Arista VM that will connect
        # to node 'r1'
        self.add_node('r3', vm_type='arista')
        self.add_interface('r1', 'swp2')
        self.add_interface('r3', 'eth1_1')

        self.add_link('r1', 'swp2', 'r3', 'eth1_1')

if __name__ == '__main__':
    # Example of running from the command line:
    #     <PATH to pydotsim library>/user_topologies/example_topology1.py --start --loglevel DEBUG
    topo = TestDynamic()
    topo.run_from_cmdline()
