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

from netman.core.objects.exceptions import VarpAlreadyExistsForVlan
from tests.adapters.compliance_test_case import ComplianceTestCase


class AddVarpIpToVlanTest(ComplianceTestCase):
    _dev_sample = "arista_http"

    def setUp(self):
        super(AddVarpIpToVlanTest, self).setUp()
        self.client.add_vlan(1000, name="vlan_name")

    def tearDown(self):
        self.janitor.remove_vlan(1000)
        super(AddVarpIpToVlanTest, self).tearDown()

    def test_assigns_the_varp_ip(self):
        self.client.add_vlan_varp_ip(1000, IPNetwork("10.10.40.2/29"))
        assert_that(self.client.get_vlan(1000).varp_ips, is_([IPNetwork("10.10.40.2/29")]))

    def test_raises_if_ip_is_already_assigned_to_current_vlan(self):
        self.client.add_vlan_varp_ip(1000, IPNetwork("10.10.10.222/29"))

        with self.assertRaises(VarpAlreadyExistsForVlan):
            self.client.add_vlan_varp_ip(1000, IPNetwork("10.10.10.222/29"))
