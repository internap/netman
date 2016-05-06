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

from hamcrest import assert_that, is_
from netman.core.objects.exceptions import UnknownVlan
from tests import has_message
from tests.adapters.compliance_test_case import ComplianceTestCase


class SetVlanIcmpRedirectsStateTest(ComplianceTestCase):
    _dev_sample = "cisco"

    def setUp(self):
        super(SetVlanIcmpRedirectsStateTest, self).setUp()
        self.client.add_vlan(1000)

    def test_enables_icmp_redirects_when_given_true(self):
        self.client.set_vlan_icmp_redirects_state(1000, True)
        vlan = self.get_vlan_from_list(1000)
        assert_that(vlan.number, is_(1000))
        assert_that(vlan.icmp_redirects, is_(True))

    def test_disables_icmp_redirects_when_given_false(self):
        self.client.set_vlan_icmp_redirects_state(1000, False)
        vlan = self.get_vlan_from_list(1000)
        assert_that(vlan.number, is_(1000))
        assert_that(vlan.icmp_redirects, is_(False))

    def test_raises_UnknownVlan_when_operating_on_a_vlan_that_does_not_exist(self):
        with self.assertRaises(UnknownVlan) as expect:
            self.client.set_vlan_icmp_redirects_state(2000, False)

        assert_that(expect.exception, has_message("Vlan 2000 not found"))

    def tearDown(self):
        self.janitor.remove_vlan(1000)
        super(SetVlanIcmpRedirectsStateTest, self).tearDown()
