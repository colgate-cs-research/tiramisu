#!/usr/bin/python3

import config
import graph

class RPG(graph.Graph):
    def __init__(self, net, subnets=None):
        super().__init__(net)

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
            for iface in vlan.ifaces:
                if (iface.neighbor.vlan.num == vlan.num 
                        and iface.neighbor.router.ospf is not None):
                    self.add_edge(self.ospf_name(vlan), 
                            self.ospf_name(iface.neighbor.vlan),
                            color="forestgreen", combine=False)

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
            self.add_edge(self.ospf_name(vlan), self._s, color="red")

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
            self.add_edge(self.bgp_name(vlan), self._s, color="red")

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
            lateral = (("OSPF" in edge[0]) and ("OSPF" in edge[1]))
            dependency = (edge.attr["style"] == "dashed")
            print("%s %s %s" % (edge, ibgp, lateral))
            if ((not (ibgp and noibgp))
                and (not (lateral and nolateral))):
                edge.attr["color"] = "red"
                self.propagate_taint(edge[1], ibgp, dependency)

