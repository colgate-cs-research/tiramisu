#!/usr/bin/python3

import pygraphviz

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
    def __init__(self, net):
        super().__init__()
        self._ospf_sub = self.add_subgraph("ospf", color="green")
        self._bgp_sub = self.add_subgraph("bgp", color="orange")
        for router in net.routers.values():
            if (router.ospf is not None):
                self.add_vertex(self.ospf_name(router), color='green', 
                    subgraph=self._ospf_sub)
            if (router.bgp is not None):
                self.add_vertex(self.bgp_name(router), color='orange', 
                    subgraph=self._bgp_sub)

        for router in net.routers.values():
            if (router.ospf is not None):
                self.add_ospf_adjacencies(router)
            if (router.bgp is not None):
                self.add_bgp_adjacencies(router)

    def add_ospf_adjacencies(self, router):
        for vlan in router.ospf.active_vlans:
            for iface in vlan.ifaces:
                if (iface.neighbor.vlan.num == vlan.num 
                        and iface.neighbor.router.ospf is not None):
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
    def __init__(self, net):
        super().__init__()
        self._vlan_sub = self.add_subgraph("vlan", color="blue")
        self._ospf_sub = self.add_subgraph("ospf", color="green")
        self._bgp_sub = self.add_subgraph("bgp", color="orange")
        for router in net.routers.values():
            self.add_vlan_vertices(router)
            if (router.ospf is not None):
                self.add_ospf_vertices(router)
            if (router.bgp is not None):
                self.add_bgp_vertices(router)

        for router in net.routers.values():
            self.add_vlan_to_vlan_edges(router)
            if (router.ospf is not None):
                self.add_ospf_to_vlan_edges(router)
                self.add_vlan_to_ospf_edges(router) # TODO: check taints
            if (router.bgp is not None):
                self.add_bgp_to_vlan_ospf_edges(router)
                self.add_vlan_to_bgp_edges(router) # TODO: check taints

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

    def add_vlan_to_ospf_edges(self, router):
        for vlan in router.vlans.values():
            self.add_edge(self.vlan_name(vlan), self.ospf_name(router))

    def add_vlan_to_bgp_edges(self, router):
        for vlan in router.vlans.values():
            for neighbor in router.bgp.neighbors:
                self.add_edge(self.vlan_name(vlan), self.bgp_name(neighbor))

    def vlan_name(self, vlan):
        return "%s:VLAN:%s" % (vlan.router.name, vlan.num)

    def ospf_name(self, router):
        return "%s:OSPF" % (router.name)

    def bgp_name(self, neighbor):
        return "%s:BGP:%s" % (neighbor.bgp.router.name, 
                neighbor.iface.router.name)
