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
from netman.core.objects.access_groups import IN, OUT
from netman.core.objects.exceptions import BadVlanNumber, BadVlanName, \
    BondAlreadyExist, BadBondNumber
from netman.core.objects.port_modes import DYNAMIC

from tests.adapters.configured_test_case import ConfiguredTestCase


class AddBondTest(ConfiguredTestCase):
    _dev_sample = "cisco"

    def test_creates_an_empty_bond(self):
        self.client.add_bond(10)

        bonds = self.client.get_bonds()
        assert_that(bonds, has_item(has_properties(number=10)))

        bond = next((b for b in bonds if b.number == 10))
        assert_that(bond.number, is_(10))
        assert_that(bond.members, is_([]))
        assert_that(bond.link_speed, is_(None))
        assert_that(bond.shutdown, is_(False))
        assert_that(bond.port_mode, is_(DYNAMIC))
        assert_that(bond.access_vlan, is_(None))
        assert_that(bond.trunk_native_vlan, is_(None))
        assert_that(bond.trunk_vlans, is_([]))

    def test_fails_if_the_bond_already_exist(self):
        self.client.add_bond(10)

        with self.assertRaises(BondAlreadyExist):
            self.client.add_bond(10)

    def tearDown(self):
        self.janitor.remove_bond(10)
        super(AddBondTest, self).tearDown()


