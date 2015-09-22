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

from hamcrest import assert_that, has_item, has_entry, has_key, is_not

from tests.adapters.unified_tests.configured_test_case import ConfiguredTestCase, skip_on_switches


class BondManagementTest(ConfiguredTestCase):
    __test__ = False

    @skip_on_switches("cisco", "brocade", "dell", "dell_telnet")
    def test_creating_deleting_a_bond(self):
        self.post("/switches/{switch}/bonds", data={"number": 3})

        list_of_bonds = self.get("/switches/{switch}/bonds")
        assert_that(list_of_bonds, has_item(has_entry('number', 3)))

        bond = self.get("/switches/{switch}/bonds/3")
        assert_that(bond, has_entry('number', 3))
        assert_that(bond, has_key('interface'))

        self.delete("/switches/{switch}/bonds/3")

        new_list_of_bonds = self.get("/switches/{switch}/bonds")
        assert_that(new_list_of_bonds, is_not(has_item(has_entry('number', 3))))

        with self.assertRaises(AssertionError):
            self.get("/switches/{switch}/bonds/3")
