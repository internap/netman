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

from tests.adapters.unified_tests.configured_test_case import ConfiguredTestCase, skip_on_switches


class VrrpTest(ConfiguredTestCase):
    __test__ = False

    @skip_on_switches("juniper", "juniper_qfx_copper", "dell", "dell_telnet")
    def test_add_and_get_group(self):
        try:
            self.post("/switches/{switch}/vlans", data={"number": 2999, "name": "my-test-vlan"})
            self.post("/switches/{switch}/vlans/2999/ips", data={"address": "10.10.0.3", "mask": 27})

            self.post("/switches/{switch}/vlans/2999/vrrp-groups", data={
                "id": 73,
                "ips": ["10.10.0.1", "10.10.0.2"],
                "priority": 110,
                "track_id": 101,
                "track_decrement": 50,
                "hello_interval": 5,
                "dead_interval": 15
            })

            vlan = self.get_vlan(2999)
            vrrp_group = next((g for g in vlan["vrrp_groups"] if g["id"] == 73), None)

            assert_that(vrrp_group, is_not(None))

            assert_that(vrrp_group["ips"], is_(["10.10.0.1", "10.10.0.2"]))
            assert_that(vrrp_group["priority"], is_(110))
            assert_that(vrrp_group["track_id"], is_("101"))
            assert_that(vrrp_group["track_decrement"], is_(50))
            assert_that(vrrp_group["hello_interval"], is_(5))
            assert_that(vrrp_group["dead_interval"], is_(15))

            self.delete("/switches/{switch}/vlans/2999/vrrp-groups/73")

            vlan = self.get_vlan(2999)
            vrrp_group = next((g for g in vlan["vrrp_groups"] if g["id"] == 73), None)
            assert_that(vrrp_group, is_(none()))

        finally:
            self.delete("/switches/{switch}/vlans/2999", fail_on_bad_code=False)
