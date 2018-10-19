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

from hamcrest import assert_that, has_item, is_not, has_properties
from netman.core.objects.exceptions import UnknownBond

from tests.adapters.configured_test_case import skip_on_switches, ConfiguredTestCase


class BondManagementTest(ConfiguredTestCase):
    __test__ = False

    @skip_on_switches("cisco", "brocade", "brocade_telnet", "dell", "dell_telnet", "dell10g", "dell10g_telnet", "juniper_mx", "arista")
    def test_creating_deleting_a_bond(self):
        self.client.add_bond(3)

        list_of_bonds = self.client.get_bonds()
        assert_that(list_of_bonds, has_item(has_properties(number=3)))

        bond = self.client.get_bond(3)
        assert_that(bond, has_properties(number=3))

        self.client.remove_bond(3)

        new_list_of_bonds = self.client.get_bonds()
        assert_that(new_list_of_bonds, is_not(has_item(has_properties(number=3))))

        with self.assertRaises(UnknownBond):
            self.client.get_bond(3)
