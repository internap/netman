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
from hamcrest import assert_that, has_length, equal_to, is_, instance_of
import mock
from netaddr import IPNetwork
from netaddr.ip import IPAddress

from netman.adapters.switches import cisco
from netman.core.objects.switch_transactional import SwitchTransactional
from netman.adapters.switches.cisco import Cisco, parse_vlan_ranges
from netman.core.objects.access_groups import IN, OUT
from netman.core.objects.exceptions import IPNotAvailable, UnknownVlan, UnknownIP, UnknownAccessGroup, BadVlanNumber, \
    BadVlanName, UnknownInterface, UnknownVrf, VlanVrfNotSet, IPAlreadySet, BadVrrpGroupNumber, \
    BadVrrpPriorityNumber, VrrpDoesNotExistForVlan, VrrpAlreadyExistsForVlan, BadVrrpTimers, \
    BadVrrpTracking, DhcpRelayServerAlreadyExists, UnknownDhcpRelayServer
from netman.core.objects.port_modes import ACCESS, TRUNK, DYNAMIC
from netman.core.objects.switch_descriptor import SwitchDescriptor


def test_factory():
    lock = mock.Mock()
    switch = cisco.factory(SwitchDescriptor(hostname='hostname', model='cisco', username='username', password='password', port=22), lock)

    assert_that(switch, instance_of(SwitchTransactional))
    assert_that(switch.impl, instance_of(Cisco))
    assert_that(switch.lock, is_(lock))
    assert_that(switch.switch_descriptor.hostname, equal_to("hostname"))
    assert_that(switch.switch_descriptor.model, equal_to("cisco"))
    assert_that(switch.switch_descriptor.username, equal_to("username"))
    assert_that(switch.switch_descriptor.password, equal_to("password"))
    assert_that(switch.switch_descriptor.port, equal_to(22))


class CiscoTest(unittest.TestCase):

    def setUp(self):
        self.lock = mock.Mock()
        self.switch = cisco.factory(SwitchDescriptor(model='cisco', hostname="my.hostname", password="the_password"), self.lock)

    def tearDown(self):
        flexmock_teardown()

    def command_setup(self):
        self.mocked_ssh_client = flexmock()
        self.switch.impl.ssh = self.mocked_ssh_client
        self.mocked_ssh_client.should_receive("do").with_args("terminal length 0").never()
        self.mocked_ssh_client.should_receive("do").with_args("enable", wait_for=": ").never()
        self.mocked_ssh_client.should_receive("do").with_args("the_password").never()

    def test_switch_has_a_logger_configured_with_the_switch_name(self):
        assert_that(self.switch.logger.name, is_(Cisco.__module__ + ".my.hostname"))

    def test_get_vlan(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show vlan brief").once().ordered().and_return([
            "VLAN Name                             Status    Ports",
            "---- -------------------------------- --------- -------------------------------",
            "1    default                          active    Fa0/2, Fa0/3, Fa0/4",
            "2222 your-name-is-way-too-long-for-th active",
            "2500 no-ip                            active",
            "2998 VLAN2998                         active    Fa0/1",
            "3333 some-name                        active",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("show ip interface").once().ordered().and_return([
            "Vlan2222 is down, line protocol is down",
            "  Internet protocol processing disabled",
            "Vlan2500 is down, line protocol is down",
            "  Internet protocol processing disabled",
            "Vlan2723 is down, line protocol is down",
            "  Internet protocol processing disabled",
            "Vlan2998 is down, line protocol is down",
            "  Internet protocol processing disabled",
            "GigabitEthernet1/0/1 is up, line protocol is up",
            "  Inbound  access list is not set"
        ])

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface vlan 2222").once().ordered().and_return([
            "Building configuration...",
            "Current configuration : 41 bytes",
            "!",
            "interface Vlan2222",
            " no ip address",
            "end"
        ])

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface vlan 2500").once().ordered().and_return([
            "Building configuration...",
            "Current configuration : 41 bytes",
            "!",
            "interface Vlan2500",
            " ip access-group SHIZZLE in",
            " ip access-group WHIZZLE out",
            " ip vrf forwarding BLAH",
            "end"
        ])

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface vlan 2998").once().ordered().and_return([
            "Building configuration...",
            "Current configuration : 41 bytes",
            "!",
            "interface Vlan2998",
            " ip vrf forwarding patate",
            " ip address 1.1.1.1 255.255.255.0",
            " ip address 2.1.1.1 255.255.255.0 secondary",
            " ip address 3.1.1.1 255.255.255.0 secondary",
            " ip access-group GAGA out",
            " standby 1 ip 1.1.1.2",
            " standby 1 ip 2.1.1.2 secondary",
            " standby 1 ip 3.1.1.2 secondary",
            " standby 1 timers 5 15",
            " standby 1 priority 110",
            " standby 1 preempt delay minimum 60",
            " standby 1 authentication VLAN2998",
            " standby 1 track 101 decrement 50",
            " ip helper-address 10.10.10.1",
            " ip helper-address 10.10.10.2",
            "end"
        ])

        vlan_list = self.switch.get_vlans()
        vlan_list = sorted(vlan_list, key=lambda x: x.number)

        assert_that(vlan_list, has_length(5))
        assert_that(vlan_list[0].number, equal_to(1))
        assert_that(vlan_list[0].name, equal_to("default"))
        assert_that(len(vlan_list[0].ips), equal_to(0))

        assert_that(vlan_list[1].number, equal_to(2222))
        assert_that(vlan_list[1].name, equal_to("your-name-is-way-too-long-for-th"))
        assert_that(vlan_list[1].vrf_forwarding, equal_to(None))
        assert_that(vlan_list[1].access_groups[IN], equal_to(None))
        assert_that(vlan_list[1].access_groups[OUT], equal_to(None))
        assert_that(len(vlan_list[1].ips), equal_to(0))

        assert_that(vlan_list[2].vrf_forwarding, equal_to("BLAH"))
        assert_that(vlan_list[2].access_groups[IN], equal_to("SHIZZLE"))
        assert_that(vlan_list[2].access_groups[OUT], equal_to("WHIZZLE"))

        v3 = vlan_list[3]
        assert_that(v3.number, equal_to(2998))
        assert_that(v3.name, equal_to(""))
        assert_that(v3.vrf_forwarding, equal_to("patate"))
        assert_that(v3.access_groups[IN], equal_to(None))
        assert_that(v3.access_groups[OUT], equal_to("GAGA"))
        assert_that(len(v3.ips), equal_to(3))

        v3.ips = sorted(v3.ips, key=lambda ip: (ip.value, ip.prefixlen))
        assert_that(str(v3.ips[0].ip), equal_to('1.1.1.1'))
        assert_that(v3.ips[0].prefixlen, equal_to(24))

        assert_that(str(v3.ips[1].ip), equal_to('2.1.1.1'))
        assert_that(v3.ips[1].prefixlen, equal_to(24))

        assert_that(str(v3.ips[2].ip), equal_to('3.1.1.1'))
        assert_that(v3.ips[2].prefixlen, equal_to(24))

        v3_vrrp = v3.vrrp_groups[0]
        assert_that(len(v3_vrrp.ips), equal_to(3))
        assert_that(v3_vrrp.ips[0], equal_to(IPAddress('1.1.1.2')))
        assert_that(v3_vrrp.ips[1], equal_to(IPAddress('2.1.1.2')))
        assert_that(v3_vrrp.ips[2], equal_to(IPAddress('3.1.1.2')))
        assert_that(v3_vrrp.hello_interval, equal_to(5))
        assert_that(v3_vrrp.dead_interval, equal_to(15))
        assert_that(v3_vrrp.priority, equal_to(110))
        assert_that(v3_vrrp.track_id, equal_to('101'))
        assert_that(v3_vrrp.track_decrement, equal_to(50))

        assert_that(len(v3.dhcp_relay_servers), equal_to(2))
        assert_that(str(v3.dhcp_relay_servers[0]), equal_to('10.10.10.1'))
        assert_that(str(v3.dhcp_relay_servers[1]), equal_to('10.10.10.2'))

        assert_that(vlan_list[4].number, equal_to(3333))
        assert_that(vlan_list[4].name, equal_to("some-name"))
        assert_that(len(vlan_list[4].ips), equal_to(0))
        assert_that(vlan_list[4].access_groups[IN], equal_to(None))
        assert_that(vlan_list[4].access_groups[OUT], equal_to(None))

    def test_add_vlan(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([
            "Enter configuration commands, one per line.  End with CNTL/Z."
        ])
        self.mocked_ssh_client.should_receive("do").with_args("vlan 2999").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("name Gertrude").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("write memory").and_return([]).once().ordered()

        self.switch.add_vlan(2999, name="Gertrude")

    def test_add_vlan_refused_number(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([
            "Enter configuration commands, one per line.  End with CNTL/Z."
        ])
        self.mocked_ssh_client.should_receive("do").with_args("vlan 2999").once().ordered().and_return([
            "Command rejected: Bad VLAN list - character #5 (EOL) delimits a VLAN",
            "number which is out of the range 1..4094."
        ])
        self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered()

        with self.assertRaises(BadVlanNumber) as expect:
            self.switch.add_vlan(2999, name="Gertrude")

        assert_that(str(expect.exception), equal_to("Vlan number is invalid"))

    def test_add_vlan_refused_name(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([
            "Enter configuration commands, one per line.  End with CNTL/Z."
        ])
        self.mocked_ssh_client.should_receive("do").with_args("vlan 2999").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("name Gertr dude").once().ordered().and_return([
            "name Gertr dude",
            "           ^",
            "% Invalid input detected at '^' marker."
        ])
        self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])
        self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        with self.assertRaises(BadVlanName) as expect:
            self.switch.add_vlan(2999, name="Gertr dude")

        assert_that(str(expect.exception), equal_to("Vlan name is invalid"))

    def test_add_vlan_no_name(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([
            "Enter configuration commands, one per line.  End with CNTL/Z."
        ])
        self.mocked_ssh_client.should_receive("do").with_args("vlan 2999").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("write memory").and_return([]).once().ordered()

        self.switch.add_vlan(2999)

    def test_remove_vlan_also_removes_associated_vlan_interface(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan 2999").and_return([
            "Building configuration...",
            "Current configuration:",
            "!",
            "vlan 2999",
            "end"]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([
            "Enter configuration commands, one per line.  End with CNTL/Z."
        ])

        self.mocked_ssh_client.should_receive("do").with_args("no interface vlan 2999").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("no vlan 2999").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("write memory").and_return([]).once().ordered()

        self.switch.remove_vlan(2999)

    def test_remove_vlan_invalid_vlan_raises(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan 2999").and_return([
            "Building configuration...",
            "Current configuration:",
            "end"]).once().ordered()

        with self.assertRaises(UnknownVlan) as expect:
            self.switch.remove_vlan(2999)

        assert_that(str(expect.exception), equal_to("Vlan 2999 not found"))

    def test_remove_vlan_ignores_removing_interface_not_created(self):
        self.command_setup()
        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan 2999").and_return([
            "Building configuration...",
            "Current configuration:",
            "!",
            "vlan 2999",
            "end"]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([
            "Enter configuration commands, one per line.  End with CNTL/Z."
        ])
        self.mocked_ssh_client.should_receive("do").with_args("no interface vlan 2999").once().ordered().and_return([
            "                                     ^",
            "% Invalid input detected at '^' marker."
        ])
        self.mocked_ssh_client.should_receive("do").with_args("no vlan 2999").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("write memory").and_return([]).once().ordered()

        self.switch.remove_vlan(2999)

    def test_get_interfaces(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config | begin interface").once().ordered().and_return([
            "interface FastEthernet0/1",
            "!",
            "interface FastEthernet0/2",
            " switchport access vlan 100",
            " switchport trunk native vlan 200",
            " switchport trunk allowed vlan 300,302-304",
            " switchport mode access",
            "!",
            "interface GigabitEthernet0/3",
            " switchport access vlan 100",
            " switchport trunk native vlan 200",
            " switchport trunk allowed vlan 300,302-304",
            " switchport mode trunk",
            " shutdown",
            "!",
            "interface GigabitEthernet0/4",
            " switchport access vlan 100",
            " switchport trunk native vlan 200",
            " switchport trunk allowed vlan 300,302-304",
            "!",
            "interface GigabitEthernet1/0/5",
            " switchport trunk allowed vlan 300,302-304",
            " switchport mode trunk",
            "!",
            "interface Vlan722",
            " description MANAGEMENT_VLAN",
            " ip address 172.19.234.11 255.255.255.224",
            " no ip route-cache",
            "!",
            " interface Vlan2999",
            " no ip address",
            " no ip route-cache",
            " shutdown",
            "!",
            "end",
        ])

        result = self.switch.get_interfaces()

        if1, if2, if3, if4, if5 = result

        assert_that(if1.name, equal_to("FastEthernet0/1"))
        assert_that(if1.shutdown, equal_to(False))
        assert_that(if1.port_mode, equal_to(DYNAMIC))
        assert_that(if1.access_vlan, equal_to(None))
        assert_that(if1.trunk_native_vlan, equal_to(None))
        assert_that(if1.trunk_vlans, equal_to([]))

        assert_that(if2.name, equal_to("FastEthernet0/2"))
        assert_that(if2.shutdown, equal_to(False))
        assert_that(if2.port_mode, equal_to(ACCESS))
        assert_that(if2.access_vlan, equal_to(100))
        assert_that(if2.trunk_native_vlan, equal_to(None))
        assert_that(if2.trunk_vlans, equal_to([]))

        assert_that(if3.name, equal_to("GigabitEthernet0/3"))
        assert_that(if3.shutdown, equal_to(True))
        assert_that(if3.port_mode, equal_to(TRUNK))
        assert_that(if3.access_vlan, equal_to(None))
        assert_that(if3.trunk_native_vlan, equal_to(200))
        assert_that(if3.trunk_vlans, equal_to([300, 302, 303, 304]))

        assert_that(if4.name, equal_to("GigabitEthernet0/4"))
        assert_that(if4.port_mode, equal_to(DYNAMIC))
        assert_that(if4.access_vlan, equal_to(100))
        assert_that(if4.trunk_native_vlan, equal_to(200))
        assert_that(if4.trunk_vlans, equal_to([300, 302, 303, 304]))

        assert_that(if5.name, equal_to("GigabitEthernet1/0/5"))
        assert_that(if5.trunk_native_vlan, equal_to(None))
        assert_that(if5.trunk_vlans, equal_to([300, 302, 303, 304]))

    def parse_range_test(self):

        result = parse_vlan_ranges(None)
        assert_that(list(result), equal_to(range(1, 4094)))

        result = parse_vlan_ranges("none")
        assert_that(list(result), equal_to([]))

        result = parse_vlan_ranges("1")
        assert_that(list(result), equal_to([1]))

        result = parse_vlan_ranges("2-5")
        assert_that(list(result), equal_to([2, 3, 4, 5]))

        result = parse_vlan_ranges("1,3-5,7")
        assert_that(list(result), equal_to([1, 3, 4, 5, 7]))

    def test_set_access_vlan(self):
        self.command_setup()
        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan 2999").and_return([
            "Building configuration...",
            "Current configuration:",
            "!",
            "vlan 2999",
            "end"]).once().ordered()

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([
            "Enter configuration commands, one per line.  End with CNTL/Z."
        ])
        self.mocked_ssh_client.should_receive("do").with_args("interface FastEthernet0/4").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("switchport access vlan 2999").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("write memory").and_return([]).once().ordered()

        self.switch.set_access_vlan("FastEthernet0/4", vlan=2999)

    def test_set_access_vlan_invalid_vlan_raises(self):
        self.command_setup()
        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan 2999").and_return([
            "Building configuration...",
            "Current configuration:",
            "end"]).once().ordered()

        with self.assertRaises(UnknownVlan) as expect:
            self.switch.set_access_vlan("FastEthernet0/4", vlan=2999)

        assert_that(str(expect.exception), equal_to("Vlan 2999 not found"))

    def test_set_access_vlan_invalid_interface_raises(self):
        self.command_setup()
        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan 2999").and_return([
            "Building configuration...",
            "Current configuration:",
            "!",
            "vlan 2999",
            "end"]).once().ordered()

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([
            "Enter configuration commands, one per line.  End with CNTL/Z."
        ])
        self.mocked_ssh_client.should_receive("do").with_args("interface SlowEthernet42/9999").and_return([
            "        ^",
            "% Invalid input detected at '^' marker."
        ])
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).once().ordered()

        with self.assertRaises(UnknownInterface) as expect:
            self.switch.set_access_vlan("SlowEthernet42/9999", vlan=2999)

        assert_that(str(expect.exception), equal_to("Unknown interface SlowEthernet42/9999"))

    def test_remove_access_vlan(self):
        self.command_setup()
        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([
            "Enter configuration commands, one per line.  End with CNTL/Z."
        ])
        self.mocked_ssh_client.should_receive("do").with_args("interface FastEthernet0/4").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("no switchport access vlan").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("write memory").and_return([]).once().ordered()

        self.switch.remove_access_vlan("FastEthernet0/4")

    def test_remove_access_vlan_invalid_interface_raises(self):
        self.command_setup()
        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([
            "Enter configuration commands, one per line.  End with CNTL/Z."
        ])
        self.mocked_ssh_client.should_receive("do").with_args("interface SlowEthernet42/9999").and_return([
            "        ^",
            "% Invalid input detected at '^' marker."
        ])
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).once().ordered()

        with self.assertRaises(UnknownInterface) as expect:
            self.switch.remove_access_vlan("SlowEthernet42/9999")

        assert_that(str(expect.exception), equal_to("Unknown interface SlowEthernet42/9999"))

    def test_set_access_mode(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([
            "Enter configuration commands, one per line.  End with CNTL/Z."
        ])
        self.mocked_ssh_client.should_receive("do").with_args("interface FastEthernet0/4").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("switchport mode access").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("no switchport trunk native vlan").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("no switchport trunk allowed vlan").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("write memory").and_return([]).once().ordered()

        self.switch.set_access_mode("FastEthernet0/4")

    def test_set_access_mode_invalid_interface_raises(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([
            "Enter configuration commands, one per line.  End with CNTL/Z."
        ])
        self.mocked_ssh_client.should_receive("do").with_args("interface SlowEthernet42/9999").and_return([
            "        ^",
            "% Invalid input detected at '^' marker."
        ])
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).once().ordered()

        with self.assertRaises(UnknownInterface) as expect:
            self.switch.set_access_mode("SlowEthernet42/9999")

        assert_that(str(expect.exception), equal_to("Unknown interface SlowEthernet42/9999"))

    def test_set_trunk_mode_initial(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface FastEthernet0/4").once().ordered().and_return([
            "Building configuration...",
            "Current configuration : 156 bytes",
            "!",
            "interface FastEthernet0/4",
            "end"
        ])
        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([
            "Enter configuration commands, one per line.  End with CNTL/Z."
        ])
        self.mocked_ssh_client.should_receive("do").with_args("interface FastEthernet0/4").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("switchport mode trunk").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("switchport trunk allowed vlan none").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("no switchport access vlan").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("write memory").and_return([]).once().ordered()

        self.switch.set_trunk_mode("FastEthernet0/4")

    def test_set_trunk_mode_initial_invalid_interface_raises(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface SlowEthernet42/9999").and_return([
            "        ^",
            "% Invalid input detected at '^' marker."
        ])

        with self.assertRaises(UnknownInterface) as expect:
            self.switch.set_trunk_mode("SlowEthernet42/9999")

        assert_that(str(expect.exception), equal_to("Unknown interface SlowEthernet42/9999"))

    def test_set_trunk_mode_switching_mode(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface FastEthernet0/4").once().ordered().and_return([
            "Building configuration...",
            "Current configuration : 156 bytes",
            "!",
            "interface FastEthernet0/4",
            " switchport mode access",
            "end"
        ])
        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([
            "Enter configuration commands, one per line.  End with CNTL/Z."
        ])
        self.mocked_ssh_client.should_receive("do").with_args("interface FastEthernet0/4").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("switchport mode trunk").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("switchport trunk allowed vlan none").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("no switchport access vlan").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("write memory").and_return([]).once().ordered()

        self.switch.set_trunk_mode("FastEthernet0/4")

    def test_set_trunk_mode_idempotent(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface FastEthernet0/4").once().ordered().and_return([
            "Building configuration...",
            "Current configuration : 156 bytes",
            "!",
            "interface FastEthernet0/4",
            " switchport trunk allowed vlan 2999",
            " switchport mode trunk",
            "end"
        ])
        self.mocked_ssh_client.should_receive("do").with_args("switchport trunk allowed vlan none").never()
        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([
            "Enter configuration commands, one per line.  End with CNTL/Z."
        ])
        self.mocked_ssh_client.should_receive("do").with_args("interface FastEthernet0/4").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("switchport mode trunk").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("no switchport access vlan").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("write memory").and_return([]).once().ordered()

        self.switch.set_trunk_mode("FastEthernet0/4")

    def test_add_trunk_vlan(self):
        self.command_setup()
        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan 2999").and_return([
            "Building configuration...",
            "Current configuration:",
            "!",
            "vlan 2999",
            "end"]).once().ordered()

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([
            "Enter configuration commands, one per line.  End with CNTL/Z."
        ])
        self.mocked_ssh_client.should_receive("do").with_args("interface FastEthernet0/4").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("switchport trunk allowed vlan add 2999").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("write memory").and_return([]).once().ordered()

        self.switch.add_trunk_vlan("FastEthernet0/4", vlan=2999)

    def test_add_trunk_vlan_invalid_vlan_raises(self):
        self.command_setup()
        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan 2999").and_return([
            "Building configuration...",
            "Current configuration:",
            "end"]).once().ordered()

        with self.assertRaises(UnknownVlan) as expect:
            self.switch.add_trunk_vlan("FastEthernet0/4", vlan=2999)

        assert_that(str(expect.exception), equal_to("Vlan 2999 not found"))

    def test_add_trunk_vlan_invalid_interface_raises(self):
        self.command_setup()
        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan 2999").and_return([
            "Building configuration...",
            "Current configuration:",
            "!",
            "vlan 2999",
            "end"]).once().ordered()

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([
            "Enter configuration commands, one per line.  End with CNTL/Z."
        ])
        self.mocked_ssh_client.should_receive("do").with_args("interface SlowEthernet42/9999").once().ordered().and_return([
            "        ^",
            "% Invalid input detected at '^' marker."
        ])
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).once().ordered()

        with self.assertRaises(UnknownInterface) as expect:
            self.switch.add_trunk_vlan("SlowEthernet42/9999", vlan=2999)

        assert_that(str(expect.exception), equal_to("Unknown interface SlowEthernet42/9999"))

    def test_remove_trunk_vlan(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface FastEthernet0/4 | begin interface").once().ordered().and_return([
            "interface FastEthernet0/4",
            " switchport access vlan 100",
            " switchport trunk native vlan 200",
            " switchport trunk allowed vlan 300,302-304,2998-3000",
            " switchport mode trunk",
            "end",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([
            "Enter configuration commands, one per line.  End with CNTL/Z."
        ])
        self.mocked_ssh_client.should_receive("do").with_args("interface FastEthernet0/4").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("switchport trunk allowed vlan remove 2999").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("write memory").and_return([]).once().ordered()

        self.switch.remove_trunk_vlan("FastEthernet0/4", vlan=2999)

    def test_remove_trunk_vlan_invalid_vlan_raises(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface FastEthernet0/4 | begin interface").once().ordered().and_return([
            "interface FastEthernet0/4",
            " switchport access vlan 100",
            " switchport trunk native vlan 200",
            " switchport trunk allowed vlan 300,302-304",
            " switchport mode trunk",
            "end",
        ])

        with self.assertRaises(UnknownVlan) as expect:
            self.switch.remove_trunk_vlan("FastEthernet0/4", vlan=2999)

        assert_that(str(expect.exception), equal_to("Vlan 2999 not found"))

    def test_remove_trunk_vlan_invalid_interface_raises(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface SlowEthernet42/9999 | begin interface").once().ordered().and_return([
            "        ^",
            "% Invalid input detected at '^' marker."
        ])

        with self.assertRaises(UnknownInterface) as expect:
            self.switch.remove_trunk_vlan("SlowEthernet42/9999", vlan=2999)

        assert_that(str(expect.exception), equal_to("Unknown interface SlowEthernet42/9999"))

    def test_remove_trunk_vlan_no_port_mode_still_working(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface FastEthernet0/4 | begin interface").once().ordered().and_return([
            "interface FastEthernet0/4",
            " switchport access vlan 100",
            " switchport trunk native vlan 200",
            " switchport trunk allowed vlan 300,302-304",
            "end",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([
            "Enter configuration commands, one per line.  End with CNTL/Z."
        ])
        self.mocked_ssh_client.should_receive("do").with_args("interface FastEthernet0/4").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("switchport trunk allowed vlan remove 303").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("write memory").and_return([]).once().ordered()

        self.switch.remove_trunk_vlan("FastEthernet0/4", vlan=303)

    def test_shutdown_interface(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([
            "Enter configuration commands, one per line.  End with CNTL/Z."
        ])
        self.mocked_ssh_client.should_receive("do").with_args("interface FastEthernet0/4").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("shutdown").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("write memory").and_return([]).once().ordered()

        self.switch.shutdown_interface("FastEthernet0/4")

    def test_shutdown_interface_invalid_interface_raises(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([
            "Enter configuration commands, one per line.  End with CNTL/Z."
        ])
        self.mocked_ssh_client.should_receive("do").with_args("interface SlowEthernet42/9999").once().ordered().and_return([
            "        ^",
            "% Invalid input detected at '^' marker."
        ])
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).once().ordered()

        with self.assertRaises(UnknownInterface) as expect:
            self.switch.shutdown_interface("SlowEthernet42/9999")

        assert_that(str(expect.exception), equal_to("Unknown interface SlowEthernet42/9999"))

    def test_openup_interface(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([
            "Enter configuration commands, one per line.  End with CNTL/Z."
        ])
        self.mocked_ssh_client.should_receive("do").with_args("interface FastEthernet0/4").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("no shutdown").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("write memory").and_return([]).once().ordered()

        self.switch.openup_interface("FastEthernet0/4")

    def test_openup_interface_invalid_interface_raises(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([
            "Enter configuration commands, one per line.  End with CNTL/Z."
        ])
        self.mocked_ssh_client.should_receive("do").with_args("interface SlowEthernet42/9999").once().ordered().and_return([
            "        ^",
            "% Invalid input detected at '^' marker."
        ])
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).once().ordered()

        with self.assertRaises(UnknownInterface) as expect:
            self.switch.openup_interface("SlowEthernet42/9999")

        assert_that(str(expect.exception), equal_to("Unknown interface SlowEthernet42/9999"))

    def test_configure_native_vlan_on_trunk(self):
        self.command_setup()
        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan 2999").and_return([
            "Building configuration...",
            "Current configuration:",
            "!",
            "vlan 2999",
            "end"]).once().ordered()

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([
            "Enter configuration commands, one per line.  End with CNTL/Z."
        ])
        self.mocked_ssh_client.should_receive("do").with_args("interface FastEthernet0/4").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("switchport trunk native vlan 2999").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("write memory").and_return([]).once().ordered()

        self.switch.configure_native_vlan("FastEthernet0/4", vlan=2999)

    def test_configure_native_vlan_on_trunk_invalid_vlan_raises(self):
        self.command_setup()
        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan 2999").and_return([
            "Building configuration...",
            "Current configuration:",
            "end"]).once().ordered()

        with self.assertRaises(UnknownVlan) as expect:
            self.switch.configure_native_vlan("FastEthernet0/4", vlan=2999)

        assert_that(str(expect.exception), equal_to("Vlan 2999 not found"))

    def test_configure_native_vlan_on_trunk_invalid_interface_raises(self):
        self.command_setup()
        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan 2999").and_return([
            "Building configuration...",
            "Current configuration:",
            "!",
            "vlan 2999",
            "end"]).once().ordered()

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([
            "Enter configuration commands, one per line.  End with CNTL/Z."
        ])
        self.mocked_ssh_client.should_receive("do").with_args("interface SlowEthernet42/9999").once().ordered().and_return([
            "        ^",
            "% Invalid input detected at '^' marker."
        ])
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).once().ordered()

        with self.assertRaises(UnknownInterface) as expect:
            self.switch.configure_native_vlan("SlowEthernet42/9999", vlan=2999)

        assert_that(str(expect.exception), equal_to("Unknown interface SlowEthernet42/9999"))

    def test_remove_native_vlan_on_trunk(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([
            "Enter configuration commands, one per line.  End with CNTL/Z."
        ])
        self.mocked_ssh_client.should_receive("do").with_args("interface FastEthernet0/4").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("no switchport trunk native vlan").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("write memory").and_return([]).once().ordered()

        self.switch.remove_native_vlan("FastEthernet0/4")

    def test_remove_native_vlan_on_trunk_invalid_interface_raises(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([
            "Enter configuration commands, one per line.  End with CNTL/Z."
        ])
        self.mocked_ssh_client.should_receive("do").with_args("interface SlowEthernet42/9999").once().ordered().and_return([
            "        ^",
            "% Invalid input detected at '^' marker."
        ])
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).once().ordered()

        with self.assertRaises(UnknownInterface) as expect:
            self.switch.remove_native_vlan("SlowEthernet42/9999")

        assert_that(str(expect.exception), equal_to("Unknown interface SlowEthernet42/9999"))

    def test_add_ip(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface vlan 1234").once().ordered().and_return([
            "Building configuration...",
            "Current configuration : 41 bytes",
            "!",
            "interface Vlan1234",
            " no ip address",
            "end"
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([
            "Enter configuration commands, one per line.  End with CNTL/Z."
        ])
        self.mocked_ssh_client.should_receive("do").with_args("interface vlan 1234").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("no shutdown").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("ip address 1.2.3.4 255.255.255.0").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("write memory").and_return([]).once().ordered()

        self.switch.add_ip_to_vlan(1234, IPNetwork("1.2.3.4/24"))

    def test_add_another_ip(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface vlan 1234").once().ordered().and_return([
            "Building configuration...",
            "Current configuration : 41 bytes",
            "!",
            "interface Vlan1234",
            " ip address 2.1.1.1 255.255.255.0 secondary",
            " ip address 1.2.1.1 255.255.255.128",
            " ip access-group SHIZZLE in",
            " ip access-group wHIZZLE out",
            "end"
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([
            "Enter configuration commands, one per line.  End with CNTL/Z."
        ])
        self.mocked_ssh_client.should_receive("do").with_args("interface vlan 1234").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("no shutdown").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("no ip redirects").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("ip address 2.3.4.5 255.255.255.128 secondary").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("write memory").and_return([]).once().ordered()

        self.switch.add_ip_to_vlan(1234, IPNetwork("2.3.4.5/25"))

    def test_add_unavailable_ip_raises(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface vlan 1234").once().ordered().and_return([
            "Building configuration...",
            "Current configuration : 41 bytes",
            "!",
            "interface Vlan1234",
            " no ip address",
            "end"
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([
            "Enter configuration commands, one per line.  End with CNTL/Z."
        ])
        self.mocked_ssh_client.should_receive("do").with_args("interface vlan 1234").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("no shutdown").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("ip address 1.2.3.4 255.255.255.0").and_return([
            "% 2.1.1.128 overlaps with secondary address on Vlan2998"
        ]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()

        with self.assertRaises(IPNotAvailable) as expect:
            self.switch.add_ip_to_vlan(1234, IPNetwork("1.2.3.4/24"))

        assert_that(str(expect.exception), equal_to("IP 1.2.3.4/24 is not available in this vlan: % 2.1.1.128 overlaps with secondary address on Vlan2998"))

    def test_add_unavailable_ip_because_secondary_elsewhere_raises(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface vlan 1234").once().ordered().and_return([
            "Building configuration...",
            "Current configuration : 41 bytes",
            "!",
            "interface Vlan1234",
            " no ip address",
            "end"
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([
            "Enter configuration commands, one per line.  End with CNTL/Z."
        ])
        self.mocked_ssh_client.should_receive("do").with_args("interface vlan 1234").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("no shutdown").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("ip address 1.2.3.4 255.255.255.0").and_return([
            "% 2.1.1.128 is assigned as a secondary address on Vlan2998"
        ]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()

        with self.assertRaises(IPNotAvailable) as expect:
            self.switch.add_ip_to_vlan(1234, IPNetwork("1.2.3.4/24"))

        assert_that(str(expect.exception), equal_to("IP 1.2.3.4/24 is not available in this vlan: % 2.1.1.128 is assigned as a secondary address on Vlan2998"))

    def test_add_an_ip_already_present_in_the_same_port_raises(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface vlan 1234").once().ordered().and_return([
            "Building configuration...",
            "Current configuration : 41 bytes",
            "!",
            "interface Vlan1234",
            " ip address 1.2.3.4 255.255.255.128",
            " ip access-group SHIZZLE in",
            " ip access-group wHIZZLE out",
            "end"
        ])

        with self.assertRaises(IPAlreadySet) as expect:
            self.switch.add_ip_to_vlan(1234, IPNetwork("1.2.3.4/24"))

        assert_that(str(expect.exception), equal_to("IP 1.2.3.4/24 is already present in this vlan as 1.2.3.4/25"))

    def test_add_an_ip_already_present_in_the_same_port_secondary_raises(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface vlan 1234").once().ordered().and_return([
            "Building configuration...",
            "Current configuration : 41 bytes",
            "!",
            "interface Vlan1234",
            " ip address 2.1.1.1 255.255.255.0 secondary",
            " ip address 1.2.3.4 255.255.255.128",
            " ip access-group SHIZZLE in",
            " ip access-group wHIZZLE out",
            "end"
        ])

        with self.assertRaises(IPAlreadySet) as expect:
            self.switch.add_ip_to_vlan(1234, IPNetwork("2.1.1.1/24"))

        assert_that(str(expect.exception), equal_to("IP 2.1.1.1/24 is already present in this vlan as 2.1.1.1/24"))

    def test_add_ip_to_vlan_without_interface_creates_it(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface vlan 1234").once().ordered().and_return([
            "                                  ^",
            "% Invalid input detected at '^' marker.",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan 1234").once().ordered().and_return([
            "Building configuration...",
            "Current configuration:",
            "!",
            "vlan 1234",
            "end",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([
            "Enter configuration commands, one per line.  End with CNTL/Z."
        ])
        self.mocked_ssh_client.should_receive("do").with_args("interface vlan 1234").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("no shutdown").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("ip address 1.2.3.4 255.255.255.0").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("write memory").and_return([]).once().ordered()

        self.switch.add_ip_to_vlan(1234, IPNetwork("1.2.3.4/24"))

    def test_add_ip_to_unknown_vlan(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface vlan 1234").once().ordered().and_return([
            "                                  ^",
            "% Invalid input detected at '^' marker.",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan 1234").once().ordered().and_return([
            "Building configuration...",
            "Current configuration:",
            "end",
        ])

        with self.assertRaises(UnknownVlan) as expect:
            self.switch.add_ip_to_vlan(1234, IPNetwork("1.2.3.4/24"))

        assert_that(str(expect.exception), equal_to("Vlan 1234 not found"))

    def test_remove_lonely_ip(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface vlan 1234").once().ordered().and_return([
            "Building configuration...",
            "Current configuration : 41 bytes",
            "!",
            "interface Vlan1234",
            " ip address 1.2.3.4 255.255.255.128",
            "end"
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([
            "Enter configuration commands, one per line.  End with CNTL/Z."
        ])
        self.mocked_ssh_client.should_receive("do").with_args("interface vlan 1234").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("no shutdown").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("no ip address 1.2.3.4 255.255.255.128").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("write memory").and_return([]).once().ordered()

        self.switch.remove_ip_from_vlan(1234, IPNetwork("1.2.3.4/25"))

    def test_remove_secondary_ip(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface vlan 1234").once().ordered().and_return([
            "Building configuration...",
            "Current configuration : 41 bytes",
            "!",
            "interface Vlan1234",
            " ip address 2.1.1.1 255.255.255.0 secondary",
            " ip address 1.2.3.4 255.255.255.128",
            "end"
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([
            "Enter configuration commands, one per line.  End with CNTL/Z."
        ])
        self.mocked_ssh_client.should_receive("do").with_args("interface vlan 1234").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("no shutdown").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("no ip address 2.1.1.1 255.255.255.0 secondary").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("write memory").and_return([]).once().ordered()

        self.switch.remove_ip_from_vlan(1234, IPNetwork("2.1.1.1/24"))

    def test_remove_a_primary_ip_that_have_secondary_ips(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface vlan 1234").once().ordered().and_return([
            "Building configuration...",
            "Current configuration : 41 bytes",
            "!",
            "interface Vlan1234",
            " ip address 2.1.1.1 255.255.255.0 secondary",
            " ip address 3.1.1.1 255.255.255.0 secondary",
            " ip address 1.2.3.4 255.255.255.128",
            "end"
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([
            "Enter configuration commands, one per line.  End with CNTL/Z."
        ])
        self.mocked_ssh_client.should_receive("do").with_args("interface vlan 1234").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("no shutdown").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("ip address 2.1.1.1 255.255.255.0").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("write memory").and_return([]).once().ordered()

        self.switch.remove_ip_from_vlan(1234, IPNetwork("1.2.3.4/25"))

    def test_cant_remove_unknown_ip(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface vlan 1234").once().ordered().and_return([
            "Building configuration...",
            "Current configuration : 41 bytes",
            "!",
            "interface Vlan1234",
            " ip address 2.1.1.1 255.255.255.0 secondary",
            " ip address 3.1.1.1 255.255.255.0 secondary",
            " ip address 1.2.3.4 255.255.255.128",
            "end"
        ])

        with self.assertRaises(UnknownIP) as expect:
            self.switch.remove_ip_from_vlan(1234, IPNetwork("5.5.5.5/25"))

        assert_that(str(expect.exception), equal_to("IP 5.5.5.5/25 not found"))

    def test_cant_remove_known_ip_with_wrong_netmask(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface vlan 1234").once().ordered().and_return([
            "Building configuration...",
            "Current configuration : 41 bytes",
            "!",
            "interface Vlan1234",
            " ip address 2.1.1.1 255.255.255.0 secondary",
            " ip address 3.1.1.1 255.255.255.0 secondary",
            " ip address 1.2.3.4 255.255.255.128",
            "end"
        ])

        with self.assertRaises(UnknownIP) as expect:
            self.switch.remove_ip_from_vlan(1234, IPNetwork("1.2.3.4/27"))

        assert_that(str(expect.exception), equal_to("IP 1.2.3.4/27 not found"))

    def test_remove_ip_from_known_vlan_with_no_interface(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface vlan 1234").once().ordered().and_return([
            "                                  ^",
            "% Invalid input detected at '^' marker.",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan 1234").once().ordered().and_return([
            "Building configuration...",
            "Current configuration:",
            "!",
            "vlan 1234",
            "end",
        ])

        with self.assertRaises(UnknownIP) as expect:
            self.switch.remove_ip_from_vlan(1234, IPNetwork("1.2.3.4/24"))

        assert_that(str(expect.exception), equal_to("IP 1.2.3.4/24 not found"))

    def test_remove_ip_from_unknown_vlan(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface vlan 1234").once().ordered().and_return([
            "                                  ^",
            "% Invalid input detected at '^' marker.",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan 1234").once().ordered().and_return([
            "Building configuration...",
            "Current configuration:",
            "end",
        ])

        with self.assertRaises(UnknownVlan) as expect:
            self.switch.remove_ip_from_vlan(1234, IPNetwork("1.2.3.4/24"))

        assert_that(str(expect.exception), equal_to("Vlan 1234 not found"))

    def test_set_access_group_success(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface vlan 2500").once().ordered().and_return([
            "Building configuration...",
            "Current configuration : 41 bytes",
            "!",
            "interface Vlan2500",
            " no ip address",
            "end"
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([
            "Enter configuration commands, one per line.  End with CNTL/Z."
        ])
        self.mocked_ssh_client.should_receive("do").with_args("interface vlan 2500").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("no shutdown").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("ip access-group TheAccessGroup in").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("write memory").and_return([]).once().ordered()

        self.switch.set_vlan_access_group(2500, IN, "TheAccessGroup")

    def test_set_access_group_incorrect_name(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface vlan 2500").once().ordered().and_return([
            "Building configuration...",
            "Current configuration : 41 bytes",
            "!",
            "interface Vlan2500",
            " no ip address",
            "end"
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([
            "Enter configuration commands, one per line.  End with CNTL/Z."
        ])
        self.mocked_ssh_client.should_receive("do").with_args("interface vlan 2500").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("no shutdown").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("ip access-group TheAc cessGroup out").once().ordered().and_return([
            "                                              ^",
            "% Invalid input detected at '^' marker."
        ])
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()

        with self.assertRaises(ValueError) as expect:
            self.switch.set_vlan_access_group(2500, OUT, "TheAc cessGroup")

        assert_that(str(expect.exception), equal_to("Access group name \"TheAc cessGroup\" is invalid"))

    def test_set_access_group_without_interface_creates_it(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface vlan 2500").once().ordered().and_return([
            "                                  ^",
            "% Invalid input detected at '^' marker.",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan 2500").once().ordered().and_return([
            "Building configuration...",
            "Current configuration:",
            "!",
            "vlan 2500",
            "end",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([
            "Enter configuration commands, one per line.  End with CNTL/Z."
        ])
        self.mocked_ssh_client.should_receive("do").with_args("interface vlan 2500").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("no shutdown").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("ip access-group TheAccessGroup in").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("write memory").and_return([]).once().ordered()

        self.switch.set_vlan_access_group(2500, IN, "TheAccessGroup")

    def test_set_access_group_unknown_vlan(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface vlan 2500").once().ordered().and_return([
            "                                  ^",
            "% Invalid input detected at '^' marker.",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan 2500").once().ordered().and_return([
            "Building configuration...",
            "Current configuration:",
            "end",
        ])

        with self.assertRaises(UnknownVlan) as expect:
            self.switch.set_vlan_access_group(2500, IN, "TheAccessGroup")

        assert_that(str(expect.exception), equal_to("Vlan 2500 not found"))

    def test_remove_access_group_success(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface vlan 2500").once().ordered().and_return([
            "Building configuration...",
            "Current configuration : 41 bytes",
            "!",
            "interface Vlan2500",
            " no ip address",
            " ip access-group TheAccessGroup in",
            "end"
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([
            "Enter configuration commands, one per line.  End with CNTL/Z."
        ])
        self.mocked_ssh_client.should_receive("do").with_args("interface vlan 2500").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("no shutdown").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("no ip access-group in").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("write memory").and_return([]).once().ordered()

        self.switch.remove_vlan_access_group(2500, IN)

    def test_remove_access_group_success_out_also(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface vlan 2500").once().ordered().and_return([
            "Building configuration...",
            "Current configuration : 41 bytes",
            "!",
            "interface Vlan2500",
            " no ip address",
            " ip access-group TheAccessGroup out",
            "end"
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([
            "Enter configuration commands, one per line.  End with CNTL/Z."
        ])
        self.mocked_ssh_client.should_receive("do").with_args("interface vlan 2500").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("no shutdown").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("no ip access-group out").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("write memory").and_return([]).once().ordered()

        self.switch.remove_vlan_access_group(2500, OUT)

    def test_remove_access_group_not_set(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface vlan 2500").once().ordered().and_return([
            "Building configuration...",
            "Current configuration : 41 bytes",
            "!",
            "interface Vlan2500",
            " no ip address",
            " ip access-group TheAccessGroup in",
            "end"
        ])

        with self.assertRaises(UnknownAccessGroup) as expect:
            self.switch.remove_vlan_access_group(2500, OUT)

        assert_that(str(expect.exception), equal_to("Outgoing IP access group not found"))

    def test_remove_access_group_from_known_vlan_with_no_interface(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface vlan 2500").once().ordered().and_return([
            "                                  ^",
            "% Invalid input detected at '^' marker.",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan 2500").once().ordered().and_return([
            "Building configuration...",
            "Current configuration:",
            "!",
            "vlan 2500",
            "end",
        ])

        with self.assertRaises(UnknownAccessGroup) as expect:
            self.switch.remove_vlan_access_group(2500, IN)

        assert_that(str(expect.exception), equal_to("Inbound IP access group not found"))

    def test_remove_access_group_from_unknown_vlan(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface vlan 2500").once().ordered().and_return([
            "                                  ^",
            "% Invalid input detected at '^' marker.",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan 2500").once().ordered().and_return([
            "Building configuration...",
            "Current configuration:",
            "end",
        ])

        with self.assertRaises(UnknownVlan) as expect:
            self.switch.remove_vlan_access_group(2500, IN)

        assert_that(str(expect.exception), equal_to("Vlan 2500 not found"))

    def test_set_vlan_vrf_success(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface vlan 2500").once().ordered().and_return([
            "Building configuration...",
            "Current configuration : 41 bytes",
            "!",
            "interface Vlan2500",
            " no ip address",
            "end"
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([
            "Enter configuration commands, one per line.  End with CNTL/Z."
        ])
        self.mocked_ssh_client.should_receive("do").with_args("interface vlan 2500").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("no shutdown").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("ip vrf forwarding MYVRF").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("write memory").and_return([]).once().ordered()

        self.switch.set_vlan_vrf(2500, "MYVRF")

    def test_set_vlan_vrf_incorrect_name(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface vlan 2500").once().ordered().and_return([
            "Building configuration...",
            "Current configuration : 41 bytes",
            "!",
            "interface Vlan2500",
            " no ip address",
            "end"
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([
            "Enter configuration commands, one per line.  End with CNTL/Z."
        ])
        self.mocked_ssh_client.should_receive("do").with_args("interface vlan 2500").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("no shutdown").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("ip vrf forwarding MYVRF").once().ordered().and_return([
            "% VRF MYVRF not configured."
        ])
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()

        with self.assertRaises(UnknownVrf) as expect:
            self.switch.set_vlan_vrf(2500, "MYVRF")

        assert_that(str(expect.exception), equal_to("VRF name \"MYVRF\" was not configured."))

    def test_set_vlan_vrf_without_interface_creates_it(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface vlan 2500").once().ordered().and_return([
            "                                  ^",
            "% Invalid input detected at '^' marker.",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan 2500").once().ordered().and_return([
            "Building configuration...",
            "Current configuration:",
            "!",
            "vlan 2500",
            "end",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([
            "Enter configuration commands, one per line.  End with CNTL/Z."
        ])
        self.mocked_ssh_client.should_receive("do").with_args("interface vlan 2500").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("no shutdown").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("ip vrf forwarding MYVRF").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("write memory").and_return([]).once().ordered()

        self.switch.set_vlan_vrf(2500, "MYVRF")

    def test_set_vlan_vrf_unknown_vlan(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface vlan 2500").once().ordered().and_return([
            "                                  ^",
            "% Invalid input detected at '^' marker.",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan 2500").once().ordered().and_return([
            "Building configuration...",
            "Current configuration:",
            "end",
        ])

        with self.assertRaises(UnknownVlan) as expect:
            self.switch.set_vlan_vrf(2500, "MYVRF")

        assert_that(str(expect.exception), equal_to("Vlan 2500 not found"))

    def test_remove_vlan_vrf_success(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface vlan 2500").once().ordered().and_return([
            "Building configuration...",
            "Current configuration : 41 bytes",
            "!",
            "interface Vlan2500",
            " no ip address",
            " ip vrf forwarding DEFAULT-LAN",
            "end"
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([
            "Enter configuration commands, one per line.  End with CNTL/Z."
        ])
        self.mocked_ssh_client.should_receive("do").with_args("interface vlan 2500").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("no shutdown").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("no ip vrf forwarding").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("write memory").and_return([]).once().ordered()

        self.switch.remove_vlan_vrf(2500)

    def test_remove_vlan_vrf_not_set(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface vlan 2500").once().ordered().and_return([
            "Building configuration...",
            "Current configuration : 41 bytes",
            "!",
            "interface Vlan2500",
            " no ip address",
            "end"
        ])

        with self.assertRaises(VlanVrfNotSet) as expect:
            self.switch.remove_vlan_vrf(2500)

        assert_that(str(expect.exception), equal_to("VRF is not set on vlan 2500"))

    def test_remove_vlan_vrf_from_known_vlan_with_no_interface(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface vlan 2500").once().ordered().and_return([
            "                                  ^",
            "% Invalid input detected at '^' marker.",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan 2500").once().ordered().and_return([
            "Building configuration...",
            "Current configuration:",
            "!",
            "vlan 2500",
            "end",
        ])

        with self.assertRaises(VlanVrfNotSet) as expect:
            self.switch.remove_vlan_vrf(2500)

        assert_that(str(expect.exception), equal_to("VRF is not set on vlan 2500"))

    def test_remove_vlan_vrf_from_unknown_vlan(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface vlan 2500").once().ordered().and_return([
            "                                  ^",
            "% Invalid input detected at '^' marker.",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan 2500").once().ordered().and_return([
            "Building configuration...",
            "Current configuration:",
            "end",
        ])

        with self.assertRaises(UnknownVlan) as expect:
            self.switch.remove_vlan_vrf(2500)

        assert_that(str(expect.exception), equal_to("Vlan 2500 not found"))

    @mock.patch("netman.adapters.shell.ssh.SshClient")
    def test_connect(self, ssh_client_class_mock):
        self.switch = Cisco(SwitchDescriptor(hostname="my.hostname", username="the_user", password="the_password", model="cisco"))

        self.mocked_ssh_client = flexmock()
        ssh_client_class_mock.return_value = self.mocked_ssh_client
        self.mocked_ssh_client.should_receive("get_current_prompt").and_return("hostname>").once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("enable", wait_for=": ").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("the_password").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("terminal length 0").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("terminal width 0").and_return([]).once().ordered()

        self.switch.connect()

        ssh_client_class_mock.assert_called_with(
            host="my.hostname",
            username="the_user",
            password="the_password",
            port=22
        )

    @mock.patch("netman.adapters.shell.ssh.SshClient")
    def test_auto_enabled_switch_doesnt_require_enable(self, ssh_client_class_mock):
        self.switch = Cisco(SwitchDescriptor(hostname="my.hostname", username="the_user", password="the_password", model="cisco", port=8000))

        self.mocked_ssh_client = flexmock()
        ssh_client_class_mock.return_value = self.mocked_ssh_client
        self.mocked_ssh_client.should_receive("get_current_prompt").and_return("hostname#").once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("enable", wait_for=": ").never()
        self.mocked_ssh_client.should_receive("do").with_args("terminal length 0").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("terminal width 0").and_return([]).once().ordered()

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

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([
            "Enter configuration commands, one per line.  End with CNTL/Z."
        ])
        self.mocked_ssh_client.should_receive("do").with_args("vlan 2999").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("name Gertrude").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).once().ordered()

        self.switch.start_transaction()
        self.switch.add_vlan(2999, name="Gertrude")

        self.mocked_ssh_client.should_receive("do").with_args("write memory").once().ordered()

        self.switch.commit_transaction()
        self.switch.end_transaction()

    def test_add_vrrp_success_single_ip(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface vlan 1234").once().ordered().and_return([
            "Building configuration...",
            "Current configuration : 41 bytes",
            "!",
            "interface Vlan1234",
            " no ip address",
            "end"
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([
            "Enter configuration commands, one per line.  End with CNTL/Z."
        ])
        self.mocked_ssh_client.should_receive("do").with_args("interface vlan 1234").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("no shutdown").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("standby 1 timers 5 15").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("standby 1 priority 110").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("standby 1 preempt delay minimum 60").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("standby 1 authentication VLAN1234").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("standby 1 track 101 decrement 50").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("standby 1 ip 1.2.3.4").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("write memory").and_return([]).once().ordered()

        self.switch.add_vrrp_group(1234, 1, ips=[IPAddress("1.2.3.4")], priority=110, hello_interval=5, dead_interval=15,
                                   track_id=101, track_decrement=50)

    def test_add_vrrp_success_multiple_ip(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface vlan 1234").once().ordered().and_return([
            "Building configuration...",
            "Current configuration : 41 bytes",
            "!",
            "interface Vlan1234",
            " no ip address",
            "end"
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([
            "Enter configuration commands, one per line.  End with CNTL/Z."
        ])
        self.mocked_ssh_client.should_receive("do").with_args("interface vlan 1234").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("no shutdown").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("standby 1 timers 5 15").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("standby 1 priority 110").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("standby 1 preempt delay minimum 60").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("standby 1 authentication VLAN1234").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("standby 1 track 101 decrement 50").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("standby 1 ip 1.2.3.4").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("standby 1 ip 5.6.7.8 secondary").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("write memory").and_return([]).once().ordered()

        self.switch.add_vrrp_group(1234, 1, ips=[IPAddress("1.2.3.4"), IPAddress("5.6.7.8")], priority=110,
                                   hello_interval=5, dead_interval=15, track_id=101,
                                   track_decrement=50)

    def test_add_vrrp_from_unknown_vlan(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface vlan 1234").once().ordered().and_return([
            "                                  ^",
            "% Invalid input detected at '^' marker.",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan 1234").once().ordered().and_return([
            "Building configuration...",
            "Current configuration:",
            "end",
        ])

        with self.assertRaises(UnknownVlan) as expect:
            self.switch.add_vrrp_group(1234, 1, ips=[IPAddress("1.2.3.4")])

        assert_that(str(expect.exception), equal_to("Vlan 1234 not found"))

    def test_add_existing_vrrp_to_same_vlan(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface vlan 1234").once().ordered().and_return([
            "Building configuration...",
            "Current configuration : 41 bytes",
            "!",
            "interface Vlan1234",
            " no ip address",
            " standby 1 ip 5.6.7.8",
            " standby 1 priority 80",
            "end"
        ])

        with self.assertRaises(VrrpAlreadyExistsForVlan) as expect:
            self.switch.add_vrrp_group(1234, 1, ips=[IPAddress("1.2.3.4")], priority=90)

        assert_that(str(expect.exception), equal_to("Vrrp group 1 is already in use on vlan 1234"))

    def test_add_vrrp_to_vlan_with_another_vrrp(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface vlan 1234").once().ordered().and_return([
            "Building configuration...",
            "Current configuration : 41 bytes",
            "!",
            "interface Vlan1234",
            " no ip address",
            " standby 1 ip 5.6.7.8",
            " standby 1 priority 80",
            " standby 1 preempt delay minimum 60",
            "end"
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([
            "Enter configuration commands, one per line.  End with CNTL/Z."
        ])
        self.mocked_ssh_client.should_receive("do").with_args("interface vlan 1234").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("no shutdown").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("standby 2 priority 90").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("standby 2 preempt delay minimum 60").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("standby 2 authentication VLAN1234").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("standby 2 ip 1.2.3.5").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("write memory").and_return([]).once().ordered()

        self.switch.add_vrrp_group(1234, 2, ips=[IPAddress("1.2.3.5")], priority=90)

    def test_add_vrrp_with_out_of_range_group_id(self):
        self.command_setup()

        with self.assertRaises(BadVrrpGroupNumber) as expect:
            self.switch.add_vrrp_group(1234, 0, ips=[IPAddress("1.2.3.4")], priority=255)

        assert_that(str(expect.exception), equal_to("VRRP group number is invalid, must be contained between 1 and 255"))

    def test_add_vrrp_with_bad_priority(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface vlan 1234").once().ordered().and_return([
            "Building configuration...",
            "Current configuration : 41 bytes",
            "!",
            "interface Vlan1234",
            " no ip address",
            "end"
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([
            "Enter configuration commands, one per line.  End with CNTL/Z."
        ])
        self.mocked_ssh_client.should_receive("do").with_args("interface vlan 1234").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("no shutdown").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("standby 1 priority 256").and_return(["                                               ^",
                                                                                                    "% Invalid input detected at '^' marker."
                                                                                                    ""]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()

        with self.assertRaises(BadVrrpPriorityNumber) as expect:
            self.switch.add_vrrp_group(1234, 1, ips=[IPAddress("1.2.3.4")], priority=256)

        assert_that(str(expect.exception), equal_to("VRRP priority value is invalid, must be contained between 1 and 255"))

    def test_add_vrrp_with_bad_timers(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface vlan 1234").once().ordered().and_return([
            "Building configuration...",
            "Current configuration : 41 bytes",
            "!",
            "interface Vlan1234",
            " no ip address",
            "end"
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([
            "Enter configuration commands, one per line.  End with CNTL/Z."
        ])
        self.mocked_ssh_client.should_receive("do").with_args("interface vlan 1234").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("no shutdown").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("standby 1 timers -1 -1").and_return([
            "                                               ^",
            "% Invalid input detected at '^' marker.",
            ""
        ]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()

        with self.assertRaises(BadVrrpTimers) as expect:
            self.switch.add_vrrp_group(1234, 1, ips=[IPAddress("1.2.3.4")], hello_interval=-1, dead_interval=-1)

        assert_that(str(expect.exception), equal_to("VRRP timers values are invalid"))

    def test_add_vrrp_with_bad_tracking(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface vlan 1234").once().ordered().and_return([
            "Building configuration...",
            "Current configuration : 41 bytes",
            "!",
            "interface Vlan1234",
            " no ip address",
            "end"
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([
            "Enter configuration commands, one per line.  End with CNTL/Z."
        ])
        self.mocked_ssh_client.should_receive("do").with_args("interface vlan 1234").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("no shutdown").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("standby 1 preempt delay minimum 60").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("standby 1 authentication VLAN1234").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("standby 1 track SOMETHING decrement VALUE").and_return([
            "                                               ^",
            "% Invalid input detected at '^' marker.",
            ""
        ]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()

        with self.assertRaises(BadVrrpTracking) as expect:
            self.switch.add_vrrp_group(1234, 1, ips=[IPAddress("1.2.3.4")], track_id='SOMETHING', track_decrement='VALUE')

        assert_that(str(expect.exception), equal_to("VRRP tracking values are invalid"))

    def test_remove_vrrp_success(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface vlan 1234").once().ordered().and_return([
            "Building configuration...",
            "Current configuration : 41 bytes",
            "!",
            "interface Vlan1234",
            " standby 1 ip 1.2.3.4",
            " standby 1 ip 5.6.7.8 secondary",
            " standby 1 timers 5 15",
            " standby 1 priority 110",
            " standby 1 preempt delay minimum 60",
            " standby 1 authentication VLAN1234",
            " standby 1 track 101 decrement 50",
            "end"
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([
            "Enter configuration commands, one per line.  End with CNTL/Z."
        ])
        self.mocked_ssh_client.should_receive("do").with_args("interface vlan 1234").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("no shutdown").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("no standby 1").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("write memory").and_return([]).once().ordered()

        self.switch.remove_vrrp_group(1234, 1)

    def test_remove_vrrp_with_invalid_group_id(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface vlan 1234").once().ordered().and_return([
            "Building configuration...",
            "Current configuration : 41 bytes",
            "!",
            "interface Vlan1234",
            " no ip address",
            "end"
        ])

        with self.assertRaises(VrrpDoesNotExistForVlan) as expect:
            self.switch.remove_vrrp_group(1234, 256)

        assert_that(str(expect.exception), equal_to("Vrrp group 256 does not exist for vlan 1234"))

    def test_remove_vrrp_from_unknown_vlan(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface vlan 1234").once().ordered().and_return([
            "                                  ^",
            "% Invalid input detected at '^' marker.",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan 1234").once().ordered().and_return([
            "Building configuration...",
            "Current configuration:",
            "end",
        ])

        with self.assertRaises(UnknownVlan) as expect:
            self.switch.remove_vrrp_group(1234, 1)

        assert_that(str(expect.exception), equal_to("Vlan 1234 not found"))

    def test_add_dhcp_relay_server(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface vlan 1234").once().ordered().and_return([
            "Building configuration...",
            "Current configuration : 41 bytes",
            "!",
            "interface Vlan1234",
            " no ip address",
            "end"
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([
            "Enter configuration commands, one per line.  End with CNTL/Z."
        ])
        self.mocked_ssh_client.should_receive("do").with_args("interface vlan 1234").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("no shutdown").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("ip helper-address 10.10.10.1").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("write memory").and_return([]).once().ordered()

        self.switch.add_dhcp_relay_server(1234, IPAddress('10.10.10.1'))

    def test_add_second_dhcp_relay_server(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface vlan 1234").once().ordered().and_return([
            "Building configuration...",
            "Current configuration : 41 bytes",
            "!",
            "interface Vlan1234",
            " no ip address",
            " ip helper-address 10.10.10.1",
            "end"
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([
            "Enter configuration commands, one per line.  End with CNTL/Z."
        ])
        self.mocked_ssh_client.should_receive("do").with_args("interface vlan 1234").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("no shutdown").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("ip helper-address 10.10.10.2").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("write memory").and_return([]).once().ordered()

        self.switch.add_dhcp_relay_server(1234, IPAddress('10.10.10.2'))

    def test_add_same_dhcp_relay_server_fails(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface vlan 1234").once().ordered().and_return([
            "Building configuration...",
            "Current configuration : 41 bytes",
            "!",
            "interface Vlan1234",
            " no ip address",
            " ip helper-address 10.10.10.1",
            "end"
        ])

        with self.assertRaises(DhcpRelayServerAlreadyExists) as expect:
            self.switch.add_dhcp_relay_server(1234, IPAddress('10.10.10.1'))

        assert_that(str(expect.exception), equal_to("DHCP relay server 10.10.10.1 already exists on VLAN 1234"))

    def test_remove_dhcp_relay_server(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface vlan 1234").once().ordered().and_return([
            "Building configuration...",
            "Current configuration : 41 bytes",
            "!",
            "interface Vlan1234",
            " no ip address",
            " ip helper-address 10.10.10.1",
            "end"
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([
            "Enter configuration commands, one per line.  End with CNTL/Z."
        ])
        self.mocked_ssh_client.should_receive("do").with_args("interface vlan 1234").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("no shutdown").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("no ip helper-address 10.10.10.1").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("write memory").and_return([]).once().ordered()

        self.switch.remove_dhcp_relay_server(1234, IPAddress('10.10.10.1'))

    def test_remove_non_existent_dhcp_relay_server_fails(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface vlan 1234").once().ordered().and_return([
            "Building configuration...",
            "Current configuration : 41 bytes",
            "!",
            "interface Vlan1234",
            " no ip address",
            "end"
        ])

        with self.assertRaises(UnknownDhcpRelayServer) as expect:
            self.switch.remove_dhcp_relay_server(1234, IPAddress('10.10.10.1'))

        assert_that(str(expect.exception), equal_to("DHCP relay server 10.10.10.1 not found on VLAN 1234"))
