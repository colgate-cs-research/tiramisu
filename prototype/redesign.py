#!/usr/bin/python3

import config
import graph

class RAG(graph.Graph):
    def __init__(self, net, l2, subnet=None):
        super().__init__(net)
        self._l2 = l2
        self._subnet = subnet
        self._ospf_sub = self.add_subgraph("ospf", color="forestgreen")
        self._bgp_sub = self.add_subgraph("bgp", color="orange")
        self._subnet_sub = self.add_subgraph("subnet", color="red")
        for router in net.routers.values():
            if (router.ospf is not None):
                self.add_vertex(self.ospf_name(router), subgraph=self._ospf_sub)
            if (router.bgp is not None):
                self.add_vertex(self.bgp_name(router), subgraph=self._bgp_sub)

        if (subnet is not None):
            self.add_vertex(subnet, subgraph=self._subnet_sub)

        for router in net.routers.values():
            if (router.ospf is not None):
                self.add_ospf_adjacencies(router)
                if ("bgp" in router.ospf.redistribute):
                    self.add_edge(self.bgp_name(router), self.ospf_name(router))
                if (subnet in router.ospf.origins):
                    self.add_edge(subnet, self.ospf_name(router), color="red")
            if (router.bgp is not None):
                self.add_bgp_adjacencies(router)
                if ("ospf" in router.bgp.redistribute):
                    self.add_edge(self.ospf_name(router), self.bgp_name(router))
                if (subnet in router.bgp.origins):
                    self.add_edge(subnet, self.bgp_name(router), color="red")

    def taint(self, verbose=False):
        if (self._subnet is not None):
            if (verbose):
                print("Tainting %s..." % self._subnet)
            vertex = self.get_vertex(self._subnet)
            vertex.attr["color"] = "black"
            self.propagate_taint(vertex, verbose=verbose)

    def propagate_taint(self, vertex, noibgp=False, verbose=False):
        if vertex.attr["color"] == "red":
            return

        vertex.attr["color"] = "red"
        if (verbose):
            print("\tTaint %s" % vertex)

        for edge in self._graph.out_edges(vertex):
            ibgp = (edge.attr["style"] == "dashed")
            if (not (ibgp and noibgp)):
                edge.attr["color"] = "red"
                if (verbose):
                    print("\tPropagate from %s to %s" % edge)
                self.propagate_taint(edge[1], noibgp=ibgp, verbose=verbose)

    def is_tainted(self, process):
        if (type(process) is config.Ospf):
            vertex_name = self.ospf_name(process.router)
        elif (type(process) is config.Bgp):
            vertex_name = self.bgp_name(process.router)
        return (self.get_vertex(vertex_name).attr["color"] == "red")

    def add_ospf_adjacencies(self, router):
        for vlan in router.ospf.active_vlans:
            for adjacent in self._l2.get_adjacent_vlans(vlan):
                if (adjacent.router.ospf is not None):
                    self.add_edge(self.ospf_name(router), 
                            self.ospf_name(adjacent.router), 
                            color="forestgreen")

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

class TPG(graph.TPG):
    def __init__(self, net, subnets, rag):
        super().__init__(net, subnets)

        self._rag = rag

        self._subnet_sub = self.add_subgraph("subnet", color="red")
        self._bgp_sub = self.add_subgraph("bgp", color="orange")
        self._ospf_sub = self.add_subgraph("ospf", color="forestgreen")
        self._vlan_sub = self.add_subgraph("vlan", color="blue")
        self._rib_sub = self.add_subgraph("rib", color="black", shape="diamond")

        self._nexthops = {}

        for router in net.routers.values():
            self.add_vertex(self.rib_name(router), subgraph=self._rib_sub)
            self.add_vlan_vertices(router)
            if (router.ospf is not None):
                self.add_ospf_vertices(router)
            if (router.bgp is not None):
                self.add_bgp_vertices(router)

        self.add_vertex(self._t, subgraph=self._subnet_sub)
        self.add_vertex(self._s, subgraph=self._subnet_sub)

        for router in net.routers.values():
            self.add_vlan_to_vlan_edges(router)
            self.add_vlan_to_rib_edges(router)
            self.add_subnet_to_rib_edges(router)
            if (router.ospf is not None):
                self.add_ospf_to_vlan_edges(router)
                self.add_ospf_to_subnet_edges(router)
                self.add_rib_to_ospf_edges(router)
            if (router.bgp is not None):
                self.add_bgp_intraprocess_edges(router)
                self.add_bgp_dependence_edges(router)
                self.add_bgp_to_subnet_edges(router)
                self.add_rib_to_bgp_edges(router)

    def add_vlan_vertices(self, router, subgraph=None, name_prefix=""):
        """
        For each of a router's VLANs, create an incoming VLAN vertex and
        outgoing VLAN vertex
        """
        if (subgraph is None):
            subgraph = self._vlan_sub
        for vlan in router.vlans.values():
            self.add_vertex(name_prefix + self.vlan_name(vlan, "I"), 
                    subgraph=subgraph)
            self.add_vertex(name_prefix + self.vlan_name(vlan, "O"), 
                    subgraph=subgraph)

    def add_ospf_vertices(self, router, subgraph=None, name_prefix=""):
        if (subgraph is None):
            subgraph = self._ospf_sub
        self.add_vertex(name_prefix + self.ospf_name(router), 
                subgraph=subgraph)

    def add_bgp_vertices(self, router):
        """
        Create an "incoming" BGP vertex for a router and an "outgoing" BGP
        vertex for each BGP neighbor
        """
        self.add_vertex(self.bgp_name(router), subgraph=self._bgp_sub)
        for neighbor in router.bgp.neighbors:
            self.add_vertex(self.bgp_name(neighbor), subgraph=self._bgp_sub)

    def add_bgp_intraprocess_edges(self, router):
        """
        Connect a router's "incoming" BGP vertex to all of the router's
        "outgoing" per-BGP-neighbor BGP vertices
        """
        for neighbor in router.bgp.neighbors:
            self.add_edge(self.bgp_name(router), self.bgp_name(neighbor),
                    label=neighbor.import_policy)
#            if (neighbor.import_policy is not None):
#                print("%s->%s %s" % (self.bgp_name(router), 
#                        self.bgp_name(neighbor), neighbor.import_policy))

    def add_vlan_to_vlan_edges(self, router, name_prefix=""):
        for vlan in router.vlans.values():
            self.add_edge(name_prefix + self.vlan_name(vlan, "I"),
                    name_prefix + self.vlan_name(vlan, "O"))
            for iface in vlan.ifaces:
                self.add_edge(name_prefix + self.vlan_name(vlan, "O"),
                        name_prefix + self.vlan_name(iface.neighbor.vlan, "I"))

    def add_ospf_to_vlan_edges(self, router, name_prefix=""):
        for vlan in router.ospf.active_vlans:
            self.add_edge(name_prefix + self.ospf_name(router), 
                    name_prefix + self.vlan_name(vlan, "O"), label={"cost":1})

    def add_bgp_dependence_edges(self, router):
        """
        For each BGP neighbor, connect per-neighbor BGP vertex to VLAN vertex
        (if neighbor is reachable via connected route) or OSPF vertex (if
        neighbor is not reachable via connected route)
        """
        for neighbor in router.bgp.neighbors:
            matching_vlan = None
            for vlan in router.vlans.values():
                if neighbor.addr in vlan.addr.network:
                    matching_vlan = vlan
                    break
            if (matching_vlan):
                self.add_edge(self.bgp_name(neighbor),
                        self.vlan_name(matching_vlan, "O"))
#                        label=neighbor.import_policy)
            elif (router.ospf is not None):
                if (neighbor.iface not in self._nexthops):
                    self.add_nexthop_subgraph(neighbor.iface)
                name_prefix = self._nexthops[neighbor.iface].get_name()
                self.add_edge(self.bgp_name(neighbor),
                        name_prefix + self.ospf_name(router))

    def add_nexthop_subgraph(self, nexthop_iface):
        name_prefix = "[%s:%s]" % (nexthop_iface.router.name, 
                nexthop_iface.num)
        nexthop_sub = self.add_subgraph(name_prefix, rank=None)
        self._nexthops[nexthop_iface] = nexthop_sub

        nexthop_ospf_sub = self.add_subgraph("%sospf" % (name_prefix), 
                color="forestgreen", shape="box", supergraph=nexthop_sub)
        nexthop_vlan_sub = self.add_subgraph("%svlan" % (name_prefix), 
                color="blue", shape="box", supergraph=nexthop_sub)

        for router in self._net.routers.values():
            self.add_vlan_vertices(router, nexthop_vlan_sub, name_prefix)
            if (router.ospf is not None):
                self.add_ospf_vertices(router, nexthop_ospf_sub, name_prefix)
        
        for router in self._net.routers.values():
            self.add_vlan_to_vlan_edges(router, name_prefix)
            if (router.ospf is not None):
                self.add_ospf_to_vlan_edges(router, name_prefix)
                # add_vlan_to_ospf_edges
                for vlan in router.vlans.values():
                    self.add_edge(name_prefix + self.vlan_name(vlan, "I"), 
                            name_prefix + self.ospf_name(router))

        # Add edge to BGP
        self.add_edge(name_prefix + self.vlan_name(nexthop_iface, "I"), 
                    self.bgp_name(nexthop_iface.router))

    def add_subnet_to_rib_edges(self, router):
        if (self._s in router.subnets):
            self.add_edge(self._s, self.rib_name(router))

    def add_rib_to_ospf_edges(self, router):
        if (not self._rag.is_tainted(router.ospf)):
            return
        self.add_edge(self.rib_name(router), self.ospf_name(router))

    def add_rib_to_bgp_edges(self, router):
        """
        If the router's BGP process may learn a route to the destination
        (indicated by the router's BGP vertex in the RAG being tainted), then
        connect all of the router's VLAN vertices to the "incoming" BGP vertex
        for the router
        """
        if (not self._rag.is_tainted(router.bgp)):
            return
        self.add_edge(self.rib_name(router), self.bgp_name(router))

    def add_ospf_to_subnet_edges(self, router):
        if (self._t in router.subnets and router.ospf is not None
                and self._t in router.ospf.origins):
            self.add_edge(self.ospf_name(router), self._t)

    def add_bgp_to_subnet_edges(self, router):
        if (self._t in router.subnets and router.bgp is not None
                and self._t in router.bgp.origins):
            self.add_edge(self.bgp_name(router), self._t)

    def add_vlan_to_rib_edges(self, router):
        for vlan in router.vlans.values():
            self.add_edge(self.vlan_name(vlan, "I"), self.rib_name(router))

    def rib_name(self, router):
        return "%s" % (router.name)

    def vlan_name(self, vlan, direction):
        return "%s:VLAN:%s:%s" % (vlan.router.name, vlan.num, direction)

    def ospf_name(self, router):
        return "%s:OSPF" % (router.name)

    def bgp_name(self, config_object):
        if isinstance(config_object, config.Router):
            return "%s:BGP" % (config_object.name)
        elif isinstance(config_object, config.BgpNeighbor):
            return "%s:BGP:%s" % (config_object.bgp.router.name,
                    config_object.iface.router.name)
        else:
            raise "Unacceptable BGP-related config object"
