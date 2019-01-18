import re
import warnings

import pyeapi
from netaddr import IPNetwork, IPAddress, AddrFormatError
from pyeapi.api.vlans import isvlan
from pyeapi.eapilib import CommandError

from netman import regex
from netman.adapters.shell import default_command_timeout
from netman.adapters.switches.util import split_on_dedent
from netman.core.objects.exceptions import VlanAlreadyExist, UnknownVlan, BadVlanNumber, BadVlanName, \
    IPAlreadySet, IPNotAvailable, UnknownIP, DhcpRelayServerAlreadyExists, UnknownDhcpRelayServer, UnknownInterface, \
    UnknownBond, VarpAlreadyExistsForVlan, VarpDoesNotExistForVlan, BadLoadIntervalNumber
from netman.core.objects.interface import Interface
from netman.core.objects.interface_states import OFF, ON
from netman.core.objects.port_modes import ACCESS, TRUNK
from netman.core.objects.switch_base import SwitchBase
from netman.core.objects.vlan import Vlan
from netman.core.validator import is_valid_mpls_state


def eapi_http(switch_descriptor):
    return Arista(switch_descriptor, transport="http")


def eapi_https(switch_descriptor):
    return Arista(switch_descriptor, transport="https")


def eapi(switch_descriptor):
    warnings.warn("Use either the _http or _https driver", DeprecationWarning)

    m = re.match('^(https?):\/\/(.*)$', switch_descriptor.hostname.lower())
    transport, hostname = (m.group(1), m.group(2)) if m else ('https', switch_descriptor.hostname)

    switch_descriptor.hostname = hostname
    return Arista(switch_descriptor, transport=transport)


class Arista(SwitchBase):
    def __init__(self, switch_descriptor, transport):
        super(Arista, self).__init__(switch_descriptor)
        self.switch_descriptor = switch_descriptor
        self.transport = transport

    def _connect(self):
        self.node = pyeapi.connect(host=self.switch_descriptor.hostname,
                                   username=self.switch_descriptor.username,
                                   password=self.switch_descriptor.password,
                                   port=self.switch_descriptor.port,
                                   transport=self.transport,
                                   return_node=True,
                                   timeout=default_command_timeout)

    def _disconnect(self):
        self.node = None

    def _end_transaction(self):
        pass

    def _start_transaction(self):
        pass

    def commit_transaction(self):
        self.node.enable('write memory')

    def rollback_transaction(self):
        pass

    def get_vlan(self, number):
        try:
            vlans_result, interfaces_result = self.node.enable(
                ["show vlan {}".format(number), "show interfaces Vlan{}".format(number)], strict=True)
            vlans_info = vlans_result['result']
            interfaces_info = interfaces_result['result']
        except CommandError as e:
            if "not found in current VLAN database" in e.command_error:
                raise UnknownVlan(number)
            elif "Invalid input" in e.command_error:
                raise BadVlanNumber()
            elif "Interface does not exist" in e.command_error:
                vlans_info = e.output[1]
                interfaces_info = {"interfaces": {}}
            else:
                raise

        vlans = _extract_vlans(vlans_info)
        _apply_interface_data(interfaces_info, vlans)
        self._apply_interface_vlan_data(vlans)

        return vlans[0]

    def get_vlans(self):
        vlans_result, interfaces_result = self.node.enable(["show vlan", "show interfaces"], strict=True)

        vlans = _extract_vlans(vlans_result['result'])
        _apply_interface_data(interfaces_result['result'], vlans)
        self._apply_interface_vlan_data(vlans)

        return sorted(vlans, key=lambda v: v.number)

    def add_vlan(self, number, name=None):
        if not isvlan(number):
            raise BadVlanNumber()
        try:
            self.node.enable(["show vlan {}".format(number)], strict=True)
            raise VlanAlreadyExist(number)
        except CommandError:
            pass

        commands = ["vlan {}".format(number)]
        if name is not None:
            commands.append("name {}".format(name))

        try:
            self.node.config(commands)
        except CommandError:
            raise BadVlanName()

    def remove_vlan(self, number):
        try:
            self.node.enable(["show vlan {}".format(number)], strict=True)
        except CommandError:
            raise UnknownVlan(number)

        self.node.config(["no interface Vlan{}".format(number), "no vlan {}".format(number)])

    def add_ip_to_vlan(self, vlan_number, ip_network):
        vlan = self.get_vlan(vlan_number)

        ip_found = next((ip for ip in vlan.ips if ip.ip == ip_network.ip), False)
        if ip_found:
            raise IPAlreadySet(ip_network, ip_found)

        has_ips = len(vlan.ips) > 0
        add_ip_command = "ip address {}{}".format(str(ip_network), " secondary" if has_ips else "")

        commands = [
            "interface vlan {}".format(vlan_number),
            add_ip_command
        ]
        try:
            self.node.config(commands)
        except CommandError as e:
            raise IPNotAvailable(ip_network, reason=str(e))

    def remove_ip_from_vlan(self, vlan_number, ip_network):
        vlan = self.get_vlan(vlan_number)
        existing_ip = next((ip for ip in vlan.ips
                            if ip.ip == ip_network.ip and ip.netmask == ip_network.netmask),
                           False)

        if existing_ip:
            ip_index = vlan.ips.index(existing_ip)
            if ip_index == 0:
                if len(vlan.ips) == 1:
                    remove_ip_command = "no ip address {}".format(str(ip_network))
                else:
                    remove_ip_command = "ip address {}".format(str(vlan.ips[1]))
            else:
                remove_ip_command = "no ip address {} secondary".format(str(ip_network))

            commands = [
                "interface Vlan{}".format(vlan_number),
                remove_ip_command
            ]
            self.node.config(commands)
        else:
            raise UnknownIP(ip_network)

    def get_interface(self, interface_id):
        commands = [
            "show interfaces {}".format(interface_id),
            "show interfaces {} switchport".format(interface_id)
        ]
        try:
            result = self.node.enable(commands, strict=True)
        except CommandError:
            raise UnknownInterface(interface_id)

        interfaces = parse_interfaces(result[0]['result']['interfaces'], result[1]['result']['switchports'])
        if len(interfaces) > 0:
            return interfaces[0]
        raise UnknownInterface(interface_id)

    def get_interfaces(self):
        commands = [
            "show interfaces",
            "show interfaces switchport"
        ]
        result = self.node.enable(commands, strict=True)

        interfaces = parse_interfaces(result[0]['result']['interfaces'], result[1]['result']['switchports'])
        return interfaces

    def set_trunk_mode(self, interface_id):
        commands = [
            "interface {}".format(interface_id),
            "switchport mode trunk",
            "switchport trunk allowed vlan none"
        ]
        try:
            self.node.config(commands)
        except CommandError:
            raise UnknownInterface(interface_id)

    def add_trunk_vlan(self, interface_id, vlan):
        self.get_vlan(vlan)
        commands = [
            "interface {}".format(interface_id),
            "switchport trunk allowed vlan add {}".format(vlan)
        ]
        try:
            self.node.config(commands)
        except CommandError:
            raise UnknownInterface(interface_id)

    def remove_trunk_vlan(self, interface_id, vlan):
        interface = self.get_interface(interface_id)
        if vlan not in interface.trunk_vlans:
            raise UnknownVlan(vlan)

        commands = [
            "interface {}".format(interface_id),
            "switchport trunk allowed vlan remove {}".format(vlan)
        ]
        self.node.config(commands)

    def set_bond_trunk_mode(self, number):
        with NamedBond(number) as bond:
            return self.set_trunk_mode(bond.name)

    def add_bond_trunk_vlan(self, number, vlan):
        with NamedBond(number) as bond:
            return self.add_trunk_vlan(bond.name, vlan)

    def remove_bond_trunk_vlan(self, number, vlan):
        with NamedBond(number) as bond:
            return self.remove_trunk_vlan(bond.name, vlan)

    def add_dhcp_relay_server(self, vlan_number, ip_address):
        vlan = self.get_vlan(vlan_number)

        if ip_address in vlan.dhcp_relay_servers:
            raise DhcpRelayServerAlreadyExists(vlan_number=vlan_number, ip_address=ip_address)

        self.node.config(['interface Vlan{}'.format(vlan_number),
                          'ip helper-address {}'.format(ip_address)])

    def remove_dhcp_relay_server(self, vlan_number, ip_address):
        vlan = self.get_vlan(vlan_number)

        if ip_address not in vlan.dhcp_relay_servers:
            raise UnknownDhcpRelayServer(vlan_number=vlan_number, ip_address=ip_address)

        self.node.config(['interface Vlan{}'.format(vlan_number),
                          'no ip helper-address {}'.format(ip_address)])

    def set_vlan_load_interval(self, vlan_number, time_interval):
        self.get_vlan(vlan_number)

        try:
            self.node.config(['interface Vlan{}'.format(vlan_number),
                              'load-interval {}'.format(time_interval)])
        except CommandError:
            raise BadLoadIntervalNumber()

    def unset_vlan_load_interval(self, vlan_number):
        self.get_vlan(vlan_number)

        self.node.config(['interface Vlan{}'.format(vlan_number),
                          'no load-interval'])

    def set_vlan_mpls_ip_state(self, vlan_number, state):
        is_valid_mpls_state(state)
        self.get_vlan(vlan_number)

        self.node.config(['interface Vlan{}'.format(vlan_number),
                          'mpls ip' if state else 'no mpls ip'])

    def add_vlan_varp_ip(self, vlan_number, ip_network):
        vlan = self.get_vlan(vlan_number)

        if ip_network in vlan.varp_ips:
            raise VarpAlreadyExistsForVlan(vlan=vlan_number, ip_network=ip_network)

        try:
            self.node.config(['interface Vlan{}'.format(vlan_number),
                              'ip virtual-router address {}'.format(ip_network)])
        except CommandError as e:
            if regex.match("^.*is already assigned to interface Vlan(\d+)]", e.message):
                raise IPNotAvailable(ip_network=ip_network, reason=str(e))
            raise

    def remove_vlan_varp_ip(self, vlan_number, ip_network):
        vlan = self.get_vlan(vlan_number)

        if ip_network not in vlan.varp_ips:
            raise VarpDoesNotExistForVlan(vlan=vlan_number, ip_network=ip_network)

        self.node.config(['interface Vlan{}'.format(vlan_number),
                          'no ip virtual-router address {}'.format(ip_network)])

    def _apply_interface_vlan_data(self, vlans):
        config = self._fetch_interface_vlans_config(vlans)

        for interface in split_on_dedent(config):
            if regex.match("^.*Vlan(\d+)$", interface[0]):
                vlan = _find_vlan_by_number(vlans, regex[0])
                for line in interface[1:]:
                    if regex.match(" *ip helper-address (.*)", line):
                        try:
                            vlan.dhcp_relay_servers.append(IPAddress(regex[0]))
                        except AddrFormatError:
                            self.logger.warning(
                                'Unsupported IP Helper address found in Vlan {} : {}'.format(vlan.number, regex[0]))
                    if regex.match(" *ip virtual-router address (.*)", line):
                        vlan.varp_ips.append(IPNetwork(regex[0]))
                    if regex.match(" *load-interval (.*)", line):
                        vlan.load_interval = int(regex[0])
                    if regex.match(" *no mpls ip", line):
                        vlan.mpls_ip = False

    def _fetch_interface_vlans_config(self, vlans):
        all_interface_vlans = sorted('Vlan{}'.format(vlan.number) for vlan in vlans)
        return self.node.get_config(params='interfaces {}'.format(' '.join(all_interface_vlans)))


def _find_vlan_by_number(vlans, number):
    return next((vlan for vlan in vlans if vlan.number == int(number)))


def parse_interfaces(interfaces_data, switchports_data):
    interfaces = []
    for interface_data in interfaces_data.values():
        if regex.match("(\w*Ethernet[^\s]*)", interface_data["name"]) or \
                regex.match("(Port-channel[^\s]*)", interface_data["name"]):

            interface = Interface(name=interface_data["name"], shutdown=False)

            if interface_data["lineProtocolStatus"] == "down":
                interface.shutdown = True

            interface.mtu = int(interface_data["mtu"])
            interface.auto_negotiation = ON if interface_data["autoNegotiate"] == "on" else OFF

            if interface.name in switchports_data:
                patch_switchport(interface, switchports_data[interface.name]["switchportInfo"])

            interfaces.append(interface)

    return interfaces


def patch_switchport(interface, data):
    if data["mode"] == "access":
        interface.port_mode = ACCESS
    elif data["mode"] == "trunk":
        interface.port_mode = TRUNK

    interface.trunk_native_vlan = data["trunkingNativeVlanId"]
    interface.trunk_vlans = parse_vlan_ranges(data["trunkAllowedVlans"]) if data["trunkAllowedVlans"] else []


def parse_vlan_ranges(all_ranges):
    if all_ranges is None or all_ranges == "ALL":
        return range(1, 4094)
    elif all_ranges == "NONE":
        return []
    else:
        full_list = []
        for vlan_list in [parse_range(r) for r in all_ranges.split(",")]:
            full_list += vlan_list
        return full_list


def parse_range(single_range):
    if regex.match("(\d+)-(\d+)", single_range):
        return range(int(regex[0]), int(regex[1]) + 1)
    else:
        return [int(single_range)]


def bond_name(number):
    return "Port-Channel{}".format(number)


class NamedBond(object):
    def __init__(self, number):
        self.number = number

    @property
    def name(self):
        return bond_name(self.number)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is UnknownInterface:
            raise UnknownBond(self.number), None, exc_tb


def _extract_vlans(vlans_info):
    vlan_list = []
    for id, vlan in vlans_info['vlans'].items():
        if vlan['name'] == "VLAN{:04d}".format(int(id)):
            vlan['name'] = None

        vlan_list.append(Vlan(number=int(id), name=vlan['name'], icmp_redirects=True,
                              arp_routing=True, ntp=True, mpls_ip=True))
    return vlan_list


def _apply_interface_data(interfaces_result, vlans):
    interfaces = interfaces_result["interfaces"]
    for vlan in vlans:
        interface_name = "Vlan{}".format(vlan.number)

        interface_data = interfaces.get(interface_name)
        if interface_data is not None and len(interface_data["interfaceAddress"]) > 0:
            interface_address = interface_data["interfaceAddress"][0]

            primary_ip_data = interface_address["primaryIp"]
            secondary_ips_data = interface_address["secondaryIpsOrderedList"]

            primary_ip = _to_ip(primary_ip_data)

            if primary_ip.ip != IPNetwork("0.0.0.0/0").ip:
                vlan.ips.append(primary_ip)

                for addr in secondary_ips_data:
                    vlan.ips.append(_to_ip(addr))


def _to_ip(ip_data):
    return IPNetwork("{}/{}".format(ip_data["address"], ip_data["maskLen"]))
