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

from hamcrest import assert_that, is_, none, empty
from netman.core.objects.access_groups import IN, OUT
from netman.core.objects.exceptions import BadVlanNumber, BadVlanName, VlanAlreadyExist

from tests.adapters.configured_test_case import ConfiguredTestCase


class AddVlanTest(ConfiguredTestCase):
    _dev_sample = "juniper_qfx_copper"

    def test_creates_an_empty_vlan(self):
        self.client.add_vlan(1000)

        vlan = self.get_vlan_from_list(1000)
        assert_that(vlan.number, is_(1000))
        assert_that(vlan.name, is_(none()))
        assert_that(vlan.access_groups[IN], is_(none()))
        assert_that(vlan.access_groups[OUT], is_(none()))
        assert_that(vlan.vrf_forwarding, is_(none()))
        assert_that(vlan.ips, is_(empty()))
        assert_that(vlan.vrrp_groups, is_(empty()))
        assert_that(vlan.dhcp_relay_servers, is_(empty()))

    def test_sets_the_name_when_given(self):
        self.client.add_vlan(1000, name="Hey")

        vlan = self.get_vlan_from_list(1000)
        assert_that(vlan.name, is_("Hey"))

    def test_fails_if_the_vlan_already_exist(self):
        self.client.add_vlan(1000)

        with self.assertRaises(VlanAlreadyExist):
            self.client.add_vlan(1000)

    def test_fails_with_a_wrong_number(self):
        with self.assertRaises(BadVlanNumber):
            self.client.add_vlan(9001)

    def test_fails_with_a_wrong_name(self):
        with self.assertRaises(BadVlanName):
            self.client.add_vlan(1000, name="A space isn't good")

    def tearDown(self):
        self.janitor.remove_vlan(1000)
        super(AddVlanTest, self).tearDown()


