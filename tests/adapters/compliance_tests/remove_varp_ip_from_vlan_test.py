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
from netaddr import IPNetwork

from netman.core.objects.exceptions import VarpDoesNotExistForVlan
from tests.adapters.compliance_test_case import ComplianceTestCase


class RemoveVarpIpFromVlanTest(ComplianceTestCase):
    _dev_sample = "arista_http"

    def setUp(self):
        super(RemoveVarpIpFromVlanTest, self).setUp()
        self.client.add_vlan(1000, name="vlan_name")
        self.client.add_vlan_varp_ip(1000, IPNetwork("10.10.40.2/29"))
        self.client.add_vlan_varp_ip(1000, IPNetwork("10.10.30.2/29"))
        self.client.get_vlans()

    def tearDown(self):
        self.janitor.remove_vlan(1000)
        super(RemoveVarpIpFromVlanTest, self).tearDown()

    def test_removes_a_varp_ip(self):
        self.client.remove_vlan_varp_ip(1000, IPNetwork("10.10.40.2/29"))

        assert_that(self.client.get_vlan(1000).varp_ips, is_([IPNetwork("10.10.30.2/29")]))

    def test_raises_if_ip_is_not_on_current_vlan(self):
        with self.assertRaises(VarpDoesNotExistForVlan):
            self.client.remove_vlan_varp_ip(1000, IPNetwork("1.2.3.4/29"))
