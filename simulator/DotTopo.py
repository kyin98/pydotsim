#!/usr/bin/env python

import pydot
import os
import argparse
from collections import OrderedDict
from logging import getLogger

log = getLogger()

known_node_attributes = set(['vm_type', 'bridge', 'bond', 'links'])

class DotTopo(object):
    def __init__(self, graph=None):
        if graph and isinstance(graph, pydot.Dot):
            self.graph = graph
        elif graph and isinstance(graph, str):
            self.graph = pydot.graph_from_dot_data(graph)
            if self.graph:
                self.graph = self.graph[0]

                # Make sure that the nodes have the custom
                # attributes
                nodes = self.graph.get_nodes()
                for node in nodes:
                    node_attrs = set(node.get_attributes().keys())
                    missing_attrs = known_node_attributes.difference(node_attrs)

                    for attr in missing_attrs:
                        if attr == 'vm_type':
                            node.set(attr, 'default')
                        else:
                            node.set(attr, [])

                    # populate links attribute
                    links = self._populate_links_(node.get_name())
                    for link in links:
                        if link not in node.get('links'):
                            node.get('links').append(link)
        else:
            self.graph = pydot.Dot(graph_type='graph')

    def _populate_links_(self, node_name):
        """
        Method Name:    _populate_links_
                          - Used in the initialization to populate the
                            links attribute field for a given node

        Parameters:     node_name
                          - Name of the node to populate links attribute

        Returns:        list
                          - list of edges associated with the given node
        """
        edges = self.graph.get_edges()
        links = []

        for edge in edges:
            src, sintf = edge.get_source().split(':')
            dst, dintf = edge.get_destination().split(':')

            if (src == node_name) or (dst == node_name):
                links.append(edge)

        return links

    def add_node(self, node_name, vm_type='default', **kwargs):
        """
        Method Name:    add_node
                          - Add a node to the graph

        Parameters:     node_name
                          - Name of the node to be added to the graph.
                            The name should be unique in the graph
                        vm_type
                          - VM type the node will instantiate
                        kwargs
                          - dictionary of other node attributes to be
                            added to 'attributes'

        Returns:        pydot.Node
                          - Created node with the name 'node_name' or
                            the existing node with the name 'node_name'
        """
        # Check if the node exists
        nodes = self.graph.get_node(node_name)
        if nodes:
            log.debug('Node {0} already exists'.format(node_name))
            node = nodes[0]
        else:
            if 'bridges' in kwargs:
                bridges = kwargs.pop('bridges')
            else:
                bridges = []

            if 'bonds' in kwargs:
                bonds = kwargs.pop('bonds')
            else:
                bonds = []

            node = pydot.Node(node_name, vm_type=vm_type, bridges=bridges, 
                              bonds=bonds, **kwargs)
            self.graph.add_node(node)

        return node

    def delete_node(self, node_name):
        """
        Method Name:    delete_node
                          - Remove the node and all of the associated edges
                            from the graph

        Parameter:      node_name
                          - Name of the node to be removed

        Returns:        Boolean
                          - True is returned if the node was deleted.  Otherwise,
                            False is returned
        """
        nodes = self.graph.get_node(node_name)
        if not nodes:
            log.debug('No Node with the name {0} was found'.format(node_name))
            return False
        else:
            # Find all the edges that have this node as a source or destination
            node = nodes[0]
            edges = self.graph.get_edge_list()

            for edge in edges:
                src = edge.get_source()
                dst = edge.get_destination()
                if (node.get_name() in src) or (node.get_name in dst):
                    self.graph.del_edge(src, dst)

        return self.graph.del_node(node_name)

    def add_interface(self, node_name, intf_name):
        """
        Method Name:    add_interfaces
                          - Add a label to a specifc node.  If the node
                            doesn't exist, create the node with the label

        Parameters:     node_name
                          - Name of the node to add the label(interface)
                        intf_name
                          - Name of the label(interface) to add
        """
        nodes = self.graph.get_node(node_name)

        if not nodes:
            node = self.add_node(node_name)
        else:
            node = nodes[0]

        labels = node.get_label()
        if not labels:
            labels = intf_name
        else:
            intfs = labels.split('|')
            if intf_name not in intfs:
                # Add this label to the node
                labels += '|{0}'.format(intf_name)
            else:
                log.debug('This interface {0} already exists'.format(intf_name))
                return

        node.set_label(labels)

    def delete_interface(self, node_name, intf_name):
        """
        Method Name:    delete_interface
                          - Remove the label(interface) and all the associated
                            edges

        Parameters:     node_name
                          - Name of the node that the interfaces is going to
                            be removed
                        intf_name
                          - Name of the interface to be removed
        """
        nodes = self.graph.get_node(node_name)

        if not nodes:
            log.debug('No node with the name {0} was found'.format(node_name))
            return

        node = nodes[0]
        labels = node.get_label()

        intfs = labels.split('|')
        if intf_name not in intfs:
            log.debug('Interface name {0} wasn\'t found in the list of interfaces'.format(intf_name))
            return

        intfs.remove(intf_name)
        node.set_label('|'.join(intfs))

    def get_interfaces(self, node_name):
        """
        Method Name:    get_interfaces
                          - Get the interfaces of a particular node

        Parameters:     node_name
                          - Name of the node whose interfaces to retrieve

        Return          list object
                          - list of interfaces found for the given node.
                            An empty list is returned if not interfaces
                            are found or if there is no node found
        """
        nodes = self.graph.get_node(node_name)

        if not nodes:
            return []
        
        node = nodes[0]
        labels = node.get_label()

        return labels.split('|')

    def add_link(self, local_node, local_intf, remote_node, remote_intf, 
                 **kwargs):
        """
        Method Name:    add_link
                          - Add an edge between the local node and remote
                            node
        """
        # Add an edge to the graph
        edge = pydot.Edge('{0}:{1}'.format(local_node, local_intf), 
                          '{0}:{1}'.format(remote_node, remote_intf),
                          **kwargs)

        self.graph.add_edge(edge)

        for name in [local_node, remote_node]:
            node = self.get_node_from_name(name)
            links = node.get('links')
            if links:
                links.append(edge)
            else:
                node.set('links', [edge])

        return edge

    def delete_link(self, local_node, local_intf, remote_node, remote_intf):
        # TODO: Find the edge in all the associated nodes and remove the edge
        edge = self.get_links(local_node, local_intf, remote_node, remote_intf)
        if edge:
            for name in [local_node, remote_node]:
                node = self.get_node_from_name(name)
                links = node.get('links')
                if links and (edge in links):
                    links.remove(edge[0])

            # Delete edge from the graph
            return self.graph.del_edge('{0}:{1}'.format(local_node, local_intf),
                                       dst='{0}:{1}'.format(remote_node, remote_intf))

    def get_links(self, local_node, remote_node, local_intf=None, remote_intf=None):
        # TODO: Need to handle the reverse case
        if local_intf and remote_intf:
            return self.graph.get_edge('{0}:{1}'.format(local_node, local_intf),
                                       dst='{0}:{1}'.format(remote_node, remote_intf))
        else:
            found_edges = []
            for edge in self.graph.get_edges():
                src_node, src_intf = edge.get_source().split(':')
                dst_node, dst_intf = edge.get_destination().split(':')

                if (((src_node == local_node) and (dst_node == remote_node)) or \
                    ((src_node == remote_node) and (dst_node == local_node))) and \
                   not local_intf and not remote_intf:
                    found_edges.append(edge)
                elif (src_node == local_node) and (dst_node == remote_node) and \
                   local_intf and (local_intf == src_intf) and (not remote_intf):
                    found_edges.append(edge)
                elif (src_node == remote_node) and (dst_node == local_node) and \
                   remote_intf and (remote_intf == src_intf) and (not local_intf):
                    found_edges.append(edge)
                elif (src_node == local_node) and (dst_node == remote_node) and \
                   remote_intf and (remote_intf == dst_intf) and (not local_intf):
                    found_edges.append(edge)
                elif (src_node == remote_node) and (dst_node == local_node) and \
                   local_intf and (local_intf == dst_intf) and (not remote_intf):
                    found_edges.append(edge)

            return found_edges

    def get_links_for_node(self, node_name):
        """
        edges = self.graph.get_edges()
        links = []

        for edge in edges:
            src, sintf = edge.get_source().split(':')
            dst, dintf = edge.get_destination().split(':')

            if (src == node_name) or (dst == node_name):
                links.append(edge)

        return links
        """
        node = self.get_node_from_name(node_name)

        if not node:
            return []
        else:
            links = node.get('links')
            if links:
                return links
            else:
                return []

    def get_node_from_name(self, node_name):
        nodes = self.graph.get_node(node_name)

        if nodes:
            return nodes[0]
        else:
            return None

    def get_nodes(self):
        return self.graph.get_nodes()

    def write_to_file(self):
        pass

    def show(self):
        print self.graph.to_string()
