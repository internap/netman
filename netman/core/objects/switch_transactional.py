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
from functools import wraps
import logging

from .switch_base import SwitchOperations


def transactional(fn):
    @wraps(fn)
    def wrapper(self, *args, **kwargs):
        if self.in_transaction:
            return fn(self, *args, **kwargs)
        else:
            with self.transaction():
                return fn(self, *args, **kwargs)

    return wrapper


class SwitchTransactional(SwitchOperations):
    def __init__(self, impl, lock):
        self.impl = impl
        self.lock = lock
        self.logger = logging.getLogger("{module}.{hostname}".format(
            module=self.impl.__module__,
            hostname=self.switch_descriptor.hostname))
        self.in_transaction = False

    @property
    def switch_descriptor(self):
        return self.impl.switch_descriptor

    @contextmanager
    def transaction(self):
        self.start_transaction()
        try:
            yield self
            self.commit_transaction()
        except Exception as e:
            self.logger.exception(e)
            self.rollback_transaction()
            raise
        finally:
            self.end_transaction()

    def start_transaction(self):
        self.logger.info('Acquiring lock')
        self.lock.acquire()
        self.in_transaction = True
        try:
            self.impl.start_transaction()
        except Exception as e:
            self.logger.exception(e)
            self.in_transaction = False
            self.lock.release()
            self.logger.info('Lock released')
            raise

    def commit_transaction(self):
        self.impl.commit_transaction()

    def rollback_transaction(self):
        self.impl.rollback_transaction()

    def end_transaction(self):
        try:
            self.impl.end_transaction()
        finally:
            self.in_transaction = False
            self.lock.release()
            self.logger.info('Lock released')

    def connect(self):
        self.impl.connect()

    def disconnect(self):
        self.impl.disconnect()

    def get_interfaces(self):
        return self.impl.get_interfaces()

    def get_vlans(self):
        return self.impl.get_vlans()

    def get_bond(self, bond_number):
        return self.impl.get_bond(bond_number)

    def get_bonds(self):
        return self.impl.get_bonds()

    @transactional
    def add_bond_trunk_vlan(self, bond_number, vlan):
        self.impl.add_bond_trunk_vlan(bond_number, vlan)

    @transactional
    def remove_bond_trunk_vlan(self, bond_number, vlan):
        self.impl.remove_bond_trunk_vlan(bond_number, vlan)

    @transactional
    def configure_bond_native_vlan(self, bond_number, vlan):
        self.impl.configure_bond_native_vlan(bond_number, vlan)

    @transactional
    def remove_bond_native_vlan(self, bond_number):
        self.impl.remove_bond_native_vlan(bond_number)

    @transactional
    def set_vlan_vrf(self, vlan_number, vrf_name):
        self.impl.set_vlan_vrf(vlan_number, vrf_name)

    @transactional
    def remove_vlan_vrf(self, vlan_number):
        self.impl.remove_vlan_vrf(vlan_number)

    @transactional
    def add_ip_to_vlan(self, vlan_number, ip_network):
        self.impl.add_ip_to_vlan(vlan_number, ip_network)

    @transactional
    def remove_ip_from_vlan(self, vlan_number, ip_network):
        self.impl.remove_ip_from_vlan(vlan_number, ip_network)

    @transactional
    def set_interface_description(self, interface_id, description):
        self.impl.set_interface_description(interface_id, description)

    @transactional
    def remove_interface_description(self, interface_id):
        self.impl.remove_interface_description(interface_id)

    @transactional
    def edit_interface_spanning_tree(self, interface_id, edge=None):
        self.impl.edit_interface_spanning_tree(interface_id, edge=edge)

    @transactional
    def openup_interface(self, interface_id):
        self.impl.openup_interface(interface_id)

    @transactional
    def shutdown_interface(self, interface_id):
        self.impl.shutdown_interface(interface_id)

    @transactional
    def configure_native_vlan(self, interface_id, vlan):
        self.impl.configure_native_vlan(interface_id, vlan)

    @transactional
    def remove_native_vlan(self, interface_id):
        self.impl.remove_native_vlan(interface_id)

    @transactional
    def set_access_vlan(self, interface_id, vlan):
        self.impl.set_access_vlan(interface_id, vlan)

    @transactional
    def remove_access_vlan(self, interface_id):
        self.impl.remove_access_vlan(interface_id)

    @transactional
    def remove_vlan_access_group(self, vlan_number, direction):
        self.impl.remove_vlan_access_group(vlan_number, direction)

    @transactional
    def set_vlan_access_group(self, vlan_number, direction, name):
        self.impl.set_vlan_access_group(vlan_number, direction, name)

    @transactional
    def add_interface_to_bond(self, interface, bond_number):
        self.impl.add_interface_to_bond(interface, bond_number)

    @transactional
    def remove_interface_from_bond(self, interface):
        self.impl.remove_interface_from_bond(interface)

    @transactional
    def add_vlan(self, number, name=None):
        self.impl.add_vlan(number, name)

    @transactional
    def remove_vlan(self, number):
        self.impl.remove_vlan(number)

    @transactional
    def set_access_mode(self, interface_id):
        self.impl.set_access_mode(interface_id)

    @transactional
    def set_trunk_mode(self, interface_id):
        self.impl.set_trunk_mode(interface_id)

    @transactional
    def add_trunk_vlan(self, interface_id, vlan):
        self.impl.add_trunk_vlan(interface_id, vlan)

    @transactional
    def remove_trunk_vlan(self, interface_id, vlan):
        self.impl.remove_trunk_vlan(interface_id, vlan)

    @transactional
    def set_bond_description(self, bond_number, description):
        self.impl.set_bond_description(bond_number, description)

    @transactional
    def remove_bond_description(self, bond_number):
        self.impl.remove_bond_description(bond_number)

    @transactional
    def set_bond_link_speed(self, number, speed):
        self.impl.set_bond_link_speed(number, speed)

    @transactional
    def add_bond(self, number):
        self.impl.add_bond(number)

    @transactional
    def remove_bond(self, number):
        self.impl.remove_bond(number)

    @transactional
    def set_bond_access_mode(self, bond_number):
        self.impl.set_bond_access_mode(bond_number)

    @transactional
    def set_bond_trunk_mode(self, bond_number):
        self.impl.set_bond_trunk_mode(bond_number)

    @transactional
    def edit_bond_spanning_tree(self, number, edge=None):
        self.impl.edit_bond_spanning_tree(number, edge=edge)

    @transactional
    def add_vrrp_group(self, *args, **kwargs):
        self.impl.add_vrrp_group(*args, **kwargs)

    @transactional
    def remove_vrrp_group(self, *args, **kwargs):
        self.impl.remove_vrrp_group(*args, **kwargs)

    @transactional
    def add_dhcp_relay_server(self, vlan_number, ip_address):
        self.impl.add_dhcp_relay_server(vlan_number, ip_address)

    @transactional
    def remove_dhcp_relay_server(self, vlan_number, ip_address):
        self.impl.remove_dhcp_relay_server(vlan_number, ip_address)

    @transactional
    def enable_lldp(self, interface_id, enabled):
        self.impl.enable_lldp(interface_id, enabled)
