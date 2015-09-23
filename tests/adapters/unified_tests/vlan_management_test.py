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

from hamcrest import equal_to, assert_that, has_length, is_, none

from tests.adapters.unified_tests.configured_test_case import ConfiguredTestCase, skip_on_switches


class VlanManagementTest(ConfiguredTestCase):
    __test__ = False

    def test_adding_and_removing_a_vlan(self):
        self.post("/switches/{switch}/vlans", data={"number": 2999, "name": "my-test-vlan"})

        vlan = self.get_vlan(2999)
        assert_that(vlan["name"], equal_to('my-test-vlan'))
        assert_that(len(vlan["ips"]), equal_to(0))

        self.delete("/switches/{switch}/vlans/2999")

        response = self.get("/switches/{switch}/vlans")
        vlan = next((vlan for vlan in response if vlan["number"] == 2999), None)
        assert_that(vlan is None)

    def test_setting_a_vlan_on_an_interface(self):
        self.post("/switches/{switch}/vlans", data={"number": 2999, "name": "my-test-vlan"})

        self.put("/switches/{switch}/interfaces/{port}/port-mode", raw_data="access")

        self.put("/switches/{switch}/interfaces/{port}/access-vlan", raw_data="2999")

        self.delete("/switches/{switch}/interfaces/{port}/access-vlan")

        self.delete("/switches/{switch}/vlans/2999")

    def test_port_mode_trunk(self):
        self.post("/switches/{switch}/vlans", data={"number": 2999, "name": "my-test-vlan"})

        self.put("/switches/{switch}/interfaces/{port}/port-mode", raw_data='trunk')

        self.delete("/switches/{switch}/vlans/2999")

    def test_port_mode_access(self):
        self.post("/switches/{switch}/vlans", data={"number": 2999, "name": "my-test-vlan"})

        self.put("/switches/{switch}/interfaces/{port}/port-mode", raw_data='access')

        self.delete("/switches/{switch}/vlans/2999")

    def test_native_trunk(self):
        self.post("/switches/{switch}/vlans", data={"number": 2999, "name": "my-test-vlan"})

        self.put("/switches/{switch}/interfaces/{port}/port-mode", raw_data='trunk')

        self.put("/switches/{switch}/interfaces/{port}/trunk-native-vlan", raw_data='2999')

        self.delete("/switches/{switch}/interfaces/{port}/trunk-native-vlan")

        self.put("/switches/{switch}/interfaces/{port}/port-mode", raw_data='access')

        self.delete("/switches/{switch}/vlans/2999")

    def test_passing_from_trunk_mode_to_access_gets_rid_of_stuff_in_trunk_mode(self):
        self.post("/switches/{switch}/vlans", data={"number": 1100})
        self.post("/switches/{switch}/vlans", data={"number": 1200})
        self.post("/switches/{switch}/vlans", data={"number": 1300})
        self.post("/switches/{switch}/vlans", data={"number": 1400})

        self.put("/switches/{switch}/interfaces/{port}/port-mode", raw_data='trunk')
        self.put("/switches/{switch}/interfaces/{port}/trunk-native-vlan", raw_data='1200')
        self.post("/switches/{switch}/interfaces/{port}/trunk-vlans", raw_data='1100')
        self.post("/switches/{switch}/interfaces/{port}/trunk-vlans", raw_data='1300')
        self.post("/switches/{switch}/interfaces/{port}/trunk-vlans", raw_data='1400')

        interfaces = self.get("/switches/{switch}/interfaces")
        test_if = next(i for i in interfaces if i["name"] == self.test_port)

        assert_that(test_if["port_mode"], equal_to('trunk'))
        assert_that(test_if["trunk_native_vlan"], equal_to(1200))
        assert_that(test_if["access_vlan"], equal_to(None))
        assert_that(test_if["trunk_vlans"], equal_to([1100, 1300, 1400]))

        self.put("/switches/{switch}/interfaces/{port}/port-mode", raw_data='access')

        interfaces = self.get("/switches/{switch}/interfaces")
        test_if = next(i for i in interfaces if i["name"] == self.test_port)

        assert_that(test_if["port_mode"], equal_to('access'))
        assert_that(test_if["trunk_native_vlan"], equal_to(None))
        assert_that(test_if["access_vlan"], equal_to(None))
        assert_that(test_if["trunk_vlans"], has_length(0))

        self.delete("/switches/{switch}/vlans/1100")
        self.delete("/switches/{switch}/vlans/1200")
        self.delete("/switches/{switch}/vlans/1300")
        self.delete("/switches/{switch}/vlans/1400")

    def test_invalid_vlan_parameter_fails(self):
        response = self.delete("/switches/{switch}/vlans/2999", fail_on_bad_code=False)
        assert_that(response.status_code, equal_to(404))

        response = self.put("/switches/{switch}/interfaces/{port}/access-vlan", raw_data="2999", fail_on_bad_code=False)
        assert_that(response.status_code, equal_to(404))

        self.put("/switches/{switch}/interfaces/{port}/port-mode", raw_data='trunk')

        response = self.post("/switches/{switch}/interfaces/{port}/trunk-vlans", raw_data='2999', fail_on_bad_code=False)
        assert_that(response.status_code, equal_to(404))

        response = self.put("/switches/{switch}/interfaces/{port}/trunk-native-vlan", raw_data='2999', fail_on_bad_code=False)
        assert_that(response.status_code, equal_to(404))

        response = self.delete("/switches/{switch}/interfaces/{port}/trunk-vlans/2999", fail_on_bad_code=False)
        assert_that(response.status_code, equal_to(404))

        self.post("/switches/{switch}/vlans", data={"number": 2999, "name": "my-test-vlan"})
        response = self.delete("/switches/{switch}/interfaces/{port}/trunk-vlans/2999", fail_on_bad_code=False)
        assert_that(response.status_code, equal_to(404))
        self.delete("/switches/{switch}/vlans/2999")

        self.put("/switches/{switch}/interfaces/{port}/port-mode", raw_data='access')

    @skip_on_switches("juniper", "juniper_qfx_copper")
    def test_invalid_interface_parameter_fails(self):
        response = self.put("/switches/{switch}/interfaces/42/9999/shutdown", raw_data='true', fail_on_bad_code=False)
        assert_that(response.status_code, equal_to(404))

        response = self.put("/switches/{switch}/interfaces/42/9999/shutdown", raw_data='false', fail_on_bad_code=False)
        assert_that(response.status_code, equal_to(404))

        response = self.put("/switches/{switch}/interfaces/42/9999/port-mode", raw_data='access', fail_on_bad_code=False)
        assert_that(response.status_code, equal_to(404))

        response = self.put("/switches/{switch}/interfaces/42/9999/port-mode", raw_data='trunk', fail_on_bad_code=False)
        assert_that(response.status_code, equal_to(404))

        response = self.delete("/switches/{switch}/interfaces/42/9999/access-vlan", fail_on_bad_code=False)
        assert_that(response.status_code, equal_to(404))

        response = self.delete("/switches/{switch}/interfaces/42/9999/access-vlan", fail_on_bad_code=False)
        assert_that(response.status_code, equal_to(404))

        response = self.post("/switches/{switch}/interfaces/42/9999/trunk-vlans", data=2999, fail_on_bad_code=False)
        assert_that(response.status_code, equal_to(404))

        self.delete("/switches/{switch}/interfaces/{port}/trunk-native-vlan", fail_on_bad_code=False)
        assert_that(response.status_code, equal_to(404))

        self.post("/switches/{switch}/vlans", data={"number": 2999, "name": "my-test-vlan"})

        response = self.put("/switches/{switch}/interfaces/42/9999/access-vlan", raw_data="2999", fail_on_bad_code=False)
        assert_that(response.status_code, equal_to(404))

        response = self.delete("/switches/{switch}/interfaces/42/9999/trunk-vlans/2999", fail_on_bad_code=False)
        assert_that(response.status_code, equal_to(404))

        response = self.put("/switches/{switch}/interfaces/42/9999/trunk-native-vlan", raw_data='2999', fail_on_bad_code=False)
        assert_that(response.status_code, equal_to(404))

        self.delete("/switches/{switch}/vlans/2999")

    @skip_on_switches("juniper", "juniper_qfx_copper", "dell", "dell_telnet")
    def test_vrf_management(self):

        self.post("/switches/{switch}/vlans", data={"number": 2999, "name": "my-test-vlan"})

        self.put("/switches/{switch}/vlans/2999/vrf-forwarding", raw_data='DEFAULT-LAN')

        vlan = self.get_vlan(2999)
        assert_that(vlan["vrf_forwarding"], is_('DEFAULT-LAN'))

        self.delete("/switches/{switch}/vlans/2999/vrf-forwarding")

        vlan = self.get_vlan(2999)
        assert_that(vlan["vrf_forwarding"], is_(none()))

        self.delete("/switches/{switch}/vlans/2999")
