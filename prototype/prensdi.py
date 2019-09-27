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
        for neighbor in router.bgp.external:
            if (neighbor.iface.num in router.vlans):
                self.add_edge(self.bgp_name(router.vlans[neighbor.iface.num]), 
                        self.bgp_name(neighbor.iface), combine=False,
                        color="orange")
        for neighbor in router.bgp.internal:
            if (neighbor.iface.num in router.vlans):
                self.add_edge(self.bgp_name(router.vlans[neighbor.iface.num]), 
                        self.bgp_name(neighbor.iface), combine=False,
                        color="orange", style="dotted")

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
            if not (("OSPF" in edge[0]) and ("OSPF" in edge[1])):
                continue
            routerA = edge[0].split(':')[0]
            routerB = edge[0].split(':')[0]
            if (routerA == routerB):
                continue
            if (edge.attr["color"] == "red"):
                return True
        return False

    def vlan_name(self, vlan):
        return "%s:VLAN:%d" % (vlan.router.name, vlan.num)

    def ospf_name(self, vlan):
        return "%s:OSPF:VLAN:%d" % (vlan.router.name, vlan.num)

    def bgp_name(self, vlan):
        return "%s:BGP:VLAN:%d" % (vlan.router.name, vlan.num)

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

            # TODO: Add subnet edges


    def add_vertices_based_on_taints(self):
        for vertex in self._rpg._graph.nodes():
            # Ignore untainted vertices
            if vertex.attr["color"] != "red":
                continue

            if vertex.attr["fontcolor"] == "purple":
                self.add_vertex(vertex, subgraph=self._switch_sub)
            elif vertex.attr["fontcolor"] == "orange":
                self.add_vertex("%s:IN" % vertex, subgraph=self._bgp_sub)
                self.add_vertex("%s:OUT" % vertex, subgraph=self._bgp_sub)
            elif vertex.attr["fontcolor"] == "forestgreen":
                self.add_vertex("%s:IN" % vertex, subgraph=self._ospf_sub)
                self.add_vertex("%s:OUT" % vertex, subgraph=self._ospf_sub)
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
                        if self.has_vertex(self.ospf_name(neighbor.vlan, "IN")):
                            self.add_edge(self.vlan_name(vlan),
                                    self.ospf_name(neighbor.vlan, "IN"))
                            self.add_edge(self.ospf_name(neighbor.vlan, "OUT"), 
                                    self.vlan_name(vlan))
                    if (neighbor.router.bgp is not None):
                        if self.has_vertex(self.bgp_name(neighbor.vlan, "IN")):
                            self.add_edge(self.vlan_name(vlan),
                                    self.bgp_name(neighbor.vlan, "IN"))
                            self.add_edge(self.bgp_name(neighbor.vlan, "OUT"), 
                                    self.vlan_name(vlan))
                    if (neighbor.router.ospf is None 
                            and neighbor.router.bgp is None):
                        self.add_edge(self.vlan_name(neighbor.vlan), 
                                self.vlan_name(vlan),
                                combine=False, color="purple")

    def add_intraospf_edges(self, router):
        for vlan in router.vlans.values():
            if not self.has_vertex(self.ospf_name(vlan, "IN")):
                continue
            if (self._rpg.was_tainted_by_adjacency(vlan)):
                self.add_edge(self.ospf_name(vlan, "IN"), 
                        self.ospf_name(vlan, "OUT"), color="forestgreen")

    def add_intrabgp_edges(self, router):
        for vlan in router.vlans.values():
            if not self.has_vertex(self.bgp_name(vlan, "IN")):
                continue
            self.add_edge(self.bgp_name(vlan, "IN"), 
                    self.bgp_name(vlan, "OUT"), color="orange")

    def add_bgp_dependency(self, router):
        for vlan in router.vlans.values():
            if ((not self.has_vertex(self.bgp_name(vlan, "IN")))
                    or (not self.has_vertex(self.ospf_name(vlan, "IN")))):
                continue
            self.add_edge(self.bgp_name(vlan, "OUT"), 
                    self.ospf_name(vlan, "OUT"))
            self.add_edge(self.ospf_name(vlan, "IN"), 
                    self.bgp_name(vlan, "IN"))

    def add_ospf_adjacencies(self, router):
        for vlan in router.ospf.active_vlans:
            if not self.has_vertex(self.ospf_name(vlan, "OUT")):
                continue
            for adjacent in self._rpg._l2.get_adjacent_vlans(vlan):
                if ((adjacent.router.ospf is not None)
                        and self.has_vertex(self.ospf_name(adjacent, "IN"))):
                    self.add_edge(self.ospf_name(vlan, "OUT"), 
                            self.ospf_name(adjacent, "IN"), color="forestgreen")

    def add_bgp_adjacencies(self, router):
        for neighbor in router.bgp.neighbors:
            for vlan in router.vlans.values():
                if neighbor.addr not in vlan.addr.network:
                    continue
                if not self.has_vertex(self.bgp_name(vlan, "OUT")):
                    continue
                for iface in vlan.ifaces:
                    if ((iface.neighbor.router == neighbor.iface.router)
                            and self.has_vertex(
                                self.bgp_name(neighbor.iface, "IN"))):
                        self.add_edge(self.bgp_name(vlan, "OUT"),
                                self.bgp_name(neighbor.iface, "IN"),
                                combine=False, color="orange")

    def add_src_to_ospf_edges(self, router):
        for vlan in router.vlans.values():
            if not self.has_vertex(self.ospf_name(vlan, "IN")):
                continue
            self.add_edge(self._s, self.ospf_name(vlan, "IN"))

    def add_src_to_bgp_edges(self, router):
        for vlan in router.vlans.values():
            if not self.has_vertex(self.bgp_name(vlan, "IN")):
                continue
            self.add_edge(self._s, self.bgp_name(vlan, "IN"))

    def add_ospf_to_dst_edges(self, router):
        for vlan in router.vlans.values():
            if not self.has_vertex(self.ospf_name(vlan, "OUT")):
                continue
            self.add_edge(self.ospf_name(vlan, "OUT"), self._t)

    def add_bgp_to_dst_edges(self, router):
        for vlan in router.vlans.values():
            if not self.has_vertex(self.bgp_name(vlan, "OUT")):
                continue
            self.add_edge(self.bgp_name(vlan, "OUT"), self._t)

    def vlan_name(self, vlan):
        return "%s:VLAN:%d" % (vlan.router.name, vlan.num)

    def ospf_name(self, vlan, inout):
        return "%s:OSPF:VLAN:%d:%s" % (vlan.router.name, vlan.num, inout)

    def bgp_name(self, vlan, inout):
        return "%s:BGP:VLAN:%d:%s" % (vlan.router.name, vlan.num, inout)


