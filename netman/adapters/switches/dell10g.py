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
from netman import regex
from netman.adapters.shell.ssh import SshClient
from netman.adapters.shell.telnet import TelnetClient
from netman.adapters.switches.cisco import parse_vlan_ranges
from netman.adapters.switches.dell import Dell, resolve_port_mode
from netman.core.objects.exceptions import InterfaceInWrongPortMode, UnknownVlan, UnknownInterface, BadVlanName, \
    BadVlanNumber, TrunkVlanNotSet, VlanAlreadyExist
from netman.core.objects.interface import Interface
from netman.core.objects.port_modes import TRUNK, ACCESS
from netman.core.objects.switch_transactional import SwitchTransactional
from netman.core.objects.vlan import Vlan


def factory_ssh(switch_descriptor, lock):
    return SwitchTransactional(
        impl=Dell10G(switch_descriptor=switch_descriptor, shell_factory=SshClient),
        lock=lock,
    )


def factory_telnet(switch_descriptor, lock):
    return SwitchTransactional(
        impl=Dell10G(switch_descriptor=switch_descriptor, shell_factory=TelnetClient),
        lock=lock,
    )


class Dell10G(Dell):

    def connect(self):
        super(Dell10G, self).connect()

        self.shell.do("terminal length 0")

    def get_vlans(self):
        result = self.shell.do('show vlan')
        return parse_vlan_list(result)

    def get_interfaces(self):
        result = self.shell.do('show interfaces status')
        return [self.read_interface(name) for name in parse_interface_names(result)]

    def add_vlan(self, number, name=None):
        result = self.shell.do("show vlan id {}".format(number))
        if regex.match(".*\^.*", result[0]):
            raise BadVlanNumber()
        elif regex.match("^VLAN", result[0]):
            raise VlanAlreadyExist(number)

        with self.config():
            result = self.shell.do('vlan {}'.format(number))
            if len(result) > 0:
                raise BadVlanNumber()
            else:
                if name:
                    result = self.shell.do('name {}'.format(name))

                self.shell.do('exit')

                if len(result) > 0:
                    raise BadVlanName()

    def remove_vlan(self, number, name=None):
        with self.config():
            self.set('no vlan {}', number).on_result_matching(".*These VLANs do not exist:.*", UnknownVlan, number)

    def set_access_mode(self, interface_id):
        with self.config(), self.interface(interface_id):
            self.shell.do("no switchport trunk allowed vlan")
            self.shell.do("no switchport general allowed vlan")
            self.shell.do("no switchport general pvid")
            self.shell.do("switchport mode access")

    def set_trunk_mode(self, interface_id):
        interface_data = self.get_interface_data(interface_id)
        actual_port_mode = resolve_port_mode(interface_data)

        if actual_port_mode in ("access", None):
            with self.config(), self.interface(interface_id):
                self.shell.do("no switchport access vlan")
                self.shell.do("switchport mode trunk")

    def set_access_vlan(self, interface_id, vlan):
        interface_data = self.get_interface_data(interface_id)

        actual_port_mode = resolve_port_mode(interface_data)
        if actual_port_mode in ("trunk", "general"):
            raise InterfaceInWrongPortMode(actual_port_mode)

        with self.config(), self.interface(interface_id):
            self.set("switchport access vlan {}", vlan) \
                .on_result_matching(".*VLAN ID not found.*", UnknownVlan, vlan)

    def add_trunk_vlan(self, interface_id, vlan):
        interface_data = self.get_interface_data(interface_id)

        actual_port_mode = resolve_port_mode(interface_data)
        if actual_port_mode == "access":
            raise InterfaceInWrongPortMode("access")

        vlans = self.get_vlans()
        if not [v for v in vlans if v.number == vlan]:
            raise UnknownVlan(vlan)

        with self.config(), self.interface(interface_id):
            if actual_port_mode is None:
                self.set("switchport mode trunk")
                actual_port_mode = "trunk"

            if actual_port_mode == "trunk":
                if has_trunk_vlans(interface_data):
                    self.set("switchport {} allowed vlan add {}", actual_port_mode, vlan) \
                        .on_result_matching(".*VLAN does not exist.*", UnknownVlan, vlan)
                else:
                    self.set("switchport {} allowed vlan {}", actual_port_mode, vlan) \
                        .on_result_matching(".*VLAN does not exist.*", UnknownVlan, vlan)
            else:
                self.set("switchport {} allowed vlan add {}", actual_port_mode, vlan) \
                    .on_result_matching(".*VLAN does not exist.*", UnknownVlan, vlan)

    def remove_trunk_vlan(self, interface_id, vlan):
        interface_data = self.get_interface_data(interface_id)
        trunk_vlans = resolve_trunk_vlans(interface_data)

        if vlan not in trunk_vlans:
            raise TrunkVlanNotSet(interface_id)

        actual_port_mode = resolve_port_mode(interface_data)
        with self.config(), self.interface(interface_id):
            self.set("switchport {} allowed vlan remove {}", actual_port_mode, vlan)

    def get_interface_data(self, interface_id):
        interface_data = self.shell.do("show running-config interface {}".format(interface_id))
        if len(interface_data) > 0 and regex.match(".*invalid interface.*", interface_data[0]):
            raise UnknownInterface(interface_id)
        return interface_data

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
            if regex.match("switchport \S* allowed vlan (add )?(\S+)", line):
                interface.trunk_vlans = parse_vlan_ranges(regex[1])

        return interface


def has_trunk_vlans(interface_data):
    for line in interface_data:
        if regex.match(".*trunk allowed vlan.*", line):
            return True
    return False


def parse_interface_names(status_list):
    interfaces = []
    for line in status_list:
        if regex.match("Te(\d+/\d+/\S+).*", line):
            interfaces.append("tengigabitethernet {}".format(regex[0]))
        elif regex.match("Po(\d+).*", line):
            interfaces.append("port-channel {}".format(regex[0]))

    return interfaces


def parse_vlan_list(result):
    vlans = []
    for line in result:
        if regex.match('^(\d+)\s{1,6}(\S+).*', line):
            number, name = regex
            if name == "VLAN{:0>4}".format(number):
                name = None
            vlans.append(Vlan(number=int(number),
                              name=name if int(number) > 1 else "default"))
        elif regex.match('^(\d+)\s+.*', line):
            number = regex[0]
            vlans.append(Vlan(number=int(number)))
    return vlans


def resolve_trunk_vlans(interface_data):
    for line in interface_data:
        if regex.match("switchport \S+ allowed vlan (add )?(\S+)", line):
            return parse_vlan_ranges(regex[1])
    return []
