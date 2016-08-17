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
import copy
from collections import OrderedDict

from netman.core.objects.bond import Bond
from netman.core.objects.interface import Interface
from netman.core.objects.interface_states import OFF, ON
from netman.core.objects.port_modes import ACCESS, TRUNK
from netman.core.objects.switch_base import SwitchBase
from netman.core.objects.vlan import Vlan
from netman.core.objects.vrrp_group import VrrpGroup

__all__ = ['CachedSwitch']


class Cache(object):
    object_type = None
    object_key = None

    def __init__(self, *key_value_tuples):
        self.refresh_items = set()
        self.dict = OrderedDict(*key_value_tuples)

    def create_fake_object(self, item):
        params = {self.object_key: item}
        return self.object_type(**params)

    def invalidated(self):
        self.refresh_items.add(None)
        return self

    def __getitem__(self, item):
        try:
            return self.dict[item]
        except KeyError:
            self.refresh_items.add(item)
            return self.create_fake_object(item)

    def __setitem__(self, key, value):
        self.dict[key] = value
        try:
            self.refresh_items.remove(key)
        except KeyError:
            pass

    def __contains__(self, item):
        return item in self.dict

    def __len__(self):
        return len(self.dict)

    def __delitem__(self, key):
        try:
            del self.dict[key]
            self.refresh_items.remove(key)
        except KeyError:
            pass

    def values(self):
        return self.dict.values()


class VlanCache(Cache):
    object_type = Vlan
    object_key = 'number'


class InterfaceCache(Cache):
    object_type = Interface
    object_key = 'name'


class VlanInterfaceCache(Cache):
    object_type = str
    object_key = 'number'


class BondCache(Cache):
    object_type = Bond
    object_key = 'number'


class CachedSwitch(SwitchBase):
    def __init__(self, real_switch):
        super(CachedSwitch, self).__init__(real_switch.switch_descriptor)
        self.real_switch = real_switch
        self.vlans_cache = VlanCache().invalidated()
        self.interfaces_cache = InterfaceCache().invalidated()
        self.vlan_interfaces_cache = VlanInterfaceCache().invalidated()
        self.bonds_cache = BondCache().invalidated()
        self.versions_cache = Cache().invalidated()

    def _connect(self):
        return self.real_switch.connect()

    def _disconnect(self):
        return self.real_switch.disconnect()

    def _start_transaction(self):
        return self.real_switch.start_transaction()

    def commit_transaction(self):
        return self.real_switch.commit_transaction()

    def rollback_transaction(self):
        return self.real_switch.rollback_transaction()

    def _end_transaction(self):
        return self.real_switch.end_transaction()

    def get_vlan(self, number):
        if (self.vlans_cache.refresh_items and number not in self.vlans_cache) \
                or number in self.vlans_cache.refresh_items:
            self.vlans_cache[number] = self.real_switch.get_vlan(number)
        return copy.deepcopy(self.vlans_cache[number])

    def get_vlans(self):
        if None in self.vlans_cache.refresh_items:
            self.vlans_cache = VlanCache((vlan.number, vlan) for vlan in self.real_switch.get_vlans())

        for number in list(self.vlans_cache.refresh_items):
            self.get_vlan(number)

        return copy.deepcopy(self.vlans_cache.values())

    def get_vlan_interfaces(self, number):
        if (self.vlan_interfaces_cache.refresh_items and number not in self.vlan_interfaces_cache) \
                or number in self.vlan_interfaces_cache.refresh_items:
            self.vlan_interfaces_cache[number] = self.real_switch.get_vlan_interfaces(number)
        return copy.deepcopy(self.vlan_interfaces_cache[number])

    def get_interface(self, instance_id):
        if (self.interfaces_cache.refresh_items and instance_id not in self.interfaces_cache) \
                or instance_id in self.interfaces_cache.refresh_items:
            self.interfaces_cache[instance_id] = self.real_switch.get_interface(instance_id)
        return copy.deepcopy(self.interfaces_cache[instance_id])

    def get_interfaces(self):
        if self.interfaces_cache.refresh_items:
            self.interfaces_cache = InterfaceCache(
                (interface.name, interface)
                 for interface in self.real_switch.get_interfaces())
        return copy.deepcopy(self.interfaces_cache.values())

    def get_bond(self, number):
        if (self.bonds_cache.refresh_items and number not in self.bonds_cache)\
                or number in self.bonds_cache.refresh_items:
            self.bonds_cache[number] = self.real_switch.get_bond(number)
        return copy.deepcopy(self.bonds_cache[number])

    def get_bonds(self):
        if self.bonds_cache.refresh_items:
            self.bonds_cache = BondCache(
                (bond.number, bond) for bond in self.real_switch.get_bonds())
        return copy.deepcopy(self.bonds_cache.values())

    def add_vlan(self, number, name=None):
        extras = {}
        if name is not None:
            extras["name"] = name
        result = self.real_switch.add_vlan(number, **extras)
        self.vlans_cache.refresh_items.add(number)
        return result

    def remove_vlan(self, number):
        self.real_switch.remove_vlan(number)
        del self.vlans_cache[number]

    def set_vlan_access_group(self, vlan_number, direction, name):
        self.real_switch.set_vlan_access_group(vlan_number, direction, name)
        self.vlans_cache[vlan_number].access_groups[direction] = name

    def unset_vlan_access_group(self, vlan_number, direction):
        self.real_switch.unset_vlan_access_group(vlan_number, direction)
        self.vlans_cache[vlan_number].access_groups[direction] = None

    def add_ip_to_vlan(self, vlan_number, ip_network):
        self.real_switch.add_ip_to_vlan(vlan_number, ip_network)
        self.vlans_cache[vlan_number].ips.append(ip_network)

    def remove_ip_from_vlan(self, vlan_number, ip_network):
        self.real_switch.remove_ip_from_vlan(vlan_number, ip_network)
        self.vlans_cache[vlan_number].ips = [
            net for net in self.vlans_cache[vlan_number].ips
            if str(net) != str(ip_network)]

    def set_vlan_vrf(self, vlan_number, vrf_name):
        self.real_switch.set_vlan_vrf(vlan_number, vrf_name)
        self.vlans_cache[vlan_number].vrf_forwarding = vrf_name

    def unset_vlan_vrf(self, vlan_number):
        self.real_switch.unset_vlan_vrf(vlan_number)
        self.vlans_cache[vlan_number].vrf_forwarding = None

    def set_access_mode(self, interface_id):
        self.real_switch.set_access_mode(interface_id)
        self.interfaces_cache[interface_id].port_mode = ACCESS
        self.interfaces_cache[interface_id].trunk_native_vlan = None
        self.interfaces_cache[interface_id].trunk_vlans = []

    def set_trunk_mode(self, interface_id):
        self.real_switch.set_trunk_mode(interface_id)
        self.interfaces_cache[interface_id].port_mode = TRUNK

    def set_bond_access_mode(self, bond_number):
        self.real_switch.set_bond_access_mode(bond_number)
        self.bonds_cache[bond_number].port_mode = ACCESS

    def set_bond_trunk_mode(self, bond_number):
        self.real_switch.set_bond_trunk_mode(bond_number)
        self.bonds_cache[bond_number].port_mode = TRUNK

    def set_access_vlan(self, interface_id, vlan):
        self.real_switch.set_access_vlan(interface_id, vlan)
        self.interfaces_cache[interface_id].access_vlan = vlan

    def reset_interface(self, interface_id):
        self.real_switch.reset_interface(interface_id)
        self.interfaces_cache.refresh_items.add(interface_id)

    def unset_interface_access_vlan(self, interface_id):
        self.real_switch.unset_interface_access_vlan(interface_id)
        self.interfaces_cache[interface_id].access_vlan = None

    def set_interface_native_vlan(self, interface_id, vlan):
        self.real_switch.set_interface_native_vlan(interface_id, vlan)
        self.interfaces_cache[interface_id].trunk_native_vlan = vlan

    def unset_interface_native_vlan(self, interface_id):
        self.real_switch.unset_interface_native_vlan(interface_id)
        self.interfaces_cache[interface_id].trunk_native_vlan = None

    def set_bond_native_vlan(self, bond_number, vlan):
        self.real_switch.set_bond_native_vlan(bond_number, vlan)
        self.bonds_cache[bond_number].trunk_native_vlan = vlan

    def unset_bond_native_vlan(self, bond_number):
        self.real_switch.unset_bond_native_vlan(bond_number)
        self.bonds_cache[bond_number].trunk_native_vlan = None

    def add_trunk_vlan(self, interface_id, vlan):
        self.real_switch.add_trunk_vlan(interface_id, vlan)
        self.interfaces_cache[interface_id].trunk_vlans.append(vlan)

    def remove_trunk_vlan(self, interface_id, vlan):
        self.real_switch.remove_trunk_vlan(interface_id, vlan)
        try:
            self.interfaces_cache[interface_id].trunk_vlans.remove(vlan)
        except ValueError:
            pass

    def add_bond_trunk_vlan(self, bond_number, vlan):
        self.real_switch.add_bond_trunk_vlan(bond_number, vlan)
        self.bonds_cache[bond_number].trunk_vlans.append(vlan)

    def remove_bond_trunk_vlan(self, bond_number, vlan):
        self.real_switch.remove_bond_trunk_vlan(bond_number, vlan)
        try:
            self.bonds_cache[bond_number].trunk_vlans.remove(vlan)
        except ValueError:
            pass

    def set_interface_description(self, interface_id, description):
        # No cache to update
        self.real_switch.set_interface_description(interface_id, description)

    def unset_interface_description(self, interface_id):
        # No cache to update
        self.real_switch.unset_interface_description(interface_id)

    def set_bond_description(self, bond_number, description):
        # No cache to update
        self.real_switch.set_bond_description(bond_number, description)

    def unset_bond_description(self, bond_number):
        # No cache to update
        self.real_switch.unset_bond_description(bond_number)

    def edit_interface_spanning_tree(self, interface_id, edge=None):
        # No cache to update
        self.real_switch.edit_interface_spanning_tree(interface_id, edge=edge)

    def set_interface_state(self, interface_id, state):
        self.real_switch.set_interface_state(interface_id, state)
        self.interfaces_cache[interface_id].shutdown = (state == OFF)

    def unset_interface_state(self, interface_id):
        self.real_switch.unset_interface_state(interface_id)
        self.interfaces_cache.refresh_items.add(interface_id)

    def set_interface_auto_negotiation_state(self, interface_id, state):
        self.real_switch.set_interface_auto_negotiation_state(interface_id, state)
        self.interfaces_cache[interface_id].auto_negotiation = (state == ON)

    def unset_interface_auto_negotiation_state(self, interface_id):
        self.real_switch.unset_interface_auto_negotiation_state(interface_id)
        self.interfaces_cache[interface_id].auto_negotiation = None

    def add_bond(self, number):
        self.real_switch.add_bond(number)
        self.bonds_cache.refresh_items.add(number)

    def remove_bond(self, number):
        self.real_switch.remove_bond(number)
        del self.bonds_cache[number]

    def add_interface_to_bond(self, interface, bond_number):
        self.real_switch.add_interface_to_bond(interface, bond_number)
        self.bonds_cache[bond_number].members.append(interface)
        self.interfaces_cache.refresh_items.add(interface)

    def remove_interface_from_bond(self, interface):
        self.real_switch.remove_interface_from_bond(interface)
        self.interfaces_cache[interface].bond_master = None
        self.interfaces_cache.refresh_items.add(interface)
        for bond in self.bonds_cache.values():
            try:
                bond.members.remove(interface)
            except ValueError:
                pass

    def set_bond_link_speed(self, number, speed):
        self.real_switch.set_bond_link_speed(number, speed)
        self.bonds_cache[number].link_speed = speed

    def edit_bond_spanning_tree(self, number, edge=None):
        self.real_switch.edit_bond_spanning_tree(number, edge=edge)

    def add_vrrp_group(self, vlan_number, group_id, ips=None, priority=None,
                       hello_interval=None, dead_interval=None ,track_id=None,
                       track_decrement=None):
        self.real_switch.add_vrrp_group(vlan_number, group_id, ips=ips,
                                        priority=priority,
                                        hello_interval=hello_interval,
                                        dead_interval=dead_interval,
                                        track_id=track_id,
                                        track_decrement=track_decrement)
        self.vlans_cache[vlan_number].vrrp_groups.append(VrrpGroup(
            id=group_id, ips=ips, priority=priority,
            hello_interval=hello_interval, dead_interval=dead_interval,
            track_id=track_id, track_decrement=track_decrement
        ))

    def remove_vrrp_group(self, vlan_number, group_id):
        self.real_switch.remove_vrrp_group(vlan_number, group_id)
        for group in self.vlans_cache[vlan_number].vrrp_groups:
            if group.id == group_id:
                self.vlans_cache[vlan_number].vrrp_groups.remove(group)

    def add_dhcp_relay_server(self, vlan_number, ip_address):
        self.real_switch.add_dhcp_relay_server(vlan_number, ip_address)
        self.vlans_cache[vlan_number].dhcp_relay_servers.append(ip_address)

    def remove_dhcp_relay_server(self, vlan_number, ip_address):
        self.real_switch.remove_dhcp_relay_server(vlan_number, ip_address)
        try:
            self.vlans_cache[vlan_number].dhcp_relay_servers.remove(ip_address)
        except ValueError:
            pass

    def set_interface_lldp_state(self, interface_id, enabled):
        self.real_switch.set_interface_lldp_state(interface_id, enabled)

    def set_vlan_icmp_redirects_state(self, vlan_number, state):
        self.real_switch.set_vlan_icmp_redirects_state(vlan_number, state)
        self.vlans_cache[vlan_number].icmp_redirects = state

    def get_versions(self):
        if self.versions_cache.refresh_items:
            self.versions_cache = Cache([(0, self.real_switch.get_versions())])
        return copy.deepcopy(self.versions_cache[0])

    def set_interface_mtu(self, interface_id, size):
        self.real_switch.set_interface_mtu(interface_id, size)
        self.interfaces_cache[interface_id].mtu = size

    def unset_interface_mtu(self, interface_id):
        self.real_switch.unset_interface_mtu(interface_id)
        self.interfaces_cache[interface_id].mtu = None

    def set_bond_mtu(self, bond_number, size):
        self.real_switch.set_bond_mtu(bond_number, size)
        self.bonds_cache[bond_number].mtu = size

    def unset_bond_mtu(self, bond_number):
        self.real_switch.unset_bond_mtu(bond_number)
        self.bonds_cache[bond_number].mtu = None
