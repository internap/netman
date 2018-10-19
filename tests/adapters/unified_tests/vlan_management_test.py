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
from netaddr import IPNetwork, IPAddress

from netman.core.objects.access_groups import IN, OUT
from netman.core.objects.exceptions import UnknownVlan, UnknownInterface, \
    UnknownResource
from netman.core.objects.interface_states import OFF, ON
from netman.core.objects.port_modes import ACCESS, TRUNK
from tests.adapters.configured_test_case import ConfiguredTestCase, skip_on_switches


class VlanManagementTest(ConfiguredTestCase):
    __test__ = False

    @skip_on_switches("juniper", "juniper_qfx_copper", "dell", "dell_telnet", "dell10g", "dell10g_telnet", "juniper_mx", "arista")
    def test_get_vlan(self):
        self.client.add_vlan(2999, name="my-test-vlan")
        self.client.set_vlan_access_group(2999, IN, "ACL-IN")
        self.client.set_vlan_access_group(2999, OUT, "ACL-OUT")
        self.client.set_vlan_vrf(2999, "DEFAULT-LAN")
        self.client.add_ip_to_vlan(2999, IPNetwork("10.10.10.2/29"))
        self.client.add_vrrp_group(vlan_number=2999, group_id=73, ips=[IPAddress("10.10.10.1")], priority=110,
                                   track_id=self.test_vrrp_track_id, track_decrement=50, hello_interval=5, dead_interval=15)
        self.client.add_dhcp_relay_server(2999, IPAddress("10.10.10.11"))
        self.try_to.set_vlan_icmp_redirects_state(2999, False)
        self.try_to.set_vlan_ntp_state(2999, False)

        single_vlan = self.client.get_vlan(2999)
        vlan_from_list = self.get_vlan_from_list(2999)

        assert_that(single_vlan, equal_to(vlan_from_list))

    @skip_on_switches("juniper", "juniper_qfx_copper", "dell", "dell_telnet", "dell10g", "dell10g_telnet", "juniper_mx", "arista")
    def test_get_vlan_defaults(self):
        self.client.add_vlan(2999, name="my-test-vlan")

        single_vlan = self.client.get_vlan(2999)
        vlan_from_list = self.get_vlan_from_list(2999)

        assert_that(single_vlan, equal_to(vlan_from_list))

    @skip_on_switches("juniper", "juniper_qfx_copper", "dell", "dell_telnet", "dell10g", "dell10g_telnet", "juniper_mx", "arista")
    def test_get_vlan_fails(self):
        with self.assertRaises(UnknownVlan):
            self.client.get_vlan(4000)

    @skip_on_switches("juniper_mx", "arista")
    def test_adding_and_removing_a_vlan(self):
        self.client.add_vlan(2999, name="my-test-vlan")

        vlan = self.get_vlan_from_list(2999)
        assert_that(vlan.name, equal_to('my-test-vlan'))
        assert_that(len(vlan.ips), equal_to(0))

        self.client.remove_vlan(2999)

        vlans = self.client.get_vlans()
        vlan = next((vlan for vlan in vlans if vlan.number == 2999), None)
        assert_that(vlan is None)

    @skip_on_switches("juniper_mx", "arista")
    def test_setting_a_vlan_on_an_interface(self):
        self.client.add_vlan(2999, name="my-test-vlan")

        self.client.set_access_mode(self.test_port)

        self.client.set_access_vlan(self.test_port, vlan=2999)

        self.client.unset_interface_access_vlan(self.test_port)

        self.client.remove_vlan(2999)

    @skip_on_switches("juniper_mx", "arista")
    def test_port_mode_trunk(self):
        self.client.add_vlan(2999, name="my-test-vlan")

        self.client.set_trunk_mode(self.test_port)

        self.client.remove_vlan(2999)

    @skip_on_switches("juniper_mx", "arista")
    def test_port_mode_access(self):
        self.client.add_vlan(2999, name="my-test-vlan")

        self.client.set_access_mode(self.test_port)

        self.client.remove_vlan(2999)

    @skip_on_switches("juniper_mx", "arista")
    def test_native_trunk(self):
        self.client.add_vlan(2999, name="my-test-vlan")

        self.client.set_trunk_mode(self.test_port)

        self.client.set_interface_native_vlan(self.test_port, vlan=2999)

        self.client.unset_interface_native_vlan(self.test_port)

        self.client.set_access_mode(self.test_port)

        self.client.remove_vlan(2999)

    @skip_on_switches("juniper_mx", "arista")
    def test_passing_from_trunk_mode_to_access_gets_rid_of_stuff_in_trunk_mode(self):
        self.client.add_vlan(1100)
        self.client.add_vlan(1200)
        self.client.add_vlan(1300)
        self.client.add_vlan(1400)

        self.client.set_trunk_mode(self.test_port)
        self.client.set_interface_native_vlan(self.test_port, vlan=1200)
        self.client.add_trunk_vlan(self.test_port, vlan=1100)
        self.client.add_trunk_vlan(self.test_port, vlan=1300)
        self.client.add_trunk_vlan(self.test_port, vlan=1400)

        interfaces = self.client.get_interfaces()
        test_if = next(i for i in interfaces if i.name == self.test_port)

        assert_that(test_if.port_mode, equal_to(TRUNK))
        assert_that(test_if.trunk_native_vlan, equal_to(1200))
        assert_that(test_if.access_vlan, equal_to(None))
        assert_that(test_if.trunk_vlans, equal_to([1100, 1300, 1400]))

        self.client.set_access_mode(self.test_port)

        interfaces = self.client.get_interfaces()
        test_if = next(i for i in interfaces if i.name == self.test_port)

        assert_that(test_if.port_mode, equal_to(ACCESS))
        assert_that(test_if.trunk_native_vlan, equal_to(None))
        assert_that(test_if.access_vlan, equal_to(None))
        assert_that(test_if.trunk_vlans, has_length(0))

        self.client.remove_vlan(1100)
        self.client.remove_vlan(1200)
        self.client.remove_vlan(1300)
        self.client.remove_vlan(1400)

    @skip_on_switches("juniper_mx", "arista")
    def test_invalid_vlan_parameter_fails(self):
        with self.assertRaises(UnknownVlan):
            self.client.remove_vlan(2999)

        with self.assertRaises(UnknownVlan):
            self.client.set_access_vlan(self.test_port, vlan=2999)

        self.client.set_trunk_mode(self.test_port)

        with self.assertRaises(UnknownVlan):
            self.client.add_trunk_vlan(self.test_port, vlan=2999)

        with self.assertRaises(UnknownVlan):
            self.client.set_interface_native_vlan(self.test_port, vlan=2999)

        with self.assertRaises(UnknownVlan):
            self.client.add_trunk_vlan(self.test_port, vlan=2999)

        self.client.add_vlan(2999, name="my-test-vlan")
        # TODO(jprovost) Unify switch adapters to raise the same exception
        with self.assertRaises(UnknownResource):
            self.client.remove_trunk_vlan(self.test_port, vlan=2999)

    @skip_on_switches("juniper", "juniper_qfx_copper", "juniper_mx", "arista")
    def test_invalid_interface_parameter_fails(self):
        with self.assertRaises(UnknownInterface):
            self.client.set_interface_state('42/9999', ON)

        with self.assertRaises(UnknownInterface):
            self.client.set_interface_state('42/9999', OFF)

        with self.assertRaises(UnknownInterface):
            self.client.set_access_mode('42/9999')

        with self.assertRaises(UnknownInterface):
            self.client.set_trunk_mode('42/9999')

        # TODO(jprovost) Unify switch adapters to raise the same exception
        with self.assertRaises(UnknownResource):
            self.client.set_access_vlan('42/9999', 1234)

        with self.assertRaises(UnknownInterface):
            self.client.unset_interface_access_vlan('42/9999')

        # TODO(jprovost) Unify switch adapters to raise the same exception
        # Dell 10G raises UnknownInterface
        # other raises UnknownVlan
        with self.assertRaises(UnknownResource):
            self.client.add_trunk_vlan('42/9999', 2999)

        # TODO(jprovost) Behavior is inconsistent across switch adapters
        # Brocade raises UnknownInterface
        # Dell 10G raises NativeVlanNotSet
        # Cisco does not raise
        try:
            self.client.unset_interface_native_vlan(self.test_port)
        except UnknownResource:
            pass

        self.client.add_vlan(2999, name="my-test-vlan")

        with self.assertRaises(UnknownInterface):
            self.client.set_access_vlan('42/9999', 2999)

        # TODO(jprovost) Unify switch adapters to raise the same exception
        # Dell 10G raises UnknownInterface
        # other raises TrunkVlanNotSet
        with self.assertRaises(UnknownResource):
            self.client.remove_trunk_vlan('42/9999', 2999)

        with self.assertRaises(UnknownInterface):
            self.client.set_interface_native_vlan('42/9999', 2999)

    @skip_on_switches("juniper", "juniper_qfx_copper", "dell", "dell_telnet", "dell10g", "dell10g_telnet", "juniper_mx", "arista")
    def test_vrf_management(self):

        self.client.add_vlan(2999, name="my-test-vlan")

        self.client.set_vlan_vrf(2999, 'DEFAULT-LAN')

        vlan = self.get_vlan_from_list(2999)
        assert_that(vlan.vrf_forwarding, is_('DEFAULT-LAN'))

        self.client.unset_vlan_vrf(2999)

        vlan = self.get_vlan_from_list(2999)
        assert_that(vlan.vrf_forwarding, is_(none()))

    def tearDown(self):
        self.janitor.remove_vlan(2999)
        self.janitor.set_access_mode(self.test_port)
        super(VlanManagementTest, self).tearDown()
