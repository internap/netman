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
from netman.adapters.shell.ssh import SshClient
from netman.adapters.shell.telnet import TelnetClient
from netman.core.objects.port_modes import TRUNK
from netman.core.objects.port_modes import ACCESS
from netman.core.objects.interface import Interface
from netman.adapters.switches.cisco import parse_vlan_ranges
from netman.core.objects.vlan import Vlan
from netman import regex
from netman.core.objects.switch_transactional import SwitchTransactional
from netman.adapters.switches import SubShell, no_output, ResultChecker
from netman.core.objects.exceptions import UnknownInterface, BadVlanName, \
    BadVlanNumber, UnknownVlan, InterfaceInWrongPortMode, NativeVlanNotSet, TrunkVlanNotSet
from netman.core.objects.switch_base import SwitchBase


def factory_ssh(switch_descriptor, lock):
    return SwitchTransactional(
        impl=Dell(switch_descriptor=switch_descriptor, shell_factory=SshClient),
        lock=lock,
    )


def factory_telnet(switch_descriptor, lock):
    return SwitchTransactional(
        impl=Dell(switch_descriptor=switch_descriptor, shell_factory=TelnetClient),
        lock=lock,
    )


class Dell(SwitchBase):

    def __init__(self, switch_descriptor, shell_factory):
        super(Dell, self).__init__(switch_descriptor)
        self.shell = None
        self.shell_factory = shell_factory

    def connect(self):
        self.shell = self.shell_factory(
            host=self.switch_descriptor.hostname,
            username=self.switch_descriptor.username,
            password=self.switch_descriptor.password,
            port=self.switch_descriptor.port or 22
        )

        self.shell.do("enable", wait_for=":")
        self.shell.do(self.switch_descriptor.password)

    def disconnect(self):
        self.shell.quit("quit")
        self.logger.info(self.shell.full_log)

    def start_transaction(self):
        pass

    def end_transaction(self):
        pass

    def rollback_transaction(self):
        pass

    def commit_transaction(self):
        self.shell.do("copy running-config startup-config", wait_for="? (y/n) ")
        self.shell.send_key("y")

    def openup_interface(self, interface_id):
        with self.config(), self.interface(interface_id):
            self.shell.do('no shutdown')

    def shutdown_interface(self, interface_id):
        with self.config(), self.interface(interface_id):
            self.shell.do('shutdown')

    def get_vlans(self):
        result = self.shell.do('show vlan', wait_for=("--More-- or (q)uit", "#"), include_last_line=True)
        vlans = parse_vlan_list(result)
        while len(result) > 0 and "--More--" in result[-1]:
            result = self.shell.send_key("m", wait_for=("--More-- or (q)uit", "#"), include_last_line=True)
            vlans += parse_vlan_list(result)

        return vlans

    def get_interfaces(self):
        result = self.shell.do('show interfaces status', wait_for=("--More-- or (q)uit", "#"), include_last_line=True)
        name_list = self.parse_interface_names(result)

        while len(result) > 0 and "--More--" in result[-1]:
            result = self.shell.send_key("m", wait_for=("--More-- or (q)uit", "#"), include_last_line=True)
            name_list += self.parse_interface_names(result)

        return [self.read_interface(name) for name in name_list]

    def add_vlan(self, number, name=None):
        with self.config():
            with self.vlan_database():
                self.set('vlan {}', number).on_result_matching(".*Failure.*", BadVlanNumber)

            if name is not None:
                with self.interface("vlan {}".format(number)):
                    self.set('name {}', name).on_any_result(BadVlanName)

    def remove_vlan(self, number, name=None):
        with self.config():
            with self.vlan_database():
                self.set('no vlan {}', number).on_result_matching(".*These VLANs do not exist:.*", UnknownVlan, number)

    def set_access_mode(self, interface_id):
        with self.config(), self.interface(interface_id):
            self.shell.do("switchport mode access")

    def set_trunk_mode(self, interface_id):
        interface_data = self.get_interface_data(interface_id)
        actual_port_mode = resolve_port_mode(interface_data)

        if actual_port_mode in ("access", None):
            with self.config(), self.interface(interface_id):
                self.shell.do("switchport mode trunk")

    def set_access_vlan(self, interface_id, vlan):
        with self.config(), self.interface(interface_id):
            self.set("switchport access vlan {}", vlan)\
                .on_result_matching(".*VLAN ID not found.*", UnknownVlan, vlan)\
                .on_result_matching(".*Interface not in Access Mode.*", InterfaceInWrongPortMode, "trunk")

    def remove_access_vlan(self, interface_id):
        with self.config(), self.interface(interface_id):
            self.shell.do("no switchport access vlan")

    def configure_native_vlan(self, interface_id, vlan):
        interface_data = self.get_interface_data(interface_id)

        actual_port_mode = resolve_port_mode(interface_data)
        if actual_port_mode == "access":
            raise InterfaceInWrongPortMode("access")

        with self.config(), self.interface(interface_id):
            if actual_port_mode != "general":
                self.set("switchport mode general")
            if actual_port_mode == "trunk":
                self.copy_vlans(interface_data, "trunk", "general")

            self.set("switchport general pvid {}", vlan).on_any_result(UnknownVlan, vlan)

    def remove_native_vlan(self, interface_id):
        interface_data = self.get_interface_data(interface_id)
        assert_native_vlan_is_set(interface_id, interface_data)

        with self.config(), self.interface(interface_id):
            self.set("switchport mode trunk")
            self.copy_vlans(interface_data, "general", "trunk")

    def add_trunk_vlan(self, interface_id, vlan):
        interface_data = self.get_interface_data(interface_id)

        actual_port_mode = resolve_port_mode(interface_data)
        if actual_port_mode == "access":
            raise InterfaceInWrongPortMode("access")

        with self.config(), self.interface(interface_id):
            if actual_port_mode is None:
                self.set("switchport mode trunk")
                actual_port_mode = "trunk"

            self.set("switchport {} allowed vlan add {}", actual_port_mode, vlan)\
                .on_result_matching(".*VLAN does not exist.*", UnknownVlan, vlan)

    def remove_trunk_vlan(self, interface_id, vlan):
        interface_data = self.get_interface_data(interface_id)
        trunk_vlans = resolve_trunk_vlans(interface_data)

        if vlan not in trunk_vlans:
            raise TrunkVlanNotSet(interface_id)

        actual_port_mode = resolve_port_mode(interface_data)
        with self.config(), self.interface(interface_id):
            self.set("switchport {} allowed vlan remove {}", actual_port_mode, vlan)

    def edit_interface_spanning_tree(self, interface_id, edge=None):
        commands = []
        if edge is not None:
            commands.append("{}spanning-tree portfast".format("" if edge else "no "))

        if commands:
            with self.config(), self.interface(interface_id):
                [self.shell.do(cmd) for cmd in commands]

    def enable_lldp(self, interface_id, enabled):
        with self.config(), self.interface(interface_id):
            self.set("{}lldp transmit", "" if enabled else "no ")
            self.set("{}lldp receive", "" if enabled else "no ")
            self.set("{}lldp med transmit-tlv capabilities", "" if enabled else "no ")
            self.set("{}lldp med transmit-tlv network-policy", "" if enabled else "no ")

    def config(self):
        return SubShell(self.shell, enter="configure", exit_cmd='exit')

    def vlan_database(self):
        return SubShell(self.shell, enter="vlan database", exit_cmd='exit')

    def interface(self, interface_id):
        return SubShell(self.shell, enter="interface %s" % interface_id, exit_cmd='exit',
                        validate=no_output(UnknownInterface, interface_id))

    def set(self, command, *arguments):
        result = self.shell.do(command.format(*arguments))

        return ResultChecker(result)

    def get_interface_data(self, interface_id):
        interface_data = self.shell.do("show running-config interface {}".format(interface_id))
        if len(interface_data) > 0 and regex.match("ERROR.*", interface_data[0]):
            raise UnknownInterface(interface_id)
        return interface_data

    def copy_vlans(self, data, from_mode, to_mode):
        for line in data:
            if regex.match("switchport {} allowed vlan.*".format(from_mode), line):
                self.shell.do(line.replace(from_mode, to_mode))

    def parse_interface_names(self, status_list):
        interfaces = []
        for line in status_list:
            if regex.match("(\d\S+).*", line):
                interfaces.append("ethernet {}".format(regex[0]))
            elif regex.match("ch(\d+).*", line):
                interfaces.append("port-channel {}".format(regex[0]))

        return interfaces

    def read_interface(self, interface_name):
        data = self.get_interface_data(interface_name)

        interface = Interface(name=interface_name, port_mode=ACCESS, shutdown=False)
        for line in data:
            if regex.match("switchport mode \S+", line):
                interface.port_mode = TRUNK
            if regex.match("shutdown", line):
                interface.shutdown = True
            if regex.match("switchport access vlan (\d+)", line):
                interface.access_vlan = int(regex[0])
            if regex.match("switchport general pvid (\d+)", line):
                interface.trunk_native_vlan = int(regex[0])
            if regex.match("switchport \S+ allowed vlan add (\S+)", line):
                interface.trunk_vlans = parse_vlan_ranges(regex[0])

        return interface


def parse_vlan_list(result):
    vlans = []
    for line in result:
        if regex.match('^(\d+)\s{1,6}(\S+).*', line):
            number, name = regex
            vlans.append(Vlan(number=int(number),
                              name=name if int(number) > 1 else "default"))
        elif regex.match('^(\d+)\s+.*', line):
            number = regex[0]
            vlans.append(Vlan(number=int(number)))
    return vlans


def resolve_port_mode(interface_data):
    for line in interface_data:
        if regex.match("switchport mode (\S+)", line):
            return regex[0]
        elif regex.match("switchport access vlan .*", line):
            return "access"
    return None


def assert_native_vlan_is_set(interface_id, interface_data):
    for line in interface_data:
        if regex.match("switchport general pvid (\S+)", line):
            return
    raise NativeVlanNotSet(interface_id)


def resolve_trunk_vlans(interface_data):
    for line in interface_data:
        if regex.match("switchport \S+ allowed vlan add (\S+)", line):
            return parse_vlan_ranges(regex[0])
    return []
