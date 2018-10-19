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
from netman.core.objects.interface_states import OFF, ON
from tests.adapters.configured_test_case import ConfiguredTestCase, skip_on_switches


class InterfaceManagementTest(ConfiguredTestCase):
    __test__ = False

    @skip_on_switches("juniper", "juniper_qfx_copper", "juniper_mx", "arista")
    def test_set_interface_state_off(self):
        self.client.set_interface_state(self.test_port, OFF)

    @skip_on_switches("juniper", "juniper_qfx_copper", "juniper_mx", "arista")
    def test_set_interface_state_on(self):
        self.client.set_interface_state(self.test_port, ON)

    @skip_on_switches("cisco", "brocade", "brocade_telnet", "juniper_mx", "arista")
    def test_edit_spanning_tree(self):
        self.client.edit_interface_spanning_tree(self.test_port, edge=True)

    @skip_on_switches("cisco", "brocade", "brocade_telnet", "juniper_mx", "arista")
    def test_set_interface_lldp_state(self):
        self.client.set_interface_lldp_state(self.test_port, enabled=True)

    @skip_on_switches("cisco", "brocade", "brocade_telnet", "juniper_mx", "arista")
    def test_disable_lldp(self):
        self.client.set_interface_lldp_state(self.test_port, enabled=False)
