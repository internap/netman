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
from netaddr import IPNetwork

from netman.core.objects.access_groups import IN, OUT
from netman.core.objects.exceptions import UnknownVlan, UnknownIP, \
    IPNotAvailable, Conflict

from tests.adapters.configured_test_case import ConfiguredTestCase, skip_on_switches


class IpManagementTest(ConfiguredTestCase):
    __test__ = False

    @skip_on_switches("juniper", "juniper_qfx_copper", "dell", "dell_telnet", "dell10g", "dell10g_telnet")
    def test_adding_and_removing_ip_basic(self):
        self.client.add_vlan(2345)

        self.client.add_ip_to_vlan(2345, ip_network=IPNetwork("2.2.2.2/24"))
        self.client.add_ip_to_vlan(2345, ip_network=IPNetwork("1.1.1.1/24"))
        self.client.add_ip_to_vlan(2345, ip_network=IPNetwork("1.1.1.2/24"))
        self.client.add_ip_to_vlan(2345, ip_network=IPNetwork("1.1.1.3/24"))
        self.client.add_ip_to_vlan(2345, ip_network=IPNetwork("1.1.1.4/24"))

        vlans = self.client.get_vlans()
        vlan2345 = next(vlan for vlan in vlans if vlan.number == 2345)

        assert_that(vlan2345.ips, has_length(5))
        assert_that(str(vlan2345.ips[0]), equal_to("1.1.1.1/24"))
        assert_that(str(vlan2345.ips[1]), equal_to("1.1.1.2/24"))
        assert_that(str(vlan2345.ips[2]), equal_to("1.1.1.3/24"))
        assert_that(str(vlan2345.ips[3]), equal_to("1.1.1.4/24"))
        assert_that(str(vlan2345.ips[4]), equal_to("2.2.2.2/24"))

        self.client.remove_ip_from_vlan(2345, ip_network=IPNetwork("1.1.1.1/24"))
        self.client.remove_ip_from_vlan(2345, ip_network=IPNetwork("1.1.1.3/24"))

        vlans = self.client.get_vlans()
        vlan2345 = next(vlan for vlan in vlans if vlan.number == 2345)

        assert_that(vlan2345.ips, has_length(3))
        assert_that(str(vlan2345.ips[0]), equal_to("1.1.1.2/24"))
        assert_that(str(vlan2345.ips[1]), equal_to("1.1.1.4/24"))
        assert_that(str(vlan2345.ips[2]), equal_to("2.2.2.2/24"))

        self.client.remove_vlan(2345)

    @skip_on_switches("juniper", "juniper_qfx_copper", "dell", "dell_telnet", "dell10g", "dell10g_telnet")
    def test_adding_unavailable_ips_and_various_errors(self):
        self.client.add_vlan(2345)

        self.client.add_ip_to_vlan(2345, ip_network=IPNetwork("1.1.1.1/24"))

        with self.assertRaises(UnknownVlan):
            self.client.add_ip_to_vlan(3333, ip_network=IPNetwork("1.1.1.1/24"))

        # TODO(jprovost) Unify switch adapters to raise the same exception
        # multiple exceptions: IPNotAvailable, IPAlreadySet
        with self.assertRaises(Conflict): 
            self.client.add_ip_to_vlan(2345, ip_network=IPNetwork("1.1.1.1/24"))

        self.client.add_vlan(2999)
        with self.assertRaises(IPNotAvailable):
            self.client.add_ip_to_vlan(2999, ip_network=IPNetwork("1.1.1.1/24"))

        with self.assertRaises(IPNotAvailable):
            self.client.add_ip_to_vlan(2999, ip_network=IPNetwork("1.1.1.2/24"))
        self.client.remove_vlan(2999)

        with self.assertRaises(UnknownVlan):
            self.client.remove_ip_from_vlan(1111, ip_network=IPNetwork("1.1.1.1/24"))

        with self.assertRaises(UnknownIP):
            self.client.remove_ip_from_vlan(2345, ip_network=IPNetwork("2.2.2.2/24"))

        with self.assertRaises(UnknownIP):
            self.client.remove_ip_from_vlan(2345, ip_network=IPNetwork("1.1.1.1/30"))

        self.client.remove_vlan(2345)

    @skip_on_switches("juniper", "juniper_qfx_copper", "dell", "dell_telnet", "dell10g", "dell10g_telnet")
    def test_handling_access_groups(self):
        self.client.add_vlan(2345)

        self.client.set_vlan_access_group(2345, direction=IN, name="my-group")
        self.client.set_vlan_access_group(2345, direction=OUT, name="your-group")

        vlans = self.client.get_vlans()
        vlan2345 = next(vlan for vlan in vlans if vlan.number == 2345)

        assert_that(vlan2345.access_groups[IN], equal_to("my-group"))
        assert_that(vlan2345.access_groups[OUT], equal_to("your-group"))

        self.client.unset_vlan_access_group(2345, direction=IN)
        self.client.unset_vlan_access_group(2345, direction=OUT)

        vlans = self.client.get_vlans()
        vlan2345 = next(vlan for vlan in vlans if vlan.number == 2345)

        assert_that(vlan2345.access_groups[IN], equal_to(None))
        assert_that(vlan2345.access_groups[OUT], equal_to(None))

        self.client.remove_vlan(2345)


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
