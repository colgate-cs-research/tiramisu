#!/usr/bin/python3

import config
import graph

class RPG(graph.Graph):
    def __init__(self, net, l2, subnets=None):
        super().__init__(net)

        self._l2 = l2
        self._t = self._s = None
        if (subnets is not None):
            self._t, self._s = subnets

        self._subnet_sub = self.add_subgraph("subnet", color="red")
        self._bgp_sub = self.add_subgraph("bgp", color="orange")
        self._ospf_sub = self.add_subgraph("ospf", color="forestgreen")
        self._switch_sub = self.add_subgraph("switch", color="purple")

        if (self._t is not None):
            self.add_vertex(self._t, subgraph=self._subnet_sub)
            self.add_vertex(self._s, subgraph=self._subnet_sub)

        for router in net.routers.values():
            if (router.ospf is None and router.bgp is None):
                self.add_vlan_vertices(router)
            if (router.ospf is not None):
                self.add_ospf_vertices(router)
            if (router.bgp is not None):
                self.add_bgp_vertices(router)
        
        for router in net.routers.values():
            if (router.ospf is None and router.bgp is None):
                self.add_vlan_adjacencies(router)
            if (router.ospf is not None):
                self.add_ospf_adjacencies(router)
                self.add_ospf_intraproc(router)
                if (self._t in router.ospf.origins):
                    self.add_ospf_origins(router)
                if (self._s in router.subnets):
                    self.add_ospf_reaches(router)
            if (router.bgp is not None):
                self.add_bgp_adjacencies(router)
                self.add_bgp_intraproc(router)
                if (router.ospf is not None):
                    self.add_bgp_dependency(router)
                if (self._t in router.bgp.origins):
                    self.add_bgp_origins(router)
                if (self._s in router.subnets):
                    self.add_bgp_reaches(router)



    def add_vlan_vertices(self, router):
        for vlan in router.vlans.values():
            self.add_vertex(self.vlan_name(vlan), 
                    subgraph=self._switch_sub)

    def add_ospf_vertices(self, router):
        for vlan in router.vlans.values():
            self.add_vertex(self.ospf_name(vlan), subgraph=self._ospf_sub)

    def add_bgp_vertices(self, router):
        for vlan in router.vlans.values():
            self.add_vertex(self.bgp_name(vlan), subgraph=self._bgp_sub)

    def add_ospf_adjacencies(self, router):
        for vlan in router.ospf.active_vlans:
            for adjacent in self._l2.get_adjacent_vlans(vlan):
                if (adjacent.router.ospf is not None):
                    self.add_edge(self.ospf_name(vlan), 
                            self.ospf_name(adjacent), color="forestgreen")

    def add_ospf_intraproc(self, router):
        for vlanA in router.vlans.values():
            for vlanB in router.vlans.values():
                if vlanA == vlanB:
                    continue
                self.add_edge(self.ospf_name(vlanA), self.ospf_name(vlanB),
                        color="forestgreen", combine=False)

    def add_ospf_origins(self, router):
        for vlan in router.vlans.values():
            self.add_edge(self._t, self.ospf_name(vlan), color="red")

    def add_ospf_reaches(self, router):
        for vlan in router.vlans.values():
            self.add_edge(self.ospf_name(vlan), self._s)

    def add_bgp_adjacencies(self, router):
        for neighbor in router.bgp.neighbors:
            style = ("dotted" if neighbor in router.bgp.internal else "solid")
#            # Only connect matching VLAN
#            if (neighbor.iface.num in router.vlans):
#                self.add_edge(self.bgp_name(router.vlans[neighbor.iface.num]), 
#                        self.bgp_name(neighbor.iface), combine=False,
#                        color="orange", style=style)
            # Connect all VLANs
            for vlanA in router.vlans.values():
                for vlanB in neighbor.iface.router.vlans.values():
                    self.add_edge(self.bgp_name(vlanA), 
                        self.bgp_name(vlanB), combine=False,
                        color="orange", style=style)


    def add_bgp_intraproc(self, router):
        for vlanA in router.vlans.values():
            for vlanB in router.vlans.values():
                if vlanA == vlanB:
                    continue
                self.add_edge(self.bgp_name(vlanA), self.bgp_name(vlanB),
                        color="orange", combine=False)

    def add_bgp_dependency(self, router):
        for vlan in router.vlans.values():
            self.add_edge(self.bgp_name(vlan), self.ospf_name(vlan),
                    style="dashed")

    def add_bgp_origins(self, router):
        for vlan in router.vlans.values():
            self.add_edge(self._t, self.bgp_name(vlan), color="red")

    def add_bgp_reaches(self, router):
        for vlan in router.vlans.values():
            self.add_edge(self.bgp_name(vlan), self._s)

    def add_vlan_adjacencies(self, router):
        for vlan in router.vlans.values():
            for iface in vlan.ifaces:
                neighbor = iface.neighbor
                if (neighbor.vlan.num == vlan.num):
                    if (neighbor.router.ospf is not None):
                        self.add_edge(self.ospf_name(neighbor.vlan), 
                                self.vlan_name(vlan),
                                combine=False)
                    if (neighbor.router.bgp is not None):
                        self.add_edge(self.bgp_name(neighbor.vlan), 
                                self.vlan_name(vlan),
                                combine=False)
                    if (neighbor.router.ospf is None 
                            and neighbor.router.bgp is None):
                        self.add_edge(self.vlan_name(neighbor.vlan), 
                                self.vlan_name(vlan),
                                combine=False, color="purple")

    def was_tainted_by_adjacency(self, vlan):
        vertex = self.get_vertex(self.ospf_name(vlan))
        for edge in self._graph.in_edges(vertex):
            routerA = edge[0].split(':')[0]
            routerB = edge[1].split(':')[0]
            if (routerA == routerB):
                continue
            if (edge.attr["color"] == "red" and edge.attr["style"] != "dashed"):
                return True
        return False

    def vlan_name(self, vlan):
        return "%s:V:%d" % (vlan.router.name, vlan.num)

    def ospf_name(self, vlan):
        return "%s:OSPF:V:%d" % (vlan.router.name, vlan.num)

    def bgp_name(self, vlan):
        return "%s:BGP:V:%d" % (vlan.router.name, vlan.num)

    def taint(self):
        if (self._t is not None):
            vertex = self.get_vertex(self._t)
            vertex.attr["color"] = "black"
            self.propagate_taint(vertex)

    def propagate_taint(self, vertex, noibgp=False, nolateral=False):
        if vertex.attr["color"] == "red":
            return

        vertex.attr["color"] = "red"

        for edge in self._graph.out_edges(vertex):
            ibgp = (edge.attr["style"] == "dotted")
            ospf = (("OSPF" in edge[0]) and ("OSPF" in edge[1])) 
            routerA = edge[0].split(':')[0] 
            routerB = edge[1].split(':')[0] 
            intradevice = (routerA == routerB)
            lateral = (ospf and not intradevice)
            dependency = (edge.attr["style"] == "dashed")
            if ((not (ibgp and noibgp))
                and (not (lateral and nolateral))):
                edge.attr["color"] = "red"
                self.propagate_taint(edge[1], ibgp or (noibgp and intradevice), 
                        nolateral or dependency)

class RPGMod(graph.Graph):
    def __init__(self, net, l2, subnets=None):
        super().__init__(net)

        self._l2 = l2
        self._t = self._s = None
        if (subnets is not None):
            self._t, self._s = subnets

        self._subnet_sub = self.add_subgraph("subnet", color="red")
        self._bgp_sub = self.add_subgraph("bgp", color="orange")
        self._ospf_sub = self.add_subgraph("ospf", color="forestgreen")
        self._switch_sub = self.add_subgraph("switch", color="purple")

        if (self._t is not None):
            self.add_vertex(self._t, subgraph=self._subnet_sub)
            self.add_vertex(self._s, subgraph=self._subnet_sub)

        for router in net.routers.values():
            if (router.ospf is None and router.bgp is None):
                self.add_vlan_vertices(router)
            if (router.ospf is not None):
                self.add_ospf_vertices(router)
            if (router.bgp is not None):
                self.add_bgp_vertices(router)

        for router in net.routers.values():
            if (router.ospf is None and router.bgp is None):
                self.add_vlan_adjacencies(router)
            if (router.ospf is not None):
                self.add_ospf_adjacencies(router)
                self.add_ospf_intraproc(router)
                if (self._t in router.ospf.origins):
                    self.add_ospf_origins(router)
                if (self._s in router.subnets):
                    self.add_ospf_reaches(router)
            if (router.bgp is not None):
                self.add_bgp_adjacencies(router)
                if (router.ospf is not None):
                    self.add_bgp_dependency(router)
                if (self._t in router.bgp.origins):
                    self.add_bgp_origins(router)
                if (self._s in router.subnets):
                    self.add_bgp_reaches(router)

    def add_vlan_vertices(self, router):
        for vlan in router.vlans.values():
            self.add_vertex(self.vlan_name(vlan), 
                    subgraph=self._switch_sub)

    def add_ospf_vertices(self, router):
        for vlan in router.vlans.values():
            self.add_vertex(self.ospf_name(vlan), subgraph=self._ospf_sub)

    def add_bgp_vertices(self, router):
        self.add_vertex(self.bgp_name(router), subgraph=self._bgp_sub)

    def add_ospf_adjacencies(self, router):
        for vlan in router.ospf.active_vlans:
            for adjacent in self._l2.get_adjacent_vlans(vlan):
                if (adjacent.router.ospf is not None):
                    self.add_edge(self.ospf_name(vlan),
                            self.ospf_name(adjacent), color="forestgreen")

    def add_ospf_intraproc(self, router):
        for vlanA in router.vlans.values():
            for vlanB in router.vlans.values():
                if vlanA == vlanB:
                    continue
                self.add_edge(self.ospf_name(vlanA), self.ospf_name(vlanB),
                        color="forestgreen", combine=False)

    def add_ospf_origins(self, router):
        for vlan in router.vlans.values():
            self.add_edge(self._t, self.ospf_name(vlan), color="red")

    def add_ospf_reaches(self, router):
        for vlan in router.vlans.values():
            self.add_edge(self.ospf_name(vlan), self._s)

    def add_bgp_adjacencies(self, router):
        for neighbor in router.bgp.neighbors:
            style = ("dotted" if neighbor in router.bgp.internal else "solid")
            self.add_edge(self.bgp_name(router),
                    self.bgp_name(neighbor.iface.router), combine=False,
                    color="orange", style=style)

    def add_bgp_dependency(self, router):
        for vlan in router.vlans.values():
            self.add_edge(self.bgp_name(router), self.ospf_name(vlan),
                    style="dashed")

    def add_bgp_origins(self, router):
        self.add_edge(self._t, self.bgp_name(router), color="red")

    def add_bgp_reaches(self, router):
        self.add_edge(self.bgp_name(router), self._s)

    def add_vlan_adjacencies(self, router):
        for vlan in router.vlans.values():
            for iface in vlan.ifaces:
                neighbor = iface.neighbor
                if (neighbor.vlan.num == vlan.num):
                    if (neighbor.router.ospf is not None):
                        self.add_edge(self.ospf_name(neighbor.vlan),
                                self.vlan_name(vlan),
                                combine=False)
                    if (neighbor.router.bgp is not None):
                        self.add_edge(self.bgp_name(neighbor.router), #FIXME?
                                self.vlan_name(vlan),
                                combine=False)
                    if (neighbor.router.ospf is None
                            and neighbor.router.bgp is None):
                        self.add_edge(self.vlan_name(neighbor.vlan),
                                self.vlan_name(vlan),
                                combine=False, color="purple")

    def was_tainted_by_adjacency(self, vlan):
        vertex = self.get_vertex(self.ospf_name(vlan))
        for edge in self._graph.in_edges(vertex):
            routerA = edge[0].split(':')[0]
            routerB = edge[1].split(':')[0]
            if (routerA == routerB):
                continue
            if (edge.attr["color"] == "red" and edge.attr["style"] != "dashed"):
                return True
        return False

    def vlan_name(self, vlan):
        return "%s:V:%d" % (vlan.router.name, vlan.num)

    def ospf_name(self, vlan):
        return "%s:OSPF:V:%d" % (vlan.router.name, vlan.num)

    def bgp_name(self, router):
        return "%s:BGP" % (router.name)

    def taint(self):
        if (self._t is not None):
            vertex = self.get_vertex(self._t)
            vertex.attr["color"] = "black"
            self.propagate_taint(vertex)

    def propagate_taint(self, vertex, noibgp=False, nolateral=False):
        if vertex.attr["color"] == "red":
            return

        vertex.attr["color"] = "red"

        for edge in self._graph.out_edges(vertex):
            ibgp = (edge.attr["style"] == "dotted")
            ospf = (("OSPF" in edge[0]) and ("OSPF" in edge[1]))
            routerA = edge[0].split(':')[0]
            routerB = edge[1].split(':')[0]
            intradevice = (routerA == routerB)
            lateral = (ospf and not intradevice)
            dependency = (edge.attr["style"] == "dashed")
            if ((not (ibgp and noibgp))
                and (not (lateral and nolateral))):
                edge.attr["color"] = "red"
                self.propagate_taint(edge[1], ibgp or (noibgp and intradevice),
                        nolateral or dependency)



class TPG(graph.Graph):
    def __init__(self, net, rpg, subnets=None):
        super().__init__(net)

        self._rpg = rpg
        self._t = self._s = None
        if (subnets is not None):
            self._t, self._s = subnets

        self._subnet_sub = self.add_subgraph("subnet", color="red")
        self._bgp_sub = self.add_subgraph("bgp", color="orange")
        self._ospf_sub = self.add_subgraph("ospf", color="forestgreen")
        self._switch_sub = self.add_subgraph("switch", color="purple")

        self.add_vertices_based_on_taints()

        for router in net.routers.values():
            if (router.ospf is None and router.bgp is None):
                self.add_vlan_adjacencies(router)
            if (router.ospf is not None):
                self.add_ospf_adjacencies(router)
                self.add_intraospf_edges(router)
                if (self._s in router.subnets):
                    self.add_src_to_ospf_edges(router)
                if (self._t in router.subnets):
                    self.add_ospf_to_dst_edges(router)
            if (router.bgp is not None):
                self.add_bgp_adjacencies(router)
                self.add_intrabgp_edges(router)
                if (router.ospf is not None):
                    self.add_bgp_dependency(router)
                if (self._s in router.subnets):
                    self.add_src_to_bgp_edges(router)
                if (self._t in router.subnets):
                    self.add_bgp_to_dst_edges(router)

    def add_vertices_based_on_taints(self):
        for vertex in self._rpg._graph.nodes():
            # Ignore untainted vertices
            if vertex.attr["color"] != "red":
                continue

            if vertex.attr["fontcolor"] == "purple":
                self.add_vertex(vertex, subgraph=self._switch_sub)
            elif vertex.attr["fontcolor"] == "orange":
                self.add_vertex("%s:I" % vertex, subgraph=self._bgp_sub)
                self.add_vertex("%s:O" % vertex, subgraph=self._bgp_sub)
            elif vertex.attr["fontcolor"] == "forestgreen":
                self.add_vertex("%s:I" % vertex, subgraph=self._ospf_sub)
                self.add_vertex("%s:O" % vertex, subgraph=self._ospf_sub)
            elif vertex.attr["fontcolor"] == "red":
                self.add_vertex(vertex, subgraph=self._subnet_sub)

    def add_vlan_adjacencies(self, router):
        for vlan in router.vlans.values():
            if not self.has_vertex(self.vlan_name(vlan)):
                continue
            for iface in vlan.ifaces:
                neighbor = iface.neighbor
                if (neighbor.vlan.num == vlan.num):
                    if (neighbor.router.ospf is not None):
                        if self.has_vertex(self.ospf_name(neighbor.vlan, "I")):
                            self.add_edge(self.vlan_name(vlan),
                                    self.ospf_name(neighbor.vlan, "I"))
                            self.add_edge(self.ospf_name(neighbor.vlan, "O"), 
                                    self.vlan_name(vlan))
                    if (neighbor.router.bgp is not None):
                        if self.has_vertex(self.bgp_name(neighbor.vlan, "I")):
                            self.add_edge(self.vlan_name(vlan),
                                    self.bgp_name(neighbor.vlan, "I"))
                            self.add_edge(self.bgp_name(neighbor.vlan, "O"), 
                                    self.vlan_name(vlan))
                    if (neighbor.router.ospf is None 
                            and neighbor.router.bgp is None):
                        self.add_edge(self.vlan_name(neighbor.vlan), 
                                self.vlan_name(vlan),
                                combine=False, color="purple")

    def add_intraospf_edges(self, router):
        for vlan in router.vlans.values():
            if not self.has_vertex(self.ospf_name(vlan, "I")):
                continue
            if (self._rpg.was_tainted_by_adjacency(vlan)):
#                # Connect only to same VLAN
#                self.add_edge(self.ospf_name(vlan, "I"), 
#                        self.ospf_name(vlan, "O"), color="forestgreen")
                # Connect across VLANs
                for vlanB in router.vlans.values():
                    if not self.has_vertex(self.ospf_name(vlanB, "I")):
                        continue
                    self.add_edge(self.ospf_name(vlan, "I"), 
                            self.ospf_name(vlanB, "O"), color="forestgreen")


    def add_intrabgp_edges(self, router):
        for vlan in router.vlans.values():
            if not self.has_vertex(self.bgp_name(vlan, "I")):
                continue
#            # Connect only to same VLAN
#            self.add_edge(self.bgp_name(vlan, "I"), 
#                    self.bgp_name(vlan, "O"), color="orange")
            # Connect across VLANs
            for vlanB in router.vlans.values():
                if not self.has_vertex(self.bgp_name(vlanB, "I")):
                    continue
                self.add_edge(self.bgp_name(vlan, "I"), 
                        self.bgp_name(vlanB, "O"), color="orange")

    def add_bgp_dependency(self, router):
        for vlan in router.vlans.values():
            if ((not self.has_vertex(self.bgp_name(vlan, "I")))
                    or (not self.has_vertex(self.ospf_name(vlan, "I")))):
                continue
            self.add_edge(self.bgp_name(vlan, "O"), 
                    self.ospf_name(vlan, "O"))
            self.add_edge(self.ospf_name(vlan, "I"), 
                    self.bgp_name(vlan, "I"))

    def add_ospf_adjacencies(self, router):
        for vlan in router.ospf.active_vlans:
            if not self.has_vertex(self.ospf_name(vlan, "O")):
                continue
            for adjacent in self._rpg._l2.get_adjacent_vlans(vlan):
                if ((adjacent.router.ospf is not None)
                        and self.has_vertex(self.ospf_name(adjacent, "I"))):
                    self.add_edge(self.ospf_name(vlan, "O"), 
                            self.ospf_name(adjacent, "I"), color="forestgreen",
                            label={"cost":1})

    def add_bgp_adjacencies(self, router):
        for neighbor in router.bgp.neighbors:
            for vlan in router.vlans.values():
                if neighbor.addr not in vlan.addr.network:
                    continue
                if not self.has_vertex(self.bgp_name(vlan, "O")):
                    continue
                for iface in vlan.ifaces:
                    if ((iface.neighbor.router == neighbor.iface.router)
                            and self.has_vertex(
                                self.bgp_name(neighbor.iface, "I"))):
                        self.add_edge(self.bgp_name(vlan, "O"),
                                self.bgp_name(neighbor.iface, "I"),
                                combine=False, color="orange", 
                                label=neighbor.import_policy)
                        if (neighbor.import_policy is not None):
                            print("%s->%s %s" % (self.bgp_name(vlan, "O"), 
                                self.bgp_name(neighbor.iface, "I"), 
                                neighbor.import_policy))


    def add_src_to_ospf_edges(self, router):
        for vlan in router.vlans.values():
            if not self.has_vertex(self.ospf_name(vlan, "I")):
                continue
            self.add_edge(self._s, self.ospf_name(vlan, "I"))

    def add_src_to_bgp_edges(self, router):
        for vlan in router.vlans.values():
            if not self.has_vertex(self.bgp_name(vlan, "I")):
                continue
            self.add_edge(self._s, self.bgp_name(vlan, "I"))

    def add_ospf_to_dst_edges(self, router):
        for vlan in router.vlans.values():
            if not self.has_vertex(self.ospf_name(vlan, "O")):
                continue
            self.add_edge(self.ospf_name(vlan, "O"), self._t)

    def add_bgp_to_dst_edges(self, router):
        for vlan in router.vlans.values():
            if not self.has_vertex(self.bgp_name(vlan, "O")):
                continue
            self.add_edge(self.bgp_name(vlan, "O"), self._t)

    def vlan_name(self, vlan):
        return "%s:V:%d" % (vlan.router.name, vlan.num)

    def ospf_name(self, vlan, inout):
        return "%s:OSPF:V:%d:%s" % (vlan.router.name, vlan.num, inout)

    def bgp_name(self, vlan, inout):
        return "%s:BGP:V:%d:%s" % (vlan.router.name, vlan.num, inout)

    
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

    def tpvp(self):
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
        bestsign[dst] = {'lp':0,'len':0,'cost':0}
        
        change = True
        i = 0

        # Line 4
        while change:
            i += 1

            print('ROUND %d' % i)
            for v in sorted(bestpath.keys()):
                print('\t%s %s' % (bestpath[v], bestsign[v]))

            change = False

            # Line 5
            for u in self._graph.nodes():

                if (u == dst): 
                    continue

                # Line 6
                for e in self._graph.out_edges(u):
                    v = e[1]

                    if (bestpath[v] is not None and u not in bestpath[v]):

                        # Line 7
                        path[u][v] = [u] + bestpath[v]

                        # Line 8
                        L = {}
                        if "label" in e.attr and e.attr["label"] != '':
                            L = eval(e.attr["label"])
                        sign[u][v] = self.sign_combine(L, bestsign[v])

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

        src = self.get_vertex(self._s)
#        print(bestsign)
        return (bestpath[src], bestsign[src])

    def sign_combine(self, label, sign):
        newsign = sign.copy()
        for k,v in label.items():
            if k == 'cost' or k == 'len':
                newsign[k] = v + (newsign[k] if k in newsign else 0)
            elif k == 'lp':
                newsign[k] = v

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

class TPGMod(graph.Graph):
    def __init__(self, net, rpg, subnets=None):
        super().__init__(net)

        self._rpg = rpg
        self._t = self._s = None
        if (subnets is not None):
            self._t, self._s = subnets

        self._subnet_sub = self.add_subgraph("subnet", color="red")
        self._bgp_sub = self.add_subgraph("bgp", color="orange")
        self._ospf_sub = self.add_subgraph("ospf", color="forestgreen")
        self._switch_sub = self.add_subgraph("switch", color="purple")

        self.add_vertices_based_on_taints()

        for router in net.routers.values():
            if (router.ospf is None and router.bgp is None):
                self.add_vlan_adjacencies(router)
            if (router.ospf is not None):
                self.add_ospf_adjacencies(router)
                self.add_intraospf_edges(router)
                if (self._s in router.subnets):
                    self.add_src_to_ospf_edges(router)
                if (self._t in router.subnets):
                    self.add_ospf_to_dst_edges(router)
            if (router.bgp is not None):
                self.add_bgp_adjacencies(router)
                self.add_intrabgp_edges(router)
                if (router.ospf is not None):
                    self.add_bgp_dependency(router)
                if (self._s in router.subnets):
                    self.add_src_to_bgp_edges(router)
                if (self._t in router.subnets):
                    self.add_bgp_to_dst_edges(router)

    def add_vertices_based_on_taints(self):
        for vertex in self._rpg._graph.nodes():
            # Ignore untainted vertices
            if vertex.attr["color"] != "red":
                continue

            if vertex.attr["fontcolor"] == "purple":
                self.add_vertex(vertex, subgraph=self._switch_sub)
            elif vertex.attr["fontcolor"] == "orange":
                self.add_vertex("%s:I" % vertex, subgraph=self._bgp_sub)
                self.add_vertex("%s:O" % vertex, subgraph=self._bgp_sub)
            elif vertex.attr["fontcolor"] == "forestgreen":
                self.add_vertex("%s:I" % vertex, subgraph=self._ospf_sub)
                self.add_vertex("%s:O" % vertex, subgraph=self._ospf_sub)
            elif vertex.attr["fontcolor"] == "red":
                self.add_vertex(vertex, subgraph=self._subnet_sub)

    def add_vlan_adjacencies(self, router):
        for vlan in router.vlans.values():
            if not self.has_vertex(self.vlan_name(vlan)):
                continue
            for iface in vlan.ifaces:
                neighbor = iface.neighbor
                if (neighbor.vlan.num == vlan.num):
                    if (neighbor.router.ospf is not None):
                        if self.has_vertex(self.ospf_name(neighbor.vlan, "I")):
                            self.add_edge(self.vlan_name(vlan),
                                    self.ospf_name(neighbor.vlan, "I"))
                            self.add_edge(self.ospf_name(neighbor.vlan, "O"),
                                    self.vlan_name(vlan))
#                    if (neighbor.router.bgp is not None): #FIXME
#                        if self.has_vertex(self.bgp_name(neighbor.vlan, "I")):
#                            self.add_edge(self.vlan_name(vlan),
#                                    self.bgp_name(neighbor.vlan, "I"))
#                            self.add_edge(self.bgp_name(neighbor.vlan, "O"),
#                                    self.vlan_name(vlan))
                    if (neighbor.router.ospf is None
                            and neighbor.router.bgp is None):
                        self.add_edge(self.vlan_name(neighbor.vlan),
                                self.vlan_name(vlan),
                                combine=False, color="purple")

    def add_intraospf_edges(self, router):
        for vlan in router.vlans.values():
            if not self.has_vertex(self.ospf_name(vlan, "I")):
                continue
            if (self._rpg.was_tainted_by_adjacency(vlan)):
#                # Connect only to same VLAN
#                self.add_edge(self.ospf_name(vlan, "I"),
#                        self.ospf_name(vlan, "O"), color="forestgreen")
                # Connect across VLANs
                for vlanB in router.vlans.values():
                    if not self.has_vertex(self.ospf_name(vlanB, "I")):
                        continue
                    self.add_edge(self.ospf_name(vlan, "I"),
                            self.ospf_name(vlanB, "O"), color="forestgreen")

    def add_intrabgp_edges(self, router):
        if self.has_vertex(self.bgp_name(router, "I")):
            self.add_edge(self.bgp_name(router, "I"),
                    self.bgp_name(router, "O"), color="orange")

    def add_bgp_dependency(self, router):
        for vlan in router.vlans.values():
            if ((not self.has_vertex(self.bgp_name(router, "I")))
                    or (not self.has_vertex(self.ospf_name(vlan, "I")))):
                continue
            self.add_edge(self.bgp_name(router, "O"),
                    self.ospf_name(vlan, "O"))
            self.add_edge(self.ospf_name(vlan, "I"),
                    self.bgp_name(router, "I"))

    def add_ospf_adjacencies(self, router):
        for vlan in router.ospf.active_vlans:
            if not self.has_vertex(self.ospf_name(vlan, "O")):
                continue
            for adjacent in self._rpg._l2.get_adjacent_vlans(vlan):
                if ((adjacent.router.ospf is not None)
                        and self.has_vertex(self.ospf_name(adjacent, "I"))):
                    self.add_edge(self.ospf_name(vlan, "O"),
                            self.ospf_name(adjacent, "I"), color="forestgreen",
                            label={"cost":1})

    def add_bgp_adjacencies(self, router):
        for neighbor in router.bgp.neighbors:
            for vlan in router.vlans.values():
                if neighbor.addr not in vlan.addr.network:
                    continue
                if not self.has_vertex(self.bgp_name(router, "O")):
                    continue
                for iface in vlan.ifaces:
                    if ((iface.neighbor.router == neighbor.iface.router)
                            and self.has_vertex(
                                self.bgp_name(neighbor.iface.router, "I"))):
                        self.add_edge(self.bgp_name(router, "O"),
                                self.bgp_name(neighbor.iface.router, "I"),
                                combine=False, color="orange",
                                label=neighbor.import_policy)
                        if (neighbor.import_policy is not None):
                            print("%s->%s %s" % (self.bgp_name(router, "O"),
                                self.bgp_name(neighbor.iface.router, "I"),
                                neighbor.import_policy))

    def add_src_to_ospf_edges(self, router):
        for vlan in router.vlans.values():
            if not self.has_vertex(self.ospf_name(vlan, "I")):
                continue
            self.add_edge(self._s, self.ospf_name(vlan, "I"))

    def add_src_to_bgp_edges(self, router):
        if self.has_vertex(self.bgp_name(router, "I")):
            self.add_edge(self._s, self.bgp_name(router, "I"))

    def add_ospf_to_dst_edges(self, router):
        for vlan in router.vlans.values():
            if not self.has_vertex(self.ospf_name(vlan, "O")):
                continue
            self.add_edge(self.ospf_name(vlan, "O"), self._t)

    def add_bgp_to_dst_edges(self, router):
        if self.has_vertex(self.bgp_name(router, "O")):
            self.add_edge(self.bgp_name(router, "O"), self._t)

    def vlan_name(self, vlan):
        return "%s:V:%d" % (vlan.router.name, vlan.num)

    def ospf_name(self, vlan, inout):
        return "%s:OSPF:V:%d:%s" % (vlan.router.name, vlan.num, inout)

    def bgp_name(self, router, inout):
        return "%s:BGP:%s" % (router.name, inout)

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

    def tpvp(self):
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
        bestsign[dst] = {'lp':0,'len':0,'cost':0}

        change = True
        i = 0

        # Line 4
        while change:
            i += 1

            print('ROUND %d' % i)
            for v in sorted(bestpath.keys()):
                print('\t%s %s' % (bestpath[v], bestsign[v]))

            change = False

            # Line 5
            for u in self._graph.nodes():

                if (u == dst):
                    continue

                # Line 6
                for e in self._graph.out_edges(u):
                    v = e[1]

                    if (bestpath[v] is not None and u not in bestpath[v]):

                        # Line 7
                        path[u][v] = [u] + bestpath[v]

                        # Line 8
                        L = {}
                        if "label" in e.attr and e.attr["label"] != '':
                            L = eval(e.attr["label"])
                        sign[u][v] = self.sign_combine(L, bestsign[v])

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

        src = self.get_vertex(self._s)
#        print(bestsign)
        return (bestpath[src], bestsign[src])

    def sign_combine(self, label, sign):
        newsign = sign.copy()
        for k,v in label.items():
            if k == 'cost' or k == 'len':
                newsign[k] = v + (newsign[k] if k in newsign else 0)
            elif k == 'lp':
                newsign[k] = v

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
