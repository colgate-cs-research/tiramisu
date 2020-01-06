#!/usr/bin/python3

import copy
import pygraphviz
from tabulate import tabulate

class Graph:
    def __init__(self, net):
        self._graph = pygraphviz.AGraph(strict=False, directed=True, 
                ranksep=1.5)
        self._net = net

    def render(self, file_path):
        self._graph.layout(prog='dot')
        self._graph.draw(file_path, prog='dot')

    def add_vertex(self, name, color='black', shape='ellipse', subgraph=None):
        if (subgraph is not None):
            subgraph.add_node(name, 
                    color=(subgraph.node_attr['color'] 
                        if color=="black" else color), 
                    fontcolor=(subgraph.node_attr['fontcolor']
                        if color=="black" else color),
                    shape=(subgraph.node_attr['shape']
                        if shape=="ellipse" else shape))
        else:
            self._graph.add_node(name, color=color, fontcolor=color, 
                    shape=shape)
        return self.get_vertex(name)

    def get_vertex(self, name):
        return self._graph.get_node(name)

    def has_vertex(self, name):
        return self._graph.has_node(name)

    def add_edge(self, src, dst, combine=False, color='black', style='solid',
            label=None, headlabel='', taillabel=''):
        if (combine and self._graph.has_edge(dst, src)):
            self._graph.get_edge(dst, src).attr['dir'] = 'both'
        else:
            self._graph.add_edge(src, dst, color=color, fontcolor=color,
                    style=style, label=('' if label is None else label), 
                    headlabel=headlabel,
                    taillabel=taillabel, fontsize=10.0)

    def has_edge(self, src, dst, either=False):
        return (self._graph.has_edge(src, dst) or
                (either and self.graph.has_edge(dst, src)))

    def add_subgraph(self, name=None, color="black", shape="ellipse", 
            rank='same', supergraph=None):
        if (supergraph is None):
            supergraph = self._graph
        subgraph = supergraph.add_subgraph(name=name, rank=rank)
        subgraph.node_attr['color'] = color
        subgraph.node_attr['fontcolor'] = color
        subgraph.node_attr['shape'] = shape
        return subgraph

class Physical(Graph):
    def __init__(self, net):
        super().__init__(net)

        self._iface_sub = self.add_subgraph("iface", color="blue")
        self._subnet_sub = self.add_subgraph("subnet", color="red")

        for router in net.routers.values():
            self.add_vertex(router.name, subgraph=self._iface_sub)
            for subnet in router.subnets:
                self.add_vertex(subnet, subgraph=self._subnet_sub)

        for router in net.routers.values():
            for iface in router.ifaces.values():
                self.add_edge(router.name, iface.neighbor.router.name, True,
                        color="blue")
            for subnet in router.subnets:
                self.add_edge(subnet, router.name, True, color="red")


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

class Ospf(Graph):
    def __init__(self, net, l2):
        super().__init__(net)
        self._l2 = l2

        self._ospf_sub = self.add_subgraph("ospf", color="forestgreen")
        self._subnet_sub = self.add_subgraph("subnet", color="red")

        for router in net.routers.values():
            if router.ospf is None:
                continue

            self.add_vertex(router.name, subgraph=self._ospf_sub)
            for subnet in router.ospf.origins:
                self.add_vertex(subnet, subgraph=self._subnet_sub)

        for router in net.routers.values():
            if router.ospf is None:
                continue

            for vlan in router.ospf.active_vlans:
                for adjacent in self._l2.get_adjacent_vlans(vlan):
                    if (adjacent.router.ospf is not None):
                        self.add_edge(router.name, adjacent.router.name, 
                                color="forestgreen", label={'cost':1})

            for subnet in router.ospf.origins:
                self.add_edge(router.name, subnet, color="red")

    def tpvp(self, t):
        # Line 2
        path = {}
        sign = {}
        bestpath = {}
        bestsign = {}
        for u in self._graph.nodes():
            path[u] = {}
            sign[u] = {}
            bestpath[u] = None
            bestsign[u] = None
            for v in self._graph.out_neighbors(u):
                path[u][v] = None
                sign[u][v] = None

        # Line 3
        dst = self.get_vertex(t)
        bestpath[dst] = [t]
        bestsign[dst] = {'cost':0}
        
        change = True

        # Line 4
        while change:

            print(bestpath)
            print(bestsign)

            change = False

            # Line 5
            for u in self._graph.nodes():

                if (u == dst): 
                    continue

                # Line 6
                for e in self._graph.out_edges(u):
                    v = e[1]

                    if (bestpath[v] is not None):

                        # Line 7
                        path[u][v] = [u] + bestpath[v]

                        # Line 8
                        L = {}
                        if "label" in e.attr and e.attr["label"] != '':
                            L = eval(e.attr["label"])
                        sign[u][v] = self.sign_combine(L, bestsign[v])

                # Line 9
                newbestpath, newbestsign = self.path_rank(path[u], sign[u])

                # Line 10
                if newbestpath != bestpath[u] or newbestsign != bestsign[u]:

                    print("CHANGE: %s" % u)
                    bestpath[u] = newbestpath
                    bestsign[u] = newbestsign

                    # Line 11
                    change = True

        print("TPVP:")
        print(bestpath)
        print(bestsign)

    def sign_combine(self, label, sign):
        return {'cost' : 
                (label['cost'] if 'cost' in label else 0) 
                    + (sign['cost'] if 'cost' in sign else 0)}

    def path_rank(self, paths, signs):
        bestpath = None
        bestsign = None
        for v,sign in signs.items():
            if (sign is not None 
                    and (bestsign is None or sign['cost'] < bestsign['cost'])):
                bestsign = sign
                bestpath = paths[v]

        return bestpath, bestsign

class Bgp(Graph):
    def __init__(self, net):
        super().__init__(net)

        self._bgp_sub = self.add_subgraph("bgp", color="orange", rank="")
        self._subnet_sub = self.add_subgraph("subnet", color="red")

        for router in net.routers.values():
            if router.bgp is None:
                continue

            self.add_vertex(router.name, subgraph=self._bgp_sub)
            for subnet in router.bgp.origins:
                self.add_vertex(subnet, subgraph=self._subnet_sub)

        for router in net.routers.values():
            if router.bgp is None:
                continue

            for neighbor in router.bgp.neighbors:
                import_policy = None
                for reverse in neighbor.iface.router.bgp.neighbors:
                    if reverse.iface.router == router:
                        import_policy = reverse.import_policy

                self.add_edge("%s" % router.name,
                        "%s" % neighbor.iface.router.name, color="orange",
                        style=("dashed" if neighbor in router.bgp.internal
                            else "solid"),
                        taillabel=('' if neighbor.export_policy is None
                            else "Ex:%s" % neighbor.export_policy),
                        headlabel=('' if import_policy is None
                            else "Im:%s" % import_policy))

            for subnet in router.bgp.origins:
                self.add_edge(subnet, router.name, color="red")

class Combined(Graph):
    def __init__(self, net, l2):
        super().__init__(net) 
        self._l2 = l2

        self._subs = {}

        for router in net.routers.values():
            name = router.name
            sub = self.add_subgraph("cluster_%s" % name)
            self._subs[name] = sub
            self.add_vertex(name, subgraph=sub, color="blue")
            if (router.ospf is not None):
                self.add_vertex(("%s:OSPF" % name), subgraph=sub, 
                        color="forestgreen")
            if (router.bgp is not None):
                self.add_vertex(("%s:BGP" % name), subgraph=sub, color="orange")
            for subnet in router.subnets:
                self.add_vertex(subnet, subgraph=sub, color="red")

        for router in net.routers.values():
            for iface in router.ifaces.values():
                self.add_edge(router.name, iface.neighbor.router.name, True,
                        color="blue", label="VLAN:%d" % iface.vlan.num)

            if router.ospf is not None:
                for vlan in router.ospf.active_vlans:
                    for adjacent in self._l2.get_adjacent_vlans(vlan):
                        if (adjacent.router.ospf is not None):
                            self.add_edge("%s:OSPF" % router.name, 
                                    "%s:OSPF" % adjacent.router.name, 
                                    color="forestgreen", combine=True)

                if ("bgp" in router.ospf.redistribute):
                    self.add_edge("%s:BGP" % router.name,
                            "%s:OSPF" % router.name)

                for subnet in router.ospf.origins:
                    self.add_edge(subnet, "%s:OSPF" % router.name, color="red")

            if router.bgp is not None:
                for neighbor in router.bgp.neighbors:
                    import_policy = None
                    for reverse in neighbor.iface.router.bgp.neighbors:
                        if reverse.iface.router == router:
                            import_policy = reverse.import_policy

                    self.add_edge("%s:BGP" % router.name, 
                            "%s:BGP" % neighbor.iface.router.name, 
                            color="orange", 
                            style=("dashed" if neighbor in router.bgp.internal
                                else "solid"),
                            taillabel=('' if neighbor.export_policy is None
                                else "Ex:%s" % neighbor.export_policy),
                            headlabel=('' if import_policy is None
                                else "Im:%s" % import_policy))

                if ("ospf" in router.bgp.redistribute):
                    self.add_edge("%s:OSPF" % router.name,
                            "%s:BGP" % router.name)

                for subnet in router.bgp.origins:
                    self.add_edge(subnet, "%s:BGP" % router.name, color="red")

class TPG(Graph):
    def __init__(self, net, subnets):
        super().__init__(net)

        self._t, self._s = subnets

    def has_path(self, failset=[]):
        vertex = self.get_vertex(self._s)
        return self.dfs(vertex, [], failset)

    def dfs(self, vertex, visited, failset):
        if (vertex == self.get_vertex(self._t)):
            return True, [vertex]

        if (vertex in visited):
            return False, []
        visited.append(vertex)

        for edge in self._graph.out_edges(vertex):
            if (self.edge_has_failed(edge, failset)):
                continue
            found, subpath = self.dfs(edge[1], visited, failset)
            if (found):
                return found, [vertex] + subpath

        return False, []

    def edge_has_failed(self, edge, failset=[]):
        src = str(edge[0]).split(':')[0]
        dst = str(edge[1]).split(':')[0]
        return ([src,dst] in failset or [dst,src] in failset)

    def tpvp(self, verbose=False, failset=[], reprocess=False):
        # Line 2
        path = {}
        sign = {}
        bestpath = {}
        bestsign = {}
        for u in self._graph.nodes():
            path[u] = {}
            sign[u] = {}
            bestpath[u] = None
            bestsign[u] = None
            for v in self._graph.out_neighbors(u):
                path[u][v] = None
                sign[u][v] = None

        # Line 3
        dst = self.get_vertex(self._t)
        bestpath[dst] = [dst]
        bestsign[dst] = {'lp':100,'len':0,'cost':0,'tags':set()}

        change = True
        i = 0

        # Line 4
        while change:
            i += 1

            if (verbose):
                print('ROUND %d' % i)
                table = [[v, (None if bestpath[v] is None else
                        ' > '.join(bestpath[v])),
                        bestsign[v]] for v in sorted(bestpath.keys())]
                print(tabulate(table, headers=["Node", "Best path to %s" % dst,
                        "Best signature"]))

            change = False

            # Line 5
            for u in self._graph.nodes():

                if (u == dst): 
                    continue

                # Line 6
                for e in self._graph.out_edges(u)[::-1]:
#                    print("%s %s" % (e, e.attr["label"]))
                    if self.edge_has_failed(e, failset):
                        continue

                    v = e[1]

                    if (bestpath[v] is not None and u not in bestpath[v]):

                        # Line 7
                        path[u][v] = [u] + bestpath[v]

                        # Line 8
                        L = {}
                        if "label" in e.attr and e.attr["label"] != '':
                            L = eval(e.attr["label"])
                        sign[u][v] = self.sign_combine(L, bestsign[v])

                        if (sign[u][v] == None):
                            path[u][v] = None

                # Line 9
                newbestpath, newbestsign = self.path_rank(u, path[u], sign[u],
                        bestpath[u], bestsign[u])

                # Line 10
                if newbestpath != bestpath[u] or newbestsign != bestsign[u]:

#                    print("CHANGE: %s" % u)
                    bestpath[u] = newbestpath
                    bestsign[u] = newbestsign

                    # Line 11
                    change = True

                    # MODIFICATION: invalidate best path of upstream neighbors 
                    # whose next hop is u
                    for e in self._graph.in_edges(u):
                        v = e[0]
                        if bestpath[v] is not None and bestpath[v][1] == u:
                            bestpath[v] = None
                            bestsign[v] = None

        src = self.get_vertex(self._s)
#        print(bestsign)

        if (reprocess):
            realpath = []
            node = src
            while (node != dst):
                node_path = bestpath[node]
                if (node_path is None):
                    return (None, None)
                head_path, node = self.get_head_and_next(node_path)
                realpath += head_path
            return (realpath + [dst], {})
        else:
            return (bestpath[src], bestsign[src])

    def get_head_and_next(self, path):
        node = path[0]
        head_path = []
        for vertex in path:
            vertex_node = vertex
            if (vertex_node.startswith('[')):
                vertex_node = vertex_node.split(']')[1]
            vertex_node = vertex_node.split(':')[0]
            if vertex_node != node:
                return head_path, vertex_node
            head_path += [vertex]
        return (head_path, None)

    def sign_combine(self, label, sign):
        newsign = copy.deepcopy(sign)
        for k,v in label.items():
            if k == 'cost' or k == 'len':
                newsign[k] = v + (newsign[k] if k in newsign else 0)
            elif k == 'lp':
                newsign[k] = v
            elif k == 'at':
                newsign['tags'].update(v)
            elif k == 'rt':
                newsign['tags'].difference_update(v)
            elif k == 'bt':
                if (len(newsign['tags'].intersection(v)) > 0):
                    return None

        return newsign

    def path_rank(self, u, paths, signs, bestpath, bestsign):
        for v,sign in signs.items():
            if (sign is None):
                continue

            if (bestsign is None):
                bestsign = sign
                bestpath = paths[v]

            if ("OSPF" in str(u)):
                if (sign['cost'] < bestsign['cost']):
                    bestsign = sign
                    bestpath = paths[v]
            elif ("BGP" in str(u)):
                if (sign['lp'] > bestsign['lp']
                        or (sign['lp'] == bestsign['lp']
                            and sign['len'] < bestsign['len'])):
                    bestsign = sign
                    bestpath = paths[v]

        return bestpath, bestsign

    def contract(self):
        for u in self._graph.nodes():
            u_out = self._graph.out_edges(u)
            if (len(u_out) == 1):
                v = u_out[0][1]
                if (self._graph.in_degree(v) == 1):
                    v_out = self._graph.out_edges(v)
                    print("\t%s - %s" % (u, v))
                    uv = "%s-%s" % (u, v)
                    self.add_vertex(uv)
                    for e in self._graph.in_edges(u):
                        self.add_edge(e[0], uv, label=e.attr["label"])
                    for e in self._graph.out_edges(v):
                        self.add_edge(uv, e[1], label=e.attr["label"])
                    self._graph.remove_node(u)
                    self._graph.remove_node(v)
