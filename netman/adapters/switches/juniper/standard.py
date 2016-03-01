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

from netman.adapters.switches.juniper.base import interface_speed, interface_replace, interface_speed_update, \
    first_text, bond_name, Juniper


def netconf(switch_descriptor, *args, **kwargs):
    return Juniper(switch_descriptor, custom_strategies=JuniperCustomStrategies(), *args, **kwargs)


class JuniperCustomStrategies(object):
    def get_interface_port_mode_update_element(self, mode):
        return to_ele("<port-mode>{}</port-mode>".format(mode))

    def get_port_mode_node_in_inteface_node(self, interface_node):
        return interface_node.xpath("unit/family/ethernet-switching/port-mode")

    def add_enslave_to_bond_operations(self, update, interface, bond):
        ether_options = [
            to_ele("""
                <ieee-802.3ad>
                    <bundle>{0}</bundle>
                </ieee-802.3ad>
            """.format(bond_name(bond.number)))]

        if bond.link_speed is not None:
            ether_options.append(interface_speed(bond.link_speed))

        update.add_interface(interface_replace(interface, *ether_options))

    def add_update_bond_members_speed_operations(self, update, slave_nodes, speed):
        for interface_node in slave_nodes:
            update.add_interface(interface_speed_update(first_text(interface_node.xpath("name")), speed))

    def get_interface_trunk_native_vlan_id_node(self, interface):
        return interface.xpath("unit/family/ethernet-switching/native-vlan-id")

    def set_native_vlan_id_node(self, interface_node, native_vlan_id_node):
        return interface_node.xpath("//ethernet-switching")[0].append(native_vlan_id_node)

