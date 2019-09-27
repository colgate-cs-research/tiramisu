#!/usr/bin/python3

import pygraphviz

class Graph:
    def __init__(self, net):
        self._graph = pygraphviz.AGraph(strict=False, directed=True)
        self._net = net

    def render(self, file_path):
        self._graph.layout(prog='dot')
        self._graph.draw(file_path, prog='dot')

    def add_vertex(self, name, color='black', subgraph=None):
        if (subgraph is not None):
            subgraph.add_node(name, color=subgraph.node_attr['color'], 
                fontcolor=subgraph.node_attr['color'])
        else:
            self._graph.add_node(name, color=color, fontcolor=color)
        return self.get_vertex(name)

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
        super().__init__(net)
        for router in net.routers.values():
            for iface in router.ifaces.values():
                self.add_edge(router.name, iface.neighbor.router.name, True)

class Layer2(Graph):
    def __init__(self, net):
        super().__init__(net)

        self._vlan_sub = self.add_subgraph("vlan", color="purple")
        self._iface_sub = self.add_subgraph("iface", color="blue")

        for router in net.routers.values():
            self.add_vlan_vertices(router)
            self.add_iface_vertices(router)

        for router in net.routers.values():
            self.add_vlan_edges(router)
            self.add_iface_edges(router)

        for router in net.routers.values():
            self.add_adjacent_vlan_edges(router)

    def add_vlan_vertices(self, router):
        for vlan in router.vlans.values():
            self.add_vertex(self.vlan_name(vlan), 
                    subgraph=self._vlan_sub)

    def add_iface_vertices(self, router):
        for iface in router.ifaces.values():
            self.add_vertex(self.iface_name(iface), subgraph=self._iface_sub)

    def add_vlan_edges(self, router):
        for vlan in router.vlans.values():
            for iface in vlan.ifaces:
                self.add_edge(self.vlan_name(vlan), self.iface_name(iface),
                        color='purple')
                self.add_edge(self.iface_name(iface), self.vlan_name(vlan),
                        color='purple')

    def add_iface_edges(self, router):
        for iface in router.ifaces.values():
            self.add_edge(self.iface_name(iface), 
                    self.iface_name(iface.neighbor), color='blue')

    def vlan_name(self, vlan):
        return "%s:VLAN:%s" % (vlan.router.name, vlan.num)

    def iface_name(self, iface):
        return "%s:%s" % (iface.router.name, iface.neighbor.router.name)


    def add_adjacent_vlan_edges(self, router):
        for vlan in router.vlans.values():
            vertex = self.get_vertex(self.vlan_name(vlan))
            self.dfs(vertex, vertex, [])

    def dfs(self, origin, vertex, visited):
        if (vertex in visited):
            return
        visited.append(vertex)

        if ("VLAN" in vertex and vertex != origin):
            self.add_edge(origin, vertex, style="dashed", color="purple")

        for edge in self._graph.out_edges(vertex):
            if (edge.attr["style"] == "solid"):
                self.dfs(origin, edge[1], visited)

    def get_adjacent_vlans(self, vlan):
        adjacent = []
        for edge in self._graph.out_edges(self.vlan_name(vlan)):
            if (edge.attr["style"] == "dashed"):
                router, _, num = str(edge[1]).split(':')
                adjacent.append(self._net.routers[router].vlans[int(num)])
        return adjacent


