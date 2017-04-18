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
from netaddr import IPNetwork, IPAddress

from netman.core.objects.access_groups import IN, OUT
from netman.core.objects.exceptions import UnknownVlan
from tests import has_message
from tests.adapters.compliance_test_case import ComplianceTestCase


class GetVlanTest(ComplianceTestCase):
    _dev_sample = "cisco"

    def test_returns_a_vlan_with_all_available_data(self):
        self.client.add_vlan(1000, name="vlan_name")

        self.try_to.set_vlan_vrf(1000, "DEFAULT-LAN")
        self.try_to.add_ip_to_vlan(1000, IPNetwork("10.10.10.2/29"))
        self.try_to.set_vlan_access_group(1000, IN, "ACL-IN")
        self.try_to.set_vlan_access_group(1000, OUT, "ACL-OUT")
        self.try_to.add_vrrp_group(1000, 1,
                                   ips=[IPAddress("10.10.10.1")], priority=110, hello_interval=10,
                                   dead_interval=11, track_id=self.test_vrrp_track_id, track_decrement=50)
        self.try_to.add_dhcp_relay_server(1000, IPAddress("11.11.11.1"))
        self.try_to.set_vlan_icmp_redirects_state(1000, False)

        assert_that(self.client.get_vlan(1000), is_(self.get_vlan_from_list(1000)))

    def test_fails_when_the_vlan_does_not_exist(self):
        with self.assertRaises(UnknownVlan) as expect:
            self.client.get_vlan(2000)

        assert_that(expect.exception, has_message("Vlan 2000 not found"))

    def tearDown(self):
        self.janitor.remove_vlan(1000)
        super(GetVlanTest, self).tearDown()
