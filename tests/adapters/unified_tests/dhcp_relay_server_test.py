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


class DhcpRelayServerTest(ConfiguredTestCase):
    __test__ = False

    @skip_on_switches("juniper", "juniper_qfx_copper", "dell", "dell_telnet")
    def test_add_and_get_and_delete_dhcp_relay_server(self):
        try:
            self.post("/switches/{switch}/vlans", data={"number": 2999, "name": "my-test-vlan"})

            self.post("/switches/{switch}/vlans/2999/dhcp-relay-server", raw_data="10.10.10.1")

            vlan = self.get_vlan(2999)
            dhcp_relay_server = next((g for g in vlan["dhcp_relay_servers"] if g == '10.10.10.1'), None)

            assert_that(dhcp_relay_server, is_not(None))

            self.delete("/switches/{switch}/vlans/2999/dhcp-relay-server/10.10.10.1")

            vlan = self.get_vlan(2999)
            dhcp_relay_server = next((g for g in vlan["dhcp_relay_servers"] if g == '10.10.10.1'), None)
            assert_that(dhcp_relay_server, is_(none()))

        finally:
            self.delete("/switches/{switch}/vlans/2999", fail_on_bad_code=False)
