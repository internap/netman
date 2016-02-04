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
from unittest import TestCase

from flexmock import flexmock
from mock import patch, Mock

from netman.core.objects.access_groups import IN
from netman.core.objects.switch_base import SwitchOperations


class BackwardCompatibleSwitchOperationsTest(TestCase):
    def setUp(self):
        self.switch = flexmock(SwitchOperations())
    @patch("netman.core.objects.backward_compatible_switch_operations.warnings.warn", Mock())
    def test_remove_access_vlan_call_unset_access_vlan(self):
        self.switch.should_receive("unset_access_vlan").with_args(1000).once()

        self.switch.remove_access_vlan(1000)

    @patch("netman.core.objects.backward_compatible_switch_operations.warnings.warn", Mock())
    def test_configure_native_vlan_call_set_native_vlan(self):
        self.switch.should_receive("set_native_vlan").with_args("ethernet 1/g10", 1000).once()

        self.switch.configure_native_vlan("ethernet 1/g10", 1000)

    @patch("netman.core.objects.backward_compatible_switch_operations.warnings.warn", Mock())
    def test_remove_native_vlan_call_unset_native_vlan(self):
        self.switch.should_receive("unset_native_vlan").with_args(1000).once()

        self.switch.remove_native_vlan(1000)

    @patch("netman.core.objects.backward_compatible_switch_operations.warnings.warn", Mock())
    def test_remove_vlan_access_group_call_unset_vlan_access_group(self):
        self.switch.should_receive("unset_vlan_access_group").with_args(1000, IN).once()

        self.switch.remove_vlan_access_group(1000, IN)

    @patch("netman.core.objects.backward_compatible_switch_operations.warnings.warn", Mock())
    def test_remove_vlan_vrf_call_unset_vlan_vrf(self):
        self.switch.should_receive("unset_vlan_vrf").with_args(1000).once()

        self.switch.remove_vlan_vrf(1000)

    @patch("netman.core.objects.backward_compatible_switch_operations.warnings.warn", Mock())
    def test_remove_interface_description_call_unset_interface_description(self):
        self.switch.should_receive("unset_interface_description").with_args("ethernet 1/g10").once()

        self.switch.remove_interface_description("ethernet 1/g10")

    @patch("netman.core.objects.backward_compatible_switch_operations.warnings.warn", Mock())
    def test_edit_interface_spanning_tree_state_call_set_interface_spanning_tree_state(self):
        self.switch.should_receive("set_interface_spanning_tree_state").with_args("ethernet 1/g10").once()

        self.switch.edit_interface_spanning_tree("ethernet 1/g10")

    @patch("netman.core.objects.backward_compatible_switch_operations.warnings.warn", Mock())
    def test_remove_bond_description_call_unset_bond_description(self):
        self.switch.should_receive("unset_bond_description").with_args(295).once()

        self.switch.remove_bond_description(295)

    @patch("netman.core.objects.backward_compatible_switch_operations.warnings.warn", Mock())
    def test_configure_bond_native_vlan_call_set_bond_native_vlan(self):
        self.switch.should_receive("set_bond_native_vlan").with_args(295, 1000).once()

        self.switch.configure_bond_native_vlan(295, 1000)

    @patch("netman.core.objects.backward_compatible_switch_operations.warnings.warn", Mock())
    def test_remove_bond_native_vlan_call_unset_bond_native_vlan(self):
        self.switch.should_receive("unset_bond_native_vlan").with_args(295).once()

        self.switch.remove_bond_native_vlan(295)

    @patch("netman.core.objects.backward_compatible_switch_operations.warnings.warn", Mock())
    def test_edit_bond_spanning_tree_call_set_bond_interface_spanning_tree_state(self):
        self.switch.should_receive("set_bond_interface_spanning_tree_state").with_args(295).once()

        self.switch.edit_bond_spanning_tree(295)

    @patch("netman.core.objects.backward_compatible_switch_operations.warnings.warn", Mock())
    def test_enable_lldp_call_set_interface_lldp_state(self):
        self.switch.should_receive("set_interface_lldp_state").with_args("ethernet 1/g10", True).once()

        self.switch.enable_lldp("ethernet 1/g10", True)
