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

import unittest

from flexmock import flexmock, flexmock_teardown
from hamcrest import assert_that, has_length, equal_to, is_, instance_of, none
import mock
from netaddr import IPNetwork
from netaddr.ip import IPAddress

from netman.adapters.switches import brocade
from netman.core.objects.switch_transactional import SwitchTransactional
from netman.adapters.switches.brocade import Brocade, parse_if_ranges
from netman.core.objects.access_groups import IN, OUT
from netman.core.objects.exceptions import IPNotAvailable, UnknownVlan, UnknownIP, UnknownAccessGroup, BadVlanNumber, \
    BadVlanName, UnknownInterface, TrunkVlanNotSet, UnknownVrf, VlanVrfNotSet, VrrpAlreadyExistsForVlan, BadVrrpPriorityNumber, BadVrrpGroupNumber, \
    BadVrrpTimers, BadVrrpTracking, NoIpOnVlanForVrrp, VrrpDoesNotExistForVlan, UnknownDhcpRelayServer, DhcpRelayServerAlreadyExists
from netman.core.objects.port_modes import ACCESS, TRUNK
from netman.core.objects.switch_descriptor import SwitchDescriptor


def test_factory():
    lock = mock.Mock()
    switch = brocade.factory(SwitchDescriptor(hostname='hostname', model='brocade', username='username', password='password', port=22), lock)

    assert_that(switch, instance_of(SwitchTransactional))
    assert_that(switch.impl, instance_of(Brocade))
    assert_that(switch.lock, is_(lock))
    assert_that(switch.switch_descriptor.hostname, equal_to("hostname"))
    assert_that(switch.switch_descriptor.model, equal_to("brocade"))
    assert_that(switch.switch_descriptor.username, equal_to("username"))
    assert_that(switch.switch_descriptor.password, equal_to("password"))
    assert_that(switch.switch_descriptor.port, equal_to(22))


class BrocadeTest(unittest.TestCase):

    def setUp(self):
        self.lock = mock.Mock()
        self.switch = brocade.factory(SwitchDescriptor(model='brocade', hostname="my.hostname"), self.lock)

    def tearDown(self):
        flexmock_teardown()

    def command_setup(self):
        self.mocked_ssh_client = flexmock()
        self.switch.impl.ssh = self.mocked_ssh_client

    def test_switch_has_a_logger_configured_with_the_switch_name(self):
        assert_that(self.switch.logger.name, is_(Brocade.__module__ + ".my.hostname"))

    def test_get_vlans(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan | begin vlan").once().ordered().and_return([
            "vlan 1 name DEFAULT-VLAN",
            " no untagged ethe 1/1 ethe 1/20 to 1/22",
            "!",
            "vlan 201",
            " tagged ethe 1/1",
            " router-interface ve 201",
            "!",
            "vlan 2222 name your-name-is-way-too-long-for-t",
            " tagged ethe 1/1",
            "!",
            "vlan 3333 name some-name",
            "!",
            "!"
        ])

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface").once()\
            .ordered().and_return([
                'interface ve 428',
                ' port-name "My Awesome Port Name"',
                ' ip address 10.241.0.33/27',
                ' ip access-group ACL-IN in',
                ' ip access-group ACL-OUT out',
                '!',
                'interface ve 201',
                ' vrf forwarding SHIZZLE',
                ' ip address 1.1.1.1/24',
                ' ip address 2.1.1.1/27',
                ' ip address 1.1.1.9/24 secondary',
                ' ip helper-address 10.10.10.1',
                ' ip helper-address 10.10.10.2',
                ' ip vrrp-extended auth-type simple-text-auth VLAN201',
                ' ip vrrp-extended vrid 1',
                '  backup priority 110 track-priority 50',
                '  ip-address 1.1.1.2',
                '  hello-interval 5',
                '  dead-interval 15',
                '  advertise backup',
                '  track-port ethernet 1/1',
                '  activate',
                ' ip vrrp-extended vrid 2',
                '  backup priority 110 track-priority 50',
                '  ip-address 1.1.1.3',
                '  ip-address 1.1.1.4',
                '  hello-interval 5',
                '  dead-interval 15',
                '  advertise backup',
                '  track-port ethernet 1/1',
                '  activate',
                '!',
                'interface ve 1203',
                '!',
                'interface ve 3993',
                ' port-name Another-port-name',
                ' ip address 4.4.4.0/27',
                '!'
        ])

        vlan1, vlan201, vlan2222, vlan3333 = self.switch.get_vlans()

        assert_that(vlan1.number, equal_to(1))
        assert_that(vlan1.name, equal_to("default"))
        assert_that(vlan1.ips, has_length(0))
        assert_that(vlan1.vrf_forwarding, is_(none()))
        assert_that(vlan201.number, equal_to(201))
        assert_that(vlan201.name, equal_to(""))
        assert_that(vlan201.ips, has_length(3))
        assert_that(vlan201.vrf_forwarding, is_("SHIZZLE"))
        assert_that(vlan2222.number, equal_to(2222))
        assert_that(vlan2222.name, equal_to("your-name-is-way-too-long-for-t"))
        assert_that(vlan2222.ips, has_length(0))
        assert_that(vlan3333.number, equal_to(3333))
        assert_that(vlan3333.name, equal_to("some-name"))
        assert_that(vlan3333.ips, has_length(0))

        vrrp_group1, vrrp_group2 = vlan201.vrrp_groups
        assert_that(len(vrrp_group1.ips), equal_to(1))
        assert_that(vrrp_group1.ips[0], equal_to(IPAddress('1.1.1.2')))
        assert_that(vrrp_group1.hello_interval, equal_to(5))
        assert_that(vrrp_group1.dead_interval, equal_to(15))
        assert_that(vrrp_group1.priority, equal_to(110))
        assert_that(vrrp_group1.track_id, equal_to('1/1'))
        assert_that(vrrp_group1.track_decrement, equal_to(50))
        assert_that(len(vrrp_group2.ips), equal_to(2))
        assert_that(vrrp_group2.ips[0], equal_to(IPAddress('1.1.1.3')))
        assert_that(vrrp_group2.ips[1], equal_to(IPAddress('1.1.1.4')))
        assert_that(vrrp_group2.hello_interval, equal_to(5))
        assert_that(vrrp_group2.dead_interval, equal_to(15))
        assert_that(vrrp_group2.priority, equal_to(110))
        assert_that(vrrp_group2.track_id, equal_to('1/1'))
        assert_that(vrrp_group2.track_decrement, equal_to(50))

        assert_that(len(vlan201.dhcp_relay_servers), equal_to(2))
        assert_that(str(vlan201.dhcp_relay_servers[0]), equal_to('10.10.10.1'))
        assert_that(str(vlan201.dhcp_relay_servers[1]), equal_to('10.10.10.2'))

    def test_add_vlan(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("vlan 2999 name Gertrude").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("write memory").and_return([]).once().ordered()

        self.switch.add_vlan(2999, name="Gertrude")

    def test_add_vlan_bad_number(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("vlan 5000 name Gertrude").once().ordered().and_return([
            "Error: vlan id 4091 is outside of allowed max of 4090"
        ])
        self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered()

        with self.assertRaises(BadVlanNumber) as expect:
            self.switch.add_vlan(5000, name="Gertrude")

        assert_that(str(expect.exception), equal_to("Vlan number is invalid"))

    def test_add_vlan_bad_name(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("vlan 5000 name Gertr ude").once().ordered().and_return([
            "Invalid input -> ude"
        ])
        self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered()

        with self.assertRaises(BadVlanName) as expect:
            self.switch.add_vlan(5000, name="Gertr ude")

        assert_that(str(expect.exception), equal_to("Vlan name is invalid"))

    def test_add_vlan_no_name(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("vlan 2999").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("write memory").and_return([]).once().ordered()

        self.switch.add_vlan(2999)

    def test_remove_vlan(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan | begin vlan 2999").once().ordered().and_return([
            "vlan 2999",
            " router-interface ve 3333",
            "!",
        ])
        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("no vlan 2999").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("write memory").and_return([]).once().ordered()

        self.switch.remove_vlan(2999)

    def test_remove_vlan_invalid_vlan_raises(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan | begin vlan 2999").once().ordered().and_return([])

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").never()

        with self.assertRaises(UnknownVlan) as expect:
            self.switch.remove_vlan(2999)

        assert_that(str(expect.exception), equal_to("Vlan 2999 not found"))

    def test_set_access_vlan(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan | begin vlan 2999").once().ordered().and_return([
            "vlan 2999",
            "!",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("vlan 2999").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("untagged ethernet 1/4").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("write memory").and_return([]).once().ordered()

        self.switch.set_access_vlan("1/4", vlan=2999)

    def test_set_access_vlan_invalid_vlan_raises(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan | begin vlan 2999").once().ordered().and_return([])

        with self.assertRaises(UnknownVlan) as expect:
            self.switch.set_access_vlan("1/4", vlan=2999)

        assert_that(str(expect.exception), equal_to("Vlan 2999 not found"))

    def test_set_access_vlan_invalid_interface_raises(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan | begin vlan 2999").once().ordered().and_return([
            "vlan 2999",
            "!",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("vlan 2999").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("untagged ethernet 9/999").once().ordered().and_return([
            'Invalid input -> 9/999'
            'Type ? for a list'
        ])
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()

        with self.assertRaises(UnknownInterface) as expect:
            self.switch.set_access_vlan("9/999", vlan=2999)

        assert_that(str(expect.exception), equal_to("Unknown interface 9/999"))

    def test_remove_access_vlan(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show vlan brief | include ethe 1/4").once().ordered().and_return([
            "1202     your-name-                                        1202  -  Untagged Ports : ethe 1/10"
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.mocked_ssh_client.should_receive("do").with_args("vlan 1202").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("no untagged ethernet 1/4").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("write memory").and_return([]).once().ordered()

        self.switch.remove_access_vlan("1/4")

    def test_remove_access_vlan_invalid_interface_raises(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show vlan brief | include ethe 9/999").once().ordered().and_return([])

        with self.assertRaises(UnknownInterface) as expect:
            self.switch.remove_access_vlan("9/999")

        assert_that(str(expect.exception), equal_to("Unknown interface 9/999"))

    def test_set_access_mode_does_nothing_if_nothing_is_set(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show vlan ethernet 1/4").once().ordered().and_return([
            "VLAN: 1  Untagged"
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").never()
        self.mocked_ssh_client.should_receive("do").with_args("write memory").and_return([]).once().ordered()

        self.switch.set_access_mode("1/4")

    def test_set_access_mode_invalid_interface_raises(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show vlan ethernet 9/999").once().ordered().and_return([
            'Invalid input -> 9/999'
            'Type ? for a list'
        ])

        with self.assertRaises(UnknownInterface) as expect:
            self.switch.set_access_mode("9/999")

        assert_that(str(expect.exception), equal_to("Unknown interface 9/999"))

    def test_set_access_mode_does_nothing_if_only_an_untagged_vlan_not_knowing_if_it_is_an_access_or_native(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show vlan ethernet 1/4").once().ordered().and_return([
            "VLAN: 123  Untagged"
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").never()
        self.mocked_ssh_client.should_receive("do").with_args("write memory").and_return([]).once().ordered()

        self.switch.set_access_mode("1/4")

    def test_set_access_mode_removes_all_tagged_vlans_and_the_untagged_because_it_is_a_native_vlan(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show vlan ethernet 1/4").once().ordered().and_return([
            "VLAN: 100  Tagged",
            "VLAN: 300  Untagged",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.mocked_ssh_client.should_receive("do").with_args("vlan 100").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("no tagged ethernet 1/4").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("vlan 300").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("no untagged ethernet 1/4").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("write memory").and_return([]).once().ordered()

        self.switch.set_access_mode("1/4")

    def test_set_trunk_mode(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show vlan ethernet 1/4").once().ordered().and_return([
            "VLAN: 1  Untagged"
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").never()
        self.mocked_ssh_client.should_receive("do").with_args("write memory").and_return([]).once().ordered()

        self.switch.set_trunk_mode("1/4")

    def test_set_trunk_mode_invalid_interface_raises(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show vlan ethernet 9/999").once().ordered().and_return([
            'Invalid input -> 9/999'
            'Type ? for a list'
        ])

        with self.assertRaises(UnknownInterface) as expect:
            self.switch.set_trunk_mode("9/999")

        assert_that(str(expect.exception), equal_to("Unknown interface 9/999"))

    def test_add_trunk_vlan(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan | begin vlan 2999").once().ordered().and_return([
            "vlan 2999",
            " tagged ethe 1/10 to 1/11",
            "!",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("vlan 2999").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("tagged ethernet 1/1").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("write memory").and_return([]).once().ordered()

        self.switch.add_trunk_vlan("1/1", vlan=2999)

    def test_add_trunk_vlan_invalid_interface_raises(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan | begin vlan 2999").once().ordered().and_return([
            "vlan 2999",
            " tagged ethe 1/10 to 1/11",
            "!",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("vlan 2999").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("tagged ethernet 9/999").once().ordered().and_return([
            'Invalid input -> 9/999'
            'Type ? for a list'
        ])
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()

        with self.assertRaises(UnknownInterface) as expect:
            self.switch.add_trunk_vlan("9/999", vlan=2999)

        assert_that(str(expect.exception), equal_to("Unknown interface 9/999"))

    def test_add_trunk_vlan_invalid_vlan_raises(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan | begin vlan 2999").once().ordered().and_return([])

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").never()

        with self.assertRaises(UnknownVlan) as expect:
            self.switch.add_trunk_vlan("1/1", vlan=2999)

        assert_that(str(expect.exception), equal_to("Vlan 2999 not found"))

    def test_remove_trunk_vlan(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan | begin vlan 2999").once().ordered().and_return([
            "vlan 2999",
            " tagged ethe 1/10 to 1/11",
            "!",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("vlan 2999").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("no tagged ethernet 1/11").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("write memory").and_return([]).once().ordered()

        self.switch.remove_trunk_vlan("1/11", vlan=2999)

    def test_remove_trunk_vlan_invalid_vlan_raises(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan | begin vlan 2999").once().ordered().and_return([])

        with self.assertRaises(UnknownVlan) as expect:
            self.switch.remove_trunk_vlan("1/2", vlan=2999)

        assert_that(str(expect.exception), equal_to("Vlan 2999 not found"))

    def test_remove_trunk_vlan_invalid_interface_raises(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan | begin vlan 2999").once().ordered().and_return([
            "vlan 2999",
            " tagged ethe 1/10 to 1/13",
            "!",
        ])

        with self.assertRaises(TrunkVlanNotSet) as expect:
            self.switch.remove_trunk_vlan("1/14", vlan=2999)

        assert_that(str(expect.exception), equal_to("Trunk Vlan is not set on interface 1/14"))

    def test_shutdown_interface(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.mocked_ssh_client.should_receive("do").with_args("interface ethernet 1/4").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("disable").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("write memory").and_return([]).once().ordered()

        self.switch.shutdown_interface("1/4")

    def test_shutdown_interface_invalid_interface_raises(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.mocked_ssh_client.should_receive("do").with_args("interface ethernet 9/999").once().ordered().and_return([
            'Invalid input -> 9/999'
            'Type ? for a list'
        ])
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).once().ordered()

        with self.assertRaises(UnknownInterface) as expect:
            self.switch.shutdown_interface("9/999")

        assert_that(str(expect.exception), equal_to("Unknown interface 9/999"))

    def test_openup_interface(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.mocked_ssh_client.should_receive("do").with_args("interface ethernet 1/4").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("enable").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("write memory").and_return([]).once().ordered()

        self.switch.openup_interface("1/4")

    def test_openup_interface_invalid_interface_raises(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.mocked_ssh_client.should_receive("do").with_args("interface ethernet 9/999").once().ordered().and_return([
            'Invalid input -> 9/999'
            'Type ? for a list'
        ])
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).once().ordered()

        with self.assertRaises(UnknownInterface) as expect:
            self.switch.openup_interface("9/999")

        assert_that(str(expect.exception), equal_to("Unknown interface 9/999"))

    def test_configure_native_vlan_on_trunk(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan | begin vlan 2999").once().ordered().and_return([
            "vlan 2999",
            "!",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.mocked_ssh_client.should_receive("do").with_args("vlan 2999").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("untagged ethernet 1/4").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("write memory").and_return([]).once().ordered()

        self.switch.configure_native_vlan("1/4", vlan=2999)

    def test_configure_native_vlan_on_trunk_invalid_interface_raises(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan | begin vlan 2999").once().ordered().and_return([
            "vlan 2999",
            "!",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.mocked_ssh_client.should_receive("do").with_args("vlan 2999").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("untagged ethernet 9/999").once().ordered().and_return([
            'Invalid input -> 9/999'
            'Type ? for a list'
        ])
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()

        with self.assertRaises(UnknownInterface) as expect:
            self.switch.configure_native_vlan("9/999", vlan=2999)

        assert_that(str(expect.exception), equal_to("Unknown interface 9/999"))

    def test_configure_native_vlan_on_trunk_invalid_vlan_raises(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan | begin vlan 2999").once().ordered().and_return([])

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").never()

        with self.assertRaises(UnknownVlan) as expect:
            self.switch.configure_native_vlan("1/4", vlan=2999)

        assert_that(str(expect.exception), equal_to("Vlan 2999 not found"))

    def test_remove_native_vlan_on_trunk(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show vlan brief | include ethe 1/4").once().ordered().and_return([
            "1202     your-name-                                        1202  -  Untagged Ports : ethe 1/10"
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.mocked_ssh_client.should_receive("do").with_args("vlan 1202").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("no untagged ethernet 1/4").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("write memory").and_return([]).once().ordered()

        self.switch.remove_native_vlan("1/4")

    def test_remove_native_vlan_on_trunk_invalid_interface_raises(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show vlan brief | include ethe 9/999").once().ordered().and_return([])

        with self.assertRaises(UnknownInterface) as expect:
            self.switch.remove_native_vlan("9/999")

        assert_that(str(expect.exception), equal_to("Unknown interface 9/999"))

    def test_add_ip_creates_router_interface(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan | begin vlan 1234").once().ordered().and_return([
            "vlan 1234",
            "!",
            "vlan 4000 name some-name",
            " router-interface ve 4000",
            "!",
            "!"
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.mocked_ssh_client.should_receive("do").with_args("vlan 1234").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("router-interface ve 1234").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("interface ve 1234").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("enable").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("ip address 1.2.3.4/25").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("write memory").and_return([]).once().ordered()

        self.switch.add_ip_to_vlan(1234, IPNetwork("1.2.3.4/25"))

    def test_add_ip_doesnt_creates_router_interface_if_already_created(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan | begin vlan 1234").once().ordered().and_return([
            "vlan 1234",
            " router-interface ve 3333",
            "!",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface ve 3333").once().ordered().and_return([
            "interface ve 3333",
            "!",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.mocked_ssh_client.should_receive("do").with_args("interface ve 3333").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("enable").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("ip address 1.2.3.4/25").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("write memory").and_return([]).once().ordered()

        self.switch.add_ip_to_vlan(1234, IPNetwork("1.2.3.4/25"))

    def test_add_ip_contained_in_a_subnet_already_present_requires_the_keyword_secondary(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan | begin vlan 1234").once().ordered().and_return([
            "vlan 1234",
            " router-interface ve 1234",
            "!",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface ve 1234").once().ordered().and_return([
            "interface ve 1234",
            " ip address 1.2.3.1/24",
            "!",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.mocked_ssh_client.should_receive("do").with_args("interface ve 1234").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("enable").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("ip address 1.2.3.4/25 secondary").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("write memory").and_return([]).once().ordered()

        self.switch.add_ip_to_vlan(1234, IPNetwork("1.2.3.4/25"))

    def test_add_ip_already_defined_elsewhere_raises(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan | begin vlan 1234").once().ordered().and_return([
            "vlan 1234",
            " router-interface ve 1234",
            "!",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface ve 1234").once().ordered().and_return([
            "interface ve 1234",
            "!",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.mocked_ssh_client.should_receive("do").with_args("interface ve 1234").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("enable").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("ip address 1.2.3.4/25").and_return([
            "IP/Port: Errno(6) Duplicate ip address"
        ]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()

        with self.assertRaises(IPNotAvailable) as expect:
            self.switch.add_ip_to_vlan(1234, IPNetwork("1.2.3.4/25"))

        assert_that(str(expect.exception), equal_to("IP 1.2.3.4/25 is not available in this vlan"))

    def test_add_ip_already_a_subnet_of_another_ve(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan | begin vlan 1234").once().ordered().and_return([
            "vlan 1234",
            " router-interface ve 1234",
            "!",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface ve 1234").once().ordered().and_return([
            "interface ve 1234",
            "!",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.mocked_ssh_client.should_receive("do").with_args("interface ve 1234").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("enable").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("ip address 1.2.3.4/25").and_return([
            "IP/Port: Errno(11) ip subnet overlap with another interface"
        ]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()

        with self.assertRaises(IPNotAvailable) as expect:
            self.switch.add_ip_to_vlan(1234, IPNetwork("1.2.3.4/25"))

        assert_that(str(expect.exception), equal_to("IP 1.2.3.4/25 is not available in this vlan"))

    def test_add_ip_already_in_this_interface(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan | begin vlan 1234").once().ordered().and_return([
            "vlan 1234",
            " router-interface ve 1234",
            "!",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface ve 1234").once().ordered().and_return([
            "interface ve 1234",
            " ip address 1.2.3.4/24",
            "!",
        ])

        with self.assertRaises(IPNotAvailable) as expect:
            self.switch.add_ip_to_vlan(1234, IPNetwork("1.2.3.4/25"))

        assert_that(str(expect.exception), equal_to("IP 1.2.3.4/25 is not available in this vlan"))

    def test_add_ip_already_in_this_interface_as_a_secondary(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan | begin vlan 1234").once().ordered().and_return([
            "vlan 1234",
            " router-interface ve 1234",
            "!",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface ve 1234").once().ordered().and_return([
            "interface ve 1234",
            " ip address 1.2.3.4/24",
            " ip address 1.2.3.5/24 secondary",
            "!",
        ])

        with self.assertRaises(IPNotAvailable) as expect:
            self.switch.add_ip_to_vlan(1234, IPNetwork("1.2.3.5/25"))

        assert_that(str(expect.exception), equal_to("IP 1.2.3.5/25 is not available in this vlan"))

    def test_add_ip_to_unknown_vlan(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan | begin vlan 1234").once().ordered().and_return([])

        with self.assertRaises(UnknownVlan) as expect:
            self.switch.add_ip_to_vlan(1234, IPNetwork("1.2.3.5/25"))

        assert_that(str(expect.exception), equal_to("Vlan 1234 not found"))

    def test_remove_ip(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan | begin vlan 1234").once().ordered().and_return([
            "vlan 1234",
            " router-interface ve 1234",
            "!",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface ve 1234").once().ordered().and_return([
            "interface ve 1234",
            " ip address 1.2.3.4/24",
            "!",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.mocked_ssh_client.should_receive("do").with_args("interface ve 1234").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("enable").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("no ip address 1.2.3.4/24").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("write memory").and_return([]).once().ordered()

        self.switch.remove_ip_from_vlan(1234, IPNetwork("1.2.3.4/24"))

    def test_remove_secondary_ip(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan | begin vlan 1234").once().ordered().and_return([
            "vlan 1234",
            " router-interface ve 1234",
            "!",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface ve 1234").once().ordered().and_return([
            "interface ve 1234",
            " ip address 1.2.3.4/24",
            " ip address 1.2.3.5/24 secondary",
            "!",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.mocked_ssh_client.should_receive("do").with_args("interface ve 1234").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("enable").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("no ip address 1.2.3.5/24").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("write memory").and_return([]).once().ordered()

        self.switch.remove_ip_from_vlan(1234, IPNetwork("1.2.3.5/24"))

    def test_remove_ip_that_has_secondary_ip(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan | begin vlan 1234").once().ordered().and_return([
            "vlan 1234",
            " router-interface ve 1234",
            "!",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface ve 1234").once().ordered().and_return([
            "interface ve 1234",
            " ip address 1.2.3.4/24",
            " ip address 1.2.3.5/24 secondary",
            " ip address 1.2.3.6/24 secondary",
            "!",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.mocked_ssh_client.should_receive("do").with_args("interface ve 1234").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("enable").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("no ip address 1.2.3.5/24").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("no ip address 1.2.3.6/24").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("no ip address 1.2.3.4/24").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("ip address 1.2.3.5/24").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("ip address 1.2.3.6/24 secondary").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("write memory").and_return([]).once().ordered()

        self.switch.remove_ip_from_vlan(1234, IPNetwork("1.2.3.4/24"))

    def test_remove_unknown_ip_raises(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan | begin vlan 1234").once().ordered().and_return([
            "vlan 1234",
            " router-interface ve 1234",
            "!",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface ve 1234").once().ordered().and_return([
            "interface ve 1234",
            " ip address 1.2.3.4/24",
            " ip address 1.2.3.5/24 secondary",
            " ip address 1.2.3.6/24 secondary",
            "!",
        ])

        with self.assertRaises(UnknownIP) as expect:
            self.switch.remove_ip_from_vlan(1234, IPNetwork("5.5.5.5/25"))

        assert_that(str(expect.exception), equal_to("IP 5.5.5.5/25 not found"))

    def test_remove_known_ip_with_wrong_mask_raises(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan | begin vlan 1234").once().ordered().and_return([
            "vlan 1234",
            " router-interface ve 1234",
            "!",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface ve 1234").once().ordered().and_return([
            "interface ve 1234",
            " ip address 1.2.3.4/24",
            " ip address 1.2.3.5/24 secondary",
            " ip address 1.2.3.6/24 secondary",
            "!",
        ])

        with self.assertRaises(UnknownIP) as expect:
            self.switch.remove_ip_from_vlan(1234, IPNetwork("1.2.3.5/25"))

        assert_that(str(expect.exception), equal_to("IP 1.2.3.5/25 not found"))

    def test_remove_ip_fails_if_there_aint_even_a_router_interface(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan | begin vlan 1234").once().ordered().and_return([
            "vlan 1234",
            "!",
        ])

        with self.assertRaises(UnknownIP) as expect:
            self.switch.remove_ip_from_vlan(1234, IPNetwork("1.2.3.4/24"))

        assert_that(str(expect.exception), equal_to("IP 1.2.3.4/24 not found"))

    def test_remove_ip_on_unknown_vlan(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan | begin vlan 1234").once().ordered().and_return([])

        with self.assertRaises(UnknownVlan) as expect:
            self.switch.remove_ip_from_vlan(1234, IPNetwork("1.2.3.5/25"))

        assert_that(str(expect.exception), equal_to("Vlan 1234 not found"))

    def test_set_vlan_vrf_success(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan | begin vlan 2500").and_return([
            "vlan 2500",
            " router-interface ve 2500",
            "!",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface ve 2500").and_return([
            "interface ve 2500",
            "!",
        ])
        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.mocked_ssh_client.should_receive("do").with_args("interface ve 2500").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("enable").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("vrf forwarding MYVRF").once().ordered().and_return([
            "Warning: All IPv4 and IPv6 addresses (including link-local) on this interface have been removed"
        ])
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("write memory").and_return([]).once().ordered()

        self.switch.set_vlan_vrf(2500, "MYVRF")

    def test_set_vlan_vrf_incorrect_name(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan | begin vlan 2500").and_return([
            "vlan 2500",
            " router-interface ve 2500",
            "!",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface ve 2500").and_return([
            "interface ve 2500",
            "!",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.mocked_ssh_client.should_receive("do").with_args("interface ve 2500").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("enable").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("vrf forwarding MYVRF").once().ordered().and_return([
            "Error - VRF(MYVRF) does not exist or Route-Distinguisher not specified or Address Family not configured"
        ])
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()

        with self.assertRaises(UnknownVrf) as expect:
            self.switch.set_vlan_vrf(2500, "MYVRF")

        assert_that(str(expect.exception), equal_to("VRF name \"MYVRF\" was not configured."))

    def test_set_vlan_vrf_without_interface_creates_it(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan | begin vlan 2500").and_return([
            "vlan 2500",
            "!",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.mocked_ssh_client.should_receive("do").with_args("vlan 2500").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("router-interface ve 2500").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("interface ve 2500").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("enable").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("vrf forwarding MYVRF").once().ordered().and_return([
            "Warning: All IPv4 and IPv6 addresses (including link-local) on this interface have been removed"
        ])
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("write memory").and_return([]).once().ordered()

        self.switch.set_vlan_vrf(2500, "MYVRF")

    def test_set_vlan_vrf_unknown_vlan(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan | begin vlan 2500").and_return([])

        with self.assertRaises(UnknownVlan) as expect:
            self.switch.set_vlan_vrf(2500, "MYVRF")

        assert_that(str(expect.exception), equal_to("Vlan 2500 not found"))

    def test_remove_vlan_vrf_success(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan | begin vlan 2500").and_return([
            "vlan 2500",
            " router-interface ve 2500",
            "!",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface ve 2500").and_return([
            "interface ve 2500",
            " vrf forwarding MYVRF",
            "!",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.mocked_ssh_client.should_receive("do").with_args("interface ve 2500").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("enable").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("no vrf forwarding MYVRF").once().ordered().and_return([
            "Warning: All IPv4 and IPv6 addresses (including link-local) on this interface have been removed"
        ])
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("write memory").and_return([]).once().ordered()

        self.switch.remove_vlan_vrf(2500)

    def test_remove_vlan_vrf_not_set(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan | begin vlan 2500").and_return([
            "vlan 2500",
            " router-interface ve 2500",
            "!",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface ve 2500").and_return([
            "interface ve 2500",
            "!",
        ])

        with self.assertRaises(VlanVrfNotSet) as expect:
            self.switch.remove_vlan_vrf(2500)

        assert_that(str(expect.exception), equal_to("VRF is not set on vlan 2500"))

    def test_remove_vlan_vrf_from_known_vlan_with_no_interface(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan | begin vlan 2500").and_return([
            "vlan 2500",
            "!",
        ])

        with self.assertRaises(VlanVrfNotSet) as expect:
            self.switch.remove_vlan_vrf(2500)

        assert_that(str(expect.exception), equal_to("VRF is not set on vlan 2500"))

    def test_remove_vlan_vrf_from_unknown_vlan(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan | begin vlan 2500").and_return([])

        with self.assertRaises(UnknownVlan) as expect:
            self.switch.remove_vlan_vrf(2500)

        assert_that(str(expect.exception), equal_to("Vlan 2500 not found"))

    def test_set_access_group_creates_router_interface(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan | begin vlan 2500").once().ordered().and_return([
            "vlan 2500",
            "!",
            "vlan 4000 name some-name",
            " router-interface ve 4000",
            "!",
            "!"
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.mocked_ssh_client.should_receive("do").with_args("vlan 2500").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("router-interface ve 2500").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("interface ve 2500").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("enable").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("ip access-group TheAccessGroup in").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("write memory").and_return([]).once().ordered()

        self.switch.set_vlan_access_group(2500, IN, "TheAccessGroup")

    def test_set_access_group_doesnt_creates_router_interface_if_already_created(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan | begin vlan 2500").once().ordered().and_return([
            "vlan 2500",
            " router-interface ve 3333",
            "!",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface ve 3333").once().ordered().and_return([
            "interface ve 3333",
            "!",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.mocked_ssh_client.should_receive("do").with_args("interface ve 3333").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("enable").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("ip access-group TheAccessGroup out").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("write memory").and_return([]).once().ordered()

        self.switch.set_vlan_access_group(2500, OUT, "TheAccessGroup")

    def test_set_access_group_fails_if_switch_says_so(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan | begin vlan 2500").once().ordered().and_return([
            "vlan 2500",
            " router-interface ve 3333",
            "!",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface ve 3333").once().ordered().and_return([
            "interface ve 3333",
            "!",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.mocked_ssh_client.should_receive("do").with_args("interface ve 3333").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("enable").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("ip access-group TheAcc essGroup out").once().ordered().and_return([
            "Invalid input -> sss out",
            "Type ? for a list"
        ])
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()

        with self.assertRaises(ValueError) as expect:
            self.switch.set_vlan_access_group(2500, OUT, "TheAcc essGroup")

        assert_that(str(expect.exception), equal_to("Access group name \"TheAcc essGroup\" is invalid"))

    def test_set_access_group_needs_to_remove_actual_access_group_to_override_it(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan | begin vlan 2500").once().ordered().and_return([
            "vlan 2500",
            " router-interface ve 2500",
            "!",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface ve 2500").once().ordered().and_return([
            "interface ve 2500",
            " ip access-group helloThere! in",
            "!",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.mocked_ssh_client.should_receive("do").with_args("interface ve 2500").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("enable").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("no ip access-group helloThere! in").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("ip access-group TheAccessGroup in").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("write memory").and_return([]).once().ordered()

        self.switch.set_vlan_access_group(2500, IN, "TheAccessGroup")

    def test_set_access_group_to_unknown_vlan(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan | begin vlan 2500").once().ordered().and_return([])

        with self.assertRaises(UnknownVlan) as expect:
            self.switch.set_vlan_access_group(2500, IN, "TheAccessGroup")

        assert_that(str(expect.exception), equal_to("Vlan 2500 not found"))

    def test_remove_access_group(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan | begin vlan 2500").once().ordered().and_return([
            "vlan 2500",
            " router-interface ve 2500",
            "!",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface ve 2500").once().ordered().and_return([
            "interface ve 2500",
            " ip access-group helloThere! in",
            "!",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.mocked_ssh_client.should_receive("do").with_args("interface ve 2500").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("enable").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("no ip access-group helloThere! in").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("write memory").and_return([]).once().ordered()

        self.switch.remove_vlan_access_group(2500, IN)

    def test_remove_access_group_out(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan | begin vlan 2500").once().ordered().and_return([
            "vlan 2500",
            " router-interface ve 2500",
            "!",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface ve 2500").once().ordered().and_return([
            "interface ve 2500",
            " ip access-group Waaaat out",
            "!",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.mocked_ssh_client.should_receive("do").with_args("interface ve 2500").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("enable").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("no ip access-group Waaaat out").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("write memory").and_return([]).once().ordered()

        self.switch.remove_vlan_access_group(2500, OUT)

    def test_remove_access_group_unknown_access_group_raises(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan | begin vlan 2500").once().ordered().and_return([
            "vlan 2500",
            " router-interface ve 2500",
            "!",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface ve 2500").once().ordered().and_return([
            "interface ve 2500",
            " ip access-group Waaaat out",
            "!",
        ])

        with self.assertRaises(UnknownAccessGroup) as expect:
            self.switch.remove_vlan_access_group(2500, IN)

        assert_that(str(expect.exception), equal_to("Inbound IP access group not found"))

    def test_remove_access_group_fails_if_there_aint_even_a_router_interface(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan | begin vlan 2500").once().ordered().and_return([
            "vlan 2500",
            "!",
        ])

        with self.assertRaises(UnknownAccessGroup) as expect:
            self.switch.remove_vlan_access_group(2500, OUT)

        assert_that(str(expect.exception), equal_to("Outgoing IP access group not found"))

    def test_remove_access_group_on_unknown_vlan(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan | begin vlan 2500").once().ordered().and_return([])

        with self.assertRaises(UnknownVlan) as expect:
            self.switch.remove_vlan_access_group(2500, OUT)

        assert_that(str(expect.exception), equal_to("Vlan 2500 not found"))

    def test_get_interfaces(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show interfaces").once().ordered().and_return([
            "GigabitEthernet1/1 is down, line protocol is down",
            "  Hardware is GigabitEthernet, address is 0000.0000.0000 (bia 0000.0000.0000,",
            "  Member of VLAN 1999 (untagged), port is in untagged mode, port state is Disabled",
            "  No port name",
            "GigabitEthernet1/2 is disabled, line protocol is down",
            "  Hardware is GigabitEthernet, address is 0000.0000.0000 (bia 0000.0000.0000,",
            "  Member of VLAN 2999 (untagged), 3 L2 VLANS (tagged), port is in dual mode, port state is Disabled",
            "  Port name is hello",
            "GigabitEthernet1/3 is down, line protocol is down",
            "  Hardware is GigabitEthernet, address is 0000.0000.0000 (bia 0000.0000.0000,",
            "  Member of VLAN 1 (untagged), port is in untagged mode, port state is Disabled",
            "  No port name",
            "GigabitEthernet1/4 is disabled, line protocol is down",
            "  Hardware is GigabitEthernet, address is 0000.0000.0000 (bia 0000.0000.0000,",
            "  Member of VLAN 1 (untagged), 1 L2 VLANS (tagged), port is in dual mode (default vlan), port state is Disabled",
            "  No port name",
            "GigabitEthernet1/5 is disabled, line protocol is down",
            "  Hardware is GigabitEthernet, address is 0000.0000.0000 (bia 0000.0000.0000,",
            "  Member of 1 L2 VLAN(S) (tagged), port is in tagged mode, port state is Disabled",
            "  No port name",
            "GigabitEthernet1/6 is disabled, line protocol is down",
            "  Hardware is GigabitEthernet, address is 0000.0000.0000 (bia 0000.0000.0000,",
            "  Member of 1 L2 VLAN(S) (tagged), port is in tagged mode, port state is Disabled",
            "  No port name",
            "Ve1000 is down, line protocol is down",
            "  Hardware is Virtual Ethernet, address is 0000.0000.0000 (bia 0000.0000.0000,",
            "  Port name is Salut",
            "  Vlan id: 1000",
            "  Internet address is 0.0.0.0/0, IP MTU 1500 bytes, encapsulation ethernet",
            "Ve2000 is down, line protocol is down",
            "  Hardware is Virtual Ethernet, address is 0000.0000.0000 (bia 0000.0000.0000,",
            "  No port name",
            "  Vlan id: 2000",
            "  Internet address is 1.1.1.1/24, IP MTU 1500 bytes, encapsulation ethernet",
            "Loopback1 is up, line protocol is up",
            "  Hardware is Loopback",
            "  Port name is LOOPBACK",
            "  Internet address is 108.163.134.4/32, IP MTU 1500 bytes, encapsulation LOOPBACK"
        ])

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan").once().ordered().and_return([
            "spanning-tree",
            "!",
            "vlan 1 name DEFAULT-VLAN",
            " no untagged ethe 1/3",
            "!",
            "vlan 100",
            " tagged ethe 1/2 ethe 1/4 to 1/6",
            "!",
            "vlan 200",
            " tagged ethe 1/2",
            "!",
            "vlan 300",
            " tagged ethe 1/2",
            "!",
            "vlan 1999",
            " untagged ethe 1/1",
            "!",
            "vlan 2999",
            " untagged ethe 1/2",
            "!",
            "!"
        ])

        result = self.switch.get_interfaces()

        if1, if2, if3, if4, if5, if6 = result

        assert_that(if1.name, equal_to("1/1"))
        assert_that(if1.shutdown, equal_to(False))
        assert_that(if1.port_mode, equal_to(ACCESS))
        assert_that(if1.access_vlan, equal_to(1999))
        assert_that(if1.trunk_native_vlan, equal_to(None))
        assert_that(if1.trunk_vlans, equal_to([]))

        assert_that(if2.name, equal_to("1/2"))
        assert_that(if2.shutdown, equal_to(True))
        assert_that(if2.port_mode, equal_to(TRUNK))
        assert_that(if2.access_vlan, equal_to(None))
        assert_that(if2.trunk_native_vlan, equal_to(2999))
        assert_that(if2.trunk_vlans, equal_to([100, 200, 300]))

        assert_that(if3.name, equal_to("1/3"))
        assert_that(if3.port_mode, equal_to(ACCESS))
        assert_that(if3.access_vlan, equal_to(None))
        assert_that(if3.trunk_native_vlan, equal_to(None))
        assert_that(if3.trunk_vlans, equal_to([]))

        assert_that(if4.name, equal_to("1/4"))
        assert_that(if4.port_mode, equal_to(TRUNK))
        assert_that(if4.access_vlan, equal_to(None))
        assert_that(if4.trunk_native_vlan, equal_to(None))
        assert_that(if4.trunk_vlans, equal_to([100]))

        assert_that(if5.trunk_vlans, equal_to([100]))

        assert_that(if6.trunk_vlans, equal_to([100]))

    def test_add_vrrp_success_single_ip(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan | begin vlan 1234").once().ordered().and_return([
            "vlan 1234",
            " router-interface ve 1234",
            "!",
        ])
        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface ve 1234").once().ordered().and_return([
            "interface ve 1234",
            " ip address 1.2.3.1/27",
            "!",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.mocked_ssh_client.should_receive("do").with_args("interface ve 1234").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("enable").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("ip vrrp-extended auth-type simple-text-auth VLAN1234").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("ip vrrp-extended vrid 1").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("backup priority 110 track-priority 50").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("ip-address 1.2.3.4").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("hello-interval 5").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("dead-interval 15").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("advertise backup").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("track-port ethernet 1/1").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("activate").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("write memory").and_return([]).once().ordered()

        self.switch.add_vrrp_group(1234, 1, ips=[IPAddress("1.2.3.4")], priority=110, hello_interval=5, dead_interval=15,
                                   track_id="1/1", track_decrement=50)

    def test_add_vrrp_success_multiple_ip(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan | begin vlan 1234").once().ordered().and_return([
            "vlan 1234",
            " router-interface ve 1234",
            "!",
        ])
        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface ve 1234").once().ordered().and_return([
            "interface ve 1234",
            " ip address 1.2.3.1/27",
            "!",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.mocked_ssh_client.should_receive("do").with_args("interface ve 1234").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("enable").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("ip vrrp-extended auth-type simple-text-auth VLAN1234").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("ip vrrp-extended vrid 1").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("backup priority 110 track-priority 50").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("ip-address 1.2.3.4").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("ip-address 1.2.3.5").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("hello-interval 5").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("dead-interval 15").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("advertise backup").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("track-port ethernet 1/1").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("activate").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("write memory").and_return([]).once().ordered()

        self.switch.add_vrrp_group(1234, 1, ips=[IPAddress("1.2.3.4"), IPAddress("1.2.3.5")], priority=110,
                                   hello_interval=5, dead_interval=15, track_id="1/1", track_decrement=50)

    def test_add_vrrp_from_unknown_vlan(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan | begin vlan 1234").once().ordered().and_return([])

        with self.assertRaises(UnknownVlan) as expect:
            self.switch.add_vrrp_group(1234, 1, ips=[IPAddress("1.2.3.4")], priority=110, hello_interval=5, dead_interval=15,
                                       track_id="1/1", track_decrement=50)

        assert_that(str(expect.exception), equal_to("Vlan 1234 not found"))

    def test_add_existing_vrrp_to_same_vlan(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan | begin vlan 1234").once().ordered().and_return([
            "vlan 1234",
            " router-interface ve 1234",
            "!",
        ])
        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface ve 1234").once().ordered().and_return([
            "interface ve 1234",
            " ip address 1.2.3.1/27",
            " ip vrrp-extended auth-type simple-text-auth ********",
            " ip vrrp-extended vrid 1",
            "  backup priority 110 track-priority 50",
            "  ip-address 1.2.3.4",
            "  hello-interval 5",
            "  dead-interval 15",
            "  advertise backup",
            "  track-port ethernet 1/1",
            "  activate",
            "!",
        ])

        with self.assertRaises(VrrpAlreadyExistsForVlan) as expect:
            self.switch.add_vrrp_group(1234, 1, ips=[IPAddress("1.2.3.4")], priority=110, hello_interval=5, dead_interval=15,
                                       track_id="1/1", track_decrement=50)

        assert_that(str(expect.exception), equal_to("Vrrp group 1 is already in use on vlan 1234"))

    def test_add_vrrp_to_vlan_with_another_vrrp(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan | begin vlan 1234").once().ordered().and_return([
            "vlan 1234",
            " router-interface ve 1234",
            "!",
        ])
        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface ve 1234").once().ordered().and_return([
            "interface ve 1234",
            " ip address 1.2.3.1/27",
            " ip vrrp-extended auth-type simple-text-auth ********",
            " ip vrrp-extended vrid 1",
            "  backup priority 110 track-priority 50",
            "  ip-address 1.2.3.4",
            "  hello-interval 5",
            "  dead-interval 15",
            "  advertise backup",
            "  track-port ethernet 1/1",
            "  activate",
            "!",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.mocked_ssh_client.should_receive("do").with_args("interface ve 1234").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("enable").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("ip vrrp-extended vrid 2").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("backup priority 110 track-priority 50").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("ip-address 1.2.3.5").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("hello-interval 5").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("dead-interval 15").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("advertise backup").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("track-port ethernet 1/1").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("activate").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("write memory").and_return([]).once().ordered()

        self.switch.add_vrrp_group(1234, 2, ips=[IPAddress("1.2.3.5")], priority=110, hello_interval=5, dead_interval=15,
                                   track_id="1/1", track_decrement=50)

    def test_add_vrrp_with_out_of_range_group_id(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan | begin vlan 1234").once().ordered().and_return([
            "vlan 1234",
            " router-interface ve 1234",
            "!",
        ])
        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface ve 1234").once().ordered().and_return([
            "interface ve 1234",
            " ip address 1.2.3.1/27",
            "!",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.mocked_ssh_client.should_receive("do").with_args("interface ve 1234").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("enable").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("ip vrrp-extended auth-type simple-text-auth VLAN1234").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("ip vrrp-extended vrid 256").and_return([
            "Error - 256 not between 1 and 255"
        ]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()

        with self.assertRaises(BadVrrpGroupNumber) as expect:
            self.switch.add_vrrp_group(1234, 256, ips=[IPAddress("1.2.3.4")], priority=110, hello_interval=5, dead_interval=15,
                                       track_id="1/1", track_decrement=50)

        assert_that(str(expect.exception), equal_to("VRRP group number is invalid, must be contained between 1 and 255"))

    def test_add_vrrp_with_bad_hello_interval(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan | begin vlan 1234").once().ordered().and_return([
            "vlan 1234",
            " router-interface ve 1234",
            "!",
        ])
        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface ve 1234").once().ordered().and_return([
            "interface ve 1234",
            " ip address 1.2.3.1/27",
            "!",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.mocked_ssh_client.should_receive("do").with_args("interface ve 1234").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("enable").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("ip vrrp-extended auth-type simple-text-auth VLAN1234").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("ip vrrp-extended vrid 1").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("backup priority 110 track-priority 50").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("ip-address 1.2.3.4").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("hello-interval 100").and_return([
            "Error - 100 not between 1 and 84"
        ]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).times(3).ordered().ordered().ordered()

        with self.assertRaises(BadVrrpTimers) as expect:
            self.switch.add_vrrp_group(1234, 1, ips=[IPAddress("1.2.3.4")], priority=110, hello_interval=100, dead_interval=15,
                                       track_id="1/1", track_decrement=50)

        assert_that(str(expect.exception), equal_to("VRRP timers values are invalid"))

    def test_add_vrrp_with_bad_dead_interval(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan | begin vlan 1234").once().ordered().and_return([
            "vlan 1234",
            " router-interface ve 1234",
            "!",
        ])
        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface ve 1234").once().ordered().and_return([
            "interface ve 1234",
            " ip address 1.2.3.1/27",
            "!",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.mocked_ssh_client.should_receive("do").with_args("interface ve 1234").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("enable").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("ip vrrp-extended auth-type simple-text-auth VLAN1234").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("ip vrrp-extended vrid 1").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("backup priority 110 track-priority 50").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("ip-address 1.2.3.4").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("hello-interval 5").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("dead-interval 100").and_return([
            "Error - 100 not between 1 and 84"
        ]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).times(3).ordered().ordered().ordered()

        with self.assertRaises(BadVrrpTimers) as expect:
            self.switch.add_vrrp_group(1234, 1, ips=[IPAddress("1.2.3.4")], priority=110, hello_interval=5, dead_interval=100,
                                       track_id="1/1", track_decrement=50)

        assert_that(str(expect.exception), equal_to("VRRP timers values are invalid"))

    def test_add_vrrp_with_bad_priority(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan | begin vlan 1234").once().ordered().and_return([
            "vlan 1234",
            " router-interface ve 1234",
            "!",
        ])
        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface ve 1234").once().ordered().and_return([
            "interface ve 1234",
            " ip address 1.2.3.1/27",
            "!",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.mocked_ssh_client.should_receive("do").with_args("interface ve 1234").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("enable").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("ip vrrp-extended auth-type simple-text-auth VLAN1234").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("ip vrrp-extended vrid 1").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("backup priority 256 track-priority 50").and_return([
            "Error - 256 not between 1 and 255"
        ]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).times(3).ordered().ordered().ordered()

        with self.assertRaises(BadVrrpPriorityNumber) as expect:
            self.switch.add_vrrp_group(1234, 1, ips=[IPAddress("1.2.3.4")], priority=256, hello_interval=5, dead_interval=100,
                                       track_id="1/1", track_decrement=50)

        assert_that(str(expect.exception), equal_to("VRRP priority value is invalid, must be contained between 1 and 255"))

    def test_add_vrrp_with_bad_priority_type(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan | begin vlan 1234").once().ordered().and_return([
            "vlan 1234",
            " router-interface ve 1234",
            "!",
        ])
        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface ve 1234").once().ordered().and_return([
            "interface ve 1234",
            " ip address 1.2.3.1/27",
            "!",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.mocked_ssh_client.should_receive("do").with_args("interface ve 1234").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("enable").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("ip vrrp-extended auth-type simple-text-auth VLAN1234").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("ip vrrp-extended vrid 1").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("backup priority testvalue track-priority 50").and_return([
            "Invalid input -> testvalue track-priority 50"
        ]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).times(3).ordered().ordered().ordered()

        with self.assertRaises(BadVrrpPriorityNumber) as expect:
            self.switch.add_vrrp_group(1234, 1, ips=[IPAddress("1.2.3.4")], priority='testvalue', hello_interval=5, dead_interval=15,
                                       track_id="1/1", track_decrement=50)

        assert_that(str(expect.exception), equal_to("VRRP priority value is invalid, must be contained between 1 and 255"))

    def test_add_vrrp_with_bad_track_decrement(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan | begin vlan 1234").once().ordered().and_return([
            "vlan 1234",
            " router-interface ve 1234",
            "!",
        ])
        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface ve 1234").once().ordered().and_return([
            "interface ve 1234",
            " ip address 1.2.3.1/27",
            "!",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.mocked_ssh_client.should_receive("do").with_args("interface ve 1234").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("enable").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("ip vrrp-extended auth-type simple-text-auth VLAN1234").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("ip vrrp-extended vrid 1").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("backup priority 110 track-priority 255").and_return([
            "Error - 255 not between 1 and 254"
        ]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).times(3).ordered().ordered().ordered()

        with self.assertRaises(BadVrrpTracking) as expect:
            self.switch.add_vrrp_group(1234, 1, ips=[IPAddress("1.2.3.4")], priority=110, hello_interval=5, dead_interval=15,
                                       track_id="1/1", track_decrement=255)

        assert_that(str(expect.exception), equal_to("VRRP tracking values are invalid"))

    def test_add_vrrp_with_bad_track_decrement_type(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan | begin vlan 1234").once().ordered().and_return([
            "vlan 1234",
            " router-interface ve 1234",
            "!",
        ])
        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface ve 1234").once().ordered().and_return([
            "interface ve 1234",
            " ip address 1.2.3.1/27",
            "!",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.mocked_ssh_client.should_receive("do").with_args("interface ve 1234").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("enable").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("ip vrrp-extended auth-type simple-text-auth VLAN1234").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("ip vrrp-extended vrid 1").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("backup priority 110 track-priority testvalue").and_return([
            "Invalid input -> testvalue"
        ]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).times(3).ordered().ordered().ordered()

        with self.assertRaises(BadVrrpTracking) as expect:
            self.switch.add_vrrp_group(1234, 1, ips=[IPAddress("1.2.3.4")], priority=110, hello_interval=5, dead_interval=15,
                                       track_id="1/1", track_decrement='testvalue')

        assert_that(str(expect.exception), equal_to("VRRP tracking values are invalid"))

    def test_add_vrrp_with_no_ip_on_interface(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan | begin vlan 1234").once().ordered().and_return([
            "vlan 1234",
            " router-interface ve 1234",
            "!",
        ])
        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface ve 1234").once().ordered().and_return([
            "interface ve 1234",
            "!",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.mocked_ssh_client.should_receive("do").with_args("interface ve 1234").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("enable").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("ip vrrp-extended auth-type simple-text-auth VLAN1234").and_return([
            "error - please configure ip address before configuring vrrp-extended"
        ]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).times(2).ordered().ordered()

        with self.assertRaises(NoIpOnVlanForVrrp) as expect:
            self.switch.add_vrrp_group(1234, 1, ips=[IPAddress("1.2.3.4")], priority=110, hello_interval=5, dead_interval=100,
                                       track_id="1/1", track_decrement=50)

        assert_that(str(expect.exception), equal_to("Vlan 1234 needs an IP before configuring VRRP"))

    def test_add_vrrp_with_bad_tracking_id(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan | begin vlan 1234").once().ordered().and_return([
            "vlan 1234",
            " router-interface ve 1234",
            "!",
        ])
        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface ve 1234").once().ordered().and_return([
            "interface ve 1234",
            " ip address 1.2.3.1/27",
            "!",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.mocked_ssh_client.should_receive("do").with_args("interface ve 1234").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("enable").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("ip vrrp-extended auth-type simple-text-auth VLAN1234").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("ip vrrp-extended vrid 1").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("backup priority 110 track-priority 50").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("ip-address 1.2.3.4").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("hello-interval 5").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("dead-interval 15").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("advertise backup").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("track-port ethernet not_an_interface").and_return([
            "Invalid input -> not_an_interface"
        ]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).times(3).ordered().ordered().ordered()

        with self.assertRaises(BadVrrpTracking) as expect:
            self.switch.add_vrrp_group(1234, 1, ips=[IPAddress("1.2.3.4")], priority=110, hello_interval=5, dead_interval=15,
                                       track_id="not_an_interface", track_decrement=50)

        assert_that(str(expect.exception), equal_to("VRRP tracking values are invalid"))

    def test_remove_vrrp_success(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan | begin vlan 1234").once().ordered().and_return([
            "vlan 1234",
            " router-interface ve 1234",
            "!",
        ])
        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface ve 1234").once().ordered().and_return([
            "interface ve 1234",
            " ip address 1.2.3.1/27",
            " ip vrrp-extended auth-type simple-text-auth ********",
            " ip vrrp-extended vrid 1",
            "  backup priority 110 track-priority 50",
            "  ip-address 1.1.1.1",
            "  hello-interval 5",
            "  dead-interval 15",
            "  advertise backup",
            "  track-port ethernet 1/1",
            "  activate",
            "!",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.mocked_ssh_client.should_receive("do").with_args("interface ve 1234").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("enable").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("no ip vrrp-extended vrid 1").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("ip vrrp-extended auth-type no-auth").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("write memory").and_return([]).once().ordered()

        self.switch.remove_vrrp_group(1234, 1)

    def test_remove_one_of_two_vrrp_success(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan | begin vlan 1234").once().ordered().and_return([
            "vlan 1234",
            " router-interface ve 1234",
            "!",
        ])
        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface ve 1234").once().ordered().and_return([
            "interface ve 1234",
            " ip address 1.2.3.1/27",
            " ip vrrp-extended auth-type simple-text-auth ********",
            " ip vrrp-extended vrid 1",
            "  backup priority 110 track-priority 50",
            "  ip-address 1.1.1.1",
            "  hello-interval 5",
            "  dead-interval 15",
            "  advertise backup",
            "  track-port ethernet 1/1",
            "  activate",
            " ip vrrp-extended vrid 2",
            "  backup priority 110 track-priority 50",
            "  ip-address 1.1.1.2",
            "  hello-interval 5",
            "  dead-interval 15",
            "  advertise backup",
            "  track-port ethernet 1/1",
            "  activate",
            "!",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.mocked_ssh_client.should_receive("do").with_args("interface ve 1234").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("enable").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("no ip vrrp-extended vrid 1").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("write memory").and_return([]).once().ordered()

        self.switch.remove_vrrp_group(1234, 1)

    def test_remove_vrrp_with_invalid_group_id(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan | begin vlan 1234").once().ordered().and_return([
            "vlan 1234",
            " router-interface ve 1234",
            "!",
        ])
        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface ve 1234").once().ordered().and_return([
            "interface ve 1234",
            " ip address 1.2.3.1/27",
            " ip vrrp-extended auth-type simple-text-auth ********",
            " ip vrrp-extended vrid 1",
            "  backup priority 110 track-priority 50",
            "  ip-address 1.1.1.1",
            "  hello-interval 5",
            "  dead-interval 15",
            "  advertise backup",
            "  track-port ethernet 1/1",
            "  activate",
            "!",
        ])

        with self.assertRaises(VrrpDoesNotExistForVlan) as expect:
            self.switch.remove_vrrp_group(1234, 2)

        assert_that(str(expect.exception), equal_to("Vrrp group 2 does not exist for vlan 1234"))

    def test_remove_vrrp_from_unknown_vlan(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan | begin vlan 1234").once().ordered().and_return([])

        with self.assertRaises(UnknownVlan) as expect:
            self.switch.remove_vrrp_group(1234, 2)

        assert_that(str(expect.exception), equal_to("Vlan 1234 not found"))

    def parse_range_test(self):

        result = parse_if_ranges("")
        assert_that(list(result), equal_to([]))

        result = parse_if_ranges("ethe 1/2")
        assert_that(list(result), equal_to(["ethe 1/2"]))

        result = parse_if_ranges("ethe 1/1/2 to 1/1/5")
        assert_that(list(result), equal_to(["ethe 1/1/2", "ethe 1/1/3", "ethe 1/1/4", "ethe 1/1/5"]))

        result = parse_if_ranges("shizzle 1/1 shizzle 1/3 to 1/5 shizzle 1/7")
        assert_that(list(result), equal_to(["shizzle 1/1", "shizzle 1/3", "shizzle 1/4", "shizzle 1/5", "shizzle 1/7"]))


    @mock.patch("netman.adapters.shell.ssh.SshClient")
    def test_connect(self, ssh_client_class_mock):
        self.switch = Brocade(SwitchDescriptor(hostname="my.hostname", username="the_user", password="the_password", model="brocade"))

        self.mocked_ssh_client = flexmock()
        ssh_client_class_mock.return_value = self.mocked_ssh_client
        self.mocked_ssh_client.should_receive("get_current_prompt").and_return("hostname>").once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("enable", wait_for=":").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("the_password").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("skip-page-display").and_return([]).once().ordered()

        self.switch.connect()

        ssh_client_class_mock.assert_called_with(
            host="my.hostname",
            username="the_user",
            password="the_password",
            port=22
        )

    @mock.patch("netman.adapters.shell.ssh.SshClient")
    def test_auto_enabled_switch_doesnt_require_enable(self, ssh_client_class_mock):
        self.switch = Brocade(SwitchDescriptor(hostname="my.hostname", username="the_user", password="the_password", model="brocade", port=8000))

        self.mocked_ssh_client = flexmock()
        ssh_client_class_mock.return_value = self.mocked_ssh_client
        self.mocked_ssh_client.should_receive("get_current_prompt").and_return("hostname#").once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("enable", wait_for=": ").never()
        self.mocked_ssh_client.should_receive("do").with_args("skip-page-display").and_return([]).once().ordered()

        self.switch.connect()

        ssh_client_class_mock.assert_called_with(
            host="my.hostname",
            username="the_user",
            password="the_password",
            port=8000
        )

    def test_disconnect(self):
        logger = flexmock()
        self.switch.impl.logger = logger
        logger.should_receive("debug")

        mocked_ssh_client = flexmock()
        self.switch.impl.ssh = mocked_ssh_client
        mocked_ssh_client.should_receive("quit").with_args("exit").once().ordered()

        logger.should_receive("info").with_args("FULL TRANSACTION LOG").once()

        self.switch.impl.ssh.full_log = "FULL TRANSACTION LOG"
        self.switch.disconnect()

    def test_transactions_commit_write_memory(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("vlan 2999 name Gertrude").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])
        self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        self.switch.start_transaction()
        self.switch.add_vlan(2999, name="Gertrude")

        self.mocked_ssh_client.should_receive("do").with_args("write memory").once().ordered()

        self.switch.commit_transaction()
        self.switch.end_transaction()

    def test_add_dhcp_relay_server(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan | begin vlan 1234").once().ordered().and_return([
            "vlan 1234",
            " router-interface ve 1234",
            "!",
        ])
        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface ve 1234").once().ordered().and_return([
            "interface ve 1234",
            " ip address 1.2.3.1/27",
            "!",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.mocked_ssh_client.should_receive("do").with_args("interface ve 1234").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("enable").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("ip helper-address 10.10.10.1").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("write memory").and_return([]).once().ordered()

        self.switch.add_dhcp_relay_server(1234, IPAddress('10.10.10.1'))

    def test_add_second_dhcp_relay_server(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan | begin vlan 1234").once().ordered().and_return([
            "vlan 1234",
            " router-interface ve 1234",
            "!",
        ])
        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface ve 1234").once().ordered().and_return([
            "interface ve 1234",
            " ip address 1.2.3.1/27",
            " ip helper-address 10.10.10.1",
            "!",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.mocked_ssh_client.should_receive("do").with_args("interface ve 1234").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("enable").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("ip helper-address 10.10.10.2").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("write memory").and_return([]).once().ordered()

        self.switch.add_dhcp_relay_server(1234, IPAddress('10.10.10.2'))

    def test_add_same_dhcp_relay_server_fails(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan | begin vlan 1234").once().ordered().and_return([
            "vlan 1234",
            " router-interface ve 1234",
            "!",
        ])
        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface ve 1234").once().ordered().and_return([
            "interface ve 1234",
            " ip address 1.2.3.1/27",
            " ip helper-address 10.10.10.1",
            "!",
        ])

        with self.assertRaises(DhcpRelayServerAlreadyExists) as expect:
            self.switch.add_dhcp_relay_server(1234, IPAddress('10.10.10.1'))

        assert_that(str(expect.exception), equal_to("DHCP relay server 10.10.10.1 already exists on VLAN 1234"))

    def test_remove_dhcp_relay_server(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan | begin vlan 1234").once().ordered().and_return([
            "vlan 1234",
            " router-interface ve 1234",
            "!",
        ])
        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface ve 1234").once().ordered().and_return([
            "interface ve 1234",
            " ip address 1.2.3.1/27",
            " ip helper-address 10.10.10.1",
            "!",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.mocked_ssh_client.should_receive("do").with_args("interface ve 1234").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("enable").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("no ip helper-address 10.10.10.1").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("write memory").and_return([]).once().ordered()

        self.switch.remove_dhcp_relay_server(1234, IPAddress('10.10.10.1'))

    def test_remove_non_existent_dhcp_relay_server_fails(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan | begin vlan 1234").once().ordered().and_return([
            "vlan 1234",
            " router-interface ve 1234",
            "!",
        ])
        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface ve 1234").once().ordered().and_return([
            "interface ve 1234",
            " ip address 1.2.3.1/27",
            "!",
        ])

        with self.assertRaises(UnknownDhcpRelayServer) as expect:
            self.switch.remove_dhcp_relay_server(1234, IPAddress('10.10.10.1'))

        assert_that(str(expect.exception), equal_to("DHCP relay server 10.10.10.1 not found on VLAN 1234"))
