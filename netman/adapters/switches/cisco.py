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

from netaddr.ip import IPNetwork, IPAddress

from netman import regex
from netman.adapters.switches import SubShell, split_on_dedent, split_on_bang, no_output
from netman.adapters.shell import ssh
from netman.core.objects.access_groups import IN, OUT
from netman.core.objects.exceptions import IPNotAvailable, UnknownVlan, UnknownIP, UnknownAccessGroup, BadVlanNumber, \
    BadVlanName, UnknownInterface, UnknownVrf, VlanVrfNotSet, IPAlreadySet, VrrpAlreadyExistsForVlan, BadVrrpGroupNumber, \
    BadVrrpPriorityNumber, VrrpDoesNotExistForVlan, BadVrrpTimers, BadVrrpTracking, UnknownDhcpRelayServer, DhcpRelayServerAlreadyExists
from netman.core.objects.interface import Interface
from netman.core.objects.port_modes import DYNAMIC, ACCESS, TRUNK
from netman.core.objects.switch_base import SwitchBase
from netman.core.objects.switch_transactional import SwitchTransactional
from netman.core.objects.vlan import Vlan
from netman.core.objects.vrrp_group import VrrpGroup


def factory(switch_descriptor, lock):
    return SwitchTransactional(
        impl=Cisco(switch_descriptor=switch_descriptor),
        lock=lock
    )


class Cisco(SwitchBase):

    def __init__(self, switch_descriptor):
        super(Cisco, self).__init__(switch_descriptor)
        self.ssh = None

    def connect(self):
        self.ssh = ssh.SshClient(
            host=self.switch_descriptor.hostname,
            username=self.switch_descriptor.username,
            password=self.switch_descriptor.password,
            port=self.switch_descriptor.port or 22
        )
        if self.ssh.get_current_prompt().endswith(">"):
            self.ssh.do("enable", wait_for=": ")
            self.ssh.do(self.switch_descriptor.password)

        self.ssh.do("terminal length 0")
        self.ssh.do("terminal width 0")

    def disconnect(self):
        self.ssh.quit("exit")
        self.logger.info(self.ssh.full_log)

    def end_transaction(self):
        pass

    def start_transaction(self):
        pass

    def commit_transaction(self):
        self.ssh.do("write memory")

    def rollback_transaction(self):
        pass

    def get_vlans(self):
        vlan_list = self.ssh.do("show vlan brief")

        vlans = {}
        for line in vlan_list:
            if regex.match('^(\d+)\s+(\S+).*', line):
                number, name = regex

                if name == ("VLAN%s" % number):
                    name = ''

                vlans[number] = Vlan(int(number), name)

        for ip_interface_data in split_on_dedent(self.ssh.do("show ip interface")):
            if regex.match("^Vlan(\d+)\s.*", ip_interface_data[0]):
                current_vlan = vlans.get(regex[0])
                if current_vlan:
                    apply_interface_running_config_data(
                        current_vlan,
                        self.ssh.do("show running-config interface vlan %s" % current_vlan.number)
                    )

        return vlans.values()

    def add_vlan(self, number, name=None):
        with self.config():
            result = self.ssh.do('vlan %s' % number)
            if len(result) > 0:
                raise BadVlanNumber()
            else:
                if name:
                    result = self.ssh.do('name %s' % name)

                self.ssh.do('exit')

                if len(result) > 0:
                    raise BadVlanName()

    def remove_vlan(self, number):
        self.ensure_vlan_exists(number)

        with self.config():
            self.ssh.do('no interface vlan %s' % number)
            self.ssh.do('no vlan %s' % number)

    def get_interfaces(self):
        interfaces = []
        for data in split_on_bang(self.ssh.do("show running-config | begin interface")):
            interface = parse_interface(data)
            if interface:
                interfaces.append(interface)
        return interfaces

    def set_access_vlan(self, interface_id, vlan):
        self.ensure_vlan_exists(vlan)

        with self.config(), self.interface(interface_id):
            self.ssh.do('switchport access vlan %s' % vlan)

    def remove_access_vlan(self, interface_id):
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
        self.ensure_vlan_exists(vlan)

        with self.config(), self.interface(interface_id):
            self.ssh.do('switchport trunk allowed vlan add %s' % vlan)

    def remove_trunk_vlan(self, interface_id, vlan):
        interface = self.get_interface(interface_id)
        if vlan not in interface.trunk_vlans:
            raise UnknownVlan(vlan)

        with self.config(), self.interface(interface_id):
            self.ssh.do('switchport trunk allowed vlan remove %s' % vlan)

    def shutdown_interface(self, interface_id):
        with self.config(), self.interface(interface_id):
            self.ssh.do('shutdown')

    def openup_interface(self, interface_id):
        with self.config(), self.interface(interface_id):
            self.ssh.do('no shutdown')

    def configure_native_vlan(self, interface_id, vlan):
        self.ensure_vlan_exists(vlan)

        with self.config(), self.interface(interface_id):
            self.ssh.do('switchport trunk native vlan %s' % vlan)

    def remove_native_vlan(self, interface_id):
        with self.config(), self.interface(interface_id):
            self.ssh.do('no switchport trunk native vlan')

    def add_ip_to_vlan(self, vlan_number, ip_network):
        vlan = self.get_vlan_interface_data(vlan_number)

        ip_found = next((ip for ip in vlan.ips if ip.ip == ip_network.ip), False)
        if not ip_found:
            has_ips = len(vlan.ips) > 0
            with self.config(), self.interface_vlan(vlan_number):
                if has_ips:
                    self.ssh.do('no ip redirects')
                result = self.ssh.do('ip address %s %s%s' % (ip_network.ip, ip_network.netmask,
                                                             " secondary" if has_ips else ""))
                if len(result) > 0:
                    raise IPNotAvailable(ip_network, reason="; ".join(result))
        else:
            raise IPAlreadySet(ip_network, ip_found)

    def remove_ip_from_vlan(self, vlan_number, ip_network):
        vlan = self.get_vlan_interface_data(vlan_number)
        existing_ip = next((ip for ip in vlan.ips if ip.ip == ip_network.ip and ip.netmask == ip_network.netmask), False)

        if existing_ip:
            ip_index = vlan.ips.index(existing_ip)
            with self.config(), self.interface_vlan(vlan_number):
                if ip_index == 0:
                    if len(vlan.ips) == 1:
                        self.ssh.do('no ip address %s %s' % (ip_network.ip, ip_network.netmask))
                    else:
                        self.ssh.do('ip address %s %s' % (vlan.ips[1].ip, vlan.ips[1].netmask))
                else:
                    self.ssh.do('no ip address %s %s secondary' % (ip_network.ip, ip_network.netmask))
        else:
            raise UnknownIP(ip_network)

    def has_trunk_allowed_set(self, interface_id):
        for line in self.ssh.do('show running-config interface %s' % interface_id):
            if 'Invalid input detected' in line:
                raise UnknownInterface(interface_id)
            if 'switchport trunk allowed' in line:
                return True
        return False

    def set_vlan_access_group(self, vlan_number, direction, name):
        self.get_vlan_interface_data(vlan_number)

        with self.config(), self.interface_vlan(vlan_number):
            result = self.ssh.do("ip access-group %s %s" % (name, 'in' if direction == IN else 'out'))
            if len(result) > 0:
                raise ValueError("Access group name \"%s\" is invalid" % name)

    def remove_vlan_access_group(self, vlan_number, direction):
        vlan = self.get_vlan_interface_data(vlan_number)

        if vlan.access_groups[direction] is None:
            raise UnknownAccessGroup(direction)
        else:
            with self.config(), self.interface_vlan(vlan_number):
                self.ssh.do("no ip access-group %s" % ('in' if direction == IN else 'out'))

    def set_vlan_vrf(self, vlan_number, vrf_name):
        self.get_vlan_interface_data(vlan_number)

        with self.config(), self.interface_vlan(vlan_number):
            result = self.ssh.do("ip vrf forwarding %s" % vrf_name)
            if len(result) > 0:
                raise UnknownVrf(vrf_name)

    def remove_vlan_vrf(self, vlan_number):
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

    def config(self):
        return SubShell(self.ssh, enter="configure terminal", exit_cmd='exit')

    def interface(self, interface_id):
        return SubShell(self.ssh, enter="interface %s" % interface_id, exit_cmd='exit',
                        validate=no_output(UnknownInterface, interface_id))

    def interface_vlan(self, interface_id):
        return SubShell(self.ssh, enter=["interface vlan %s" % interface_id, "no shutdown"], exit_cmd='exit')

    def ensure_vlan_exists(self, vlan_number):
        run_config = self.ssh.do('show running-config vlan %s' % vlan_number)
        vlan = any(re.match("^vlan %s" % vlan_number, line) for line in run_config)
        if not vlan:
            raise UnknownVlan(vlan_number)

    def get_vlan_interface_data(self, vlan_number):
        run_int_vlan_data = self.ssh.do('show running-config interface vlan %s' % vlan_number)
        if not run_int_vlan_data[0].startswith("Building configuration..."):
            self.ensure_vlan_exists(vlan_number)

        vlan = Vlan(vlan_number)
        apply_interface_running_config_data(vlan, run_int_vlan_data)
        return vlan

    def get_interface(self, interface_id):
        data = self.ssh.do("show running-config interface %s | begin interface" % interface_id)
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


def parse_interface(data):
    if data and regex.match("interface (\w*Ethernet[^\s]*)", data[0]):
        i = Interface(name=regex[0], shutdown=False)
        port_mode = access_vlan = native_vlan = trunk_vlans = None
        for line in data:
            if regex.match(" switchport mode (.*)", line): port_mode = regex[0]
            if regex.match(" switchport access vlan (\d*)", line): access_vlan = int(regex[0])
            if regex.match(" switchport trunk native vlan (\d*)", line): native_vlan = int(regex[0])
            if regex.match(" switchport trunk allowed vlan (.*)", line): trunk_vlans = regex[0]
            if regex.match(" shutdown", line): i.shutdown = True

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
            ip = IPNetwork("%s/%s" % (regex[0], regex[1]))
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

        elif regex.match("^ standby ([^\s]*)(.*)", line):
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


def parse(single_range):
    if regex.match("(\d+)-(\d+)", single_range):
        return range(int(regex[0]), int(regex[1]) + 1)
    else:
        return [int(single_range)]
