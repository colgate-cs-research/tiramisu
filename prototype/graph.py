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
            subgraph.add_node(name, color=subgraph.node_attr['color'], 
                fontcolor=subgraph.node_attr['color'])
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
