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
import logging
import re
import warnings

from netaddr import IPNetwork
from netaddr.ip import IPAddress

from netman import regex
from netman.adapters.shell.ssh import SshClient
from netman.adapters.shell.telnet import TelnetClient
from netman.adapters.switches.util import SubShell, split_on_bang, split_on_dedent, no_output, \
    ResultChecker
from netman.core.objects.access_groups import IN, OUT
from netman.core.objects.exceptions import IPNotAvailable, UnknownIP, UnknownVlan, UnknownAccessGroup, BadVlanNumber, \
    BadVlanName, UnknownInterface, TrunkVlanNotSet, VlanVrfNotSet, UnknownVrf, BadVrrpTimers, BadVrrpPriorityNumber, \
    BadVrrpTracking, VrrpAlreadyExistsForVlan, VrrpDoesNotExistForVlan, NoIpOnVlanForVrrp, BadVrrpAuthentication, \
    BadVrrpGroupNumber, DhcpRelayServerAlreadyExists, UnknownDhcpRelayServer, VlanAlreadyExist, \
    InvalidAccessGroupName, IPAlreadySet
from netman.core.objects.interface import Interface
from netman.core.objects.interface_states import OFF
from netman.core.objects.port_modes import ACCESS, TRUNK
from netman.core.objects.switch_base import SwitchBase
from netman.core.objects.vlan import Vlan
from netman.core.objects.vrrp_group import VrrpGroup


def ssh(switch_descriptor):
    return BackwardCompatibleBrocade(switch_descriptor=switch_descriptor, shell_factory=SshClient)


def telnet(switch_descriptor):
    return BackwardCompatibleBrocade(switch_descriptor=switch_descriptor, shell_factory=TelnetClient)


class Brocade(SwitchBase):
    def __init__(self, switch_descriptor, shell_factory):
        super(Brocade, self).__init__(switch_descriptor)
        self.shell_factory = shell_factory
        self.shell = None

    def _connect(self):
        shell_params = dict(
            host=self.switch_descriptor.hostname,
            username=self.switch_descriptor.username,
            password=self.switch_descriptor.password,
        )
        if self.switch_descriptor.port:
            shell_params["port"] = self.switch_descriptor.port

        self.shell = self.shell_factory(**shell_params)

        if self.shell.get_current_prompt().endswith(">"):
            self.shell.do("enable", wait_for=":")
            self.shell.do(self.switch_descriptor.password)

        self.shell.do("skip-page-display")

    def _disconnect(self):
        self.shell.quit("exit")
        self.logger.info(self.shell.full_log)

    def _end_transaction(self):
        pass

    def _start_transaction(self):
        pass

    def commit_transaction(self):
        self.shell.do("write memory")

    def rollback_transaction(self):
        pass

    def get_vlans(self):
        vlans = self._list_vlans()
        self.add_vif_data_to_vlans(vlans)
        return vlans

    def get_vlan(self, number):
        return self._get_vlan(number, include_vif_data=True)

    def add_vlan(self, number, name=None):
        result = self._show_vlan(number)
        if not result[0].startswith("Error"):
            raise VlanAlreadyExist(number)

        with self.config():
            result = self.shell.do('vlan {}{}'.format(number, " name {}".format(name) if name else ""))
            if len(result) > 0:
                if result[0].startswith("Error:"):
                    raise BadVlanNumber()
                else:
                    raise BadVlanName()
            else:
                self.shell.do('exit')

    def get_interfaces(self):
        interfaces = []
        vlans = []
        interfaces_vlans = []

        for if_data in split_on_dedent(self.shell.do("show interfaces")):
            i = parse_interface(if_data)
            if i:
                interfaces.append(i)

        for vlan_data in split_on_bang(self.shell.do("show running-config vlan")):
            vlans.append(parse_vlan_runningconfig(vlan_data))

        for interface in interfaces:
            interfaces_vlans.append(get_interface_vlans_association(interface, vlans))

        for interface_vlans in interfaces_vlans:
            set_vlans_properties(interface_vlans)
        return interfaces

    def get_interface(self, interface_id):
        vlans = []

        if_data = self.shell.do("show interfaces {}".format(interface_id))
        interface = parse_interface(if_data)

        if not interface:
            raise UnknownInterface(interface=interface_id)

        for vlan_data in split_on_bang(self.shell.do("show running-config vlan")):
            vlans.append(parse_vlan_runningconfig(vlan_data))

        interface_vlans = get_interface_vlans_association(interface, vlans)
        set_vlans_properties(interface_vlans)

        return interface

    def add_trunk_vlan(self, interface_id, vlan):
        self._get_vlan(vlan)

        with self.config(), self.vlan(vlan):
            result = self.shell.do("tagged {}".format(interface_id))
            if result:
                raise UnknownInterface(interface_id)

    def set_access_vlan(self, interface_id, vlan):
        self._get_vlan(vlan)

        with self.config(), self.vlan(vlan):
            result = self.shell.do("untagged {}".format(interface_id))
            if result:
                raise UnknownInterface(interface_id)

    def set_interface_native_vlan(self, interface_id, vlan):
        return self.set_access_vlan(interface_id, vlan)

    def reset_interface(self, interface_id):
        result = self.shell.do("show vlan {}".format(interface_id))
        if result and ('Invalid input' in result[0] or 'Error' in result[0]):
            raise UnknownInterface(interface_id)

        operations = self._get_vlan_association_removal_operations(result)

        with self.config():
            if len(operations) > 0:
                for operation in operations:
                    self.shell.do("vlan {}".format(operation[0]))
                    self.shell.do("no {} {}".format(operation[1], interface_id))
                self.shell.do("exit")
            result = self.shell.do("no interface {}".format(interface_id))
            if result:
                raise UnknownInterface(interface_id)

    def set_interface_state(self, interface_id, state):
        with self.config(), self.interface(interface_id):
            self.shell.do("disable" if state is OFF else "enable")

    def unset_interface_access_vlan(self, interface_id):
        content = self.shell.do("show vlan brief | include {}".format(_to_short_name(interface_id)))
        if len(content) == 0:
            raise UnknownInterface(interface_id)

        self.logger.debug("show vlan result : \n" + "\n".join(content))
        matches = re.compile("^(\d+).*").match(content[0])

        with self.config(), self.vlan(int(matches.groups()[0])):
            self.shell.do("no untagged {}".format(interface_id))

    def unset_interface_native_vlan(self, interface_id):
        return self.unset_interface_access_vlan(interface_id)

    def remove_trunk_vlan(self, interface_id, vlan):
        self._get_vlan(vlan)

        with self.config(), self.vlan(vlan):
            self.set("no tagged {}".format(interface_id))\
                .on_result_matching("^Error.*", TrunkVlanNotSet, interface_id)\
                .on_result_matching("^Invalid input.*", UnknownInterface, interface_id)

    def remove_vlan(self, number):
        self._get_vlan(number)

        with self.config():
            self.shell.do("no vlan {}".format(number))

    def set_access_mode(self, interface_id):
        result = self.shell.do("show vlan {}".format(interface_id))
        if result and 'Invalid input' in result[0]:
            raise UnknownInterface(interface_id)

        operations = self._get_vlan_association_removal_operations(result)

        if len(operations) > 0 and not (len(operations) == 1 and operations[0][1] == "untagged"):
            with self.config():
                for operation in operations:
                    self.shell.do("vlan {}".format(operation[0]))
                    self.shell.do("no {} {}".format(operation[1], interface_id))
                self.shell.do("exit")

    def set_trunk_mode(self, interface_id):
        result = self.shell.do("show vlan {}".format(interface_id))
        if result and 'Invalid input' in result[0]:
            raise UnknownInterface(interface_id)

    def set_vlan_icmp_redirects_state(self, vlan_number, state):
        vlan = self._get_vlan(vlan_number, include_vif_data=True)

        with self.config(), self.interface_vlan(vlan):
            if state:
                self.shell.do('ip redirect')
            else:
                self.shell.do('no ip redirect')

    def add_ip_to_vlan(self, vlan_number, ip_network):
        vlan = self._get_vlan(vlan_number, include_vif_data=True)

        ip_exists = next((ip for ip in vlan.ips if ip.ip == ip_network.ip), False)
        if ip_exists:
            raise IPAlreadySet(ip_network)

        with self.config(), self.interface_vlan(vlan):
            ip_is_in_an_existing_network = any(ip_network in existing_ip for existing_ip in vlan.ips)
            result = self.shell.do("ip address {}{}".format(ip_network, " secondary" if ip_is_in_an_existing_network else ""))
            if len(result) > 0:
                raise IPNotAvailable(ip_network)

    def remove_ip_from_vlan(self, vlan_number, ip_network):
        vlan = self._get_vlan(vlan_number, include_vif_data=True)

        existing_ip = next((ip for ip in vlan.ips if ip.ip == ip_network.ip and ip.netmask == ip_network.netmask), False)
        if not existing_ip:
            raise UnknownIP(ip_network)

        with self.config(), self.interface_vlan(vlan):

            on_hold = []
            if not existing_ip.is_secondary:
                for ip in vlan.ips:
                    if ip.is_secondary and ip in existing_ip:
                        on_hold.append(ip)
                        self.shell.do("no ip address {}".format(ip))

            self.shell.do("no ip address {}".format(existing_ip))

            if len(on_hold) > 0:
                self.shell.do("ip address {}".format(on_hold[0]))
                for ip in on_hold[1:]:
                    self.shell.do("ip address {} secondary".format(ip))

    def set_vlan_access_group(self, vlan_number, direction, name):
        vlan = self._get_vlan(vlan_number, include_vif_data=True)

        with self.config(), self.interface_vlan(vlan):
            if vlan.access_groups[direction] is not None:
                self.shell.do("no ip access-group {} {}".format(vlan.access_groups[direction], {IN: 'in', OUT: 'out'}[direction]))
            result = self.shell.do("ip access-group {} {}".format(name, {IN: 'in', OUT: 'out'}[direction]))
            if len(result) > 0 and not result[0].startswith("Warning:"):
                raise InvalidAccessGroupName(name)

    def unset_vlan_access_group(self, vlan_number, direction):
        vlan = self._get_vlan(vlan_number, include_vif_data=True)

        if vlan.access_groups[direction] is None:
            raise UnknownAccessGroup(direction)
        else:
            with self.config(), self.interface_vlan(vlan):
                self.shell.do("no ip access-group {} {}".format(vlan.access_groups[direction], {IN: 'in', OUT: 'out'}[direction]))

    def set_vlan_vrf(self, vlan_number, vrf_name):
        vlan = self._get_vlan(vlan_number)
        with self.config(), self.interface_vlan(vlan):
            result = self.shell.do("vrf forwarding {}".format(vrf_name))
            if regex.match("^Error.*", result[0]):
                raise UnknownVrf(vrf_name)

    def unset_vlan_vrf(self, vlan_number):
        vlan = self._get_vlan(vlan_number, include_vif_data=True)
        if vlan.vlan_interface_name is None or vlan.vrf_forwarding is None:
            raise VlanVrfNotSet(vlan_number)
        else:
            with self.config(), self.interface_vlan(vlan):
                self.shell.do("no vrf forwarding {}".format(vlan.vrf_forwarding))

    def get_vlan_interfaces(self, vlan_number):
        interfaces = []
        result = self._show_vlan(vlan_number)
        if result[0].startswith("Error"):
            raise UnknownVlan(vlan_number)
        for line in result:
            if regex.match("(Untagged|Statically tagged) Ports\s+: (.*)$", line):
                for real_name in _to_real_names(parse_if_ranges(regex[1])):
                    interfaces.append(real_name)
        return interfaces

    def config(self):
        return SubShell(self.shell, enter="configure terminal", exit_cmd='exit')

    def vlan(self, vlan_number):
        return SubShell(self.shell, enter="vlan {}".format(vlan_number), exit_cmd='exit')

    def interface(self, interface_id):
        return SubShell(self.shell, enter="interface {}".format(interface_id), exit_cmd='exit',
                        validate=no_output(UnknownInterface, interface_id))

    def interface_vlan(self, vlan):
        if vlan.vlan_interface_name is None:
            self.shell.do("vlan {}".format(vlan.number))
            self.shell.do("router-interface ve {}".format(vlan.number))
            vlan.vlan_interface_name = str(vlan.number)

        return SubShell(self.shell, enter=["interface ve {}".format(vlan.vlan_interface_name), "enable"], exit_cmd='exit')

    def add_vrrp_group(self, vlan_number, group_id, ips=None, priority=None, hello_interval=None, dead_interval=None,
                       track_id=None, track_decrement=None):
        vlan = self._get_vlan(vlan_number, include_vif_data=True)

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
                self.shell.do('activate')
            except:
                self.shell.do('exit')
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
        self.shell.do('advertise backup')
        self.set('track-port {}', track_id).on_any_result(BadVrrpTracking)

    def remove_vrrp_group(self, vlan_number, group_id):
        vlan = self._get_vlan(vlan_number, include_vif_data=True)

        if not [group for group in vlan.vrrp_groups if group.id == group_id]:
            raise VrrpDoesNotExistForVlan(vlan=vlan_number, vrrp_group_id=group_id)

        with self.config(), self.interface_vlan(vlan):
            result = self.shell.do('no ip vrrp-extended vrid {group_id}'.format(group_id=group_id))
            if len(result) > 0:
                raise VrrpDoesNotExistForVlan(vlan=vlan_number, vrrp_group_id=group_id)
            if len(vlan.vrrp_groups) == 1:
                self.shell.do('ip vrrp-extended auth-type no-auth')

    def add_vif_data_to_vlans(self, vlans):
        vlans_interface_name_dict = {vlan.vlan_interface_name: vlan for vlan in vlans if vlan.vlan_interface_name}

        for int_vlan_data in split_on_bang(self.shell.do("show running-config interface")):
            if regex.match("^interface ve (\d+)", int_vlan_data[0]):
                current_vlan = vlans_interface_name_dict.get(regex[0])
                if current_vlan:
                    add_interface_vlan_data(current_vlan, int_vlan_data)

    def add_dhcp_relay_server(self, vlan_number, ip_address):
        vlan = self._get_vlan(vlan_number, include_vif_data=True)

        if ip_address in vlan.dhcp_relay_servers:
            raise DhcpRelayServerAlreadyExists(vlan_number=vlan_number, ip_address=ip_address)

        with self.config(), self.interface_vlan(vlan):
            self.shell.do("ip helper-address {}".format(ip_address))

    def remove_dhcp_relay_server(self, vlan_number, ip_address):
        vlan = self._get_vlan(vlan_number, include_vif_data=True)

        if ip_address not in vlan.dhcp_relay_servers:
            raise UnknownDhcpRelayServer(vlan_number=vlan_number, ip_address=ip_address)

        with self.config(), self.interface_vlan(vlan):
            self.shell.do("no ip helper-address {}".format(ip_address))

    def set(self, command, *arguments):
        result = None
        if all([a is not None for a in arguments]):
            result = self.shell.do(command.format(*arguments))

        return ResultChecker(result)

    def _list_vlans(self):
        vlans = []
        for vlan_data in split_on_bang(self.shell.do("show running-config vlan | begin vlan")):
            vlans.append(parse_vlan(vlan_data))
        return vlans

    def _get_vlan(self, vlan_number, include_vif_data=False):
        result = self._show_vlan(vlan_number)
        if result[0].startswith("Error"):
            raise UnknownVlan(vlan_number)

        vlan = VlanBrocade(vlan_number)
        for line in result:
            if regex.match(".*PORT-VLAN \d*, Name ([^,]+),.*", line):
                vlan.name = regex[0] if regex[0] != "[None]" else None
                vlan.name = vlan.name if vlan.name != "DEFAULT-VLAN" else "default"
            elif regex.match(".*Associated Virtual Interface Id: (\d+).*", line):
                vlan.vlan_interface_name = regex[0]
                if include_vif_data:
                    add_interface_vlan_data(vlan, self.shell.do("show running-config interface ve {}".format(regex[0])))
        return vlan

    def _show_vlan(self, vlan_number):
        return self.shell.do("show vlan {}".format(vlan_number))

    def _get_vlan_association_removal_operations(self, result):
        operations = []
        for line in result:
            if regex.match("VLAN: (\d*)  ([^\s]*)", line):
                vlan, state = regex
                if int(vlan) > 1:
                    operations.append((vlan, state.lower()))
        return operations


def parse_vlan(vlan_data):
    regex.match("^vlan (\d+).*", vlan_data[0])
    current_vlan = VlanBrocade(int(regex[0]))

    if regex.match("^vlan \d+ name ([^\s]*)", vlan_data[0]):
        current_vlan.name = regex[0] if regex[0] != "DEFAULT-VLAN" else "default"
    else:
        current_vlan.name = None

    for line in vlan_data[1:]:
        if regex.match("^\srouter-interface ve (\d+)", line):
            current_vlan.vlan_interface_name = regex[0]

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
        if vrrp_group:
            if regex.match("^  backup priority ([^\s]*) track-priority ([^\s]*)", line):
                vrrp_group.priority = int(regex[0])
                vrrp_group.track_decrement = int(regex[1])
            elif regex.match("^  hello-interval ([^\s]*)", line):
                vrrp_group.hello_interval = int(regex[0])
            elif regex.match("^  dead-interval ([^\s]*)", line):
                vrrp_group.dead_interval = int(regex[0])
            elif regex.match("^  track-port (.*)", line):
                vrrp_group.track_id = regex[0]
            elif regex.match("^  activate", line):
                vrrp_group = None
        elif regex.match("^ ip helper-address ([^\s]*)", line):
            target_vlan.dhcp_relay_servers.append(IPAddress(regex[0]))
        elif regex.match("^ no ip redirect", line):
            target_vlan.icmp_redirects = False


def parse_if_ranges(string):
    consumed_string = string.strip()
    while len(consumed_string) > 0:

        if regex.match("^(([^\s]*) ([^\s]*) to ([^\s]*)).*", consumed_string):
            parsed_part, port_type, lower_bound, higher_bound = regex
            lower_values = lower_bound.split("/")
            higher_values = higher_bound.split("/")
            for port_id in range(int(lower_values[-1]), int(higher_values[-1]) + 1):
                yield "{} {}/{}".format(port_type, "/".join(lower_values[:-1]), port_id)
        else:
            regex.match("^([^\s]* [^\s]*).*", consumed_string)
            parsed_part = regex[0]
            yield regex[0]

        consumed_string = consumed_string[len(parsed_part):].strip()


def _to_real_names(if_list):
    return [i.replace("ethe", "ethernet") for i in if_list]


def _to_short_name(interface_id):
    return interface_id.replace("ethernet", "ethe")


def set_vlans_properties(interface_vlans):
    if interface_vlans["untagged"] is not None and len(interface_vlans["tagged"]) == 0:
        interface_vlans["object"].access_vlan = interface_vlans["untagged"]
    elif interface_vlans["untagged"] is not None and len(interface_vlans["tagged"]) > 0:
        interface_vlans["object"].trunk_native_vlan = interface_vlans["untagged"]
    if len(interface_vlans["tagged"]) > 0:
        interface_vlans["object"].port_mode = TRUNK
        interface_vlans["object"].trunk_vlans = interface_vlans["tagged"]


def get_interface_vlans_association(interface, vlans):
    interface_dic = {"tagged": [], "untagged": None, "object": interface}
    for vlan in vlans:
        if interface.name in vlan["tagged_interface"]:
            interface_dic["tagged"].append(vlan['id'])
        if interface.name in vlan["untagged_interface"]:
            interface_dic["untagged"] = vlan['id']
    return interface_dic


def parse_vlan_runningconfig(data):
    vlan = {"tagged_interface": [], "untagged_interface": []}
    if regex.match("^vlan (\d*)", data[0]):
        vlan['id'] = int(regex[0])
        for line in data:
            if regex.match(" untagged (.*)", line):
                for name in _to_real_names(parse_if_ranges(regex[0])):
                    vlan["untagged_interface"].append(name)
            if regex.match(" tagged (.*)", line):
                for name in _to_real_names(parse_if_ranges(regex[0])):
                    vlan["tagged_interface"].append(name)
    return vlan


def parse_interface(if_data):
    if regex.match("^\w*Ethernet([^\s]*) is (\w*).*", if_data[0]):
        i = Interface(name="ethernet {}".format(regex[0]), port_mode=ACCESS, shutdown=regex[1] == "disabled")
        for line in if_data:
            if regex.match("Port name is (.*)", line):
                i.description = regex[0]
        return i


class VlanBrocade(Vlan):
    def __init__(self, *args, **kwargs):
        super(VlanBrocade, self).__init__(*args, **kwargs)

        self.vlan_interface_name = kwargs.pop('vlan_interface_name', None)
        self.icmp_redirects = True


class BrocadeIPNetwork(IPNetwork):
    def __init__(self, *args, **kwargs):

        self.is_secondary = kwargs.pop('is_secondary', False)

        super(BrocadeIPNetwork, self).__init__(*args, **kwargs)


class BackwardCompatibleBrocade(Brocade):
    def __init__(self, switch_descriptor, shell_factory):
        super(BackwardCompatibleBrocade, self).__init__(switch_descriptor, shell_factory)

        self.logger = logging.getLogger(
                "{module}.{hostname}".format(module=Brocade.__module__,
                                             hostname=self.switch_descriptor.hostname))

    def add_trunk_vlan(self, interface_id, vlan):
        return super(BackwardCompatibleBrocade, self).add_trunk_vlan(_add_ethernet(interface_id), vlan)

    def set_interface_state(self, interface_id, state):
        return super(BackwardCompatibleBrocade, self).set_interface_state(_add_ethernet(interface_id), state)

    def set_trunk_mode(self, interface_id):
        return super(BackwardCompatibleBrocade, self).set_trunk_mode(_add_ethernet(interface_id))

    def set_access_vlan(self, interface_id, vlan):
        return super(BackwardCompatibleBrocade, self).set_access_vlan(_add_ethernet(interface_id), vlan)

    def set_access_mode(self, interface_id):
        return super(BackwardCompatibleBrocade, self).set_access_mode(_add_ethernet(interface_id))

    def remove_trunk_vlan(self, interface_id, vlan):
        super(BackwardCompatibleBrocade, self).remove_trunk_vlan(_add_ethernet(interface_id), vlan)

    def unset_interface_native_vlan(self, interface_id):
        return super(BackwardCompatibleBrocade, self).unset_interface_native_vlan(_add_ethernet(interface_id))

    def unset_interface_access_vlan(self, interface_id):
        return super(BackwardCompatibleBrocade, self).unset_interface_access_vlan(_add_ethernet(interface_id))

    def interface(self, interface_id):
        return super(BackwardCompatibleBrocade, self).interface(_add_ethernet(interface_id))

    def set_interface_native_vlan(self, interface_id, vlan):
        return super(BackwardCompatibleBrocade, self).set_interface_native_vlan(_add_ethernet(interface_id), vlan)

    def add_vrrp_group(self, vlan_number, group_id, ips=None, priority=None, hello_interval=None, dead_interval=None,
                       track_id=None, track_decrement=None):
        return super(BackwardCompatibleBrocade, self).add_vrrp_group(vlan_number, group_id, ips, priority,
                                                                     hello_interval, dead_interval,
                                                                     _add_ethernet(track_id), track_decrement)

    def reset_interface(self, interface_id):
        return super(BackwardCompatibleBrocade, self).reset_interface(_add_ethernet(interface_id))


def _add_ethernet(interface_id):
    if interface_id is not None and re.match("^\d.*", interface_id):
        warnings.warn("The brocade interface naming without the \"ethernet\" prefix has been deprecated", DeprecationWarning)
        return "ethernet {}".format(interface_id)
    return interface_id
