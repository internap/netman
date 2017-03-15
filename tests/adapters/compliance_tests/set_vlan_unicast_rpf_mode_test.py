# Copyright 2016 Internap.
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
from netman.core.objects.unicast_rpf_modes import STRICT
from tests import has_message
from tests.adapters.compliance_test_case import ComplianceTestCase


class SetVlanUnicastRPFModeTest(ComplianceTestCase):
    _dev_sample = "cisco"

    def setUp(self):
        super(SetVlanUnicastRPFModeTest, self).setUp()
        self.client.add_vlan(1000)

    def test_can_activate_the_strict_unicast_anti_spoofing(self):
        self.client.set_vlan_unicast_rpf_mode(1000, STRICT)

        vlan = self.get_vlan_from_list(1000)

        assert_that(vlan.unicast_rpf_mode, is_(STRICT))

    def test_raises_UnknownVlan_when_operating_on_a_vlan_that_does_not_exist(self):
        with self.assertRaises(UnknownVlan) as expect:
            self.client.set_vlan_unicast_rpf_mode(2000, STRICT)

        assert_that(expect.exception, has_message("Vlan 2000 not found"))

    def tearDown(self):
        self.janitor.remove_vlan(1000)
        super(SetVlanUnicastRPFModeTest, self).tearDown()
