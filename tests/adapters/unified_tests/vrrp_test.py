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

from hamcrest import assert_that, is_, none, is_not
from netaddr import IPNetwork, IPAddress

from tests.adapters.configured_test_case import ConfiguredTestCase, skip_on_switches


class VrrpTest(ConfiguredTestCase):
    __test__ = False

    @skip_on_switches("juniper", "juniper_qfx_copper", "dell", "dell_telnet", "dell10g", "dell10g_telnet", "juniper_mx", "arista")
    def test_add_and_get_group(self):
        try:
            self.client.add_vlan(2999, name="my-test-vlan")
            self.client.add_ip_to_vlan(2999, IPNetwork("10.10.0.3/27"))

            self.client.add_vrrp_group(
                vlan_number=2999,
                group_id=73,
                ips=[IPAddress("10.10.0.1"), IPAddress("10.10.0.2")],
                priority=110,
                track_id=self.test_vrrp_track_id,
                track_decrement=50,
                hello_interval=5,
                dead_interval=15
            )

            vlan = self.get_vlan_from_list(2999)
            vrrp_group = next((g for g in vlan.vrrp_groups if g.id == 73), None)

            assert_that(vrrp_group, is_not(None))

            assert_that([str(ip) for ip in vrrp_group.ips], is_(["10.10.0.1", "10.10.0.2"]))
            assert_that(vrrp_group.priority, is_(110))
            assert_that(vrrp_group.track_id, is_(self.test_vrrp_track_id))
            assert_that(vrrp_group.track_decrement, is_(50))
            assert_that(vrrp_group.hello_interval, is_(5))
            assert_that(vrrp_group.dead_interval, is_(15))

            self.client.remove_vrrp_group(vlan_number=2999, group_id=73)

            vlan = self.get_vlan_from_list(2999)
            vrrp_group = next((g for g in vlan.vrrp_groups if g.id == 73), None)
            assert_that(vrrp_group, is_(none()))

        finally:
            self.client.remove_vlan(2999)
