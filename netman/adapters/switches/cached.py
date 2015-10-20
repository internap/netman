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

from collections import OrderedDict

from netman.core.objects import port_modes
from netman.core.objects.bond import Bond
from netman.core.objects.interface import Interface
from netman.core.objects.switch_base import SwitchBase
from netman.core.objects.vlan import Vlan
from netman.core.objects.vrrp_group import VrrpGroup


__all__ = ['CachedSwitch']


class Cache():
    object_type = None
    object_key = None
    object_extra = {}

    def __init__(self, *args, **kwargs):
        self.need_refresh = set()
        self.dict = OrderedDict(*args, **kwargs)

    def __getitem__(self, item):
        try:
            return self.dict[item]
        except KeyError:
            # don't create the item, just act as it is present
            self.need_refresh.add(item)
            params = {self.object_key: item}
            params.update({k:(v() if callable(v) else v)
                           for k, v in self.object_extra.iteritems()})
            return self.object_type(**params)

    def __setitem__(self, key, value):
        if not self.dict:
            self.need_refresh.add(None)
        self.dict[key] = value
        try:
            self.need_refresh.remove(key)
        except KeyError:
            pass

    def __contains__(self, item):
        return item in self.dict

    def __len__(self):
        return len(self.dict)

    def __delitem__(self, key):
        del self.dict[key]
        try:
            self.need_refresh.remove(key)
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


class BondCache(Cache):
    object_type = Bond
    object_key = 'number'
    object_extra = dict(interface=Interface)


class CachedSwitch(SwitchBase):
    def __init__(self, real_switch):
        super(CachedSwitch, self).__init__(real_switch.switch_descriptor)
        self.real_switch = real_switch
        self.vlans_cache = VlanCache()
        self.interfaces_cache = InterfaceCache()
        self.bonds_cache = BondCache()

    def connect(self):
        return self.real_switch.connect()

    def disconnect(self):
        return self.real_switch.disconnect()

    def start_transaction(self):
        return self.real_switch.start_transaction()

    def commit_transaction(self):
        return self.real_switch.commit_transaction()

    def rollback_transaction(self):
        return self.real_switch.rollback_transaction()

    def end_transaction(self):
        return self.real_switch.end_transaction()

    def get_vlans(self):
        if not self.vlans_cache or self.vlans_cache.need_refresh:
            self.vlans_cache = VlanCache(
                ((vlan.number, vlan) for vlan in self.real_switch.get_vlans()))
        return self.vlans_cache.values()

    def get_interfaces(self):
        if not self.interfaces_cache or self.interfaces_cache.need_refresh:
            self.interfaces_cache = InterfaceCache(
                ((interface.name, interface)
                 for interface in self.real_switch.get_interfaces()))
        return self.interfaces_cache.values()

    def get_bond(self, number):
        if number not in self.bonds_cache\
                or number in self.bonds_cache.need_refresh:
            self.bonds_cache[number] = self.real_switch.get_bond(number)
        return self.bonds_cache[number]

    def get_bonds(self):
        if not self.bonds_cache or self.bonds_cache.need_refresh:
            self.bonds_cache = BondCache(
                ((bond.number, bond) for bond in self.real_switch.get_bonds()))
        return self.bonds_cache.values()

    def add_vlan(self, number, name=None):
        result = self.real_switch.add_vlan(number, name)
        self.vlans_cache[number] = Vlan(number, name=name)
        return result

    def remove_vlan(self, number):
        self.real_switch.remove_vlan(number)
        del self.vlans_cache[number]

    def set_vlan_access_group(self, vlan_number, direction, name):
        self.real_switch.set_vlan_access_group(vlan_number, direction, name)
        self.vlans_cache[vlan_number].access_groups[direction] = name

    def remove_vlan_access_group(self, vlan_number, direction):
        self.real_switch.remove_vlan_access_group(vlan_number, direction)
        self.vlans_cache[vlan_number].access_groups[direction] = None

    def add_ip_to_vlan(self, vlan_number, ip_network):
        self.real_switch.add_ip_to_vlan(vlan_number, ip_network)
        self.vlans_cache[vlan_number].ips.append(ip_network)

    def remove_ip_from_vlan(self, vlan_number, ip_network):
        self.real_switch.remove_ip_from_vlan(vlan_number, ip_network)
        self.vlans_cache[vlan_number].ips.remove(
            next(net for net in self.vlans_cache[vlan_number].ips
                 if str(net) == str(ip_network)))

    def set_vlan_vrf(self, vlan_number, vrf_name):
        self.real_switch.set_vlan_vrf(vlan_number, vrf_name)
        self.vlans_cache[vlan_number].vrf_forwarding = vrf_name

    def remove_vlan_vrf(self, vlan_number):
        self.real_switch.remove_vlan_vrf(vlan_number)
        self.vlans_cache[vlan_number].vrf_forwarding = None

    def set_access_mode(self, interface_id):
        self.real_switch.set_access_mode(interface_id)
        self.interfaces_cache[interface_id].port_mode = port_modes.ACCESS

    def set_trunk_mode(self, interface_id):
        self.real_switch.set_trunk_mode(interface_id)
        self.interfaces_cache[interface_id].port_mode = port_modes.TRUNK

    def set_bond_access_mode(self, bond_number):
        self.real_switch.set_bond_access_mode(bond_number)
        self.bonds_cache[bond_number].interface.port_mode = port_modes.ACCESS

    def set_bond_trunk_mode(self, bond_number):
        self.real_switch.set_bond_trunk_mode(bond_number)
        self.bonds_cache[bond_number].interface.port_mode = port_modes.TRUNK

    def set_access_vlan(self, interface_id, vlan):
        self.real_switch.set_access_vlan(interface_id, vlan)
        self.interfaces_cache[interface_id].access_vlan = vlan

    def remove_access_vlan(self, interface_id):
        self.real_switch.remove_access_vlan(interface_id)
        self.interfaces_cache[interface_id].access_vlan = None

    def configure_native_vlan(self, interface_id, vlan):
        self.real_switch.configure_native_vlan(interface_id, vlan)
        self.interfaces_cache[interface_id].trunk_native_vlan = vlan

    def remove_native_vlan(self, interface_id):
        self.real_switch.remove_native_vlan(interface_id)
        self.interfaces_cache[interface_id].trunk_native_vlan = None

    def configure_bond_native_vlan(self, bond_number, vlan):
        self.real_switch.configure_bond_native_vlan(bond_number, vlan)
        self.bonds_cache[bond_number].interface.trunk_native_vlan = vlan

    def remove_bond_native_vlan(self, bond_number):
        self.real_switch.remove_bond_native_vlan(bond_number)
        self.bonds_cache[bond_number].interface.trunk_native_vlan = None

    def add_trunk_vlan(self, interface_id, vlan):
        self.real_switch.add_trunk_vlan(interface_id, vlan)
        self.interfaces_cache[interface_id].trunk_vlans.append(vlan)

    def remove_trunk_vlan(self, interface_id, vlan):
        self.real_switch.remove_trunk_vlan(interface_id, vlan)
        self.interfaces_cache[interface_id].trunk_vlans.remove(vlan)

    def add_bond_trunk_vlan(self, bond_number, vlan):
        self.real_switch.add_bond_trunk_vlan(bond_number, vlan)
        self.bonds_cache[bond_number].interface.trunk_vlans.append(vlan)

    def remove_bond_trunk_vlan(self, bond_number, vlan):
        self.real_switch.remove_bond_trunk_vlan(bond_number, vlan)
        self.bonds_cache[bond_number].interface.trunk_vlans.remove(vlan)

    def set_interface_description(self, interface_id, description):
        # No cache to update
        self.real_switch.set_interface_description(interface_id, description)

    def remove_interface_description(self, interface_id):
        # No cache to update
        self.real_switch.remove_interface_description(interface_id)

    def set_bond_description(self, bond_number, description):
        # No cache to update
        self.real_switch.set_bond_description(bond_number, description)

    def remove_bond_description(self, bond_number):
        # No cache to update
        self.real_switch.remove_bond_description(bond_number)

    def edit_interface_spanning_tree(self, interface_id, edge=None):
        # No cache to update
        self.real_switch.edit_interface_spanning_tree(interface_id, edge)

    def openup_interface(self, interface_id):
        self.real_switch.openup_interface(interface_id)
        self.interfaces_cache[interface_id].shutdown = False

    def shutdown_interface(self, interface_id):
        self.real_switch.shutdown_interface(interface_id)
        self.interfaces_cache[interface_id].shutdown = True

    def add_bond(self, number):
        self.real_switch.add_bond(number)
        self.bonds_cache[number] = Bond(number=number)

    def remove_bond(self, number):
        self.real_switch.remove_bond(number)
        del self.bonds_cache[number]

    def add_interface_to_bond(self, interface, bond_number):
        self.real_switch.add_interface_to_bond(interface, bond_number)
        self.bonds_cache[bond_number].members.append(interface)
        self.interfaces_cache[interface].bond_master = bond_number

    def remove_interface_from_bond(self, interface):
        self.real_switch.remove_interface_from_bond(interface)
        self.interfaces_cache[interface].bond_master = None
        for bond in self.bonds_cache.values():
            try:
                bond.members.remove(interface)
            except ValueError:
                pass

    def set_bond_link_speed(self, number, speed):
        self.real_switch.set_bond_link_speed(number, speed)
        self.bonds_cache[number].link_speed = speed

    def edit_bond_spanning_tree(self, number, edge=None):
        self.real_switch.edit_bond_spanning_tree(number, edge)

    def add_vrrp_group(self, vlan_number, group_id, ips=None, priority=None,
                       hello_interval=None, dead_interval=None ,track_id=None,
                       track_decrement=None):
        self.real_switch.add_vrrp_group(vlan_number, group_id, ips, priority,
                                   hello_interval, dead_interval, track_id,
                                   track_decrement)
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
        self.real_switch.add_dhcp_relay_server(vlan_number, ip_address)
        try:
            self.vlans_cache[vlan_number].dhcp_relay_servers.remove(ip_address)
        except ValueError:
            pass

    def enable_lldp(self, interface_id, enabled):
        self.real_switch.enable_lldp(interface_id, enabled)
