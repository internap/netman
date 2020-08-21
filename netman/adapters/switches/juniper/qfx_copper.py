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

from ncclient.xml_ import to_ele

from netman.adapters.switches.juniper.base import interface_replace, bond_name, Juniper, first_text
from netman.adapters.switches.juniper.standard import JuniperCustomStrategies
from netman.core.objects.mac_address import MacAddress


def netconf(switch_descriptor):
    return Juniper(switch_descriptor, custom_strategies=JuniperQfxCopperCustomStrategies())


class JuniperQfxCopperCustomStrategies(JuniperCustomStrategies):
    def get_interface_port_mode_update_element(self, mode):
        return to_ele("<interface-mode>{}</interface-mode>".format(mode))

    def get_port_mode_node_in_inteface_node(self, interface_node):
        return interface_node.xpath("unit/family/ethernet-switching/interface-mode")

    def add_enslave_to_bond_operations(self, update, interface, bond):
        ether_options = [
            to_ele("<auto-negotiation/>"),
            to_ele("""
                <ieee-802.3ad>
                    <bundle>{0}</bundle>
                </ieee-802.3ad>
            """.format(bond_name(bond.number)))]

        update.add_interface(interface_replace(interface, *ether_options))

    def add_update_bond_members_speed_operations(self, update, slave_nodes, speed):
        pass

    def get_interface_trunk_native_vlan_id_node(self, interface):
        return interface.xpath("native-vlan-id")

    def set_native_vlan_id_node(self, interface_node, native_vlan_id_node):
        return interface_node.xpath("//interface")[0].append(native_vlan_id_node)

    def get_protocols_interface_name(self, interface_name):
        return interface_name

    def parse_mac_address_table(self, mac_table):
        mac = []
        for vlan_path in mac_table.xpath("//l2ng-l2ald-mac-entry-vlan"):
            interface = first_text(vlan_path.xpath("l2ng-l2-mac-logical-interface"))
            vlan = int(first_text(vlan_path.xpath("l2ng-l2-vlan-id")))
            mac_address = first_text(vlan_path.xpath("l2ng-l2-mac-address"))
            interface, type = self._parse_interface_type(interface)
            mac.append(MacAddress(vlan, mac_address, interface, type))
        return mac

    def _parse_interface_type(self, interface):
        if interface.startswith("ae"):
            return interface.strip('.0'), "Agregated"
        else:
            return interface.strip('.0'), "Physical"
