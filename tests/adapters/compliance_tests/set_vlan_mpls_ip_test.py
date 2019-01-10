# Copyright 2019 Internap.
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

from netman.core.objects.exceptions import UnknownVlan, BadMplsIpState
from tests import has_message
from tests.adapters.compliance_test_case import ComplianceTestCase


class SetVlanMplsIpTest(ComplianceTestCase):
    _dev_sample = "arista_http"

    def test_sets_mpls_ip_state_false_for_the_vlan(self):
        self.client.add_vlan(1000)

        self.client.set_vlan_mpls_ip_state(1000, False)

        vlan = self.client.get_vlan(1000)
        assert_that(vlan.mpls_ip, is_(False))

    def test_fails_if_the_value_is_not_a_boolean(self):
        self.client.add_vlan(1000)

        with self.assertRaises(BadMplsIpState) as expect:
            self.client.set_vlan_mpls_ip_state(1000, 30)

        assert_that(expect.exception, has_message('MPLS IP state is invalid : 30'))

    def test_fails_if_the_vlan_does_not_exist(self):
        with self.assertRaises(UnknownVlan) as expect:
            self.client.set_vlan_mpls_ip_state(1000, False)

        assert_that(expect.exception, has_message("Vlan 1000 not found"))

    def tearDown(self):
        self.janitor.remove_vlan(1000)
        super(SetVlanMplsIpTest, self).tearDown()
