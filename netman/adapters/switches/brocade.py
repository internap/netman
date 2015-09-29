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

from netaddr import IPNetwork
from netaddr.ip import IPAddress

from netman import regex
from netman.adapters.switches import SubShell, split_on_bang, split_on_dedent, no_output, \
    ResultChecker
from netman.adapters.shell import ssh
from netman.core.objects.access_groups import IN, OUT
from netman.core.objects.exceptions import IPNotAvailable, UnknownIP, UnknownVlan, UnknownAccessGroup, BadVlanNumber, \
    BadVlanName, UnknownInterface, TrunkVlanNotSet, VlanVrfNotSet, UnknownVrf, BadVrrpTimers, BadVrrpPriorityNumber, \
    BadVrrpTracking, VrrpAlreadyExistsForVlan, VrrpDoesNotExistForVlan, NoIpOnVlanForVrrp, BadVrrpAuthentication, \
    BadVrrpGroupNumber, DhcpRelayServerAlreadyExists, UnknownDhcpRelayServer
from netman.core.objects.interface import Interface
from netman.core.objects.port_modes import ACCESS, TRUNK
from netman.core.objects.switch_base import SwitchBase
from netman.core.objects.switch_transactional import SwitchTransactional
from netman.core.objects.vlan import Vlan
from netman.core.objects.vrrp_group import VrrpGroup


def factory(switch_descriptor, lock):
    return SwitchTransactional(
        impl=Brocade(switch_descriptor=switch_descriptor),
        lock=lock
    )


class Brocade(SwitchBase):
    def __init__(self, switch_descriptor):
        super(Brocade, self).__init__(switch_descriptor)
        self.ssh = None

    def connect(self):
        self.ssh = ssh.SshClient(
            host=self.switch_descriptor.hostname,
            username=self.switch_descriptor.username,
            password=self.switch_descriptor.password,
            port=self.switch_descriptor.port or 22
        )
        if self.ssh.get_current_prompt().endswith(">"):
            self.ssh.do("enable", wait_for=":")
            self.ssh.do(self.switch_descriptor.password)

        self.ssh.do("skip-page-display")

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
        vlans = self.list_vlans()
        self.add_vif_data_to_vlans(vlans)
        return vlans

    def add_vlan(self, number, name=None):
        with self.config():
            result = self.ssh.do('vlan %s%s' % (number, (" name %s" % name) if name else ""))
            if len(result) > 0:
                if result[0].startswith("Error:"):
                    raise BadVlanNumber()
                else:
                    raise BadVlanName()
            else:
                self.ssh.do('exit')

    def get_interfaces(self):
        interfaces = []
        interface_vlans = {}
        for if_data in split_on_dedent(self.ssh.do("show interfaces")):
            if regex.match("^\w*Ethernet([^\s]*) is (\w*).*", if_data[0]):
                i = Interface(name=regex[0], port_mode=ACCESS, shutdown=regex[1] == "disabled")
                for line in if_data:
                    if regex.match("Port name is (.*)", line): i.description = regex[0]
                interfaces.append(i)
                interface_vlans["ethe %s" % i.name] = {
                    "object": i,
                    "untagged": None,
                    "tagged": []
                }

        for vlan_data in split_on_bang(self.ssh.do("show running-config vlan")):
            if regex.match("^vlan (\d*)", vlan_data[0]):
                vlan_id = int(regex[0])
                for line in vlan_data:
                    if regex.match(" untagged (.*)", line):
                        for name in parse_if_ranges(regex[0]):
                            interface_vlans[name]["untagged"] = vlan_id
                    if regex.match(" tagged (.*)", line):
                        for name in parse_if_ranges(regex[0]):
                            interface_vlans[name]["tagged"].append(vlan_id)

        for data in interface_vlans.values():
            if data["untagged"] is not None and len(data["tagged"]) == 0:
                data["object"].access_vlan = data["untagged"]
            elif data["untagged"] is not None and len(data["tagged"]) > 0:
                data["object"].trunk_native_vlan = data["untagged"]

            if len(data["tagged"]) > 0:
                data["object"].port_mode = TRUNK
                data["object"].trunk_vlans = data["tagged"]

        return interfaces

    def add_trunk_vlan(self, interface_id, vlan):
        self.get_vlan(vlan)

        with self.config(), self.vlan(vlan):
            result = self.ssh.do("tagged ethernet %s" % interface_id)
            if result:
                raise UnknownInterface(interface_id)

    def set_access_vlan(self, interface_id, vlan):
        self.get_vlan(vlan)

        with self.config(), self.vlan(vlan):
            result = self.ssh.do("untagged ethernet %s" % interface_id)
            if result:
                raise UnknownInterface(interface_id)

    def configure_native_vlan(self, interface_id, vlan):
        return self.set_access_vlan(interface_id, vlan)

    def openup_interface(self, interface_id):
        with self.config(), self.interface(interface_id):
            self.ssh.do("enable")

    def shutdown_interface(self, interface_id):
        with self.config(), self.interface(interface_id):
            self.ssh.do("disable")

    def remove_access_vlan(self, interface_id):
        content = self.ssh.do("show vlan brief | include ethe %s" % interface_id)
        if len(content) == 0:
            raise UnknownInterface(interface_id)

        self.logger.debug("show vlan result : \n" + "\n".join(content))
        matches = re.compile("^(\d+).*").match(content[0])

        with self.config(), self.vlan(int(matches.groups()[0])):
            self.ssh.do("no untagged ethernet %s" % interface_id)

    def remove_native_vlan(self, interface_id):
        return self.remove_access_vlan(interface_id)

    def remove_trunk_vlan(self, interface_id, vlan):
        vlan_object = self.get_vlan_interface_data(vlan)

        if ('ethe %s' % interface_id) not in vlan_object.tagged_interfaces:
            raise TrunkVlanNotSet(interface_id)

        with self.config(), self.vlan(vlan):
            self.ssh.do("no tagged ethernet %s" % interface_id)

    def remove_vlan(self, number):
        self.get_vlan(number)

        with self.config():
            self.ssh.do("no vlan %s" % number)

    def set_access_mode(self, interface_id):
        result = self.ssh.do("show vlan ethernet %s" % interface_id)
        if result and 'Invalid input' in result[0]:
            raise UnknownInterface(interface_id)

        operations = []
        for line in result:
            if regex.match("VLAN: (\d*)  ([^\s]*)", line):
                vlan, state = regex
                if int(vlan) > 1:
                    operations.append((vlan, state.lower()))

        if len(operations) > 0 and not (len(operations) == 1 and operations[0][1] == "untagged"):
            with self.config():
                for operation in operations:
                    self.ssh.do("vlan %s" % operation[0])
                    self.ssh.do("no %s ethernet %s" % (operation[1], interface_id))
                self.ssh.do("exit")

    def set_trunk_mode(self, interface_id):
        result = self.ssh.do("show vlan ethernet %s" % interface_id)
        if result and 'Invalid input' in result[0]:
            raise UnknownInterface(interface_id)

    def add_ip_to_vlan(self, vlan_number, ip_network):
        vlan = self.get_vlan_interface_data(vlan_number)

        ip_exists = next((ip for ip in vlan.ips if ip.ip == ip_network.ip), False)
        if ip_exists:
            raise IPNotAvailable(ip_network)

        with self.config(), self.interface_vlan(vlan):
            ip_is_in_an_existing_network = any(ip_network in existing_ip for existing_ip in vlan.ips)
            result = self.ssh.do("ip address %s%s" % (ip_network, " secondary" if ip_is_in_an_existing_network else ""))
            if len(result) > 0:
                raise IPNotAvailable(ip_network)

    def remove_ip_from_vlan(self, vlan_number, ip_network):
        vlan = self.get_vlan_interface_data(vlan_number)

        existing_ip = next((ip for ip in vlan.ips if ip.ip == ip_network.ip and ip.netmask == ip_network.netmask), False)
        if not existing_ip:
            raise UnknownIP(ip_network)

        with self.config(), self.interface_vlan(vlan):

            on_hold = []
            if not existing_ip.is_secondary:
                for ip in vlan.ips:
                    if ip.is_secondary and ip in existing_ip:
                        on_hold.append(ip)
                        self.ssh.do("no ip address %s" % ip)

            self.ssh.do("no ip address %s" % existing_ip)

            if len(on_hold) > 0:
                self.ssh.do("ip address %s" % on_hold[0])
                for ip in on_hold[1:]:
                    self.ssh.do("ip address %s secondary" % ip)

    def set_vlan_access_group(self, vlan_number, direction, name):
        vlan = self.get_vlan_interface_data(vlan_number)

        with self.config(), self.interface_vlan(vlan):
            if vlan.access_groups[direction] is not None:
                self.ssh.do("no ip access-group %s %s" % (vlan.access_groups[direction], {IN: 'in', OUT: 'out'}[direction]))
            result = self.ssh.do("ip access-group %s %s" % (name, {IN: 'in', OUT: 'out'}[direction]))
            if len(result) > 0:
                raise ValueError("Access group name \"%s\" is invalid" % name)

    def remove_vlan_access_group(self, vlan_number, direction):
        vlan = self.get_vlan_interface_data(vlan_number)

        if vlan.access_groups[direction] is None:
            raise UnknownAccessGroup(direction)
        else:
            with self.config(), self.interface_vlan(vlan):
                self.ssh.do("no ip access-group %s %s" % (vlan.access_groups[direction], {IN: 'in', OUT: 'out'}[direction]))

    def set_vlan_vrf(self, vlan_number, vrf_name):
        vlan = self.get_vlan_interface_data(vlan_number)
        with self.config(), self.interface_vlan(vlan):
            result = self.ssh.do("vrf forwarding {}".format(vrf_name))
            if regex.match("^Error.*", result[0]):
                raise UnknownVrf(vrf_name)

    def remove_vlan_vrf(self, vlan_number):
        vlan = self.get_vlan_interface_data(vlan_number)
        if vlan.vlan_interface_name is None or vlan.vrf_forwarding is None:
            raise VlanVrfNotSet(vlan_number)
        else:
            with self.config(), self.interface_vlan(vlan):
                self.ssh.do("no vrf forwarding {}".format(vlan.vrf_forwarding))

    def config(self):
        return SubShell(self.ssh, enter="configure terminal", exit_cmd='exit')

    def vlan(self, vlan_number):
        return SubShell(self.ssh, enter="vlan %s" % vlan_number, exit_cmd='exit')

    def interface(self, interface_id):
        return SubShell(self.ssh, enter="interface ethernet %s" % interface_id, exit_cmd='exit',
                        validate=no_output(UnknownInterface, interface_id))

    def interface_vlan(self, vlan):
        if vlan.vlan_interface_name is None:
            self.ssh.do("vlan %s" % vlan.number)
            self.ssh.do("router-interface ve %s" % vlan.number)
            vlan.vlan_interface_name = str(vlan.number)

        return SubShell(self.ssh, enter=["interface ve %s" % vlan.vlan_interface_name, "enable"], exit_cmd='exit')

    def add_vrrp_group(self, vlan_number, group_id, ips=None, priority=None, hello_interval=None, dead_interval=None,
                       track_id=None, track_decrement=None):
        vlan = self.get_vlan_interface_data(vlan_number)

        if len([g for g in vlan.vrrp_groups if g.id == group_id]) > 0:
            raise VrrpAlreadyExistsForVlan(vlan=vlan_number, vrrp_group_id=group_id)

        with self.config(), self.interface_vlan(vlan):
            if len(vlan.vrrp_groups) == 0:
                self.set('ip vrrp-extended auth-type simple-text-auth VLAN{}', vlan_number)\
                    .on_result_matching("^error - please configure ip address before configuring vrrp-extended.*", NoIpOnVlanForVrrp, vlan_number)\
                    .on_any_result(BadVrrpAuthentication)

            self.set("ip vrrp-extended vrid {}".format(group_id)).on_any_result(BadVrrpGroupNumber, 1, 255)
            try:
                self.set_vrrp_properties(ips, priority, track_decrement, track_id, dead_interval, hello_interval)
                self.ssh.do('activate')
            except:
                self.ssh.do('exit')
                raise

    def set_vrrp_properties(self, ips, priority, track_decrement, track_id, dead_interval, hello_interval):
        self.set('backup priority {} track-priority {}', priority, track_decrement) \
            .on_result_matching("^Invalid input -> {}.*".format(track_decrement), BadVrrpTracking) \
            .on_result_matching(".*not between 1 and 254$".format(track_decrement), BadVrrpTracking) \
            .on_any_result(BadVrrpPriorityNumber, 1, 255)

        for i, ip in enumerate(ips):
            self.set('ip-address {}', ip).on_any_result(IPNotAvailable, ip)

        self.set('hello-interval {}', hello_interval).on_any_result(BadVrrpTimers)
        self.set('dead-interval {}', dead_interval).on_any_result(BadVrrpTimers)
        self.ssh.do('advertise backup')
        self.set('track-port ethernet {}', track_id).on_any_result(BadVrrpTracking)

    def remove_vrrp_group(self, vlan_number, group_id):
        vlan = self.get_vlan_interface_data(vlan_number)

        if not [group for group in vlan.vrrp_groups if group.id == group_id]:
            raise VrrpDoesNotExistForVlan(vlan=vlan_number, vrrp_group_id=group_id)

        with self.config(), self.interface_vlan(vlan):
            result = self.ssh.do('no ip vrrp-extended vrid {group_id}'.format(group_id=group_id))
            if len(result) > 0:
                raise VrrpDoesNotExistForVlan(vlan=vlan_number, vrrp_group_id=group_id)
            if len(vlan.vrrp_groups) == 1:
                self.ssh.do('ip vrrp-extended auth-type no-auth')

    def list_vlans(self):
        vlans = []

        for vlan_data in split_on_bang(self.ssh.do("show running-config vlan | begin vlan")):
            vlans.append(parse_vlan(vlan_data))

        return vlans

    def add_vif_data_to_vlans(self, vlans):
        vlans_interface_name_dict = {vlan.vlan_interface_name: vlan for vlan in vlans if vlan.vlan_interface_name}

        for int_vlan_data in split_on_bang(self.ssh.do("show running-config interface")):
            if regex.match("^interface ve (\d+)", int_vlan_data[0]):
                current_vlan = vlans_interface_name_dict.get(regex[0])
                if current_vlan:
                    add_interface_vlan_data(current_vlan, int_vlan_data)

    def get_vlan(self, vlan_number):
        vlan_data = self.ssh.do("show running-config vlan | begin vlan %s" % vlan_number)
        if not vlan_data:
            raise UnknownVlan(vlan_number)
        return parse_vlan(next(split_on_bang(vlan_data)))

    def get_vlan_interface_data(self, vlan_number):
        vlan = self.get_vlan(vlan_number)

        if vlan.vlan_interface_name:
            add_interface_vlan_data(vlan, self.ssh.do("show running-config interface ve %s" % vlan.vlan_interface_name))

        return vlan

    def set(self, command, *arguments):
        result = None
        if all([a is not None for a in arguments]):
            result = self.ssh.do(command.format(*arguments))

        return ResultChecker(result)

    def add_dhcp_relay_server(self, vlan_number, ip_address):
        vlan = self.get_vlan_interface_data(vlan_number)

        if ip_address in vlan.dhcp_relay_servers:
            raise DhcpRelayServerAlreadyExists(vlan_number=vlan_number, ip_address=ip_address)

        with self.config(), self.interface_vlan(vlan):
            self.ssh.do("ip helper-address {}".format(ip_address))

    def remove_dhcp_relay_server(self, vlan_number, ip_address):
        vlan = self.get_vlan_interface_data(vlan_number)

        if ip_address not in vlan.dhcp_relay_servers:
            raise UnknownDhcpRelayServer(vlan_number=vlan_number, ip_address=ip_address)

        with self.config(), self.interface_vlan(vlan):
            self.ssh.do("no ip helper-address {}".format(ip_address))


def parse_vlan(vlan_data):
    regex.match("^vlan (\d+).*", vlan_data[0])
    current_vlan = VlanBrocade(int(regex[0]))

    if regex.match("^vlan \d+ name ([^\s]*)", vlan_data[0]):
        current_vlan.name = regex[0] if regex[0] != "DEFAULT-VLAN" else "default"
    else:
        current_vlan.name = ''

    for line in vlan_data[1:]:
        if regex.match("^\srouter-interface ve (\d+)", line):
            current_vlan.vlan_interface_name = regex[0]
        elif regex.match(" tagged (.*)", line):
            for name in parse_if_ranges(regex[0]):
                current_vlan.tagged_interfaces.append(name)

    return current_vlan


def add_interface_vlan_data(target_vlan, int_vlan_data):
    vrrp_group = None
    for line in int_vlan_data[1:]:
        if vrrp_group is not None and not line.startswith("  "):
            vrrp_group = False

        if regex.match("^ ip address ([^\s]*)", line):
            target_vlan.ips.append(BrocadeIPNetwork(regex[0], is_secondary=line.endswith("secondary")))
        elif regex.match("^ ip access-group ([^\s]*) ([^\s]*)", line):
            direction = {'in': IN, 'out': OUT}[regex[1]]
            target_vlan.access_groups[direction] = regex[0]
        elif regex.match("^ vrf forwarding ([^\s]*)", line):
            target_vlan.vrf_forwarding = regex[0]
        elif regex.match("^ ip vrrp-extended vrid ([^\s]*)", line):
            vrrp_group = next((group for group in target_vlan.vrrp_groups if str(group.id) == regex[0]), None)
            if vrrp_group is None:
                vrrp_group = VrrpGroup(id=int(regex[0]))
                target_vlan.vrrp_groups.append(vrrp_group)
        elif regex.match("^  ip-address ([^\s]*)", line):
            vrrp_group.ips.append(IPAddress(regex[0]))
        elif regex.match("^  backup priority ([^\s]*) track-priority ([^\s]*)", line):
            vrrp_group.priority = int(regex[0])
            vrrp_group.track_decrement = int(regex[1])
        elif regex.match("^  hello-interval ([^\s]*)", line):
            vrrp_group.hello_interval = int(regex[0])
        elif regex.match("^  dead-interval ([^\s]*)", line):
            vrrp_group.dead_interval = int(regex[0])
        elif regex.match("^  track-port ethernet ([^\s]*)", line):
            vrrp_group.track_id = regex[0]
        elif regex.match("^  activate", line):
            vrrp_group = None
        elif regex.match("^ ip helper-address ([^\s]*)", line):
            target_vlan.dhcp_relay_servers.append(IPAddress(regex[0]))


def parse_if_ranges(string):
    consumed_string = string.strip()
    while len(consumed_string) > 0:

        if regex.match("^(([^\s]*) ([^\s]*) to ([^\s]*)).*", consumed_string):
            parsed_part, port_type, lower_bound, higher_bound = regex
            lower_values = lower_bound.split("/")
            higher_values = higher_bound.split("/")
            for port_id in range(int(lower_values[-1]), int(higher_values[-1]) + 1):
                yield "%s %s/%s" % (port_type, "/".join(lower_values[:-1]), port_id)
        else:
            regex.match("^([^\s]* [^\s]*).*", consumed_string)
            parsed_part = regex[0]
            yield regex[0]

        consumed_string = consumed_string[len(parsed_part):].strip()


class VlanBrocade(Vlan):
    def __init__(self, *args, **kwargs):

        self.vlan_interface_name = kwargs.pop('vlan_interface_name', None)
        self.tagged_interfaces = []

        super(VlanBrocade, self).__init__(*args, **kwargs)


class BrocadeIPNetwork(IPNetwork):
    def __init__(self, *args, **kwargs):

        self.is_secondary = kwargs.pop('is_secondary', False)

        super(BrocadeIPNetwork, self).__init__(*args, **kwargs)
