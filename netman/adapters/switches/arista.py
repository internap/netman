import re
import warnings

import pyeapi
from netaddr import IPNetwork
from pyeapi.api.vlans import isvlan
from pyeapi.eapilib import CommandError

from netman.core.objects.exceptions import VlanAlreadyExist, UnknownVlan, BadVlanNumber, BadVlanName, \
    IPAlreadySet, IPNotAvailable, UnknownIP
from netman.core.objects.switch_base import SwitchBase
from netman.core.objects.vlan import Vlan


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
                                   return_node=True)

    def _disconnect(self):
        self.node = None

    def _end_transaction(self):
        pass

    def _start_transaction(self):
        pass

    def commit_transaction(self):
        self.node.enable('write memory')

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

        return vlans[0]

    def get_vlans(self):
        vlans_result, interfaces_result = self.node.enable(["show vlan", "show interfaces"], strict=True)

        vlans = _extract_vlans(vlans_result['result'])
        _apply_interface_data(interfaces_result['result'], vlans)

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


def _extract_vlans(vlans_info):
    vlan_list = []
    for id, vlan in vlans_info['vlans'].items():
        if vlan['name'] == "VLAN{:04d}".format(int(id)):
            vlan['name'] = None

        vlan_list.append(Vlan(number=int(id), name=vlan['name'], icmp_redirects=True, arp_routing=True, ntp=True))
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
