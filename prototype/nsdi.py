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


class RPG(graph.Graph):
    def __init__(self, net, subnets=None, rag=None):
        super().__init__(net)

        self._t = self._s = None
        self._rag = None
        if (subnets is not None):
            self._t, self._s = subnets
            self._rag = rag

        self._subnet_sub = self.add_subgraph("subnet", color="red")
        self._bgp_sub = self.add_subgraph("bgp", color="orange")
        self._ospf_sub = self.add_subgraph("ospf", color="forestgreen")
        self._vlan_sub = self.add_subgraph("vlan", color="blue")

        for router in net.routers.values():
            self.add_vlan_vertices(router)
            if (router.ospf is not None):
                self.add_ospf_vertices(router)
            if (router.bgp is not None):
                self.add_bgp_vertices(router)

        if (self._t is not None):
            self.add_vertex(self._t, subgraph=self._subnet_sub)
            self.add_vertex(self._s, subgraph=self._subnet_sub)

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
            self.add_vertex(self.vlan_name(vlan), subgraph=self._vlan_sub)

    def add_ospf_vertices(self, router):
        self.add_vertex(self.ospf_name(router), subgraph=self._ospf_sub)

    def add_bgp_vertices(self, router):
        for neighbor in router.bgp.neighbors:
            self.add_vertex(self.bgp_name(neighbor), subgraph=self._bgp_sub)

    def add_vlan_to_vlan_edges(self, router):
        for vlan in router.vlans.values():
            for iface in vlan.ifaces:
                self.add_edge(self.vlan_name(vlan), 
                        self.vlan_name(iface.neighbor.vlan))

    def add_ospf_to_vlan_edges(self, router):
        for vlan in router.ospf.active_vlans:
            self.add_edge(self.ospf_name(router), self.vlan_name(vlan),
                    label={"cost":1})

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
#                print("Origin edge: %s -> %s" % 
#                        (self._t, self.bgp_name(neighbor)))
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

    def has_path(self, failset=[]):
        vertex = self.get_vertex(self._t)
        return self.dfs(vertex, [], failset)

    def dfs(self, vertex, visited, failset):
        if (vertex == self.get_vertex(self._s)):
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
        return (None,None)

class TPG(graph.TPG):
    def __init__(self, net, subnets, rag):
        super().__init__(net, subnets)

        self._rag = rag

        self._subnet_sub = self.add_subgraph("subnet", color="red")
        self._bgp_sub = self.add_subgraph("bgp", color="orange")
        self._ospf_sub = self.add_subgraph("ospf", color="forestgreen")
        self._vlan_sub = self.add_subgraph("vlan", color="blue")

        # Create vertices for VLANs and routing processes
        for router in net.routers.values():
            self.add_vlan_vertices(router)
            if (router.ospf is not None):
                self.add_ospf_vertices(router)
            if (router.bgp is not None):
                self.add_bgp_vertices(router)

        # Create special source and target vertices
        self.add_vertex(self._t, subgraph=self._subnet_sub)
        self.add_vertex(self._s, subgraph=self._subnet_sub)

        # Create edges
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
        # Create a VLAN vertex per VLAN per router 
        for vlan in router.vlans.values():
            self.add_vertex(self.vlan_name(vlan), subgraph=self._vlan_sub)

    def add_ospf_vertices(self, router):
        # Create an OSPF vertex per OSPF process
        self.add_vertex(self.ospf_name(router), subgraph=self._ospf_sub)

    def add_bgp_vertices(self, router):
        # Create a BGP vertex per BGP process
        for neighbor in router.bgp.neighbors:
            self.add_vertex(self.bgp_name(neighbor), subgraph=self._bgp_sub)
            break

    def add_vlan_to_vlan_edges(self, router):
        for vlan in router.vlans.values():
            # Connect VLAN vertex to vertex(es) for same VLAN on physically 
            # connected routers
            for iface in vlan.ifaces:
                self.add_edge(self.vlan_name(vlan), 
                        self.vlan_name(iface.neighbor.vlan))

    def add_ospf_to_vlan_edges(self, router):
        # Connect OSPF vertex to vertex for each VLAN on which OSPF process
        # operates
        for vlan in router.ospf.active_vlans:
            self.add_edge(self.ospf_name(router), self.vlan_name(vlan),
                    label={"cost":1})

    def add_bgp_to_vlan_ospf_edges(self, router):
        # Create edge for each of a BGP process's neighbors
        for neighbor in router.bgp.neighbors:
            matching_vlan = None
            # If neighbor can be reached using a connected route (i.e., VLAN),
            # then connect BGP vertex to corresponding VLAN vertex
            for vlan in router.vlans.values():
                if neighbor.addr in vlan.addr.network:
                    matching_vlan = vlan
                    break
            if (matching_vlan):
                self.add_edge(self.bgp_name(neighbor), 
                        self.vlan_name(matching_vlan), 
                        label=neighbor.import_policy)
#                if (neighbor.import_policy is not None):
#                    print("%s->%s %s" % (self.bgp_name(neighbor), 
#                        self.vlan_name(matching_vlan), neighbor.import_policy))
            # Otherwise, connect BGP vertex to OSPF vertex
            elif (router.ospf is not None):
                self.add_edge(self.bgp_name(neighbor), 
                        self.ospf_name(router),
                        label=neighbor.import_policy)
#                if (neighbor.import_policy is not None):
#                    print("%s->%s %s" % (self.bgp_name(neighbor), 
#                        self.ospf_name(router), neighbor.import_policy))

    def add_subnet_to_ospf_edges(self, router):
        # Connect source vertex to OSPF vertex on the same router, if OSPF 
        # process is tainted in the RAG
        if (self._rag.is_tainted(router.ospf)
                and self._s in router.subnets):
            self.add_edge(self._s, self.ospf_name(router))

    def add_subnet_to_bgp_edges(self, router):
        # Connect source vertex to BGP vertex on the same router, if BGP
        # process is tainted in the RAG
        if (self._rag.is_tainted(router.bgp)
                and self._s in router.subnets):
            for neighbor in router.bgp.neighbors:
                self.add_edge(self._s, self.bgp_name(neighbor))
                break

    def add_vlan_to_ospf_edges(self, router):
        # Connect VLAN vertices to OSPF vertex on the same router, if OSPF
        # process is tainted in the RAG
        if (not self._rag.is_tainted(router.ospf)):
            return
        for vlan in router.vlans.values():
            self.add_edge(self.vlan_name(vlan), self.ospf_name(router))

    def add_vlan_to_bgp_edges(self, router):
        # Connect VLAN vertices to BGP vertex on the same router, if BGP
        # process is tainted in the RAG
        if (not self._rag.is_tainted(router.bgp)):
            return
        for vlan in router.vlans.values():
            for neighbor in router.bgp.neighbors:
                self.add_edge(self.vlan_name(vlan), self.bgp_name(neighbor))
                break

    def add_vlan_to_subnet_edges(self, router):
        # Connect VLAN vertices to target vertex on the same router, if OSPF
        # or BGP process originates a route and is tainted in the RAG
        if ((router.ospf is not None 
                and self._rag.is_tainted(router.ospf)
                and self._t in router.ospf.origins
                and self._t in router.subnets)
            or (router.bgp is not None 
                and self._rag.is_tainted(router.bgp)
                and self._t in router.bgp.origins
                and self._t in router.subnets)):
            for vlan in router.vlans.values():
                self.add_edge(self.vlan_name(vlan), self._t)


    def vlan_name(self, vlan):
        return "%s:VLAN:%s" % (vlan.router.name, vlan.num)

    def ospf_name(self, router):
        return "%s:OSPF" % (router.name)

    def bgp_name(self, neighbor):
        return "%s:BGP" % (neighbor.bgp.router.name)
#        return "%s:BGP:%s" % (neighbor.bgp.router.name, 
#                neighbor.iface.router.name)

class TPGMod(graph.TPG):
    def __init__(self, net, subnets, rag):
        super().__init__(net, subnets)

        self._rag = rag

        self._subnet_sub = self.add_subgraph("subnet", color="red")
        self._bgp_sub = self.add_subgraph("bgp", color="orange")
        self._ospf_sub = self.add_subgraph("ospf", color="forestgreen")
        self._vlan_sub = self.add_subgraph("vlan", color="blue")

        for router in net.routers.values():
            self.add_vlan_vertices(router)
            if (router.ospf is not None):
                self.add_ospf_vertices(router)
            if (router.bgp is not None):
                self.add_bgp_vertices(router)

        self.add_vertex(self._t, subgraph=self._subnet_sub)
        self.add_vertex(self._s, subgraph=self._subnet_sub)

        for router in net.routers.values():
            self.add_vlan_to_vlan_edges(router)
            self.add_vlan_to_subnet_edges(router)
            if (router.ospf is not None):
                self.add_ospf_to_vlan_edges(router)
                self.add_subnet_to_ospf_edges(router)
                self.add_vlan_to_ospf_edges(router)
            if (router.bgp is not None):
                #self.add_bgp_intraprocess_edges(router)
                self.add_bgp_to_vlan_ospf_edges(router)
                self.add_subnet_to_bgp_edges(router)
                self.add_vlan_to_bgp_edges(router)

    def add_vlan_vertices(self, router):
        """
        For each of a router's VLANs, create an incoming VLAN vertex and
        outgoing VLAN vertex
        """
        for vlan in router.vlans.values():
            self.add_vertex(self.vlan_name(vlan, "I"), subgraph=self._vlan_sub)
            self.add_vertex(self.vlan_name(vlan, "O"), subgraph=self._vlan_sub)

    def add_ospf_vertices(self, router):
        self.add_vertex(self.ospf_name(router), subgraph=self._ospf_sub)

    def add_bgp_vertices(self, router):
        """
        Create an "incoming" BGP vertex for a router and an "outgoing" BGP
        vertex for each BGP neighbor
        """
        self.add_vertex(self.bgp_name(router), subgraph=self._bgp_sub)
#        for neighbor in router.bgp.neighbors:
#            self.add_vertex(self.bgp_name(neighbor), subgraph=self._bgp_sub)

    def add_bgp_intraprocess_edges(self, router):
        """
        Connect a router's "incoming" BGP vertex to all of the router's
        "outgoing" per-BGP-neighbor BGP vertices
        """
        for neighbor in router.bgp.neighbors:
            self.add_edge(self.bgp_name(router), self.bgp_name(neighbor),
                    label=neighbor.import_policy)
            if (neighbor.import_policy is not None):
                print("%s->%s %s" % (self.bgp_name(router), 
                        self.bgp_name(neighbor), neighbor.import_policy))

    def add_vlan_to_vlan_edges(self, router):
        for vlan in router.vlans.values():
            self.add_edge(self.vlan_name(vlan, "I"),
                    self.vlan_name(vlan, "O"))
            for iface in vlan.ifaces:
                self.add_edge(self.vlan_name(vlan, "O"),
                        self.vlan_name(iface.neighbor.vlan, "I"))

    def add_ospf_to_vlan_edges(self, router):
        for vlan in router.ospf.active_vlans:
            self.add_edge(self.ospf_name(router), self.vlan_name(vlan, "O"),
                    label={"cost":1})

    def add_bgp_to_vlan_ospf_edges(self, router):
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
                self.add_edge(self.bgp_name(router),
                        self.vlan_name(matching_vlan, "O"),
                        label=neighbor.import_policy)
            elif (router.ospf is not None):
                self.add_edge(self.bgp_name(router),
                        self.ospf_name(router),
                        label=neighbor.import_policy)

    def add_subnet_to_ospf_edges(self, router):
        if (self._rag.is_tainted(router.ospf)
                and self._s in router.subnets):
            self.add_edge(self._s, self.ospf_name(router))

    def add_subnet_to_bgp_edges(self, router):
        """
        If the source (S) is connected to the router and the router's BGP
        process may learn a route to the destination (indicated by the
        router's BGP vertex in the RAG being tainted), then connect source (S)
        to the "incoming" BGP vertex for the router
        """
        if (self._rag.is_tainted(router.bgp)
                and self._s in router.subnets):
            self.add_edge(self._s, self.bgp_name(router))

    def add_vlan_to_ospf_edges(self, router):
        if (not self._rag.is_tainted(router.ospf)):
            return
        for vlan in router.vlans.values():
            self.add_edge(self.vlan_name(vlan, "I"), self.ospf_name(router))

    def add_vlan_to_bgp_edges(self, router):
        """
        If the router's BGP process may learn a route to the destination
        (indicated by the router's BGP vertex in the RAG being tainted), then
        connect all of the router's VLAN vertices to the "incoming" BGP vertex
        for the router
        """
        if (not self._rag.is_tainted(router.bgp)):
            return
        for vlan in router.vlans.values():
            self.add_edge(self.vlan_name(vlan, "I"), self.bgp_name(router))

    def add_vlan_to_subnet_edges(self, router):
        if (self._t in router.subnets and
                ((router.ospf is not None
                    and self._rag.is_tainted(router.ospf)
                    and self._t in router.ospf.origins)
                or (router.bgp is not None
                    and self._rag.is_tainted(router.bgp)
                    and self._t in router.bgp.origins))):
            for vlan in router.vlans.values():
                self.add_edge(self.vlan_name(vlan, "I"), self._t)

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
