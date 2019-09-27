#!/usr/bin/python3

import ipaddress
import json

class Iface:
    def __init__(self, neighbor, vlan=None):
        self._neighbor = neighbor
        self._vlan = vlan
        self._router = None

    @classmethod
    def create(cls, iface_json, vlans=None):
        neighbor = iface_json["neighbor"]
        vlan = None
        if ("vlan" in iface_json):
            vlan = vlans[iface_json["vlan"]]

        iface = Iface(neighbor, vlan)
        if (vlan is not None):
            vlan.add_iface(iface)
        return iface

    @property
    def neighbor(self):
        return self._neighbor

    @property
    def vlan(self):
        return self._vlan

    @property
    def router(self):
        return self._router

    def __str__(self):
        return ("Iface <neighbor=%s%s>" % (self._neighbor.router.name, 
                ("" if self._vlan is None else ", vlan=%d" % self._vlan.num)))

class Vlan:
    def __init__(self, num, addr):
        self._num = num
        self._addr = addr
        self._ifaces = []
        self._router = None

    @classmethod
    def create(cls, vlan_json):
        num = vlan_json["num"]
        addr = ipaddress.ip_interface(vlan_json["addr"]) 
        return Vlan(num, addr)

    @property
    def num(self):
        return self._num

    @property
    def addr(self):
        return self._addr

    @property
    def ifaces(self):
        return self._ifaces

    @property
    def router(self):
        return self._router

    def add_iface(self, iface):
        self._ifaces.append(iface)

    def __str__(self):
        return "Vlan <num=%s, addr=%s>" % (self._num, self._addr)

class Ospf:
    def __init__(self, active_vlans=[], origins=[]):
        self._active_vlans = active_vlans
        self._origins = origins
        self._router = None

    @classmethod
    def create(cls, ospf_json, vlans):
        active_vlans = []
        for vlan_json in ospf_json["active"]:
           active_vlans.append(vlans[vlan_json["vlan"]])
        origins = []
        if "origins" in ospf_json:
            origins = ospf_json["origins"]
        return Ospf(active_vlans, origins)

    @property
    def active_vlans(self):
        return self._active_vlans

    @property
    def origins(self):
        return self._origins

    @property
    def router(self):
        return self._router

    def __str__(self):
        result = "OSPF:"
        result += ("\n\tActive VLANs: %s" % (
                ','.join([str(v.num) for v in self._active_vlans])))
        if len(self._origins) > 0:
            result += ("\n\tOrigins: %s" % (','.join(self._origins)))
        return result

class BgpNeighbor:
    def __init__(self, addr):
        self._addr = addr
        self._iface = None
        self._bgp = None

    @classmethod
    def create(cls, neighbor_json):
        return BgpNeighbor(ipaddress.ip_address(neighbor_json["addr"]))

    @property
    def addr(self):
        return self._addr

    @property
    def iface(self):
        return self._iface

    @property
    def bgp(self):
        return self._bgp

    def __str__(self):
        return ("Neighbor <addr=%s%s>" % (self._addr,
                ('' if self._iface is None else 
                    ', router=%s' % self._iface.router.name)))

class Bgp:
    def __init__(self, external=[], internal=[], origins=[]):
        self._external = external
        for neighbor in self._external:
            neighbor._bgp = self
        self._internal = internal
        for neighbor in self._internal:
            neighbor._bgp = self
        self._origins = origins
        self._router = None

    @classmethod
    def create(cls, bgp_json):
        external = []
        if "external" in bgp_json:
            for neighbor_json in bgp_json["external"]:
                external.append(BgpNeighbor.create(neighbor_json))
        internal = []
        if "internal" in bgp_json:
            for neighbor_json in bgp_json["internal"]:
                internal.append(BgpNeighbor.create(neighbor_json))
        origins = []
        if "origins" in bgp_json:
            origins = bgp_json["origins"]
        return Bgp(external, internal, origins)

    @property
    def external(self):
        return self._external

    @property
    def internal(self):
        return self._internal

    @property
    def neighbors(self):
        neighbors = []
        neighbors.extend(self._external)
        neighbors.extend(self._internal)
        return neighbors

    @property
    def origins(self):
        return self._origins

    @property
    def router(self):
        return self._router

    def __str__(self):
        result = "BGP:"
        if len(self._external) > 0:
            result += ("\n\tExternal: %s" % 
                ',\n\t\t  '.join([str(n) for n in self._external]))
        if len(self._internal) > 0:
            result += ("\n\tInternal: %s" %
                ',\n\t\t  '.join([str(n) for n in self._internal]))
        if len(self._origins) > 0:
            result += ("\n\tOrigins: %s" % (','.join(self._origins)))
        return result

class Router:
    def __init__(self, name, ifaces=[], vlans=[], ospf=None, bgp=None, 
            subnets=[]):
        self._name = name
        self._ifaces = ifaces
        for iface in self._ifaces.values():
            iface._router = self
        self._vlans = vlans
        for vlan in self._vlans.values():
            vlan._router = self
        self._ospf = ospf
        if (self._ospf is not None):
            self._ospf._router = self
        self._bgp = bgp
        if (self._bgp is not None):
            self._bgp._router = self
        self._subnets = subnets

    @classmethod
    def create(cls, router_json):
        name = router_json["name"]

        # Create vlans
        vlans = {}
        if "vlans" in router_json:
            for vlan_json in router_json["vlans"]:
                vlan = Vlan.create(vlan_json)
                vlans[vlan.num] = vlan

        # Create ifaces
        ifaces = {}
        for iface_json in router_json["ifaces"]:
            iface = Iface.create(iface_json, vlans)
            ifaces[iface.neighbor] = iface

        # Create ospf
        ospf = None
        if "ospf" in router_json:
            ospf = Ospf.create(router_json["ospf"], vlans)

        # Create bgp
        bgp = None
        if "bgp" in router_json:
            bgp = Bgp.create(router_json["bgp"])

        subnets = []
        if "subnets" in router_json:
            subnets = router_json["subnets"]
        
        return Router(name, ifaces, vlans, ospf, bgp, subnets)

    @property
    def name(self):
        return self._name

    @property
    def ifaces(self):
        return self._ifaces

    @property
    def vlans(self):
        return self._vlans

    @property
    def ospf(self):
        return self._ospf

    @property
    def bgp(self):
        return self._bgp
    
    @property
    def subnets(self):
        return self._subnets

    def __str__(self):
        result = "Router %s:\n" % self._name
        result += ("\tVlans:\n%s\n" % 
                '\n'.join(['\t\t%s' % str(self._vlans[n]) 
                    for n in sorted(self._vlans.keys())]))
        result += ("\tIfaces:\n%s\n" %
                '\n'.join(['\t\t%s' % str(i) 
                    for i in self._ifaces.values()]))
        if (self._ospf is not None):
            result += ("\t%s\n" % str(self._ospf).replace('\n', '\n\t'))
        if (self._bgp is not None):
            result += ("\t%s\n" % (str(self._bgp).replace('\n', '\n\t')))
        if (len(self._subnets) > 0):
            result += ("\tSubnets: %s" % (','.join(self._subnets)))
        return result

class Network:
    def __init__(self, routers):
        self._routers = routers

        # Link interfaces and BGP neighbors
        for router in self._routers.values():
            for iface in router.ifaces.values():
                iface._neighbor = self._routers[iface._neighbor].ifaces[router.name]
            if router.bgp is not None:
                for neighbor in router.bgp.neighbors:
                    self._update_bgp_neighbor_iface(neighbor)

    def _update_bgp_neighbor_iface(self, neighbor):
        for router in self._routers.values():
            for vlan in router.vlans.values():
                if neighbor.addr == vlan.addr.ip:
                    neighbor._iface = vlan
                    return

    @classmethod
    def load(cls, json_path):
        # Load JSON
        with open(json_path, 'r') as json_file:
            json_str = json_file.read()
        network_json = json.loads(json_str)

        # Create routers
        routers = {}
        for router_json in network_json["routers"]:
            router = Router.create(router_json)
            routers[router.name] = router

        # Create network
        return Network(routers)

    @property
    def routers(self):
        return self._routers

    def __str__(self):
        return '\n'.join([str(self._routers[n]) 
            for n in sorted(self._routers.keys())])
