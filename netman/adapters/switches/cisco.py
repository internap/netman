# Copyright 2015 Internap.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import re
import warnings

from netaddr.ip import IPNetwork, IPAddress

from netman import regex
from netman.adapters.shell.ssh import SshClient
from netman.adapters.switches.util import SubShell, split_on_dedent, split_on_bang, no_output
from netman.core.objects.access_groups import IN, OUT
from netman.core.objects.exceptions import IPNotAvailable, UnknownVlan, UnknownIP, UnknownAccessGroup, BadVlanNumber, \
    BadVlanName, UnknownInterface, UnknownVrf, VlanVrfNotSet, IPAlreadySet, VrrpAlreadyExistsForVlan, BadVrrpGroupNumber, \
    BadVrrpPriorityNumber, VrrpDoesNotExistForVlan, BadVrrpTimers, BadVrrpTracking, UnknownDhcpRelayServer, DhcpRelayServerAlreadyExists, \
    VlanAlreadyExist, UnknownBond, InvalidAccessGroupName, InvalidUnicastRPFMode, UnsupportedOperation
from netman.core.objects.interface import Interface
from netman.core.objects.interface_states import OFF, ON
from netman.core.objects.port_modes import DYNAMIC, ACCESS, TRUNK
from netman.core.objects.switch_base import SwitchBase
from netman.core.objects.switch_transactional import FlowControlSwitch
from netman.core.objects.unicast_rpf_modes import STRICT
from netman.core.objects.vlan import Vlan
from netman.core.objects.vrrp_group import VrrpGroup


def ssh(switch_descriptor):
    return Cisco(switch_descriptor=switch_descriptor)


def factory(switch_descriptor, lock):
    warnings.warn("Use SwitchFactory.get_switch_by_descriptor directly to instantiate a switch", DeprecationWarning)

    return FlowControlSwitch(wrapped_switch=ssh(switch_descriptor), lock=lock)


class Cisco(SwitchBase):

    def __init__(self, switch_descriptor):
        super(Cisco, self).__init__(switch_descriptor)
        self.ssh = None

    def _connect(self):
        params = dict(
            host=self.switch_descriptor.hostname,
            username=self.switch_descriptor.username,
            password=self.switch_descriptor.password,
        )
        if self.switch_descriptor.port:
            params["port"] = self.switch_descriptor.port

        self.ssh = SshClient(**params)

        if self.ssh.get_current_prompt().endswith(">"):
            self.ssh.do("enable", wait_for=": ")
            self.ssh.do(self.switch_descriptor.password)

        self.ssh.do("terminal length 0")
        self.ssh.do("terminal width 0")

    def _disconnect(self):
        self.ssh.quit("exit")
        self.logger.info(self.ssh.full_log)

    def _end_transaction(self):
        pass

    def _start_transaction(self):
        pass

    def commit_transaction(self):
        self.ssh.do("write memory")

    def rollback_transaction(self):
        pass

    def get_vlan(self, number):
        vlan = Vlan(int(number), icmp_redirects=True, arp_routing=True, ntp=True)
        apply_vlan_running_config_data(vlan, self._get_vlan_run_conf(number))
        apply_interface_running_config_data(
            vlan,
            self.ssh.do("show running-config interface vlan {} | begin interface".format(number))
        )
        return vlan

    def get_vlans(self):
        vlan_list = self.ssh.do("show vlan brief")

        vlans = {}
        for line in vlan_list:
            if regex.match('^(\d+)\s+(\S+).*', line):
                number, name = regex

                if name == ("VLAN{}".format(number)):
                    name = None

                vlans[number] = Vlan(int(number), name, icmp_redirects=True, arp_routing=True, ntp=True)

        for ip_interface_data in split_on_dedent(self.ssh.do("show ip interface")):
            if regex.match("^Vlan(\d+)\s.*", ip_interface_data[0]):
                current_vlan = vlans.get(regex[0])
                if current_vlan:
                    apply_interface_running_config_data(
                        current_vlan,
                        self.ssh.do("show running-config interface vlan {}".format(current_vlan.number))
                    )
        return vlans.values()

    def add_vlan(self, number, name=None):
        if self._show_run_vlan(number):
            raise VlanAlreadyExist(number)

        with self.config():
            result = self.ssh.do('vlan {}'.format(number))
            if len(result) > 0:
                raise BadVlanNumber()
            else:
                if name:
                    result = self.ssh.do('name {}'.format(name))

                self.ssh.do('exit')

                if len(result) > 0:
                    raise BadVlanName()

    def remove_vlan(self, number):
        self._get_vlan_run_conf(number)

        with self.config():
            self.ssh.do('no interface vlan {}'.format(number))
            self.ssh.do('no vlan {}'.format(number))

    def get_interfaces(self):
        interfaces = []
        for data in split_on_bang(self.ssh.do("show running-config | begin interface")):
            interface = parse_interface(data)
            if interface:
                interfaces.append(interface)
        return interfaces

    def set_access_vlan(self, interface_id, vlan):
        self._get_vlan_run_conf(vlan)

        with self.config(), self.interface(interface_id):
            self.ssh.do('switchport access vlan {}'.format(vlan))

    def unset_interface_access_vlan(self, interface_id):
        with self.config(), self.interface(interface_id):
            self.ssh.do('no switchport access vlan')

    def set_access_mode(self, interface_id):
        with self.config(), self.interface(interface_id):
            self.ssh.do('switchport mode access')
            self.ssh.do('no switchport trunk native vlan')
            self.ssh.do('no switchport trunk allowed vlan')

    def set_trunk_mode(self, interface_id):
        has_trunk_allowed = self.has_trunk_allowed_set(interface_id)
        with self.config(), self.interface(interface_id):
            self.ssh.do('switchport mode trunk')
            if not has_trunk_allowed:
                self.ssh.do('switchport trunk allowed vlan none')
            self.ssh.do('no switchport access vlan')

    def add_trunk_vlan(self, interface_id, vlan):
        self._get_vlan_run_conf(vlan)

        with self.config(), self.interface(interface_id):
            self.ssh.do('switchport trunk allowed vlan add {}'.format(vlan))

    def remove_trunk_vlan(self, interface_id, vlan):
        interface = self.get_interface(interface_id)
        if vlan not in interface.trunk_vlans:
            raise UnknownVlan(vlan)

        with self.config(), self.interface(interface_id):
            self.ssh.do('switchport trunk allowed vlan remove {}'.format(vlan))

    def set_interface_state(self, interface_id, state):
        with self.config(), self.interface(interface_id):
            self.ssh.do('shutdown' if state is OFF else "no shutdown")

    def set_interface_native_vlan(self, interface_id, vlan):
        self._get_vlan_run_conf(vlan)

        with self.config(), self.interface(interface_id):
            self.ssh.do('switchport trunk native vlan {}'.format(vlan))

    def unset_interface_native_vlan(self, interface_id):
        with self.config(), self.interface(interface_id):
            self.ssh.do('no switchport trunk native vlan')

    def add_ip_to_vlan(self, vlan_number, ip_network):
        vlan = self.get_vlan_interface_data(vlan_number)

        ip_found = next((ip for ip in vlan.ips if ip.ip == ip_network.ip), False)
        if ip_found:
            raise IPAlreadySet(ip_network, ip_found)

        has_ips = len(vlan.ips) > 0
        with self.config(), self.interface_vlan(vlan_number):
            if has_ips:
                self.ssh.do('no ip redirects')
            result = self.ssh.do('ip address {} {}{}'.format(ip_network.ip, ip_network.netmask,
                                                             " secondary" if has_ips else ""))
            if len(result) > 0:
                raise IPNotAvailable(ip_network, reason="; ".join(result))

    def remove_ip_from_vlan(self, vlan_number, ip_network):
        vlan = self.get_vlan_interface_data(vlan_number)
        existing_ip = next((ip for ip in vlan.ips if ip.ip == ip_network.ip and ip.netmask == ip_network.netmask), False)

        if existing_ip:
            ip_index = vlan.ips.index(existing_ip)
            with self.config(), self.interface_vlan(vlan_number):
                if ip_index == 0:
                    if len(vlan.ips) == 1:
                        self.ssh.do('no ip address {} {}'.format(ip_network.ip, ip_network.netmask))
                    else:
                        self.ssh.do('ip address {} {}'.format(vlan.ips[1].ip, vlan.ips[1].netmask))
                else:
                    self.ssh.do('no ip address {} {} secondary'.format(ip_network.ip, ip_network.netmask))
        else:
            raise UnknownIP(ip_network)

    def has_trunk_allowed_set(self, interface_id):
        for line in self.ssh.do('show running-config interface {}'.format(interface_id)):
            if 'Invalid input detected' in line:
                raise UnknownInterface(interface_id)
            if 'switchport trunk allowed' in line:
                return True
        return False

    def set_vlan_access_group(self, vlan_number, direction, name):
        self.get_vlan_interface_data(vlan_number)

        with self.config(), self.interface_vlan(vlan_number):
            result = self.ssh.do("ip access-group {} {}".format(name, 'in' if direction == IN else 'out'))
            if len(result) > 0:
                raise InvalidAccessGroupName(name)

    def unset_vlan_access_group(self, vlan_number, direction):
        vlan = self.get_vlan_interface_data(vlan_number)

        if vlan.access_groups[direction] is None:
            raise UnknownAccessGroup(direction)
        else:
            with self.config(), self.interface_vlan(vlan_number):
                self.ssh.do("no ip access-group {}".format(('in' if direction == IN else 'out')))

    def set_vlan_vrf(self, vlan_number, vrf_name):
        self.get_vlan_interface_data(vlan_number)

        with self.config(), self.interface_vlan(vlan_number):
            result = self.ssh.do("ip vrf forwarding {}".format(vrf_name))
            if len(result) > 0:
                raise UnknownVrf(vrf_name)

    def unset_vlan_vrf(self, vlan_number):
        vlan = self.get_vlan_interface_data(vlan_number)

        if vlan.vrf_forwarding is None:
            raise VlanVrfNotSet(vlan_number)
        else:
            with self.config(), self.interface_vlan(vlan_number):
                self.ssh.do("no ip vrf forwarding")

    def add_dhcp_relay_server(self, vlan_number, ip_address):
        vlan = self.get_vlan_interface_data(vlan_number)

        if ip_address in vlan.dhcp_relay_servers:
            raise DhcpRelayServerAlreadyExists(vlan_number=vlan_number, ip_address=ip_address)

        with self.config(), self.interface_vlan(vlan_number):
            self.ssh.do("ip helper-address {}".format(ip_address))

    def remove_dhcp_relay_server(self, vlan_number, ip_address):
        vlan = self.get_vlan_interface_data(vlan_number)

        if ip_address not in vlan.dhcp_relay_servers:
            raise UnknownDhcpRelayServer(vlan_number=vlan_number, ip_address=ip_address)

        with self.config(), self.interface_vlan(vlan_number):
            self.ssh.do("no ip helper-address {}".format(ip_address))

    def get_vlan_interfaces(self, vlan_number):
        vlan_interfaces = get_vlan_interfaces_from_data(vlan_number, self.get_interfaces())
        if not vlan_interfaces:
            self.get_vlan(vlan_number)
        return vlan_interfaces

    def set_bond_trunk_mode(self, number):
        with NamedBond(number) as bond:
            return self.set_trunk_mode(bond.name)

    def set_bond_access_mode(self, number):
        with NamedBond(number) as bond:
            return self.set_access_mode(bond.name)

    def add_bond_trunk_vlan(self, number, vlan):
        with NamedBond(number) as bond:
            return self.add_trunk_vlan(bond.name, vlan)

    def remove_bond_trunk_vlan(self, number, vlan):
        with NamedBond(number) as bond:
            return self.remove_trunk_vlan(bond.name, vlan)

    def set_bond_native_vlan(self, number, vlan):
        with NamedBond(number) as bond:
            return self.set_interface_native_vlan(bond.name, vlan)

    def unset_bond_native_vlan(self, number):
        with NamedBond(number) as bond:
            return self.unset_interface_native_vlan(bond.name)

    def config(self):
        return SubShell(self.ssh, enter="configure terminal", exit_cmd='exit')

    def interface(self, interface_id):
        return SubShell(self.ssh, enter="interface {}".format(interface_id), exit_cmd='exit',
                        validate=no_output(UnknownInterface, interface_id))

    def interface_vlan(self, interface_id):
        return SubShell(self.ssh, enter=["interface vlan {}".format(interface_id), "no shutdown"], exit_cmd='exit')

    def _get_vlan_run_conf(self, vlan_number):
        run_config = self._show_run_vlan(vlan_number)
        if not run_config:
            raise UnknownVlan(vlan_number)
        return run_config

    def _show_run_vlan(self, vlan_number):
        return self.ssh.do('show running-config vlan {} | begin vlan'.format(vlan_number))

    def get_vlan_interface_data(self, vlan_number):
        run_int_vlan_data = self.ssh.do('show running-config interface vlan {}'.format(vlan_number))
        if not run_int_vlan_data[0].startswith("Building configuration..."):
            self._get_vlan_run_conf(vlan_number)

        vlan = Vlan(vlan_number)
        apply_interface_running_config_data(vlan, run_int_vlan_data)
        return vlan

    def get_interface(self, interface_id):
        data = self.ssh.do("show running-config interface {} | begin interface".format(interface_id))
        interface = parse_interface(data)
        if not interface:
            raise UnknownInterface(interface_id)
        return interface

    def add_vrrp_group(self, vlan_number, group_id, ips=None, priority=None, hello_interval=None, dead_interval=None,
                       track_id=None, track_decrement=None):
        if not (0 < group_id <= 255):
            raise BadVrrpGroupNumber(1, 255)

        vlan = self.get_vlan_interface_data(vlan_number)

        if [group for group in vlan.vrrp_groups if group.id == group_id]:
            raise VrrpAlreadyExistsForVlan(vlan=vlan_number, vrrp_group_id=group_id)

        with self.config(), self.interface_vlan(vlan_number):
            if len(vlan.vrrp_groups) == 0:
                self.ssh.do('standby version 2')

            if hello_interval is not None and dead_interval is not None:
                result = self.ssh.do('standby {group_id} timers {hello_interval} {dead_interval}'.format(
                    group_id=group_id, hello_interval=hello_interval, dead_interval=dead_interval))
                if len(result) > 0:
                    raise BadVrrpTimers()

            if priority is not None:
                result = self.ssh.do('standby {group_id} priority {priority}'.format(group_id=group_id, priority=priority))
                if len(result) > 0:
                    raise BadVrrpPriorityNumber(1, 255)

            self.ssh.do('standby {group_id} preempt delay minimum 60'.format(group_id=group_id))
            self.ssh.do('standby {group_id} authentication {authentication}'.format(group_id=group_id,
                                                                                    authentication='VLAN{}'.format(vlan_number)))

            if track_id is not None and track_decrement is not None:
                result = self.ssh.do('standby {group_id} track {track_id} decrement {track_decrement}'.format(
                    group_id=group_id, track_id=track_id, track_decrement=track_decrement))
                if len(result) > 0:
                    raise BadVrrpTracking()

            for i, ip in enumerate(ips):
                result = self.ssh.do('standby {group_id} ip {ip}{secondary}'.format(
                    group_id=group_id, ip=ip, secondary=' secondary' if i > 0 else ''))
                if len(result) > 0:
                    raise IPNotAvailable(ip, reason="; ".join(result))

    def remove_vrrp_group(self, vlan_number, group_id):
        vlan = self.get_vlan_interface_data(vlan_number)

        if not [group for group in vlan.vrrp_groups if group.id == group_id]:
            raise VrrpDoesNotExistForVlan(vlan=vlan_number, vrrp_group_id=group_id)

        with self.config(), self.interface_vlan(vlan_number):
            result = self.ssh.do('no standby {group_id}'.format(group_id=group_id))
            if len(result) > 0:
                raise VrrpDoesNotExistForVlan(vlan=vlan_number, vrrp_group_id=group_id)

            if len(vlan.vrrp_groups) == 1:
                self.ssh.do('no standby version')

    def set_vlan_arp_routing_state(self, vlan_number, state):
        self.get_vlan_interface_data(vlan_number)

        with self.config(), self.interface_vlan(vlan_number):
            if state == ON:
                self.ssh.do('ip proxy-arp')
            else:
                self.ssh.do('no ip proxy-arp')

    def set_vlan_icmp_redirects_state(self, vlan_number, state):
        self.get_vlan_interface_data(vlan_number)

        with self.config(), self.interface_vlan(vlan_number):
            if state:
                self.ssh.do('ip redirects')
            else:
                self.ssh.do('no ip redirects')

    def set_vlan_ntp_state(self, vlan_number, state):
        self.get_vlan_interface_data(vlan_number)

        with self.config(), self.interface_vlan(vlan_number):
            self.ssh.do('{}ntp disable'.format('no ' if state else ''))

    def reset_interface(self, interface_id):
        with self.config():
            for line in self.ssh.do('default interface {}'.format(interface_id)):
                if 'Invalid input detected' in line:
                    raise UnknownInterface(interface_id)

    def get_versions(self):
        result = self.ssh.do('show version')

        versions = {}
        for i, line in enumerate(result):
            matches = re.match("^(.*)\s:\s(.*)$", line)
            if matches:
                values = matches.groups()
                versions[values[0].strip()] = values[1]

            matches = re.match("^.*(\d+)\s+(\d+)\s+([^\s]+)\s+([^\s]+)\s+([^\s]+)\s*$", line)
            if matches:
                values = matches.groups()
                if "units" not in versions:
                    versions["units"] = {}

                versions["units"][values[0]] = {
                    "Ports": values[1],
                    "Model": values[2],
                    "SW Version": values[3],
                    "SW Image": values[4]
                }

        return versions

    def set_vlan_unicast_rpf_mode(self, vlan_number, mode):
        operations = {STRICT: self._set_unicast_rpf_strict}

        if mode not in operations:
            raise InvalidUnicastRPFMode(mode)

        self.get_vlan_interface_data(vlan_number)

        with self.config(), self.interface_vlan(vlan_number):
            operations[mode]()

    def unset_vlan_unicast_rpf_mode(self, vlan_number):
        self.get_vlan_interface_data(vlan_number)

        with self.config(), self.interface_vlan(vlan_number):
            self.ssh.do('no ip verify unicast')

    def _set_unicast_rpf_strict(self):
        result = self.ssh.do('ip verify unicast source reachable-via rx')
        if len(result) > 0:
            raise UnsupportedOperation("Unicast RPF Mode Strict", "\n".join(result))


def parse_interface(data):
    if data and (regex.match("interface (\w*Ethernet[^\s]*)", data[0]) or regex.match("interface (Port-channel[^\s]*)", data[0])):
        i = Interface(name=regex[0], shutdown=False)
        port_mode = access_vlan = native_vlan = trunk_vlans = None
        for line in data:
            if regex.match(" switchport mode (.*)", line):
                port_mode = regex[0]
            if regex.match(" switchport access vlan (\d*)", line):
                access_vlan = int(regex[0])
            if regex.match(" switchport trunk native vlan (\d*)", line):
                native_vlan = int(regex[0])
            if regex.match(" switchport trunk allowed vlan (.*)", line):
                trunk_vlans = regex[0]
            if regex.match(" shutdown", line):
                i.shutdown = True

        if not port_mode:
            i.port_mode = DYNAMIC
            i.access_vlan = access_vlan
            i.trunk_native_vlan = native_vlan
            i.trunk_vlans = parse_vlan_ranges(trunk_vlans) if trunk_vlans else []
        elif port_mode == 'access':
            i.port_mode = ACCESS
            i.access_vlan = access_vlan
        elif port_mode == 'trunk':
            i.port_mode = TRUNK
            i.trunk_native_vlan = native_vlan
            i.trunk_vlans = parse_vlan_ranges(trunk_vlans) if trunk_vlans else []

        return i
    return None


def apply_interface_running_config_data(vlan, data):
    for line in data:
        if regex.match("^ ip address ([^\s]*) ([^\s]*)(.*)", line):
            ip = IPNetwork("{}/{}".format(regex[0], regex[1]))
            if "secondary" not in regex[2]:
                vlan.ips.insert(0, ip)
            else:
                vlan.ips.append(ip)

        elif regex.match("^ ip access-group ([^\s]*) ([^\s]*).*", line):
            if regex[1] == "in":
                vlan.access_groups[IN] = regex[0]
            else:
                vlan.access_groups[OUT] = regex[0]

        elif regex.match("^ ip vrf forwarding ([^\s]*).*", line):
            vlan.vrf_forwarding = regex[0]

        elif regex.match("^ standby ([\d]+) (.*)", line):
            vrrp_group = next((group for group in vlan.vrrp_groups if str(group.id) == regex[0]), None)
            if vrrp_group is None:
                vrrp_group = VrrpGroup(id=int(regex[0]))
                vlan.vrrp_groups.append(vrrp_group)

            vrrp_info = regex[1].strip()

            if regex.match("^ip ([^\s]*).*", vrrp_info):
                vrrp_group.ips.append(IPAddress(regex[0]))
            elif regex.match("^timers ([^\s]*) ([^\s]*)", vrrp_info):
                vrrp_group.hello_interval = int(regex[0])
                vrrp_group.dead_interval = int(regex[1])
            elif regex.match("^priority ([^\s]*)", vrrp_info):
                vrrp_group.priority = int(regex[0])
            elif regex.match("^track ([^\s]*) decrement ([^\s]*)", vrrp_info):
                vrrp_group.track_id = regex[0]
                vrrp_group.track_decrement = int(regex[1])

        elif regex.match("^ ip helper-address ([^\s]*)", line):
            vlan.dhcp_relay_servers.append(IPAddress(regex[0]))

        elif regex.match("^ no ip proxy-arp", line):
            vlan.arp_routing = False

        elif regex.match("^ no ip redirects", line):
            vlan.icmp_redirects = False

        elif regex.match("^ ip verify unicast source reachable-via rx", line):
            vlan.unicast_rpf_mode = STRICT

        elif regex.match("^ ntp disable", line):
            vlan.ntp = False


def apply_vlan_running_config_data(vlan, data):
    for line in data:
        if regex.match("^ name ([^\s]*)", line):
            vlan.name = regex[0]


def parse_vlan_ranges(all_ranges):
    if all_ranges is None:
        return range(1, 4094)
    elif all_ranges == "none":
        return []
    else:
        full_list = []
        for vlan_list in [parse(r) for r in all_ranges.split(",")]:
            full_list += vlan_list
        return full_list


def get_vlan_interfaces_from_data(vlan_number, interfaces_data):
    vlan_interfaces = []
    for interface in interfaces_data:
        if interface.port_mode is TRUNK:
            if interface.trunk_vlans and vlan_number in interface.trunk_vlans:
                vlan_interfaces.append(interface.name)
            elif vlan_number == interface.trunk_native_vlan:
                vlan_interfaces.append(interface.name)
        elif interface.port_mode is ACCESS and interface.access_vlan == vlan_number:
            vlan_interfaces.append(interface.name)
        elif interface.port_mode is DYNAMIC:
            if interface.access_vlan == vlan_number or interface.trunk_native_vlan == vlan_number or \
                    (interface.trunk_vlans and vlan_number in interface.trunk_vlans):
                vlan_interfaces.append(interface.name)
    return vlan_interfaces


def parse(single_range):
    if regex.match("(\d+)-(\d+)", single_range):
        return range(int(regex[0]), int(regex[1]) + 1)
    else:
        return [int(single_range)]


def bond_name(number):
    return "Port-channel{}".format(number)


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
