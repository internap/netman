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

from contextlib import contextmanager
import logging


class SwitchOperations(object):

    def connect(self):
        raise NotImplementedError()

    def disconnect(self):
        raise NotImplementedError()

    def transaction(self):
        raise NotImplementedError()

    def start_transaction(self):
        raise NotImplementedError()

    def commit_transaction(self):
        raise NotImplementedError()

    def rollback_transaction(self):
        raise NotImplementedError()

    def end_transaction(self):
        raise NotImplementedError()

    def get_vlans(self):
        raise NotImplementedError()

    def add_vlan(self, number, name=None):
        raise NotImplementedError()

    def remove_vlan(self, number):
        raise NotImplementedError()

    def get_interfaces(self):
        raise NotImplementedError()

    def set_access_vlan(self, interface_id, vlan):
        raise NotImplementedError()

    def remove_access_vlan(self, interface_id):
        raise NotImplementedError()

    def set_access_mode(self, interface_id):
        raise NotImplementedError()

    def set_trunk_mode(self, interface_id):
        raise NotImplementedError()

    def add_trunk_vlan(self, interface_id, vlan):
        raise NotImplementedError()

    def remove_trunk_vlan(self, interface_id, vlan):
        raise NotImplementedError()

    def shutdown_interface(self, interface_id):
        raise NotImplementedError()

    def openup_interface(self, interface_id):
        raise NotImplementedError()

    def configure_native_vlan(self, interface_id, vlan):
        raise NotImplementedError()

    def remove_native_vlan(self, interface_id):
        raise NotImplementedError()

    def add_ip_to_vlan(self, vlan_number, ip_network):
        raise NotImplementedError()

    def remove_ip_from_vlan(self, vlan_number, ip_network):
        raise NotImplementedError()

    def set_vlan_access_group(self, vlan_number, direction, name):
        raise NotImplementedError()

    def remove_vlan_access_group(self, vlan_number, direction):
        raise NotImplementedError()

    def set_vlan_vrf(self, vlan_number, vrf_name):
        raise NotImplementedError()

    def remove_vlan_vrf(self, vlan_number):
        raise NotImplementedError()

    def set_interface_description(self, interface_id, description):
        raise NotImplementedError()

    def remove_interface_description(self, interface_id):
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

    def remove_bond_description(self, number):
        raise NotImplementedError()

    def set_bond_trunk_mode(self, number):
        raise NotImplementedError()

    def set_bond_access_mode(self, number):
        raise NotImplementedError()

    def add_bond_trunk_vlan(self, number, vlan):
        raise NotImplementedError()

    def remove_bond_trunk_vlan(self, number, vlan):
        raise NotImplementedError()

    def configure_bond_native_vlan(self, number, vlan):
        raise NotImplementedError()

    def remove_bond_native_vlan(self, number):
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

    def enable_lldp(self, interface_id, enabled):
        raise NotImplementedError()


class SwitchBase(SwitchOperations):
    def __init__(self, switch_descriptor):
        self.switch_descriptor = switch_descriptor
        self.logger = logging.getLogger("{module}.{hostname}".format(module=self.__module__, hostname=self.switch_descriptor.hostname))

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
