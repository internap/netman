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
from contextlib import contextmanager
from functools import wraps

from netman.core.objects.backward_compatible_switch_operations import BackwardCompatibleSwitchOperations


def not_implemented(func):
    @wraps(func)
    def func_wrapper(*args, **kwargs):
        raise NotImplementedError("'{}' is not implemented".format(func.func_name))
    return func_wrapper


class SwitchOperations(BackwardCompatibleSwitchOperations):

    @not_implemented
    def connect(self):
        pass

    @not_implemented
    def disconnect(self):
        pass

    @not_implemented
    def transaction(self):
        pass

    @not_implemented
    def start_transaction(self):
        pass

    @not_implemented
    def commit_transaction(self):
        pass

    @not_implemented
    def rollback_transaction(self):
        pass

    @not_implemented
    def end_transaction(self):
        pass

    @not_implemented
    def get_vlan(self, number):
        pass

    @not_implemented
    def get_vlans(self):
        pass

    @not_implemented
    def add_vlan(self, number, name=None):
        pass

    @not_implemented
    def remove_vlan(self, number):
        pass

    @not_implemented
    def get_interface(self, interface_id):
        pass

    @not_implemented
    def get_interfaces(self):
        pass

    @not_implemented
    def set_access_vlan(self, interface_id, vlan):
        pass

    @not_implemented
    def unset_interface_access_vlan(self, interface_id):
        pass

    @not_implemented
    def set_access_mode(self, interface_id):
        pass

    @not_implemented
    def set_trunk_mode(self, interface_id):
        pass

    @not_implemented
    def add_trunk_vlan(self, interface_id, vlan):
        pass

    @not_implemented
    def remove_trunk_vlan(self, interface_id, vlan):
        pass

    @not_implemented
    def set_interface_state(self, interface_id, state):
        pass

    @not_implemented
    def unset_interface_state(self, interface_id):
        pass

    @not_implemented
    def set_interface_auto_negotiation_state(self, interface_id, negotiation_state):
        pass

    @not_implemented
    def unset_interface_auto_negotiation_state(self, interface_id):
        pass

    @not_implemented
    def set_interface_lacp_force_up(self, interface_id):
        pass

    @not_implemented
    def unset_interface_lacp_force_up(self, interface_id):
        pass

    @not_implemented
    def set_interface_recovery_timeout(self, interface_id, recovery_timeout):
        pass

    @not_implemented
    def set_bond_recovery_timeout(self, bond_id, recovery_timeout):
        pass

    @not_implemented
    def set_interface_native_vlan(self, interface_id, vlan):
        pass

    @not_implemented
    def unset_interface_native_vlan(self, interface_id):
        pass

    @not_implemented
    def reset_interface(self, interface_id):
        pass

    @not_implemented
    def get_vlan_interfaces(self, vlan_number):
        pass

    @not_implemented
    def add_ip_to_vlan(self, vlan_number, ip_network):
        pass

    @not_implemented
    def remove_ip_from_vlan(self, vlan_number, ip_network):
        pass

    @not_implemented
    def set_vlan_access_group(self, vlan_number, direction, name):
        pass

    @not_implemented
    def unset_vlan_access_group(self, vlan_number, direction):
        pass

    @not_implemented
    def set_vlan_vrf(self, vlan_number, vrf_name):
        pass

    @not_implemented
    def unset_vlan_vrf(self, vlan_number):
        pass

    @not_implemented
    def set_interface_description(self, interface_id, description):
        pass

    @not_implemented
    def unset_interface_description(self, interface_id):
        pass

    @not_implemented
    def edit_interface_spanning_tree(self, interface_id, edge=None):
        pass

    @not_implemented
    def add_bond(self, number):
        pass

    @not_implemented
    def remove_bond(self, number):
        pass

    @not_implemented
    def get_bond(self, number):
        pass

    @not_implemented
    def get_bonds(self):
        pass

    @not_implemented
    def add_interface_to_bond(self, interface, bond_number):
        pass

    @not_implemented
    def remove_interface_from_bond(self, interface):
        pass

    @not_implemented
    def set_bond_link_speed(self, number, speed):
        pass

    @not_implemented
    def set_bond_description(self, number, description):
        pass

    @not_implemented
    def unset_bond_description(self, number):
        pass

    @not_implemented
    def set_bond_trunk_mode(self, number):
        pass

    @not_implemented
    def set_bond_access_mode(self, number):
        pass

    @not_implemented
    def add_bond_trunk_vlan(self, number, vlan):
        pass

    @not_implemented
    def remove_bond_trunk_vlan(self, number, vlan):
        pass

    @not_implemented
    def set_bond_native_vlan(self, number, vlan):
        pass

    @not_implemented
    def unset_bond_native_vlan(self, number):
        pass

    @not_implemented
    def edit_bond_spanning_tree(self, number, edge=None):
        pass

    @not_implemented
    def add_vrrp_group(self, vlan_number, group_id, ips=None, priority=None, hello_interval=None, dead_interval=None,
                       track_id=None, track_decrement=None):
        pass

    @not_implemented
    def remove_vrrp_group(self, vlan_id, group_id):
        pass

    @not_implemented
    def add_dhcp_relay_server(self, vlan_number, ip_address):
        pass

    @not_implemented
    def remove_dhcp_relay_server(self, vlan_number, ip_address):
        pass

    @not_implemented
    def set_interface_lldp_state(self, interface_id, enabled):
        pass

    @not_implemented
    def set_vlan_arp_routing_state(self, vlan_number, state):
        pass

    @not_implemented
    def set_vlan_icmp_redirects_state(self, vlan_number, state):
        pass

    @not_implemented
    def set_vlan_unicast_rpf_mode(self, vlan_number, mode):
        pass

    @not_implemented
    def unset_vlan_unicast_rpf_mode(self, vlan_number):
        pass

    @not_implemented
    def get_versions(self):
        pass

    @not_implemented
    def set_interface_mtu(self, interface_id, size):
        pass

    @not_implemented
    def unset_interface_mtu(self, interface_id):
        pass

    @not_implemented
    def set_bond_mtu(self, number, size):
        pass

    @not_implemented
    def unset_bond_mtu(self, number):
        pass

    @not_implemented
    def set_vlan_ntp_state(self, vlan_number, state):
        pass

    @not_implemented
    def add_vlan_varp_ip(self, vlan_number, ip_network):
        pass

    @not_implemented
    def remove_vlan_varp_ip(self, vlan_number, ip_network):
        pass

    @not_implemented
    def set_vlan_load_interval(self, vlan_number, time_interval):
        pass

    @not_implemented
    def unset_vlan_load_interval(self, vlan_number):
        pass

    @not_implemented
    def set_vlan_mpls_ip_state(self, vlan_number, state):
        pass

    @not_implemented
    def get_mac_addresses(self):
        pass


class SwitchBase(SwitchOperations):
    def __init__(self, switch_descriptor):
        self.switch_descriptor = switch_descriptor
        self.logger = logging.getLogger("{module}.{hostname}".format(module=self.__module__, hostname=self.switch_descriptor.hostname))
        self.connected = False
        self.in_transaction = False

    def connect(self):
        self._connect()
        self.connected = True

    def disconnect(self):
        self._disconnect()
        self.connected = False

    def start_transaction(self):
        self._start_transaction()
        self.in_transaction = True

    def end_transaction(self):
        self._end_transaction()
        self.in_transaction = False

    def _connect(self):
        """
        Adpapters should implement this rather than connect
        """
        raise NotImplementedError()

    def _disconnect(self):
        """
        Adpapters should implement this rather than disconnect
        """
        raise NotImplementedError()

    def _start_transaction(self):
        """
        Adpapters should implement this rather than connect
        """
        raise NotImplementedError()

    def _end_transaction(self):
        """
        Adpapters should implement this rather than disconnect
        """
        raise NotImplementedError()

    @contextmanager
    def transaction(self):
        self.start_transaction()
        try:
            yield self
            self.commit_transaction()
        except Exception as e:
            if self.logger:
                self.logger.exception(e)
            self.rollback_transaction()
            raise
        finally:
            self.end_transaction()
