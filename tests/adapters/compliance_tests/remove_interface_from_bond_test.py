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

from hamcrest import assert_that, is_, none, empty, has_item, has_properties
from netman.core.objects.exceptions import UnknownBond

from tests.adapters.configured_test_case import ConfiguredTestCase


class RemoveInterfaceFromBondTest(ConfiguredTestCase):
    _dev_sample = "cisco"

    def test_adding_an_interface_to_a_bond(self):
        # given
        bond_member = self.test_ports[0].name
        self.client.add_bond(9)
        self.client.add_interface_to_bond(bond_member, 9)

        # when
        self.client.remove_interface_from_bond(bond_member)

        # then
        bond = self.client.get_bond(9)
        assert_that(bond.members, is_([]))

        interfaces = self.client.get_interfaces()
        assert_that(interfaces, has_item(has_properties(name=bond_member)))
        interface = next((b for b in interfaces if b.name == bond_member))
        assert_that(interface.bond_master, is_(None))

    def tearDown(self):
        bond_member = self.test_ports[0].name
        self.janitor.remove_interface_from_bond(bond_member)
        self.janitor.remove_bond(9)
        super(RemoveInterfaceFromBondTest, self).tearDown()


