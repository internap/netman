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

import mock
from flexmock import flexmock, flexmock_teardown
from hamcrest import assert_that, has_length, equal_to, is_, none, empty
from netaddr import IPNetwork
from netaddr.ip import IPAddress

from netman.adapters.switches import brocade_factory_ssh, brocade_factory_telnet
from netman.adapters.switches.brocade import Brocade, parse_if_ranges
from netman.adapters.switches.util import SubShell
from netman.core.objects.access_groups import IN, OUT
from netman.core.objects.exceptions import IPNotAvailable, UnknownVlan, UnknownIP, UnknownAccessGroup, BadVlanNumber, \
    BadVlanName, UnknownInterface, TrunkVlanNotSet, UnknownVrf, VlanVrfNotSet, VrrpAlreadyExistsForVlan, BadVrrpPriorityNumber, BadVrrpGroupNumber, \
    BadVrrpTimers, BadVrrpTracking, NoIpOnVlanForVrrp, VrrpDoesNotExistForVlan, UnknownDhcpRelayServer, DhcpRelayServerAlreadyExists, \
    VlanAlreadyExist, InvalidAccessGroupName, IPAlreadySet
from netman.core.objects.interface_states import OFF, ON
from netman.core.objects.port_modes import ACCESS, TRUNK
from netman.core.objects.switch_descriptor import SwitchDescriptor


class BrocadeTest(unittest.TestCase):

    def setUp(self):
        self.switch = Brocade(SwitchDescriptor(model='brocade', hostname="my.hostname"), None)
        SubShell.debug = True
        self.shell_mock = flexmock()
        self.switch.shell = self.shell_mock

    def tearDown(self):
        flexmock_teardown()

    def test_switch_has_a_logger_configured_with_the_switch_name(self):
        assert_that(self.switch.logger.name, is_(Brocade.__module__ + ".my.hostname"))

    def test_ip_redirect_enable(self):
        self.shell_mock.should_receive("do").with_args("show vlan 1234").once().ordered().and_return(
            vlan_with_vif_display(1234, 999, name="Shizzle")
        )
        self.shell_mock.should_receive("do").with_args("show running-config interface ve 999").once().ordered().and_return([
            "interface ve 999",
            "!",
        ])

        self.shell_mock.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.shell_mock.should_receive("do").with_args("interface ve 999").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("enable").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("ip redirect").once().ordered()
        self.shell_mock.should_receive("do").with_args("exit").and_return([]).twice()

        self.switch.set_vlan_icmp_redirects_state(1234, True)

    def test_ip_redirect_disable(self):
        self.shell_mock.should_receive("do").with_args("show vlan 1234").once().ordered().and_return(
            vlan_with_vif_display(1234, 999, name="Shizzle")
        )
        self.shell_mock.should_receive("do").with_args("show running-config interface ve 999").once().ordered().and_return([
            "interface ve 999",
            "!",
        ])

        self.shell_mock.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.shell_mock.should_receive("do").with_args("interface ve 999").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("enable").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("no ip redirect").once().ordered()
        self.shell_mock.should_receive("do").with_args("exit").and_return([]).twice()

        self.switch.set_vlan_icmp_redirects_state(1234, False)

    def test_set_vlan_icmp_redirects_state_without_interface_creates_it(self):
        self.shell_mock.should_receive("do").with_args("show vlan 1234").once().ordered().and_return(
            vlan_with_vif_display(1234, 999, name="Shizzle")
        )
        self.shell_mock.should_receive("do").with_args("show running-config interface ve 999").once().ordered().and_return([
            "Error - ve 999 was not configured"
        ])

        self.shell_mock.should_receive("do").with_args("configure terminal").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("interface ve 999").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("enable").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("no ip redirect").once().ordered()
        self.shell_mock.should_receive("do").with_args("exit").and_return([]).twice()

        self.switch.set_vlan_icmp_redirects_state(1234, False)

    def test_set_vlan_icmp_redirects_state_unknown_vlan(self):
        self.shell_mock.should_receive("do").with_args("show vlan 1234").once().ordered().and_return([
            "Error: vlan 1234 is not configured"
        ])

        with self.assertRaises(UnknownVlan) as expect:
            self.switch.set_vlan_icmp_redirects_state(1234, False)

        assert_that(str(expect.exception), equal_to("Vlan 1234 not found"))

    def test_get_vlans(self):
        self.shell_mock.should_receive("do").with_args("show running-config vlan | begin vlan").once().ordered().and_return([
            "vlan 1 name DEFAULT-VLAN",
            ""
            " no untagged ethe 1/1 ethe 1/3 to 1/22",
            "!",
            "vlan 201",
            " tagged ethe 1/1",
            " router-interface ve 201",
            "!",
            "vlan 2222 name your-name-is-way-too-long-for-t",
            " tagged ethe 1/1",
            " untagged ethe 1/2",
            "!",
            "vlan 3333 name some-name",
            "!",
            "!"
        ])

        self.shell_mock.should_receive("do").with_args("show running-config interface").once()\
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
                ' no ip redirect'
                '!',
                'interface ve 1203',
                '!',
                'interface ve 3993',
                ' port-name Another-port-name',
                ' ip address 4.4.4.0/27',
                '!'])

        vlan1, vlan201, vlan2222, vlan3333 = self.switch.get_vlans()

        assert_that(vlan1.number, equal_to(1))
        assert_that(vlan1.name, equal_to("default"))
        assert_that(vlan1.ips, has_length(0))
        assert_that(vlan1.vrf_forwarding, is_(none()))
        assert_that(vlan201.number, equal_to(201))
        assert_that(vlan201.name, equal_to(None))
        assert_that(vlan201.ips, has_length(3))
        assert_that(vlan201.vrf_forwarding, is_("SHIZZLE"))
        assert_that(vlan201.icmp_redirects, equal_to(False))
        assert_that(vlan2222.number, equal_to(2222))
        assert_that(vlan2222.name, equal_to("your-name-is-way-too-long-for-t"))
        assert_that(vlan2222.ips, has_length(0))
        assert_that(vlan2222.icmp_redirects, equal_to(True))
        assert_that(vlan3333.number, equal_to(3333))
        assert_that(vlan3333.name, equal_to("some-name"))
        assert_that(vlan3333.ips, has_length(0))

        vrrp_group1, vrrp_group2 = vlan201.vrrp_groups
        assert_that(len(vrrp_group1.ips), equal_to(1))
        assert_that(vrrp_group1.ips[0], equal_to(IPAddress('1.1.1.2')))
        assert_that(vrrp_group1.hello_interval, equal_to(5))
        assert_that(vrrp_group1.dead_interval, equal_to(15))
        assert_that(vrrp_group1.priority, equal_to(110))
        assert_that(vrrp_group1.track_id, equal_to('ethernet 1/1'))
        assert_that(vrrp_group1.track_decrement, equal_to(50))
        assert_that(len(vrrp_group2.ips), equal_to(2))
        assert_that(vrrp_group2.ips[0], equal_to(IPAddress('1.1.1.3')))
        assert_that(vrrp_group2.ips[1], equal_to(IPAddress('1.1.1.4')))
        assert_that(vrrp_group2.hello_interval, equal_to(5))
        assert_that(vrrp_group2.dead_interval, equal_to(15))
        assert_that(vrrp_group2.priority, equal_to(110))
        assert_that(vrrp_group2.track_id, equal_to('ethernet 1/1'))
        assert_that(vrrp_group2.track_decrement, equal_to(50))

        assert_that(len(vlan201.dhcp_relay_servers), equal_to(2))
        assert_that(str(vlan201.dhcp_relay_servers[0]), equal_to('10.10.10.1'))
        assert_that(str(vlan201.dhcp_relay_servers[1]), equal_to('10.10.10.2'))

    def test_get_vlan_with_no_interface(self):
        self.shell_mock.should_receive("do").with_args("show vlan 1750").once().ordered().and_return(
            vlan_display(1750)
        )

        vlan = self.switch.get_vlan(1750)

        assert_that(vlan.number, is_(1750))
        assert_that(vlan.name, is_(None))
        assert_that(vlan.access_groups[IN], is_(none()))
        assert_that(vlan.access_groups[OUT], is_(none()))
        assert_that(vlan.vrf_forwarding, is_(none()))
        assert_that(vlan.ips, is_(empty()))
        assert_that(vlan.vrrp_groups, is_(empty()))
        assert_that(vlan.dhcp_relay_servers, is_(empty()))

    def test_get_vlan_with_an_empty_interface(self):
        self.shell_mock.should_receive("do").with_args("show vlan 1750").once().ordered().and_return(
            vlan_with_vif_display(1750, 999, name="Shizzle")
        )

        self.shell_mock.should_receive("do").with_args("show running-config interface ve 999").once().ordered().and_return([
            "interface ve 999",
            "!",
        ])

        vlan = self.switch.get_vlan(1750)

        assert_that(vlan.number, is_(1750))
        assert_that(vlan.name, is_("Shizzle"))
        assert_that(vlan.access_groups[IN], is_(none()))
        assert_that(vlan.access_groups[OUT], is_(none()))
        assert_that(vlan.vrf_forwarding, is_(none()))
        assert_that(vlan.ips, is_(empty()))
        assert_that(vlan.vrrp_groups, is_(empty()))
        assert_that(vlan.dhcp_relay_servers, is_(empty()))

    def test_get_vlan_with_a_full_interface(self):
        self.shell_mock.should_receive("do").with_args("show vlan 1750").once().ordered().and_return(
            vlan_with_vif_display(1750, 1750, name="Shizzle")
        )

        self.shell_mock.should_receive("do").with_args("show running-config interface ve 1750").once().ordered().and_return([
            "interface ve 1750",
            " vrf forwarding SHIZZLE",
            " ip address 1.1.1.1/24",
            " ip address 2.1.1.1/27",
            " ip address 1.1.1.9/24 secondary",
            " ip access-group ACL-IN in",
            " ip access-group ACL-OUT out",
            " ip helper-address 10.10.10.1",
            " ip helper-address 10.10.10.2",
            " ip vrrp-extended auth-type simple-text-auth VLAN201",
            " ip vrrp-extended vrid 1",
            "  backup priority 110 track-priority 50",
            "  ip-address 1.1.1.2",
            "  hello-interval 5",
            "  dead-interval 15",
            "  advertise backup",
            "  track-port ethernet 1/1",
            "  activate",
            " ip vrrp-extended vrid 2",
            "  backup priority 110 track-priority 50",
            "  ip-address 1.1.1.3",
            "  ip-address 1.1.1.4",
            "  hello-interval 5",
            "  dead-interval 15",
            "  advertise backup",
            "  track-port ethernet 1/1",
            "  activate",
            "!",
        ])

        vlan = self.switch.get_vlan(1750)

        assert_that(vlan.number, is_(1750))
        assert_that(vlan.name, is_("Shizzle"))
        assert_that(vlan.access_groups[IN], is_("ACL-IN"))
        assert_that(vlan.access_groups[OUT], is_("ACL-OUT"))
        assert_that(vlan.vrf_forwarding, is_("SHIZZLE"))
        assert_that(vlan.ips, has_length(3))
        assert_that(vlan.icmp_redirects, equal_to(True))

        vrrp_group1, vrrp_group2 = vlan.vrrp_groups
        assert_that(len(vrrp_group1.ips), equal_to(1))
        assert_that(vrrp_group1.ips[0], equal_to(IPAddress('1.1.1.2')))
        assert_that(vrrp_group1.hello_interval, equal_to(5))
        assert_that(vrrp_group1.dead_interval, equal_to(15))
        assert_that(vrrp_group1.priority, equal_to(110))
        assert_that(vrrp_group1.track_id, equal_to('ethernet 1/1'))
        assert_that(vrrp_group1.track_decrement, equal_to(50))
        assert_that(len(vrrp_group2.ips), equal_to(2))
        assert_that(vrrp_group2.ips[0], equal_to(IPAddress('1.1.1.3')))
        assert_that(vrrp_group2.ips[1], equal_to(IPAddress('1.1.1.4')))
        assert_that(vrrp_group2.hello_interval, equal_to(5))
        assert_that(vrrp_group2.dead_interval, equal_to(15))
        assert_that(vrrp_group2.priority, equal_to(110))
        assert_that(vrrp_group2.track_id, equal_to('ethernet 1/1'))
        assert_that(vrrp_group2.track_decrement, equal_to(50))

        assert_that(len(vlan.dhcp_relay_servers), equal_to(2))
        assert_that(str(vlan.dhcp_relay_servers[0]), equal_to('10.10.10.1'))
        assert_that(str(vlan.dhcp_relay_servers[1]), equal_to('10.10.10.2'))

    def test_get_vlan_interface_with_untagged_interface(self):
        self.shell_mock.should_receive("do").with_args("show vlan 1").once().ordered().and_return(
                vlan_display(1, 'DEFAULT-VLAN', tagged_port_str="ethe 1/2 ethe 1/23 to 1/24")
        )

        vlan_interfaces = self.switch.get_vlan_interfaces(1)

        assert_that(vlan_interfaces, equal_to(["ethernet 1/2", "ethernet 1/23", "ethernet 1/24"]))

    def test_get_vlan_interface_with_tagged_interface(self):
        self.shell_mock.should_receive("do").with_args("show vlan 1").once().ordered().and_return(
                vlan_display(1, 'DEFAULT-VLAN', untagged_port_str="ethe 1/2")
        )

        vlan_interfaces = self.switch.get_vlan_interfaces(1)

        assert_that(vlan_interfaces, equal_to(["ethernet 1/2"]))

    def test_get_vlan_interface_with_untagged_and_tagged_interface(self):
        self.shell_mock.should_receive("do").with_args("show vlan 1").once().ordered().and_return(
                vlan_display(1, 'DEFAULT-VLAN', untagged_port_str="ethe 1/1", tagged_port_str="ethe 1/2 ethe 1/23 to 1/24")
        )

        vlan_interfaces = self.switch.get_vlan_interfaces(1)

        assert_that(vlan_interfaces, equal_to(["ethernet 1/1", "ethernet 1/2", "ethernet 1/23", "ethernet 1/24"]))

    def test_get_vlan_interface_unknown_vlan(self):
        self.shell_mock.should_receive("do").with_args("show vlan inexistent").once().ordered().and_return([
            "Error: vlan inexistent is not configured"
        ])

        with self.assertRaises(UnknownVlan):
            self.switch.get_vlan_interfaces("inexistent")

    def test_get_vlan_unknown_interface_raises(self):
        self.shell_mock.should_receive("do").with_args("show vlan 1750").once().ordered().and_return([
            "Error: vlan 1750 is not configured"
        ])

        with self.assertRaises(UnknownVlan) as expect:
            self.switch.get_vlan(1750)

        assert_that(str(expect.exception), equal_to("Vlan 1750 not found"))

    def test_get_vlan_with_both_ip_and_ipv6_vrrp_groups_ipv6_is_ignored(self):
        self.shell_mock.should_receive("do").with_args("show vlan 1750").once().ordered().and_return(
                vlan_with_vif_display(1750, 1750, name="Shizzle")
        )

        self.shell_mock.should_receive("do").with_args("show running-config interface ve 1750").once()\
            .ordered().and_return([
                'interface ve 1750',
                'port-name vrrp-extended vrid 42',
                ' ip address 10.241.0.33/27',
                ' no ip redirect',
                ' ip helper-address 10.10.10.1',
                ' ip helper-address 10.10.10.2',
                ' ipv6 address 2001:47c2:19:5::2/64',
                ' ipv6 address 2001:47c2:19:5::3/64',
                ' ipv6 nd suppress-ra',
                ' ip vrrp-extended vrid 42',
                '  backup priority 130 track-priority 20',
                '  ip-address 1.1.1.2',
                '  advertise backup',
                '  hello-interval 4',
                '  track-port ethernet 1/3',
                '  activate',
                ' ipv6 vrrp-extended vrid 43',
                '  backup priority 110 track-priority 50',
                '  ipv6-address 2001:47c2:19:5::1',
                '  advertise backup',
                '  hello-interval 5',
                '  track-port ethernet 1/2',
                ' activate',
                '!'])

        vlan = self.switch.get_vlan(1750)

        assert_that(vlan.number, is_(1750))
        assert_that(vlan.ips, has_length(1))
        assert_that(vlan.icmp_redirects, equal_to(False))

        assert_that(vlan.vrrp_groups, has_length(1))
        vrrp_group1 = vlan.vrrp_groups[0]
        assert_that(len(vrrp_group1.ips), equal_to(1))
        assert_that(vrrp_group1.ips[0], equal_to(IPAddress('1.1.1.2')))
        assert_that(vrrp_group1.hello_interval, equal_to(4))
        assert_that(vrrp_group1.priority, equal_to(130))
        assert_that(vrrp_group1.track_id, equal_to('ethernet 1/3'))
        assert_that(vrrp_group1.track_decrement, equal_to(20))

        assert_that(len(vlan.dhcp_relay_servers), equal_to(2))
        assert_that(str(vlan.dhcp_relay_servers[0]), equal_to('10.10.10.1'))
        assert_that(str(vlan.dhcp_relay_servers[1]), equal_to('10.10.10.2'))

    def test_get_vlan_with_both_ip_and_ipv6_in_the_same_vrrp_group(self):
        self.shell_mock.should_receive("do").with_args("show vlan 1750").once().ordered().and_return(
                vlan_with_vif_display(1750, 1750, name="Shizzle")
        )

        self.shell_mock.should_receive("do").with_args("show running-config interface ve 1750").once() \
            .ordered()\
            .and_return(['interface ve 1750',
                         'port-name vrrp-extended vrid 42',
                         ' ip address 10.241.0.33/27',
                         ' no ip redirect',
                         ' ip helper-address 10.10.10.1',
                         ' ip helper-address 10.10.10.2',
                         ' ipv6 address 2001:47c2:19:5::2/64',
                         ' ipv6 address 2001:47c2:19:5::3/64',
                         ' ipv6 nd suppress-ra',
                         ' ip vrrp-extended vrid 42',
                         '  backup priority 130 track-priority 20',
                         '  ip-address 1.1.1.2',
                         '  advertise backup',
                         '  hello-interval 4',
                         '  track-port ethernet 1/3',
                         '  activate',
                         ' ipv6 vrrp-extended vrid 42',
                         '  backup priority 170 track-priority 40',
                         '  ipv6-address 2001:47c2:19:5::1',
                         '  advertise backup',
                         '  hello-interval 400',
                         '  track-port ethernet 4/6',
                         ' activate',
                         '!'])

        vlan = self.switch.get_vlan(1750)

        assert_that(vlan.number, is_(1750))
        assert_that(vlan.ips, has_length(1))
        assert_that(vlan.icmp_redirects, equal_to(False))

        vrrp_group = vlan.vrrp_groups[0]
        assert_that(len(vrrp_group.ips), equal_to(1))
        assert_that(vrrp_group.ips[0], equal_to(IPAddress('1.1.1.2')))
        assert_that(vrrp_group.hello_interval, equal_to(4))
        assert_that(vrrp_group.priority, equal_to(130))
        assert_that(vrrp_group.track_id, equal_to('ethernet 1/3'))
        assert_that(vrrp_group.track_decrement, equal_to(20))

    def test_add_vlan(self):
        self.shell_mock.should_receive("do").with_args("show vlan 2999").and_return([
            "Error: vlan 2999 is not configured"
        ])

        self.shell_mock.should_receive("do").with_args("configure terminal").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("vlan 2999 name Gertrude").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()

        self.switch.add_vlan(2999, name="Gertrude")

    def test_add_vlan_bad_number(self):
        self.shell_mock.should_receive("do").with_args("show vlan 5000").and_return([
            "Error: vlan 5000 is not configured"
        ])

        self.shell_mock.should_receive("do").with_args("configure terminal").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("vlan 5000 name Gertrude").once().ordered().and_return([
            "Error: vlan id 4091 is outside of allowed max of 4090"
        ])
        self.shell_mock.should_receive("do").with_args("exit").once().ordered()

        with self.assertRaises(BadVlanNumber) as expect:
            self.switch.add_vlan(5000, name="Gertrude")

        assert_that(str(expect.exception), equal_to("Vlan number is invalid"))

    def test_add_vlan_bad_name(self):
        self.shell_mock.should_receive("do").with_args("show vlan 5000").and_return([
            "Error: vlan 5000 is not configured"
        ])

        self.shell_mock.should_receive("do").with_args("configure terminal").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("vlan 5000 name Gertr ude").once().ordered().and_return([
            "Invalid input -> ude"
        ])
        self.shell_mock.should_receive("do").with_args("exit").once().ordered()

        with self.assertRaises(BadVlanName) as expect:
            self.switch.add_vlan(5000, name="Gertr ude")

        assert_that(str(expect.exception), equal_to("Vlan name is invalid"))

    def test_add_vlan_no_name(self):
        self.shell_mock.should_receive("do").with_args("show vlan 2999").and_return([
            "Error: vlan 2999 is not configured"
        ])

        self.shell_mock.should_receive("do").with_args("configure terminal").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("vlan 2999").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()

        self.switch.add_vlan(2999)

    def test_add_vlan_already_exist_fails(self):
        self.shell_mock.should_receive("do").with_args("show vlan 2999").and_return(
            vlan_display(2999)
        )

        with self.assertRaises(VlanAlreadyExist) as expect:
            self.switch.add_vlan(2999)

        assert_that(str(expect.exception), equal_to("Vlan 2999 already exists"))

    def test_remove_vlan(self):
        self.shell_mock.should_receive("do").with_args("show vlan 2999").once().ordered().and_return(
            vlan_display(2999)
        )

        self.shell_mock.should_receive("do").with_args("configure terminal").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("no vlan 2999").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("exit").and_return([]).once().ordered()

        self.switch.remove_vlan(2999)

    def test_remove_vlan_invalid_vlan_raises(self):
        self.shell_mock.should_receive("do").with_args("show vlan 2999").once().ordered().and_return([
            "Error: vlan 2999 is not configured"
        ])

        self.shell_mock.should_receive("do").with_args("configure terminal").never()

        with self.assertRaises(UnknownVlan) as expect:
            self.switch.remove_vlan(2999)

        assert_that(str(expect.exception), equal_to("Vlan 2999 not found"))

    def test_set_access_vlan(self):
        self.shell_mock.should_receive("do").with_args("show vlan 2999").once().ordered().and_return(
            vlan_display(2999)
        )

        self.shell_mock.should_receive("do").with_args("configure terminal").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("vlan 2999").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("untagged ethernet 1/4").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()

        self.switch.set_access_vlan("ethernet 1/4", vlan=2999)

    def test_set_access_vlan_invalid_vlan_raises(self):
        self.shell_mock.should_receive("do").with_args("show vlan 2999").once().ordered().and_return([
            "Error: vlan 2999 is not configured"
        ])

        with self.assertRaises(UnknownVlan) as expect:
            self.switch.set_access_vlan("ethernet 1/4", vlan=2999)

        assert_that(str(expect.exception), equal_to("Vlan 2999 not found"))

    def test_set_access_vlan_invalid_interface_raises(self):
        self.shell_mock.should_receive("do").with_args("show vlan 2999").once().ordered().and_return(
            vlan_display(2999)
        )

        self.shell_mock.should_receive("do").with_args("configure terminal").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("vlan 2999").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("untagged ethernet 9/999").once().ordered().and_return([
            'Invalid input -> 9/999'
            'Type ? for a list'
        ])
        self.shell_mock.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()

        with self.assertRaises(UnknownInterface) as expect:
            self.switch.set_access_vlan("ethernet 9/999", vlan=2999)

        assert_that(str(expect.exception), equal_to("Unknown interface ethernet 9/999"))

    def test_reset_interfaces_works(self):
        self.shell_mock.should_receive("do").with_args("show vlan ethernet 1/4").once().ordered().and_return([])

        self.shell_mock.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.shell_mock.should_receive("do").with_args("no interface ethernet 1/4").once().ordered().and_return([])
        self.shell_mock.should_receive("do").with_args("exit").once().ordered()

        self.switch.reset_interface("ethernet 1/4")

    def test_reset_interfaces_on_invalid_input_raises_unknown_interface(self):
        self.shell_mock.should_receive("do").with_args("show vlan ethernet 9/999").once().ordered().and_return([
            'Invalid input -> 9/999',
            'Type ? for a list'])

        with self.assertRaises(UnknownInterface):
            self.switch.reset_interface("ethernet 9/999")

    def test_reset_interfaces_on_invalid_interface_raises_unknown_interface(self):
        self.shell_mock.should_receive("do").with_args("show vlan ethernet 1/64").once().ordered().and_return([
            'Error - invalid interface 1/64'])

        with self.assertRaises(UnknownInterface):
            self.switch.reset_interface("ethernet 1/64")

    def test_reset_interfaces_on_invalid_slot_raises_unknown_interface(self):
        self.shell_mock.should_receive("do").with_args("show vlan ethernet 2/1").once().ordered().and_return([
            'Error - interface 2/1 is not an ETHERNET interface'])

        with self.assertRaises(UnknownInterface):
            self.switch.reset_interface("ethernet 2/1")

    def test_reset_interfaces_cleans_tagged_vlans(self):
        self.shell_mock.should_receive("do").with_args("show vlan ethernet 1/4").and_return(['VLAN: 1200  Untagged',
                                                                                             'VLAN: 1201  Tagged'])

        self.shell_mock.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.shell_mock.should_receive("do").with_args("vlan 1200").once().ordered().and_return([])
        self.shell_mock.should_receive("do").with_args("no untagged ethernet 1/4").once().ordered().and_return([])
        self.shell_mock.should_receive("do").with_args("vlan 1201").once().ordered().and_return([])
        self.shell_mock.should_receive("do").with_args("no tagged ethernet 1/4").once().ordered().and_return([])
        self.shell_mock.should_receive("do").with_args("exit").and_return([]).once().ordered()

        self.shell_mock.should_receive("do").with_args("no interface ethernet 1/4").once().ordered().and_return([])
        self.shell_mock.should_receive("do").with_args("exit").and_return([]).once().ordered()

        self.switch.reset_interface("ethernet 1/4")

    def test_unset_interface_access_vlan(self):
        self.shell_mock.should_receive("do").with_args("show vlan brief | include ethe 1/4").once().ordered().and_return([
            "1202     your-name-                                        1202  -  Untagged Ports : ethe 1/10"
        ])

        self.shell_mock.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.shell_mock.should_receive("do").with_args("vlan 1202").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("no untagged ethernet 1/4").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()

        self.switch.unset_interface_access_vlan("ethernet 1/4")

    def test_unset_interface_access_vlan_invalid_interface_raises(self):
        self.shell_mock.should_receive("do").with_args("show vlan brief | include ethe 9/999").once().ordered().and_return([])

        with self.assertRaises(UnknownInterface) as expect:
            self.switch.unset_interface_access_vlan("ethernet 9/999")

        assert_that(str(expect.exception), equal_to("Unknown interface ethernet 9/999"))

    def test_set_access_mode_does_nothing_if_nothing_is_set(self):
        self.shell_mock.should_receive("do").with_args("show vlan ethernet 1/4").once().ordered().and_return([
            "VLAN: 1  Untagged"
        ])

        self.shell_mock.should_receive("do").with_args("configure terminal").never()

        self.switch.set_access_mode("ethernet 1/4")

    def test_set_access_mode_invalid_interface_raises(self):
        self.shell_mock.should_receive("do").with_args("show vlan ethernet 9/999").once().ordered().and_return([
            'Invalid input -> 9/999'
            'Type ? for a list'
        ])

        with self.assertRaises(UnknownInterface) as expect:
            self.switch.set_access_mode("ethernet 9/999")

        assert_that(str(expect.exception), equal_to("Unknown interface ethernet 9/999"))

    def test_set_access_mode_does_nothing_if_only_an_untagged_vlan_not_knowing_if_it_is_an_access_or_native(self):
        self.shell_mock.should_receive("do").with_args("show vlan ethernet 1/4").once().ordered().and_return([
            "VLAN: 123  Untagged"
        ])

        self.shell_mock.should_receive("do").with_args("configure terminal").never()

        self.switch.set_access_mode("ethernet 1/4")

    def test_set_access_mode_removes_all_tagged_vlans_and_the_untagged_because_it_is_a_native_vlan(self):
        self.shell_mock.should_receive("do").with_args("show vlan ethernet 1/4").once().ordered().and_return([
            "VLAN: 100  Tagged",
            "VLAN: 300  Untagged",
        ])

        self.shell_mock.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.shell_mock.should_receive("do").with_args("vlan 100").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("no tagged ethernet 1/4").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("vlan 300").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("no untagged ethernet 1/4").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()

        self.switch.set_access_mode("ethernet 1/4")

    def test_set_trunk_mode(self):
        self.shell_mock.should_receive("do").with_args("show vlan ethernet 1/4").once().ordered().and_return([
            "VLAN: 1  Untagged"
        ])

        self.shell_mock.should_receive("do").with_args("configure terminal").never()

        self.switch.set_trunk_mode("ethernet 1/4")

    def test_set_trunk_mode_invalid_interface_raises(self):
        self.shell_mock.should_receive("do").with_args("show vlan ethernet 9/999").once().ordered().and_return([
            'Invalid input -> 9/999'
            'Type ? for a list'
        ])

        with self.assertRaises(UnknownInterface) as expect:
            self.switch.set_trunk_mode("ethernet 9/999")

        assert_that(str(expect.exception), equal_to("Unknown interface ethernet 9/999"))

    def test_add_trunk_vlan(self):
        self.shell_mock.should_receive("do").with_args("show vlan 2999").once().ordered().and_return(
            vlan_display(2999)
        )

        self.shell_mock.should_receive("do").with_args("configure terminal").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("vlan 2999").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("tagged ethernet 1/1").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()

        self.switch.add_trunk_vlan("ethernet 1/1", vlan=2999)

    def test_add_trunk_vlan_invalid_interface_raises(self):
        self.shell_mock.should_receive("do").with_args("show vlan 2999").once().ordered().and_return(
            vlan_display(2999)
        )

        self.shell_mock.should_receive("do").with_args("configure terminal").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("vlan 2999").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("tagged ethernet 9/999").once().ordered().and_return([
            'Invalid input -> 9/999'
            'Type ? for a list'
        ])
        self.shell_mock.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()

        with self.assertRaises(UnknownInterface) as expect:
            self.switch.add_trunk_vlan("ethernet 9/999", vlan=2999)

        assert_that(str(expect.exception), equal_to("Unknown interface ethernet 9/999"))

    def test_add_trunk_vlan_invalid_vlan_raises(self):
        self.shell_mock.should_receive("do").with_args("show vlan 2999").once().ordered().and_return([
            "Error: vlan 2999 is not configured"
        ])
        self.shell_mock.should_receive("do").with_args("configure terminal").never()

        with self.assertRaises(UnknownVlan) as expect:
            self.switch.add_trunk_vlan("ethernet 1/1", vlan=2999)

        assert_that(str(expect.exception), equal_to("Vlan 2999 not found"))

    def test_remove_trunk_vlan(self):
        self.shell_mock.should_receive("do").with_args("show vlan 2999").once().ordered().and_return(
            vlan_display(2999)
        )

        self.shell_mock.should_receive("do").with_args("configure terminal").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("vlan 2999").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("no tagged ethernet 1/11").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()

        self.switch.remove_trunk_vlan("ethernet 1/11", vlan=2999)

    def test_remove_trunk_vlan_invalid_vlan_raises(self):
        self.shell_mock.should_receive("do").with_args("show vlan 2999").once().ordered().and_return([
            "Error: vlan 2999 is not configured"
        ])
        with self.assertRaises(UnknownVlan) as expect:
            self.switch.remove_trunk_vlan("ethernet 1/2", vlan=2999)

        assert_that(str(expect.exception), equal_to("Vlan 2999 not found"))

    def test_remove_trunk_vlan_not_set_raises(self):
        self.shell_mock.should_receive("do").with_args("show vlan 2999").once().ordered().and_return(
            vlan_display(2999)
        )

        self.shell_mock.should_receive("do").with_args("configure terminal").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("vlan 2999").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("no tagged ethernet 1/14").and_return([
            "Error: ports ethe 1/14 are not tagged members of vlan 2999"
        ]).once().ordered()
        self.shell_mock.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()

        with self.assertRaises(TrunkVlanNotSet) as expect:
            self.switch.remove_trunk_vlan("ethernet 1/14", vlan=2999)

        assert_that(str(expect.exception), equal_to("Trunk Vlan is not set on interface ethernet 1/14"))

    def test_remove_trunk_vlan_invalid_interface_raises(self):
        self.shell_mock.should_receive("do").with_args("show vlan 2999").once().ordered().and_return(
            vlan_display(2999)
        )

        self.shell_mock.should_receive("do").with_args("configure terminal").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("vlan 2999").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("no tagged ethernet 9/999").and_return([
            "Invalid input -> 1/99",
            "Type ? for a list",
        ]).once().ordered()
        self.shell_mock.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()

        with self.assertRaises(UnknownInterface) as expect:
            self.switch.remove_trunk_vlan("ethernet 9/999", vlan=2999)

        assert_that(str(expect.exception), equal_to("Unknown interface ethernet 9/999"))

    def test_set_interface_state_off(self):
        self.shell_mock.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.shell_mock.should_receive("do").with_args("interface ethernet 1/4").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("disable").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()

        self.switch.set_interface_state("ethernet 1/4", OFF)

    def test_set_interface_state_off_invalid_interface_raises(self):
        self.shell_mock.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.shell_mock.should_receive("do").with_args("interface ethernet 9/999").once().ordered().and_return([
            'Invalid input -> 9/999'
            'Type ? for a list'
        ])
        self.shell_mock.should_receive("do").with_args("exit").and_return([]).once().ordered()

        with self.assertRaises(UnknownInterface) as expect:
            self.switch.set_interface_state("ethernet 9/999", OFF)

        assert_that(str(expect.exception), equal_to("Unknown interface ethernet 9/999"))

    def test_set_interface_state_on(self):
        self.shell_mock.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.shell_mock.should_receive("do").with_args("interface ethernet 1/4").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("enable").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()

        self.switch.set_interface_state("ethernet 1/4", ON)

    def test_set_interface_state_on_invalid_interface_raises(self):
        self.shell_mock.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.shell_mock.should_receive("do").with_args("interface ethernet 9/999").once().ordered().and_return([
            'Invalid input -> 9/999'
            'Type ? for a list'
        ])
        self.shell_mock.should_receive("do").with_args("exit").and_return([]).once().ordered()

        with self.assertRaises(UnknownInterface) as expect:
            self.switch.set_interface_state("ethernet 9/999", ON)

        assert_that(str(expect.exception), equal_to("Unknown interface ethernet 9/999"))

    def test_set_interface_native_vlan_on_trunk(self):
        self.shell_mock.should_receive("do").with_args("show vlan 2999").once().ordered().and_return(
            vlan_display(2999)
        )

        self.shell_mock.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.shell_mock.should_receive("do").with_args("vlan 2999").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("untagged ethernet 1/4").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()

        self.switch.set_interface_native_vlan("ethernet 1/4", vlan=2999)

    def test_set_interface_native_vlan_on_trunk_invalid_interface_raises(self):
        self.shell_mock.should_receive("do").with_args("show vlan 2999").once().ordered().and_return(
            vlan_display(2999)
        )

        self.shell_mock.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.shell_mock.should_receive("do").with_args("vlan 2999").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("untagged ethernet 9/999").once().ordered().and_return([
            'Invalid input -> 9/999'
            'Type ? for a list'
        ])
        self.shell_mock.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()

        with self.assertRaises(UnknownInterface) as expect:
            self.switch.set_interface_native_vlan("ethernet 9/999", vlan=2999)

        assert_that(str(expect.exception), equal_to("Unknown interface ethernet 9/999"))

    def test_set_interface_native_vlan_on_trunk_invalid_vlan_raises(self):
        self.shell_mock.should_receive("do").with_args("show vlan 2999").once().ordered().and_return([
            "Error: vlan 2999 is not configured"
        ])

        self.shell_mock.should_receive("do").with_args("configure terminal").never()

        with self.assertRaises(UnknownVlan) as expect:
            self.switch.set_interface_native_vlan("ethernet 1/4", vlan=2999)

        assert_that(str(expect.exception), equal_to("Vlan 2999 not found"))

    def test_unset_interface_native_vlan_on_trunk(self):
        self.shell_mock.should_receive("do").with_args("show vlan brief | include ethe 1/4").once().ordered().and_return([
            "1202     your-name-                                        1202  -  Untagged Ports : ethe 1/10"
        ])

        self.shell_mock.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.shell_mock.should_receive("do").with_args("vlan 1202").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("no untagged ethernet 1/4").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()

        self.switch.unset_interface_native_vlan("ethernet 1/4")

    def test_unset_interface_native_vlan_on_trunk_invalid_interface_raises(self):
        self.shell_mock.should_receive("do").with_args("show vlan brief | include ethe 9/999").once().ordered().and_return([])

        with self.assertRaises(UnknownInterface) as expect:
            self.switch.unset_interface_native_vlan("ethernet 9/999")

        assert_that(str(expect.exception), equal_to("Unknown interface ethernet 9/999"))

    def test_add_ip_creates_router_interface(self):
        self.shell_mock.should_receive("do").with_args("show vlan 1234").once().ordered().and_return(
            vlan_display(1234)
        )

        self.shell_mock.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.shell_mock.should_receive("do").with_args("vlan 1234").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("router-interface ve 1234").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("interface ve 1234").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("enable").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("ip address 1.2.3.4/25").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()

        self.switch.add_ip_to_vlan(1234, IPNetwork("1.2.3.4/25"))

    def test_add_ip_doesnt_creates_router_interface_if_already_created(self):
        self.shell_mock.should_receive("do").with_args("show vlan 1234").once().ordered().and_return(
            vlan_with_vif_display(1234, 3333)
        )

        self.shell_mock.should_receive("do").with_args("show running-config interface ve 3333").once().ordered().and_return([
            "interface ve 3333",
            "!",
        ])

        self.shell_mock.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.shell_mock.should_receive("do").with_args("interface ve 3333").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("enable").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("ip address 1.2.3.4/25").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()

        self.switch.add_ip_to_vlan(1234, IPNetwork("1.2.3.4/25"))

    def test_add_ip_contained_in_a_subnet_already_present_requires_the_keyword_secondary(self):
        self.shell_mock.should_receive("do").with_args("show vlan 1234").once().ordered().and_return(
            vlan_with_vif_display(1234, 1234)
        )

        self.shell_mock.should_receive("do").with_args("show running-config interface ve 1234").once().ordered().and_return([
            "interface ve 1234",
            " ip address 1.2.3.1/24",
            "!",
        ])

        self.shell_mock.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.shell_mock.should_receive("do").with_args("interface ve 1234").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("enable").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("ip address 1.2.3.4/25 secondary").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()

        self.switch.add_ip_to_vlan(1234, IPNetwork("1.2.3.4/25"))

    def test_add_ip_already_defined_elsewhere_raises(self):
        self.shell_mock.should_receive("do").with_args("show vlan 1234").once().ordered().and_return(
            vlan_with_vif_display(1234, 1234)
        )

        self.shell_mock.should_receive("do").with_args("show running-config interface ve 1234").once().ordered().and_return([
            "interface ve 1234",
            "!",
        ])

        self.shell_mock.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.shell_mock.should_receive("do").with_args("interface ve 1234").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("enable").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("ip address 1.2.3.4/25").and_return([
            "IP/Port: Errno(6) Duplicate ip address"
        ]).once().ordered()
        self.shell_mock.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()

        with self.assertRaises(IPNotAvailable) as expect:
            self.switch.add_ip_to_vlan(1234, IPNetwork("1.2.3.4/25"))

        assert_that(str(expect.exception), equal_to("IP 1.2.3.4/25 is not available in this vlan"))

    def test_add_ip_already_a_subnet_of_another_ve(self):
        self.shell_mock.should_receive("do").with_args("show vlan 1234").once().ordered().and_return(
            vlan_with_vif_display(1234, 1234)
        )

        self.shell_mock.should_receive("do").with_args("show running-config interface ve 1234").once().ordered().and_return([
            "interface ve 1234",
            "!",
        ])

        self.shell_mock.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.shell_mock.should_receive("do").with_args("interface ve 1234").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("enable").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("ip address 1.2.3.4/25").and_return([
            "IP/Port: Errno(11) ip subnet overlap with another interface"
        ]).once().ordered()
        self.shell_mock.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()

        with self.assertRaises(IPNotAvailable) as expect:
            self.switch.add_ip_to_vlan(1234, IPNetwork("1.2.3.4/25"))

        assert_that(str(expect.exception), equal_to("IP 1.2.3.4/25 is not available in this vlan"))

    def test_add_ip_already_in_this_interface(self):
        self.shell_mock.should_receive("do").with_args("show vlan 1234").once().ordered().and_return(
            vlan_with_vif_display(1234, 1234)
        )

        self.shell_mock.should_receive("do").with_args("show running-config interface ve 1234").once().ordered().and_return([
            "interface ve 1234",
            " ip address 1.2.3.4/24",
            "!",
        ])

        with self.assertRaises(IPAlreadySet) as expect:
            self.switch.add_ip_to_vlan(1234, IPNetwork("1.2.3.4/25"))

        assert_that(str(expect.exception), equal_to("IP 1.2.3.4/25 is already present in this vlan as None"))

    def test_add_ip_already_in_this_interface_as_a_secondary(self):
        self.shell_mock.should_receive("do").with_args("show vlan 1234").once().ordered().and_return(
            vlan_with_vif_display(1234, 1234)
        )

        self.shell_mock.should_receive("do").with_args("show running-config interface ve 1234").once().ordered().and_return([
            "interface ve 1234",
            " ip address 1.2.3.4/24",
            " ip address 1.2.3.5/24 secondary",
            "!",
        ])

        with self.assertRaises(IPAlreadySet) as expect:
            self.switch.add_ip_to_vlan(1234, IPNetwork("1.2.3.5/25"))

        assert_that(str(expect.exception), equal_to("IP 1.2.3.5/25 is already present in this vlan as None"))

    def test_add_ip_to_unknown_vlan(self):
        self.shell_mock.should_receive("do").with_args("show vlan 1234").once().ordered().and_return([
            "Error: vlan 1234 is not configured"
        ])

        with self.assertRaises(UnknownVlan) as expect:
            self.switch.add_ip_to_vlan(1234, IPNetwork("1.2.3.5/25"))

        assert_that(str(expect.exception), equal_to("Vlan 1234 not found"))

    def test_remove_ip(self):
        self.shell_mock.should_receive("do").with_args("show vlan 1234").once().ordered().and_return(
            vlan_with_vif_display(1234, 1234)
        )

        self.shell_mock.should_receive("do").with_args("show running-config interface ve 1234").once().ordered().and_return([
            "interface ve 1234",
            " ip address 1.2.3.4/24",
            "!",
        ])

        self.shell_mock.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.shell_mock.should_receive("do").with_args("interface ve 1234").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("enable").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("no ip address 1.2.3.4/24").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()

        self.switch.remove_ip_from_vlan(1234, IPNetwork("1.2.3.4/24"))

    def test_remove_secondary_ip(self):
        self.shell_mock.should_receive("do").with_args("show vlan 1234").once().ordered().and_return(
            vlan_with_vif_display(1234, 1234)
        )

        self.shell_mock.should_receive("do").with_args("show running-config interface ve 1234").once().ordered().and_return([
            "interface ve 1234",
            " ip address 1.2.3.4/24",
            " ip address 1.2.3.5/24 secondary",
            "!",
        ])

        self.shell_mock.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.shell_mock.should_receive("do").with_args("interface ve 1234").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("enable").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("no ip address 1.2.3.5/24").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()

        self.switch.remove_ip_from_vlan(1234, IPNetwork("1.2.3.5/24"))

    def test_remove_ip_that_has_secondary_ip(self):
        self.shell_mock.should_receive("do").with_args("show vlan 1234").once().ordered().and_return(
            vlan_with_vif_display(1234, 1234)
        )

        self.shell_mock.should_receive("do").with_args("show running-config interface ve 1234").once().ordered().and_return([
            "interface ve 1234",
            " ip address 1.2.3.4/24",
            " ip address 1.2.3.5/24 secondary",
            " ip address 1.2.3.6/24 secondary",
            "!",
        ])

        self.shell_mock.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.shell_mock.should_receive("do").with_args("interface ve 1234").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("enable").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("no ip address 1.2.3.5/24").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("no ip address 1.2.3.6/24").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("no ip address 1.2.3.4/24").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("ip address 1.2.3.5/24").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("ip address 1.2.3.6/24 secondary").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()

        self.switch.remove_ip_from_vlan(1234, IPNetwork("1.2.3.4/24"))

    def test_remove_unknown_ip_raises(self):
        self.shell_mock.should_receive("do").with_args("show vlan 1234").once().ordered().and_return(
            vlan_with_vif_display(1234, 1234)
        )

        self.shell_mock.should_receive("do").with_args("show running-config interface ve 1234").once().ordered().and_return([
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
        self.shell_mock.should_receive("do").with_args("show vlan 1234").once().ordered().and_return(
            vlan_with_vif_display(1234, 1234)
        )

        self.shell_mock.should_receive("do").with_args("show running-config interface ve 1234").once().ordered().and_return([
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
        self.shell_mock.should_receive("do").with_args("show vlan 1234").once().ordered().and_return(
            vlan_display(1234)
        )
        with self.assertRaises(UnknownIP) as expect:
            self.switch.remove_ip_from_vlan(1234, IPNetwork("1.2.3.4/24"))

        assert_that(str(expect.exception), equal_to("IP 1.2.3.4/24 not found"))

    def test_remove_ip_on_unknown_vlan(self):
        self.shell_mock.should_receive("do").with_args("show vlan 1234").once().ordered().and_return([
            "Error: vlan 1234 is not configured"
        ])

        with self.assertRaises(UnknownVlan) as expect:
            self.switch.remove_ip_from_vlan(1234, IPNetwork("1.2.3.5/25"))

        assert_that(str(expect.exception), equal_to("Vlan 1234 not found"))

    def test_set_vlan_vrf_success(self):
        self.shell_mock.should_receive("do").with_args("show vlan 2500").once().ordered().and_return(
            vlan_with_vif_display(2500, 2500)
        )

        self.shell_mock.should_receive("do").with_args("show running-config interface ve 2500").and_return([
            "interface ve 2500",
            "!",
        ])
        self.shell_mock.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.shell_mock.should_receive("do").with_args("interface ve 2500").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("enable").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("vrf forwarding MYVRF").once().ordered().and_return([
            "Warning: All IPv4 and IPv6 addresses (including link-local) on this interface have been removed"
        ])
        self.shell_mock.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()

        self.switch.set_vlan_vrf(2500, "MYVRF")

    def test_set_vlan_vrf_incorrect_name(self):
        self.shell_mock.should_receive("do").with_args("show vlan 2500").once().ordered().and_return(
            vlan_with_vif_display(2500, 2500)
        )

        self.shell_mock.should_receive("do").with_args("show running-config interface ve 2500").and_return([
            "interface ve 2500",
            "!",
        ])

        self.shell_mock.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.shell_mock.should_receive("do").with_args("interface ve 2500").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("enable").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("vrf forwarding MYVRF").once().ordered().and_return([
            "Error - VRF(MYVRF) does not exist or Route-Distinguisher not specified or Address Family not configured"
        ])
        self.shell_mock.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()

        with self.assertRaises(UnknownVrf) as expect:
            self.switch.set_vlan_vrf(2500, "MYVRF")

        assert_that(str(expect.exception), equal_to("VRF name \"MYVRF\" was not configured."))

    def test_set_vlan_vrf_without_interface_creates_it(self):
        self.shell_mock.should_receive("do").with_args("show vlan 2500").once().ordered().and_return(
            vlan_display(2500)
        )

        self.shell_mock.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.shell_mock.should_receive("do").with_args("vlan 2500").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("router-interface ve 2500").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("interface ve 2500").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("enable").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("vrf forwarding MYVRF").once().ordered().and_return([
            "Warning: All IPv4 and IPv6 addresses (including link-local) on this interface have been removed"
        ])
        self.shell_mock.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()

        self.switch.set_vlan_vrf(2500, "MYVRF")

    def test_set_vlan_vrf_unknown_vlan(self):
        self.shell_mock.should_receive("do").with_args("show vlan 2500").once().ordered().and_return([
            "Error: vlan 2500 is not configured"
        ])
        with self.assertRaises(UnknownVlan) as expect:
            self.switch.set_vlan_vrf(2500, "MYVRF")

        assert_that(str(expect.exception), equal_to("Vlan 2500 not found"))

    def test_unset_vlan_vrf_success(self):
        self.shell_mock.should_receive("do").with_args("show vlan 2500").once().ordered().and_return(
            vlan_with_vif_display(2500, 2500)
        )

        self.shell_mock.should_receive("do").with_args("show running-config interface ve 2500").and_return([
            "interface ve 2500",
            " vrf forwarding MYVRF",
            "!",
        ])

        self.shell_mock.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.shell_mock.should_receive("do").with_args("interface ve 2500").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("enable").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("no vrf forwarding MYVRF").once().ordered().and_return([
            "Warning: All IPv4 and IPv6 addresses (including link-local) on this interface have been removed"
        ])
        self.shell_mock.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()

        self.switch.unset_vlan_vrf(2500)

    def test_unset_vlan_vrf_not_set(self):
        self.shell_mock.should_receive("do").with_args("show vlan 2500").once().ordered().and_return(
            vlan_with_vif_display(2500, 2500)
        )

        self.shell_mock.should_receive("do").with_args("show running-config interface ve 2500").and_return([
            "interface ve 2500",
            "!",
        ])

        with self.assertRaises(VlanVrfNotSet) as expect:
            self.switch.unset_vlan_vrf(2500)

        assert_that(str(expect.exception), equal_to("VRF is not set on vlan 2500"))

    def test_unset_vlan_vrf_from_known_vlan_with_no_interface(self):
        self.shell_mock.should_receive("do").with_args("show vlan 2500").once().ordered().and_return(
            vlan_display(2500)
        )

        with self.assertRaises(VlanVrfNotSet) as expect:
            self.switch.unset_vlan_vrf(2500)

        assert_that(str(expect.exception), equal_to("VRF is not set on vlan 2500"))

    def test_unset_vlan_vrf_from_unknown_vlan(self):
        self.shell_mock.should_receive("do").with_args("show vlan 2500").once().ordered().and_return([
            "Error: vlan 2500 is not configured"
        ])
        with self.assertRaises(UnknownVlan) as expect:
            self.switch.unset_vlan_vrf(2500)

        assert_that(str(expect.exception), equal_to("Vlan 2500 not found"))

    def test_set_access_group_creates_router_interface(self):
        self.shell_mock.should_receive("do").with_args("show vlan 2500").once().ordered().and_return(
            vlan_display(2500)
        )

        self.shell_mock.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.shell_mock.should_receive("do").with_args("vlan 2500").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("router-interface ve 2500").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("interface ve 2500").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("enable").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("ip access-group TheAccessGroup in").and_return([
            "Warning: An undefined or zero length ACL has been applied. "
            "Filtering will not occur for the specified interface VE 2500 (outbound)."
        ]).once().ordered()
        self.shell_mock.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()

        self.switch.set_vlan_access_group(2500, IN, "TheAccessGroup")

    def test_set_access_group_doesnt_creates_router_interface_if_already_created(self):
        self.shell_mock.should_receive("do").with_args("show vlan 2500").once().ordered().and_return(
            vlan_with_vif_display(2500, 3333)
        )

        self.shell_mock.should_receive("do").with_args("show running-config interface ve 3333").once().ordered().and_return([
            "interface ve 3333",
            "!",
        ])

        self.shell_mock.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.shell_mock.should_receive("do").with_args("interface ve 3333").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("enable").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("ip access-group TheAccessGroup out").and_return([
            "Warning: An undefined or zero length ACL has been applied. "
            "Filtering will not occur for the specified interface VE 2500 (outbound)."
        ]).once().ordered()
        self.shell_mock.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()

        self.switch.set_vlan_access_group(2500, OUT, "TheAccessGroup")

    def test_set_access_group_fails_if_switch_says_so(self):
        self.shell_mock.should_receive("do").with_args("show vlan 2500").once().ordered().and_return(
            vlan_with_vif_display(2500, 3333)
        )

        self.shell_mock.should_receive("do").with_args("show running-config interface ve 3333").once().ordered().and_return([
            "interface ve 3333",
            "!",
        ])

        self.shell_mock.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.shell_mock.should_receive("do").with_args("interface ve 3333").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("enable").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("ip access-group TheAcc essGroup out").once().ordered().and_return([
            "Invalid input -> sss out",
            "Type ? for a list"
        ])
        self.shell_mock.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()

        with self.assertRaises(InvalidAccessGroupName) as expect:
            self.switch.set_vlan_access_group(2500, OUT, "TheAcc essGroup")

        assert_that(str(expect.exception), equal_to("Access Group Name is invalid: TheAcc essGroup"))

    def test_set_access_group_needs_to_remove_actual_access_group_to_override_it(self):
        self.shell_mock.should_receive("do").with_args("show vlan 2500").once().ordered().and_return(
            vlan_with_vif_display(2500, 2500)
        )

        self.shell_mock.should_receive("do").with_args("show running-config interface ve 2500").once().ordered().and_return([
            "interface ve 2500",
            " ip access-group helloThere! in",
            "!",
        ])

        self.shell_mock.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.shell_mock.should_receive("do").with_args("interface ve 2500").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("enable").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("no ip access-group helloThere! in").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("ip access-group TheAccessGroup in").and_return([
            "Warning: An undefined or zero length ACL has been applied. "
            "Filtering will not occur for the specified interface VE 2500 (outbound)."
        ]).once().ordered()
        self.shell_mock.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()

        self.switch.set_vlan_access_group(2500, IN, "TheAccessGroup")

    def test_set_access_group_to_unknown_vlan(self):
        self.shell_mock.should_receive("do").with_args("show vlan 2500").once().ordered().and_return([
            "Error: vlan 2500 is not configured"
        ])
        with self.assertRaises(UnknownVlan) as expect:
            self.switch.set_vlan_access_group(2500, IN, "TheAccessGroup")

        assert_that(str(expect.exception), equal_to("Vlan 2500 not found"))

    def test_remove_access_group(self):
        self.shell_mock.should_receive("do").with_args("show vlan 2500").once().ordered().and_return(
            vlan_with_vif_display(2500, 2500)
        )

        self.shell_mock.should_receive("do").with_args("show running-config interface ve 2500").once().ordered().and_return([
            "interface ve 2500",
            " ip access-group helloThere! in",
            "!",
        ])

        self.shell_mock.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.shell_mock.should_receive("do").with_args("interface ve 2500").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("enable").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("no ip access-group helloThere! in").and_return([
            "Warning: An undefined or zero length ACL has been applied. "
            "Filtering will not occur for the specified interface VE 2500 (outbound)."
        ]).once().ordered()
        self.shell_mock.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()

        self.switch.unset_vlan_access_group(2500, IN)

    def test_remove_access_group_out(self):
        self.shell_mock.should_receive("do").with_args("show vlan 2500").once().ordered().and_return(
            vlan_with_vif_display(2500, 2500)
        )

        self.shell_mock.should_receive("do").with_args("show running-config interface ve 2500").once().ordered().and_return([
            "interface ve 2500",
            " ip access-group Waaaat out",
            "!",
        ])

        self.shell_mock.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.shell_mock.should_receive("do").with_args("interface ve 2500").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("enable").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("no ip access-group Waaaat out").and_return([
            "Warning: An undefined or zero length ACL has been applied. "
            "Filtering will not occur for the specified interface VE 2500 (outbound)."
        ]).once().ordered()
        self.shell_mock.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()

        self.switch.unset_vlan_access_group(2500, OUT)

    def test_remove_access_group_unknown_access_group_raises(self):
        self.shell_mock.should_receive("do").with_args("show vlan 2500").once().ordered().and_return(
            vlan_with_vif_display(2500, 2500)
        )

        self.shell_mock.should_receive("do").with_args("show running-config interface ve 2500").once().ordered().and_return([
            "interface ve 2500",
            " ip access-group Waaaat out",
            "!",
        ])

        with self.assertRaises(UnknownAccessGroup) as expect:
            self.switch.unset_vlan_access_group(2500, IN)

        assert_that(str(expect.exception), equal_to("Inbound IP access group not found"))

    def test_remove_access_group_fails_if_there_aint_even_a_router_interface(self):
        self.shell_mock.should_receive("do").with_args("show vlan 2500").once().ordered().and_return(
            vlan_display(2500)
        )

        with self.assertRaises(UnknownAccessGroup) as expect:
            self.switch.unset_vlan_access_group(2500, OUT)

        assert_that(str(expect.exception), equal_to("Outgoing IP access group not found"))

    def test_remove_access_group_on_unknown_vlan(self):
        self.shell_mock.should_receive("do").with_args("show vlan 2500").once().ordered().and_return([
            "Error: vlan 2500 is not configured"
        ])

        with self.assertRaises(UnknownVlan) as expect:
            self.switch.unset_vlan_access_group(2500, OUT)

        assert_that(str(expect.exception), equal_to("Vlan 2500 not found"))

    def test_get_interfaces(self):
        self.shell_mock.should_receive("do").with_args("show interfaces").once().ordered().and_return([
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

        self.shell_mock.should_receive("do").with_args("show running-config vlan").once().ordered().and_return([
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

        assert_that(if1.name, equal_to("ethernet 1/1"))
        assert_that(if1.shutdown, equal_to(False))
        assert_that(if1.port_mode, equal_to(ACCESS))
        assert_that(if1.access_vlan, equal_to(1999))
        assert_that(if1.trunk_native_vlan, equal_to(None))
        assert_that(if1.trunk_vlans, equal_to([]))

        assert_that(if2.name, equal_to("ethernet 1/2"))
        assert_that(if2.shutdown, equal_to(True))
        assert_that(if2.port_mode, equal_to(TRUNK))
        assert_that(if2.access_vlan, equal_to(None))
        assert_that(if2.trunk_native_vlan, equal_to(2999))
        assert_that(if2.trunk_vlans, equal_to([100, 200, 300]))

        assert_that(if3.name, equal_to("ethernet 1/3"))
        assert_that(if3.port_mode, equal_to(ACCESS))
        assert_that(if3.access_vlan, equal_to(None))
        assert_that(if3.trunk_native_vlan, equal_to(None))
        assert_that(if3.trunk_vlans, equal_to([]))

        assert_that(if4.name, equal_to("ethernet 1/4"))
        assert_that(if4.port_mode, equal_to(TRUNK))
        assert_that(if4.access_vlan, equal_to(None))
        assert_that(if4.trunk_native_vlan, equal_to(None))
        assert_that(if4.trunk_vlans, equal_to([100]))

        assert_that(if5.trunk_vlans, equal_to([100]))

        assert_that(if6.trunk_vlans, equal_to([100]))

    def test_get_interface(self):
        self.shell_mock.should_receive("do").with_args("show interfaces ethernet 1/2").once().ordered().and_return([
            "GigabitEthernet1/2 is disabled, line protocol is down",
            "  Hardware is GigabitEthernet, address is 0000.0000.0000 (bia 0000.0000.0000,",
            "  Member of VLAN 2999 (untagged), 3 L2 VLANS (tagged), port is in dual mode, port state is Disabled",
            "  Port name is hello"
        ])

        self.shell_mock.should_receive("do").with_args("show running-config vlan").once().ordered().and_return([
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

        interface = self.switch.get_interface("ethernet 1/2")

        assert_that(interface.name, equal_to("ethernet 1/2"))
        assert_that(interface.shutdown, equal_to(True))
        assert_that(interface.port_mode, equal_to(TRUNK))
        assert_that(interface.access_vlan, equal_to(None))
        assert_that(interface.trunk_native_vlan, equal_to(2999))
        assert_that(interface.trunk_vlans, equal_to([100, 200, 300]))

    def test_get_nonexistent_interface_raises(self):
        self.shell_mock.should_receive("do").with_args("show interfaces ethernet 1/1999").once().ordered().and_return([
            "Invalid input -> 1/1999",
            "Type ? for a list"
        ])

        self.shell_mock.should_receive("do").with_args("show running-config vlan").never()

        with self.assertRaises(UnknownInterface) as expect:
            self.switch.get_interface("ethernet 1/1999")

        assert_that(str(expect.exception), equal_to("Unknown interface ethernet 1/1999"))

    def test_add_vrrp_success_single_ip(self):
        self.shell_mock.should_receive("do").with_args("show vlan 1234").once().ordered().and_return(
            vlan_with_vif_display(1234, 1234)
        )
        self.shell_mock.should_receive("do").with_args("show running-config interface ve 1234").once().ordered().and_return([
            "interface ve 1234",
            " ip address 1.2.3.1/27",
            "!",
        ])

        self.shell_mock.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.shell_mock.should_receive("do").with_args("interface ve 1234").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("enable").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("ip vrrp-extended auth-type simple-text-auth VLAN1234").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("ip vrrp-extended vrid 1").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("backup priority 110 track-priority 50").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("ip-address 1.2.3.4").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("hello-interval 5").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("dead-interval 15").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("advertise backup").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("track-port ethernet 1/1").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("activate").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()

        self.switch.add_vrrp_group(1234, 1, ips=[IPAddress("1.2.3.4")], priority=110, hello_interval=5, dead_interval=15,
                                   track_id="ethernet 1/1", track_decrement=50)

    def test_add_vrrp_success_multiple_ip(self):
        self.shell_mock.should_receive("do").with_args("show vlan 1234").once().ordered().and_return(
            vlan_with_vif_display(1234, 1234)
        )
        self.shell_mock.should_receive("do").with_args("show running-config interface ve 1234").once().ordered().and_return([
            "interface ve 1234",
            " ip address 1.2.3.1/27",
            "!",
        ])

        self.shell_mock.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.shell_mock.should_receive("do").with_args("interface ve 1234").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("enable").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("ip vrrp-extended auth-type simple-text-auth VLAN1234").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("ip vrrp-extended vrid 1").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("backup priority 110 track-priority 50").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("ip-address 1.2.3.4").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("ip-address 1.2.3.5").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("hello-interval 5").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("dead-interval 15").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("advertise backup").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("track-port ethernet 1/1").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("activate").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()

        self.switch.add_vrrp_group(1234, 1, ips=[IPAddress("1.2.3.4"), IPAddress("1.2.3.5")], priority=110,
                                   hello_interval=5, dead_interval=15, track_id="ethernet 1/1", track_decrement=50)

    def test_add_vrrp_from_unknown_vlan(self):
        self.shell_mock.should_receive("do").with_args("show vlan 1234").once().ordered().and_return([
            "Error: vlan 1234 is not configured"
        ])
        with self.assertRaises(UnknownVlan) as expect:
            self.switch.add_vrrp_group(1234, 1, ips=[IPAddress("1.2.3.4")], priority=110, hello_interval=5, dead_interval=15,
                                       track_id="ethernet 1/1", track_decrement=50)

        assert_that(str(expect.exception), equal_to("Vlan 1234 not found"))

    def test_add_existing_vrrp_to_same_vlan(self):
        self.shell_mock.should_receive("do").with_args("show vlan 1234").once().ordered().and_return(
            vlan_with_vif_display(1234, 1234)
        )
        self.shell_mock.should_receive("do").with_args("show running-config interface ve 1234").once().ordered().and_return([
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
                                       track_id="ethernet 1/1", track_decrement=50)

        assert_that(str(expect.exception), equal_to("Vrrp group 1 is already in use on vlan 1234"))

    def test_add_vrrp_to_vlan_with_another_vrrp(self):
        self.shell_mock.should_receive("do").with_args("show vlan 1234").once().ordered().and_return(
            vlan_with_vif_display(1234, 1234)
        )
        self.shell_mock.should_receive("do").with_args("show running-config interface ve 1234").once().ordered().and_return([
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

        self.shell_mock.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.shell_mock.should_receive("do").with_args("interface ve 1234").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("enable").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("ip vrrp-extended vrid 2").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("backup priority 110 track-priority 50").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("ip-address 1.2.3.5").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("hello-interval 5").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("dead-interval 15").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("advertise backup").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("track-port ethernet 1/1").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("activate").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()

        self.switch.add_vrrp_group(1234, 2, ips=[IPAddress("1.2.3.5")], priority=110, hello_interval=5, dead_interval=15,
                                   track_id="ethernet 1/1", track_decrement=50)

    def test_add_vrrp_with_out_of_range_group_id(self):
        self.shell_mock.should_receive("do").with_args("show vlan 1234").once().ordered().and_return(
            vlan_with_vif_display(1234, 1234)
        )
        self.shell_mock.should_receive("do").with_args("show running-config interface ve 1234").once().ordered().and_return([
            "interface ve 1234",
            " ip address 1.2.3.1/27",
            "!",
        ])

        self.shell_mock.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.shell_mock.should_receive("do").with_args("interface ve 1234").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("enable").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("ip vrrp-extended auth-type simple-text-auth VLAN1234").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("ip vrrp-extended vrid 256").and_return([
            "Error - 256 not between 1 and 255"
        ]).once().ordered()
        self.shell_mock.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()

        with self.assertRaises(BadVrrpGroupNumber) as expect:
            self.switch.add_vrrp_group(1234, 256, ips=[IPAddress("1.2.3.4")], priority=110, hello_interval=5, dead_interval=15,
                                       track_id="ethernet 1/1", track_decrement=50)

        assert_that(str(expect.exception), equal_to("VRRP group number is invalid, must be contained between 1 and 255"))

    def test_add_vrrp_with_bad_hello_interval(self):
        self.shell_mock.should_receive("do").with_args("show vlan 1234").once().ordered().and_return(
            vlan_with_vif_display(1234, 1234)
        )
        self.shell_mock.should_receive("do").with_args("show running-config interface ve 1234").once().ordered().and_return([
            "interface ve 1234",
            " ip address 1.2.3.1/27",
            "!",
        ])

        self.shell_mock.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.shell_mock.should_receive("do").with_args("interface ve 1234").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("enable").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("ip vrrp-extended auth-type simple-text-auth VLAN1234").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("ip vrrp-extended vrid 1").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("backup priority 110 track-priority 50").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("ip-address 1.2.3.4").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("hello-interval 100").and_return([
            "Error - 100 not between 1 and 84"
        ]).once().ordered()
        self.shell_mock.should_receive("do").with_args("exit").and_return([]).times(3).ordered().ordered().ordered()

        with self.assertRaises(BadVrrpTimers) as expect:
            self.switch.add_vrrp_group(1234, 1, ips=[IPAddress("1.2.3.4")], priority=110, hello_interval=100, dead_interval=15,
                                       track_id="ethernet 1/1", track_decrement=50)

        assert_that(str(expect.exception), equal_to("VRRP timers values are invalid"))

    def test_add_vrrp_with_bad_dead_interval(self):
        self.shell_mock.should_receive("do").with_args("show vlan 1234").once().ordered().and_return(
            vlan_with_vif_display(1234, 1234)
        )
        self.shell_mock.should_receive("do").with_args("show running-config interface ve 1234").once().ordered().and_return([
            "interface ve 1234",
            " ip address 1.2.3.1/27",
            "!",
        ])

        self.shell_mock.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.shell_mock.should_receive("do").with_args("interface ve 1234").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("enable").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("ip vrrp-extended auth-type simple-text-auth VLAN1234").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("ip vrrp-extended vrid 1").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("backup priority 110 track-priority 50").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("ip-address 1.2.3.4").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("hello-interval 5").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("dead-interval 100").and_return([
            "Error - 100 not between 1 and 84"
        ]).once().ordered()
        self.shell_mock.should_receive("do").with_args("exit").and_return([]).times(3).ordered().ordered().ordered()

        with self.assertRaises(BadVrrpTimers) as expect:
            self.switch.add_vrrp_group(1234, 1, ips=[IPAddress("1.2.3.4")], priority=110, hello_interval=5, dead_interval=100,
                                       track_id="ethernet 1/1", track_decrement=50)

        assert_that(str(expect.exception), equal_to("VRRP timers values are invalid"))

    def test_add_vrrp_with_bad_priority(self):
        self.shell_mock.should_receive("do").with_args("show vlan 1234").once().ordered().and_return(
            vlan_with_vif_display(1234, 1234)
        )
        self.shell_mock.should_receive("do").with_args("show running-config interface ve 1234").once().ordered().and_return([
            "interface ve 1234",
            " ip address 1.2.3.1/27",
            "!",
        ])

        self.shell_mock.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.shell_mock.should_receive("do").with_args("interface ve 1234").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("enable").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("ip vrrp-extended auth-type simple-text-auth VLAN1234").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("ip vrrp-extended vrid 1").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("backup priority 256 track-priority 50").and_return([
            "Error - 256 not between 1 and 255"
        ]).once().ordered()
        self.shell_mock.should_receive("do").with_args("exit").and_return([]).times(3).ordered().ordered().ordered()

        with self.assertRaises(BadVrrpPriorityNumber) as expect:
            self.switch.add_vrrp_group(1234, 1, ips=[IPAddress("1.2.3.4")], priority=256, hello_interval=5, dead_interval=100,
                                       track_id="ethernet 1/1", track_decrement=50)

        assert_that(str(expect.exception), equal_to("VRRP priority value is invalid, must be contained between 1 and 255"))

    def test_add_vrrp_with_bad_priority_type(self):
        self.shell_mock.should_receive("do").with_args("show vlan 1234").once().ordered().and_return(
            vlan_with_vif_display(1234, 1234)
        )
        self.shell_mock.should_receive("do").with_args("show running-config interface ve 1234").once().ordered().and_return([
            "interface ve 1234",
            " ip address 1.2.3.1/27",
            "!",
        ])

        self.shell_mock.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.shell_mock.should_receive("do").with_args("interface ve 1234").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("enable").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("ip vrrp-extended auth-type simple-text-auth VLAN1234").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("ip vrrp-extended vrid 1").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("backup priority testvalue track-priority 50").and_return([
            "Invalid input -> testvalue track-priority 50"
        ]).once().ordered()
        self.shell_mock.should_receive("do").with_args("exit").and_return([]).times(3).ordered().ordered().ordered()

        with self.assertRaises(BadVrrpPriorityNumber) as expect:
            self.switch.add_vrrp_group(1234, 1, ips=[IPAddress("1.2.3.4")], priority='testvalue', hello_interval=5, dead_interval=15,
                                       track_id="ethernet 1/1", track_decrement=50)

        assert_that(str(expect.exception), equal_to("VRRP priority value is invalid, must be contained between 1 and 255"))

    def test_add_vrrp_with_bad_track_decrement(self):
        self.shell_mock.should_receive("do").with_args("show vlan 1234").once().ordered().and_return(
            vlan_with_vif_display(1234, 1234)
        )
        self.shell_mock.should_receive("do").with_args("show running-config interface ve 1234").once().ordered().and_return([
            "interface ve 1234",
            " ip address 1.2.3.1/27",
            "!",
        ])

        self.shell_mock.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.shell_mock.should_receive("do").with_args("interface ve 1234").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("enable").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("ip vrrp-extended auth-type simple-text-auth VLAN1234").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("ip vrrp-extended vrid 1").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("backup priority 110 track-priority 255").and_return([
            "Error - 255 not between 1 and 254"
        ]).once().ordered()
        self.shell_mock.should_receive("do").with_args("exit").and_return([]).times(3).ordered().ordered().ordered()

        with self.assertRaises(BadVrrpTracking) as expect:
            self.switch.add_vrrp_group(1234, 1, ips=[IPAddress("1.2.3.4")], priority=110, hello_interval=5, dead_interval=15,
                                       track_id="ethernet 1/1", track_decrement=255)

        assert_that(str(expect.exception), equal_to("VRRP tracking values are invalid"))

    def test_add_vrrp_with_bad_track_decrement_type(self):
        self.shell_mock.should_receive("do").with_args("show vlan 1234").once().ordered().and_return(
            vlan_with_vif_display(1234, 1234)
        )
        self.shell_mock.should_receive("do").with_args("show running-config interface ve 1234").once().ordered().and_return([
            "interface ve 1234",
            " ip address 1.2.3.1/27",
            "!",
        ])

        self.shell_mock.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.shell_mock.should_receive("do").with_args("interface ve 1234").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("enable").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("ip vrrp-extended auth-type simple-text-auth VLAN1234").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("ip vrrp-extended vrid 1").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("backup priority 110 track-priority testvalue").and_return([
            "Invalid input -> testvalue"
        ]).once().ordered()
        self.shell_mock.should_receive("do").with_args("exit").and_return([]).times(3).ordered().ordered().ordered()

        with self.assertRaises(BadVrrpTracking) as expect:
            self.switch.add_vrrp_group(1234, 1, ips=[IPAddress("1.2.3.4")], priority=110, hello_interval=5, dead_interval=15,
                                       track_id="ethernet 1/1", track_decrement='testvalue')

        assert_that(str(expect.exception), equal_to("VRRP tracking values are invalid"))

    def test_add_vrrp_with_no_ip_on_interface(self):
        self.shell_mock.should_receive("do").with_args("show vlan 1234").once().ordered().and_return(
            vlan_with_vif_display(1234, 1234)
        )
        self.shell_mock.should_receive("do").with_args("show running-config interface ve 1234").once().ordered().and_return([
            "interface ve 1234",
            "!",
        ])

        self.shell_mock.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.shell_mock.should_receive("do").with_args("interface ve 1234").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("enable").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("ip vrrp-extended auth-type simple-text-auth VLAN1234").and_return([
            "error - please configure ip address before configuring vrrp-extended"
        ]).once().ordered()
        self.shell_mock.should_receive("do").with_args("exit").and_return([]).times(2).ordered().ordered()

        with self.assertRaises(NoIpOnVlanForVrrp) as expect:
            self.switch.add_vrrp_group(1234, 1, ips=[IPAddress("1.2.3.4")], priority=110, hello_interval=5, dead_interval=100,
                                       track_id="ethernet 1/1", track_decrement=50)

        assert_that(str(expect.exception), equal_to("Vlan 1234 needs an IP before configuring VRRP"))

    def test_add_vrrp_with_bad_tracking_id(self):
        self.shell_mock.should_receive("do").with_args("show vlan 1234").once().ordered().and_return(
            vlan_with_vif_display(1234, 1234)
        )
        self.shell_mock.should_receive("do").with_args("show running-config interface ve 1234").once().ordered().and_return([
            "interface ve 1234",
            " ip address 1.2.3.1/27",
            "!",
        ])

        self.shell_mock.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.shell_mock.should_receive("do").with_args("interface ve 1234").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("enable").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("ip vrrp-extended auth-type simple-text-auth VLAN1234").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("ip vrrp-extended vrid 1").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("backup priority 110 track-priority 50").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("ip-address 1.2.3.4").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("hello-interval 5").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("dead-interval 15").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("advertise backup").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("track-port ethernet not_an_interface").and_return([
            "Invalid input -> not_an_interface"
        ]).once().ordered()
        self.shell_mock.should_receive("do").with_args("exit").and_return([]).times(3).ordered().ordered().ordered()

        with self.assertRaises(BadVrrpTracking) as expect:
            self.switch.add_vrrp_group(1234, 1, ips=[IPAddress("1.2.3.4")], priority=110, hello_interval=5, dead_interval=15,
                                       track_id="ethernet not_an_interface", track_decrement=50)

        assert_that(str(expect.exception), equal_to("VRRP tracking values are invalid"))

    def test_remove_vrrp_success(self):
        self.shell_mock.should_receive("do").with_args("show vlan 1234").once().ordered().and_return(
            vlan_with_vif_display(1234, 1234)
        )
        self.shell_mock.should_receive("do").with_args("show running-config interface ve 1234").once().ordered().and_return([
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

        self.shell_mock.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.shell_mock.should_receive("do").with_args("interface ve 1234").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("enable").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("no ip vrrp-extended vrid 1").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("ip vrrp-extended auth-type no-auth").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()

        self.switch.remove_vrrp_group(1234, 1)

    def test_remove_one_of_two_vrrp_success(self):
        self.shell_mock.should_receive("do").with_args("show vlan 1234").once().ordered().and_return(
            vlan_with_vif_display(1234, 1234)
        )
        self.shell_mock.should_receive("do").with_args("show running-config interface ve 1234").once().ordered().and_return([
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

        self.shell_mock.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.shell_mock.should_receive("do").with_args("interface ve 1234").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("enable").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("no ip vrrp-extended vrid 1").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()

        self.switch.remove_vrrp_group(1234, 1)

    def test_remove_vrrp_with_invalid_group_id(self):
        self.shell_mock.should_receive("do").with_args("show vlan 1234").once().ordered().and_return(
            vlan_with_vif_display(1234, 1234)
        )
        self.shell_mock.should_receive("do").with_args("show running-config interface ve 1234").once().ordered().and_return([
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
        self.shell_mock.should_receive("do").with_args("show vlan 1234").once().ordered().and_return([
            "Error: vlan 1234 is not configured"
        ])
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

    @mock.patch("netman.adapters.switches.brocade.SshClient")
    def test_connect(self, ssh_client_class_mock):
        self.switch = brocade_factory_ssh(SwitchDescriptor(
            hostname="my.hostname", username="the_user", password="the_password", model="brocade", port=22), mock.Mock())

        self.shell_mock = flexmock()
        ssh_client_class_mock.return_value = self.shell_mock
        self.shell_mock.should_receive("get_current_prompt").and_return("hostname>").once().ordered()
        self.shell_mock.should_receive("do").with_args("enable", wait_for=":").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("the_password").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("skip-page-display").and_return([]).once().ordered()

        self.switch.connect()

        ssh_client_class_mock.assert_called_with(
            host="my.hostname",
            username="the_user",
            password="the_password",
            port=22
        )

    @mock.patch("netman.adapters.switches.brocade.TelnetClient")
    def test_connect_without_port_uses_default(self, telnet_client_class_mock):
        self.switch = brocade_factory_telnet(SwitchDescriptor(
            hostname="my.hostname", username="the_user", password="the_password", model="brocade"), mock.Mock())

        self.shell_mock = flexmock()
        telnet_client_class_mock.return_value = self.shell_mock
        self.shell_mock.should_receive("get_current_prompt").and_return("hostname>").once().ordered()
        self.shell_mock.should_receive("do").with_args("enable", wait_for=":").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("the_password").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("skip-page-display").and_return([]).once().ordered()

        self.switch.connect()

        telnet_client_class_mock.assert_called_with(
            host="my.hostname",
            username="the_user",
            password="the_password"
        )

    @mock.patch("netman.adapters.switches.brocade.SshClient")
    def test_auto_enabled_switch_doesnt_require_enable(self, ssh_client_class_mock):
        self.switch = brocade_factory_ssh(SwitchDescriptor(hostname="my.hostname", username="the_user", password="the_password", model="brocade", port=8000), mock.Mock())

        self.shell_mock = flexmock()
        ssh_client_class_mock.return_value = self.shell_mock
        self.shell_mock.should_receive("get_current_prompt").and_return("hostname#").once().ordered()
        self.shell_mock.should_receive("do").with_args("enable", wait_for=": ").never()
        self.shell_mock.should_receive("do").with_args("skip-page-display").and_return([]).once().ordered()

        self.switch.connect()

        ssh_client_class_mock.assert_called_with(
            host="my.hostname",
            username="the_user",
            password="the_password",
            port=8000
        )

    def test_disconnect(self):
        logger = flexmock()
        self.switch.logger = logger
        logger.should_receive("debug")

        self.shell_mock.should_receive("quit").with_args("exit").once().ordered()

        logger.should_receive("info").with_args("FULL TRANSACTION LOG").once()

        self.switch.shell.full_log = "FULL TRANSACTION LOG"
        self.switch.disconnect()

    def test_transactions_commit_write_memory(self):
        self.shell_mock.should_receive("do").with_args("show vlan 2999").and_return([
            "Error: vlan 2999 is not configured"
        ])

        self.shell_mock.should_receive("do").with_args("configure terminal").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("vlan 2999 name Gertrude").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("exit").once().ordered().and_return([])
        self.shell_mock.should_receive("do").with_args("exit").once().ordered().and_return([])

        self.switch.start_transaction()
        self.switch.add_vlan(2999, name="Gertrude")

        self.shell_mock.should_receive("do").with_args("write memory").once().ordered()

        self.switch.commit_transaction()
        self.switch.end_transaction()

    def test_add_dhcp_relay_server(self):
        self.shell_mock.should_receive("do").with_args("show vlan 1234").once().ordered().and_return(
            vlan_with_vif_display(1234, 1234)
        )
        self.shell_mock.should_receive("do").with_args("show running-config interface ve 1234").once().ordered().and_return([
            "interface ve 1234",
            " ip address 1.2.3.1/27",
            "!",
        ])

        self.shell_mock.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.shell_mock.should_receive("do").with_args("interface ve 1234").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("enable").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("ip helper-address 10.10.10.1").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()

        self.switch.add_dhcp_relay_server(1234, IPAddress('10.10.10.1'))

    def test_add_second_dhcp_relay_server(self):
        self.shell_mock.should_receive("do").with_args("show vlan 1234").once().ordered().and_return(
            vlan_with_vif_display(1234, 1234)
        )
        self.shell_mock.should_receive("do").with_args("show running-config interface ve 1234").once().ordered().and_return([
            "interface ve 1234",
            " ip address 1.2.3.1/27",
            " ip helper-address 10.10.10.1",
            "!",
        ])

        self.shell_mock.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.shell_mock.should_receive("do").with_args("interface ve 1234").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("enable").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("ip helper-address 10.10.10.2").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()

        self.switch.add_dhcp_relay_server(1234, IPAddress('10.10.10.2'))

    def test_add_same_dhcp_relay_server_fails(self):
        self.shell_mock.should_receive("do").with_args("show vlan 1234").once().ordered().and_return(
            vlan_with_vif_display(1234, 1234)
        )
        self.shell_mock.should_receive("do").with_args("show running-config interface ve 1234").once().ordered().and_return([
            "interface ve 1234",
            " ip address 1.2.3.1/27",
            " ip helper-address 10.10.10.1",
            "!",
        ])

        with self.assertRaises(DhcpRelayServerAlreadyExists) as expect:
            self.switch.add_dhcp_relay_server(1234, IPAddress('10.10.10.1'))

        assert_that(str(expect.exception), equal_to("DHCP relay server 10.10.10.1 already exists on VLAN 1234"))

    def test_remove_dhcp_relay_server(self):
        self.shell_mock.should_receive("do").with_args("show vlan 1234").once().ordered().and_return(
            vlan_with_vif_display(1234, 1234)
        )
        self.shell_mock.should_receive("do").with_args("show running-config interface ve 1234").once().ordered().and_return([
            "interface ve 1234",
            " ip address 1.2.3.1/27",
            " ip helper-address 10.10.10.1",
            "!",
        ])

        self.shell_mock.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.shell_mock.should_receive("do").with_args("interface ve 1234").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("enable").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("no ip helper-address 10.10.10.1").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()

        self.switch.remove_dhcp_relay_server(1234, IPAddress('10.10.10.1'))

    def test_remove_non_existent_dhcp_relay_server_fails(self):
        self.shell_mock.should_receive("do").with_args("show vlan 1234").once().ordered().and_return(
            vlan_with_vif_display(1234, 1234)
        )
        self.shell_mock.should_receive("do").with_args("show running-config interface ve 1234").once().ordered().and_return([
            "interface ve 1234",
            " ip address 1.2.3.1/27",
            "!",
        ])

        with self.assertRaises(UnknownDhcpRelayServer) as expect:
            self.switch.remove_dhcp_relay_server(1234, IPAddress('10.10.10.1'))

        assert_that(str(expect.exception), equal_to("DHCP relay server 10.10.10.1 not found on VLAN 1234"))


def vlan_with_vif_display(vlan_id, vif_id, name="[None]"):
    return vlan_display(vlan_id, name, vif_id=vif_id)


def vlan_display(vlan_id=9, vlan_name="[None]", tagged_port_str=None, untagged_port_str=None, vif_id=None):
    ret = [
        "PORT-VLAN {}, Name {}, Priority Level -, Priority Force 0, Creation Type STATIC".format(vlan_id, vlan_name),
        "Topo HW idx    : 81    Topo SW idx: 257    Topo next vlan: 0",
        "L2 protocols   : STP",
    ]
    if untagged_port_str:
        ret.append("Untagged Ports : {}".format(untagged_port_str))
    if tagged_port_str:
        ret.append("Statically tagged Ports : {}".format(tagged_port_str))
    ret.extend([
        "Associated Virtual Interface Id: {}".format(vif_id or "NONE"),
        "----------------------------------------------------------",
        "No ports associated with VLAN",
        "Arp Inspection: 0",
        "DHCP Snooping: 0",
        "IPv4 Multicast Snooping: Disabled",
        "IPv6 Multicast Snooping: Disabled",
    ])
    if vif_id:
        ret.extend([
            "Ve{} is down, line protocol is down".format(vif_id),
            "  Type is Vlan (Vlan Id: {})".format(vlan_id),
            "  Hardware is Virtual Ethernet, address is 748e.f8a7.1b01 (bia 748e.f8a7.1b01)",
            "  No port name",
            "  Vlan id: {}".format(vlan_id),
            "  Internet address is 0.0.0.0/0, IP MTU 1500 bytes, encapsulation ethernet",
            "  Configured BW 0 kbps",
        ])
    else:
        ret.append("No Virtual Interfaces configured for this vlan")
    return ret
