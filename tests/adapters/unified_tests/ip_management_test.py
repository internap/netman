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

from hamcrest import equal_to, assert_that, has_length

from tests.adapters.unified_tests.configured_test_case import ConfiguredTestCase, skip_on_switches


class IpManagementTest(ConfiguredTestCase):
    __test__ = False

    @skip_on_switches("juniper", "juniper_qfx_copper", "dell", "dell_telnet")
    def test_adding_and_removing_ip_basic(self):
        self.post("/switches/{switch}/vlans", data={"number": 2345})

        self.post("/switches/{switch}/vlans/2345/ips", data={"address": "2.2.2.2", "mask": "24"})
        self.post("/switches/{switch}/vlans/2345/ips", data={"address": "1.1.1.1", "mask": "24"})
        self.post("/switches/{switch}/vlans/2345/ips", data={"address": "1.1.1.2", "mask": "24"})
        self.post("/switches/{switch}/vlans/2345/ips", data={"address": "1.1.1.3", "mask": "24"})
        self.post("/switches/{switch}/vlans/2345/ips", data={"address": "1.1.1.4", "mask": "24"})

        vlans = self.get("/switches/{switch}/vlans")
        vlan2345 = next(vlan for vlan in vlans if vlan["number"] == 2345)

        assert_that(vlan2345["ips"], has_length(5))
        assert_that(vlan2345["ips"][0], equal_to({"address": "1.1.1.1", "mask": 24}))
        assert_that(vlan2345["ips"][1], equal_to({"address": "1.1.1.2", "mask": 24}))
        assert_that(vlan2345["ips"][2], equal_to({"address": "1.1.1.3", "mask": 24}))
        assert_that(vlan2345["ips"][3], equal_to({"address": "1.1.1.4", "mask": 24}))
        assert_that(vlan2345["ips"][4], equal_to({"address": "2.2.2.2", "mask": 24}))

        self.delete("/switches/{switch}/vlans/2345/ips/1.1.1.1/24")
        self.delete("/switches/{switch}/vlans/2345/ips/1.1.1.3/24")

        vlans = self.get("/switches/{switch}/vlans")
        vlan2345 = next(vlan for vlan in vlans if vlan["number"] == 2345)

        assert_that(vlan2345["ips"], has_length(3))
        assert_that(vlan2345["ips"][0], equal_to({"address": "1.1.1.2", "mask": 24}))
        assert_that(vlan2345["ips"][1], equal_to({"address": "1.1.1.4", "mask": 24}))
        assert_that(vlan2345["ips"][2], equal_to({"address": "2.2.2.2", "mask": 24}))

        self.delete("/switches/{switch}/vlans/2345")

    @skip_on_switches("juniper", "juniper_qfx_copper", "dell", "dell_telnet")
    def test_adding_unavailable_ips_and_various_errors(self):
        self.post("/switches/{switch}/vlans", data={"number": 2345})

        self.post("/switches/{switch}/vlans/2345/ips", data={"address": "1.1.1.1", "mask": "24"})

        response = self.post("/switches/{switch}/vlans/3333/ips", data={"address": "1.1.1.1", "mask": "24"}, fail_on_bad_code=False)
        assert_that(response.status_code, equal_to(404)) #vlan not found

        response = self.post("/switches/{switch}/vlans/2345/ips", data={"address": "1.1.1.1", "mask": "24"}, fail_on_bad_code=False)
        assert_that(response.status_code, equal_to(409))

        self.post("/switches/{switch}/vlans", data={"number": 2999})
        response = self.post("/switches/{switch}/vlans/2999/ips", data={"address": "1.1.1.1", "mask": "24"}, fail_on_bad_code=False)
        assert_that(response.status_code, equal_to(409))

        response = self.post("/switches/{switch}/vlans/2999/ips", data={"address": "1.1.1.2", "mask": "24"}, fail_on_bad_code=False)
        assert_that(response.status_code, equal_to(409))
        self.delete("/switches/{switch}/vlans/2999")

        response = self.delete("/switches/{switch}/vlans/1111/ips/1.1.1.1/24", fail_on_bad_code=False)
        assert_that(response.status_code, equal_to(404)) #vlan not found

        response = self.delete("/switches/{switch}/vlans/2345/ips/2.2.2.2/24", fail_on_bad_code=False)
        assert_that(response.status_code, equal_to(404)) #ip not found

        response = self.delete("/switches/{switch}/vlans/2345/ips/1.1.1.1/30", fail_on_bad_code=False)
        assert_that(response.status_code, equal_to(404)) #ip not found

        self.delete("/switches/{switch}/vlans/2345")

    @skip_on_switches("juniper", "juniper_qfx_copper", "dell", "dell_telnet")
    def test_handling_access_groups(self):
        self.post("/switches/{switch}/vlans", data={"number": 2345})

        self.put("/switches/{switch}/vlans/2345/access-groups/in", raw_data="my-group")
        self.put("/switches/{switch}/vlans/2345/access-groups/out", raw_data="your-group")

        vlans = self.get("/switches/{switch}/vlans")
        vlan2345 = next(vlan for vlan in vlans if vlan["number"] == 2345)

        assert_that(vlan2345["access_groups"]["in"], equal_to("my-group"))
        assert_that(vlan2345["access_groups"]["out"], equal_to("your-group"))


        self.delete("/switches/{switch}/vlans/2345/access-groups/in")
        self.delete("/switches/{switch}/vlans/2345/access-groups/out")

        vlans = self.get("/switches/{switch}/vlans")
        vlan2345 = next(vlan for vlan in vlans if vlan["number"] == 2345)

        assert_that(vlan2345["access_groups"]["in"], equal_to(None))
        assert_that(vlan2345["access_groups"]["out"], equal_to(None))

        self.delete("/switches/{switch}/vlans/2345")


# all covered cases

# add an ip
# add a second ip
# add the same ip - error
# add the same ip, different subnet - error
# add ip in the same subnet as another ip in the same port
# add the same ip in the same subnet as another ip in the same port - error
# add ip belonging to another port - error
# add ip with a different subnet belonging to another port - error
# add ip in a subnet belonging to another port - error

# remove ip
# remove secondary ip
# remove ip with secondaries
