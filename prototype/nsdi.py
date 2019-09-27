#!/usr/bin/python3

import pygraphviz
import config

class Graph:
    def __init__(self):
        self._graph = pygraphviz.AGraph(strict=False, directed=True)

    def render(self, file_path):
        self._graph.layout(prog='dot')
        self._graph.draw(file_path, prog='dot')

    def add_vertex(self, name, color='black', subgraph=None):
        if (subgraph is not None):
            subgraph.add_node(name, color=color, fontcolor=color)
        else:
            self._graph.add_node(name, color=color, fontcolor=color)

    def get_vertex(self, name):
        return self._graph.get_node(name)

    def add_edge(self, src, dst, combine=False, color='black', style='solid'):
        if (combine and self._graph.has_edge(dst, src)):
            self._graph.get_edge(dst, src).attr['dir'] = 'both'
        else:
            self._graph.add_edge(src, dst, color=color, style=style)

    def has_edge(self, src, dst, either=False):
        return (self._graph.has_edge(src, dst) or
                (either and self.graph.has_edge(dst, src)))

    def add_subgraph(self, name=None, color='black'):
        subgraph = self._graph.add_subgraph(name=name, rank='same')
        subgraph.node_attr['color'] = color
        subgraph.node_attr['fontcolor'] = color
        return subgraph

class Physical(Graph):
    def __init__(self, net):
        super().__init__()
        for router in net.routers.values():
            for iface in router.ifaces.values():
                self.add_edge(router.name, iface.neighbor.router.name, True)

class RAG(Graph):
    def __init__(self, net, subnet=None):
        super().__init__()
        self._subnet = subnet
        self._ospf_sub = self.add_subgraph("ospf", color="green")
        self._bgp_sub = self.add_subgraph("bgp", color="orange")
        self._subnet_sub = self.add_subgraph("subnet", color="red")
        for router in net.routers.values():
            if (router.ospf is not None):
                self.add_vertex(self.ospf_name(router), color='green', 
                    subgraph=self._ospf_sub)
            if (router.bgp is not None):
                self.add_vertex(self.bgp_name(router), color='orange', 
                    subgraph=self._bgp_sub)

        if (subnet is not None):
            self.add_vertex(subnet, subgraph=self._subnet_sub)

        for router in net.routers.values():
            if (router.ospf is not None):
                self.add_ospf_adjacencies(router)
                if (subnet in router.ospf.origins):
                    self.add_edge(subnet, self.ospf_name(router), color="red")
            if (router.bgp is not None):
                self.add_bgp_adjacencies(router)
                if (subnet in router.bgp.origins):
                    self.add_edge(subnet, self.bgp_name(router), color="red")

    def taint(self):
        if (self._subnet is not None):
            vertex = self.get_vertex(self._subnet)
            vertex.attr["fontcolor"] = "red"
            self.propagate_taint(vertex)

    def propagate_taint(self, vertex, noibgp=False):
        if vertex.attr["color"] == "red":
            return

        vertex.attr["color"] = "red"

        for edge in self._graph.out_edges(vertex):
            ibgp = (edge.attr["style"] == "dashed")
            if (not (ibgp and noibgp)):
                edge.attr["color"] = "red"
                self.propagate_taint(edge[1], ibgp)

    def is_tainted(self, process):
        if (type(process) is config.Ospf):
            vertex_name = self.ospf_name(process.router)
        elif (type(process) is config.Bgp):
            vertex_name = self.bgp_name(process.router)
        return (self.get_vertex(vertex_name).attr["color"] == "red")

    def add_ospf_adjacencies(self, router):
        for vlan in router.ospf.active_vlans:
            for iface in vlan.ifaces:
                if (iface.neighbor.vlan.num == vlan.num 
                        and iface.neighbor.router.ospf is not None):
                    # FIXME: handle OSPF adjacencies with multiple L2 hops
                    self.add_edge(self.ospf_name(router), 
                            self.ospf_name(iface.neighbor.router), 
                            color="green")

    def add_bgp_adjacencies(self, router):
        for neighbor in router.bgp.external:
            self.add_edge(self.bgp_name(router), 
                    self.bgp_name(neighbor.iface.router), color="orange")
        for neighbor in router.bgp.internal:
            self.add_edge(self.bgp_name(router), 
                    self.bgp_name(neighbor.iface.router), color="orange",
                    style="dashed")

    def ospf_name(self, router):
        return "%s:OSPF" % (router.name)

    def bgp_name(self, router):
        return "%s:BGP" % (router.name)


class RPG(Graph):
    def __init__(self, net, subnets=None, rag=None):
        super().__init__()

        self._t = self._s = None
        self._rag = None
        if (subnets is not None):
            self._t, self._s = subnets
            self._rag = rag

        self._subnet_sub = self.add_subgraph("subnet", color="red")
        self._bgp_sub = self.add_subgraph("bgp", color="orange")
        self._ospf_sub = self.add_subgraph("ospf", color="green")
        self._vlan_sub = self.add_subgraph("vlan", color="blue")

        for router in net.routers.values():
            self.add_vlan_vertices(router)
            if (router.ospf is not None):
                self.add_ospf_vertices(router)
            if (router.bgp is not None):
                self.add_bgp_vertices(router)

        if (self._t is not None):
            self.add_vertex(self._t, subgraph=self._subnet_sub, color="red")
            self.add_vertex(self._s, subgraph=self._subnet_sub, color="red")

        for router in net.routers.values():
            self.add_vlan_to_vlan_edges(router)
            self.add_vlan_to_subnet_edges(router)
            if (router.ospf is not None):
                self.add_ospf_to_vlan_edges(router)
                self.add_subnet_to_ospf_edges(router)
                self.add_vlan_to_ospf_edges(router)
            if (router.bgp is not None):
                self.add_bgp_to_vlan_ospf_edges(router)
                self.add_subnet_to_bgp_edges(router)
                self.add_vlan_to_bgp_edges(router)

    def add_vlan_vertices(self, router):
        for vlan in router.vlans.values():
            self.add_vertex(self.vlan_name(vlan), color='blue',
                    subgraph=self._vlan_sub)

    def add_ospf_vertices(self, router):
        self.add_vertex(self.ospf_name(router), color='green', 
                subgraph=self._ospf_sub)

    def add_bgp_vertices(self, router):
        for neighbor in router.bgp.neighbors:
            self.add_vertex(self.bgp_name(neighbor), color='orange',
                    subgraph=self._bgp_sub)

    def add_vlan_to_vlan_edges(self, router):
        for vlan in router.vlans.values():
            for iface in vlan.ifaces:
                self.add_edge(self.vlan_name(vlan), 
                        self.vlan_name(iface.neighbor.vlan))

    def add_ospf_to_vlan_edges(self, router):
        for vlan in router.ospf.active_vlans:
            self.add_edge(self.ospf_name(router), self.vlan_name(vlan))

    def add_bgp_to_vlan_ospf_edges(self, router):
        for neighbor in router.bgp.neighbors:
            matching_vlan = None
            for vlan in router.vlans.values():
                if neighbor.addr in vlan.addr.network:
                    matching_vlan = vlan
                    break
            if (matching_vlan):
                self.add_edge(self.bgp_name(neighbor), 
                        self.vlan_name(matching_vlan))
            elif (router.ospf is not None):
                self.add_edge(self.bgp_name(neighbor), 
                        self.ospf_name(router))

    def add_subnet_to_ospf_edges(self, router):
        if (self._t is not None and self._t in router.ospf.origins):
            self.add_edge(self._t, self.ospf_name(router))

    def add_subnet_to_bgp_edges(self, router):
        if (self._t is not None and self._t in router.bgp.origins):
            for neighbor in router.bgp.neighbors:
                print("Origin edge: %s -> %s" % 
                        (self._t, self.bgp_name(neighbor)))
                self.add_edge(self._t, self.bgp_name(neighbor))

    def add_vlan_to_ospf_edges(self, router):
        if (not self._rag.is_tainted(router.ospf)):
            return
        for vlan in router.vlans.values():
            self.add_edge(self.vlan_name(vlan), self.ospf_name(router))

    def add_vlan_to_bgp_edges(self, router):
        if (not self._rag.is_tainted(router.bgp)):
            return
        for vlan in router.vlans.values():
            for neighbor in router.bgp.neighbors:
                self.add_edge(self.vlan_name(vlan), self.bgp_name(neighbor))

    def add_vlan_to_subnet_edges(self, router):
        if (self._s in router.subnets
                and ((router.ospf is not None 
                        and self._rag.is_tainted(router.ospf))
                    or (router.bgp is not None 
                        and self._rag.is_tainted(router.bgp)))):
            for vlan in router.vlans.values():
                self.add_edge(self.vlan_name(vlan), self._s)


    def vlan_name(self, vlan):
        return "%s:VLAN:%s" % (vlan.router.name, vlan.num)

    def ospf_name(self, router):
        return "%s:OSPF" % (router.name)

    def bgp_name(self, neighbor):
        return "%s:BGP:%s" % (neighbor.bgp.router.name, 
                neighbor.iface.router.name)
