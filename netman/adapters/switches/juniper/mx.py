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

from netman.adapters.switches.juniper.base import Juniper
from netman.adapters.switches.juniper.qfx_copper import JuniperQfxCopperCustomStrategies


class MxJuniper(Juniper):
    def get_vlan(self, number):
        raise NotImplementedError()

    def get_vlans(self):
        raise NotImplementedError()

    def add_vlan(self, number, name=None):
        raise NotImplementedError()

    def remove_vlan(self, number):
        raise NotImplementedError()

    def get_interface(self, interface_id):
        raise NotImplementedError()

    def get_interfaces(self):
        raise NotImplementedError()

    def set_access_vlan(self, interface_id, vlan):
        raise NotImplementedError()

    def unset_interface_access_vlan(self, interface_id):
        raise NotImplementedError()

    def set_access_mode(self, interface_id):
        raise NotImplementedError()

    def set_trunk_mode(self, interface_id):
        raise NotImplementedError()

    def add_trunk_vlan(self, interface_id, vlan):
        raise NotImplementedError()

    def remove_trunk_vlan(self, interface_id, vlan):
        raise NotImplementedError()

    def set_interface_state(self, interface_id, state):
        raise NotImplementedError()

    def unset_interface_state(self, interface_id):
        raise NotImplementedError()

    def set_interface_auto_negotiation_state(self, interface_id, negotiation_state):
        raise NotImplementedError()

    def unset_interface_auto_negotiation_state(self, interface_id):
        raise NotImplementedError()

    def set_interface_native_vlan(self, interface_id, vlan):
        raise NotImplementedError()

    def unset_interface_native_vlan(self, interface_id):
        raise NotImplementedError()

    def reset_interface(self, interface_id):
        raise NotImplementedError()

    def get_vlan_interfaces(self, vlan_number):
        raise NotImplementedError()

    def add_ip_to_vlan(self, vlan_number, ip_network):
        raise NotImplementedError()

    def remove_ip_from_vlan(self, vlan_number, ip_network):
        raise NotImplementedError()

    def set_vlan_access_group(self, vlan_number, direction, name):
        raise NotImplementedError()

    def unset_vlan_access_group(self, vlan_number, direction):
        raise NotImplementedError()

    def set_vlan_vrf(self, vlan_number, vrf_name):
        raise NotImplementedError()

    def unset_vlan_vrf(self, vlan_number):
        raise NotImplementedError()

    def set_interface_description(self, interface_id, description):
        raise NotImplementedError()

    def unset_interface_description(self, interface_id):
        raise NotImplementedError()

    def edit_interface_spanning_tree(self, interface_id, edge=None):
        raise NotImplementedError()

    def add_bond(self, number):
        raise NotImplementedError()

    def remove_bond(self, number):
        raise NotImplementedError()

    def get_bond(self, number):
        raise NotImplementedError()

    def get_bonds(self):
        raise NotImplementedError()

    def add_interface_to_bond(self, interface, bond_number):
        raise NotImplementedError()

    def remove_interface_from_bond(self, interface):
        raise NotImplementedError()

    def set_bond_link_speed(self, number, speed):
        raise NotImplementedError()

    def set_bond_description(self, number, description):
        raise NotImplementedError()

    def unset_bond_description(self, number):
        raise NotImplementedError()

    def set_bond_trunk_mode(self, number):
        raise NotImplementedError()

    def set_bond_access_mode(self, number):
        raise NotImplementedError()

    def add_bond_trunk_vlan(self, number, vlan):
        raise NotImplementedError()

    def remove_bond_trunk_vlan(self, number, vlan):
        raise NotImplementedError()

    def set_bond_native_vlan(self, number, vlan):
        raise NotImplementedError()

    def unset_bond_native_vlan(self, number):
        raise NotImplementedError()

    def edit_bond_spanning_tree(self, number, edge=None):
        raise NotImplementedError()

    def add_vrrp_group(self, vlan_number, group_id, ips=None, priority=None, hello_interval=None, dead_interval=None,
                       track_id=None, track_decrement=None):
        raise NotImplementedError()

    def remove_vrrp_group(self, vlan_id, group_id):
        raise NotImplementedError()

    def add_dhcp_relay_server(self, vlan_number, ip_address):
        raise NotImplementedError()

    def remove_dhcp_relay_server(self, vlan_number, ip_address):
        raise NotImplementedError()

    def set_interface_lldp_state(self, interface_id, enabled):
        raise NotImplementedError()

    def set_vlan_arp_routing_state(self, vlan_number, state):
        raise NotImplementedError()

    def set_vlan_icmp_redirects_state(self, vlan_number, state):
        raise NotImplementedError()

    def set_vlan_unicast_rpf_mode(self, vlan_number, mode):
        raise NotImplementedError()

    def unset_vlan_unicast_rpf_mode(self, vlan_number):
        raise NotImplementedError()

    def get_versions(self):
        raise NotImplementedError()

    def set_interface_mtu(self, interface_id, size):
        raise NotImplementedError()

    def unset_interface_mtu(self, interface_id):
        raise NotImplementedError()

    def set_bond_mtu(self, number, size):
        raise NotImplementedError()

    def unset_bond_mtu(self, number):
        raise NotImplementedError()


def netconf(switch_descriptor):
    return MxJuniper(switch_descriptor, custom_strategies=JuniperMXCustomStrategies())


class JuniperMXCustomStrategies(JuniperQfxCopperCustomStrategies):
    pass
