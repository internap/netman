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
from contextlib import contextmanager

import mock
from flexmock import flexmock, flexmock_teardown
from hamcrest import assert_that, equal_to, is_, instance_of, has_length, none

from netman.adapters.shell.ssh import SshClient
from netman.adapters.shell.telnet import TelnetClient
from netman.adapters.switches import dell
from netman.adapters.switches.dell import Dell
from netman.adapters.switches.util import SubShell
from netman.core.objects.exceptions import UnknownInterface, BadVlanNumber, \
    BadVlanName, UnknownVlan, InterfaceInWrongPortMode, NativeVlanNotSet, TrunkVlanNotSet, BadInterfaceDescription, \
    VlanAlreadyExist, UnknownBond, InvalidMtuSize, InterfaceResetIncomplete, \
    PrivilegedAccessRefused
from netman.core.objects.interface_states import OFF, ON
from netman.core.objects.port_modes import ACCESS, TRUNK
from netman.core.objects.switch_descriptor import SwitchDescriptor
from netman.core.objects.switch_transactional import FlowControlSwitch
from tests import ignore_deprecation_warnings


@ignore_deprecation_warnings
def test_factory_ssh():
    lock = mock.Mock()
    descriptor = SwitchDescriptor(hostname='hostname', model='dell', username='username', password='password', port=22)
    switch = dell.factory_ssh(descriptor, lock)

    assert_that(switch, instance_of(FlowControlSwitch))
    assert_that(switch.wrapped_switch, instance_of(Dell))
    assert_that(switch.wrapped_switch.shell_factory, equal_to(SshClient))
    assert_that(switch.lock, is_(lock))
    assert_that(switch.switch_descriptor, is_(descriptor))


@ignore_deprecation_warnings
def test_factory_telnet():
    lock = mock.Mock()
    descriptor = SwitchDescriptor(hostname='hostname', model='dell', username='username', password='password', port=22)
    switch = dell.factory_telnet(descriptor, lock)

    assert_that(switch, instance_of(FlowControlSwitch))
    assert_that(switch.wrapped_switch, instance_of(Dell))
    assert_that(switch.wrapped_switch.shell_factory, equal_to(TelnetClient))
    assert_that(switch.lock, is_(lock))
    assert_that(switch.switch_descriptor, is_(descriptor))


class DellTest(unittest.TestCase):

    def setUp(self):
        self.switch = Dell(SwitchDescriptor(model='dell', hostname="my.hostname", password="the_password"), None)
        SubShell.debug = True
        self.mocked_ssh_client = flexmock()
        self.switch.shell = self.mocked_ssh_client

    def tearDown(self):
        flexmock_teardown()

    def test_switch_has_a_logger_configured_with_the_switch_name(self):
        assert_that(self.switch.logger.name, is_(Dell.__module__ + ".my.hostname"))

    @mock.patch("netman.adapters.shell.ssh.SshClient")
    def test_connect(self, ssh_client_class_mock):
        self.switch = Dell(
            SwitchDescriptor(hostname="my.hostname", username="the_user", password="the_password", model="dell", port=22),
            shell_factory=ssh_client_class_mock)

        self.mocked_ssh_client = flexmock()
        ssh_client_class_mock.return_value = self.mocked_ssh_client
        self.mocked_ssh_client.should_receive("do").with_args("enable", wait_for=":").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("the_password", use_connect_timeout=True)\
            .and_return([]).once().ordered()

        self.switch.connect()

        ssh_client_class_mock.assert_called_with(
            host="my.hostname",
            username="the_user",
            password="the_password",
            port=22
        )

    @mock.patch("netman.adapters.shell.telnet.TelnetClient")
    def test_connect_without_port_uses_default(self, telnet_client_class_mock):
        self.switch = Dell(
            SwitchDescriptor(hostname="my.hostname", username="the_user", password="the_password", model="dell"),
            shell_factory=telnet_client_class_mock)

        self.mocked_ssh_client = flexmock()
        telnet_client_class_mock.return_value = self.mocked_ssh_client
        self.mocked_ssh_client.should_receive("do").with_args("enable", wait_for=":").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("the_password", use_connect_timeout=True)\
            .and_return([]).once().ordered()

        self.switch.connect()

        telnet_client_class_mock.assert_called_with(
            host="my.hostname",
            username="the_user",
            password="the_password"
        )

    @mock.patch("netman.adapters.shell.telnet.TelnetClient")
    def test_enable_with_wrong_password(self, telnet_client_class_mock):
        self.switch = Dell(
            SwitchDescriptor(hostname="my.hostname", username="the_user",
                             password="the_password", model="dell"),
            shell_factory=telnet_client_class_mock)

        self.mocked_ssh_client = flexmock()
        telnet_client_class_mock.return_value = self.mocked_ssh_client
        self.mocked_ssh_client.should_receive("do").with_args("enable", wait_for=":")\
            .and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("the_password", use_connect_timeout=True)\
            .and_return(['Incorrect Password!']).once().ordered()

        with self.assertRaises(PrivilegedAccessRefused) as expect:
            self.switch.connect()

        assert_that(str(expect.exception),
                    equal_to("Could not get PRIVILEGED exec mode. "
                             "Current read buffer: ['Incorrect Password!']"))

    def test_disconnect(self):
        logger = flexmock()
        self.switch.logger = logger
        logger.should_receive("debug")

        mocked_ssh_client = flexmock()
        self.switch.shell = mocked_ssh_client
        mocked_ssh_client.should_receive("quit").with_args("quit").once().ordered()

        logger.should_receive("info").with_args("FULL TRANSACTION LOG").once()

        self.switch.shell.full_log = "FULL TRANSACTION LOG"
        self.switch.disconnect()

    def test_set_interface_state_off(self):
        with self.configuring_and_committing():
            self.mocked_ssh_client.should_receive("do").with_args("interface ethernet 1/g4").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("shutdown").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        self.switch.set_interface_state("ethernet 1/g4", OFF)

    def test_set_interface_state_off_invalid_interface_raises(self):
        self.mocked_ssh_client.should_receive("do").with_args("configure").once().ordered().and_return([])
        self.mocked_ssh_client.should_receive("do").with_args("interface ethernet 99/g99").once().ordered().and_return([
            "An invalid interface has been used for this function."
        ])
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).once().ordered()

        with self.assertRaises(UnknownInterface) as expect:
            self.switch.set_interface_state("ethernet 99/g99", OFF)

        assert_that(str(expect.exception), equal_to("Unknown interface ethernet 99/g99"))

    def test_set_interface_state_on(self):
        with self.configuring_and_committing():
            self.mocked_ssh_client.should_receive("do").with_args("interface ethernet 1/g4").and_return([]).once().ordered()
            self.mocked_ssh_client.should_receive("do").with_args("no shutdown").and_return([]).once().ordered()
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().and_return([])

        self.switch.set_interface_state("ethernet 1/g4", ON)

    def test_set_interface_state_on_invalid_interface_raises(self):
        self.mocked_ssh_client.should_receive("do").with_args("configure").once().ordered().and_return([])
        self.mocked_ssh_client.should_receive("do").with_args("interface ethernet 99/g99").once().ordered().and_return([
            "An invalid interface has been used for this function."
        ])
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).once().ordered()

        with self.assertRaises(UnknownInterface) as expect:
            self.switch.set_interface_state("ethernet 99/g99", ON)

        assert_that(str(expect.exception), equal_to("Unknown interface ethernet 99/g99"))

    def test_get_vlans(self):
        flexmock(self.switch.page_reader).should_receive("do").with_args(self.mocked_ssh_client, "show vlan").once().ordered().and_return([
            "VLAN       Name                         Ports          Type      Authorization",
            "-----  ---------------                  -------------  -----     -------------",
            "1      Default                          ch2-3,ch5-6,   Default   Required",
            "                                        1/g2-1/g3,",
            "20     your-name-is-way-too-long-for-th 1/g23          Static    Required",
            "300                                     1/g23          Static    Required",
            "2000   meh                                             Static    Required",
            "4000                                                   Static    Required",
        ])

        vlan1, vlan20, vlan300, vlan2000, vlan4000 = self.switch.get_vlans()

        assert_that(vlan1.number, equal_to(1))
        assert_that(vlan1.name, equal_to("default"))
        assert_that(vlan1.ips, has_length(0))

        assert_that(vlan20.number, equal_to(20))
        assert_that(vlan20.name, equal_to("your-name-is-way-too-long-for-th"))
        assert_that(len(vlan20.ips), equal_to(0))

        assert_that(vlan300.number, equal_to(300))
        assert_that(vlan300.name, equal_to(None))
        assert_that(len(vlan300.ips), equal_to(0))

        assert_that(vlan2000.number, equal_to(2000))
        assert_that(vlan2000.name, equal_to("meh"))
        assert_that(len(vlan2000.ips), equal_to(0))

        assert_that(vlan4000.number, equal_to(4000))
        assert_that(vlan4000.name, equal_to(None))
        assert_that(len(vlan4000.ips), equal_to(0))

    def test_get_vlan_standard_no_name(self):
        flexmock(self.switch.page_reader).should_receive("do").with_args(self.mocked_ssh_client, "show vlan id 1000").once().ordered().and_return([
            "VLAN       Name                         Ports          Type      Authorization",
            "-----  ---------------                  -------------  -----     -------------",
            "1000                                    ch2-3,ch5-6,   Static    Required",
            "                                        ch8-48,",
            "                                        1/g2-1/g3"
        ])

        vlan = self.switch.get_vlan(1000)

        assert_that(vlan.number, equal_to(1000))
        assert_that(vlan.name, equal_to(None))
        assert_that(len(vlan.ips), equal_to(0))

    def test_get_vlan_with_name(self):
        flexmock(self.switch.page_reader).should_receive("do").with_args(self.mocked_ssh_client, "show vlan id 1000").once().ordered().and_return([
            "VLAN       Name                         Ports          Type      Authorization",
            "-----  ---------------                  -------------  -----     -------------",
            "1000   shizzle                          ch2-3,ch5-6,   Static    Required",
            "                                        ch8-48,",
            "                                        1/g2-1/g3"
        ])

        vlan = self.switch.get_vlan(1000)

        assert_that(vlan.number, equal_to(1000))
        assert_that(vlan.name, equal_to("shizzle"))
        assert_that(len(vlan.ips), equal_to(0))

    def test_get_vlan_default(self):
        flexmock(self.switch.page_reader).should_receive("do").with_args(self.mocked_ssh_client, "show vlan id 1").once().ordered().and_return([
            "VLAN       Name                         Ports          Type      Authorization",
            "-----  ---------------                  -------------  -----     -------------",
            "1      Default                          ch2-3,ch5-6,   Default   Required",
            "                                        ch8-48,1/g2,",
            "                                        1/g4,1/g7,",
            "                                        1/g13,",
            "                                        1/g17-1/g20,",
            "                                        1/xg4,2/g2,",
            "                                        2/g4,2/g7,",
            "                                        2/g9,",
            "                                        2/g12-2/g20,",
            "                                        2/g23-2/g24,",
            "                                        2/xg3-2/xg4"
        ])

        vlan = self.switch.get_vlan(1)

        assert_that(vlan.number, equal_to(1))
        assert_that(vlan.name, equal_to("default"))
        assert_that(len(vlan.ips), equal_to(0))

    def test_get_vlan_with_bad_number(self):
        flexmock(self.switch.page_reader).should_receive("do").with_args(self.mocked_ssh_client, "show vlan id 5000").once().ordered().and_return([
            "                     ^",
            "Invalid input. Please specify an integer in the range 1 to 4093."
        ])

        with self.assertRaises(BadVlanNumber) as expect:
            self.switch.get_vlan(5000)

        assert_that(str(expect.exception), equal_to("Vlan number is invalid"))

    def test_get_vlan_with_unknown_number(self):
        flexmock(self.switch.page_reader).should_receive("do").with_args(self.mocked_ssh_client, "show vlan id 2019").once().ordered().and_return([
            "ERROR: This VLAN does not exist."
        ])

        with self.assertRaises(UnknownVlan) as expect:
            self.switch.get_vlan(2019)

        assert_that(str(expect.exception), equal_to("Vlan 2019 not found"))

    def test_get_vlan_interfaces(self):
        flexmock(self.switch.page_reader).should_receive("do").with_args(self.mocked_ssh_client, "show vlan id 1000").once().ordered().and_return([
            "VLAN       Name                         Ports          Type      Authorization",
            "-----  ---------------                  -------------  -----     -------------",
            "1000   MyVlanName                       ch2-3,ch5-6,   Static    Required",
            "                                        1/g4,1/g7,",
        ])

        vlan_interfaces = self.switch.get_vlan_interfaces(1000)

        assert_that(vlan_interfaces, equal_to(['port-channel 2', 'port-channel 3', 'port-channel 5', 'port-channel 6', 'ethernet 1/g4', 'ethernet 1/g7']))

    def test_get_vlan_interfaces_with_unknown_vlan_raises(self):
        flexmock(self.switch.page_reader).should_receive("do").with_args(self.mocked_ssh_client, "show vlan id 2019").once().ordered().and_return([
            "ERROR: This VLAN does not exist."
        ])

        with self.assertRaises(UnknownVlan) as expect:
            self.switch.get_vlan_interfaces(2019)

        assert_that(str(expect.exception), equal_to("Vlan 2019 not found"))

    def test_get_interface(self):
        flexmock(self.switch.page_reader).should_receive("do").with_args(self.mocked_ssh_client, "show running-config interface ethernet 1/g1").and_return([
            "switchport access vlan 1234"
        ])

        interface = self.switch.get_interface("ethernet 1/g1")

        assert_that(interface.name, is_("ethernet 1/g1"))
        assert_that(interface.port_mode, is_(ACCESS))
        assert_that(interface.access_vlan, is_(1234))

    def test_get_malformed_interface_raises(self):
        flexmock(self.switch.page_reader).should_receive("do").with_args(self.mocked_ssh_client, "show running-config interface patate").once().ordered().and_return([
            "                                      ^",
            "% Invalid input detected at '^' marker."])

        with self.assertRaises(UnknownInterface) as expect:
            self.switch.get_interface('patate')

        assert_that(str(expect.exception), equal_to("Unknown interface patate"))

    def test_get_nonexistent_interface_raises(self):
        flexmock(self.switch.page_reader).should_receive("do").with_args(self.mocked_ssh_client, "show running-config interface ethernet 1/g9999").once().ordered().and_return([
            "ERROR: Invalid input!"
        ])

        with self.assertRaises(UnknownInterface) as expect:
            self.switch.get_interface('ethernet 1/g9999')

        assert_that(str(expect.exception), equal_to("Unknown interface ethernet 1/g9999"))

    def test_get_interfaces(self):
        flexmock(self.switch.page_reader).should_receive("do").with_args(self.mocked_ssh_client, "show interfaces status").and_return([
            "Port   Type                            Duplex  Speed    Neg  Link  Flow Control",
            "                                                             State Status",
            "-----  ------------------------------  ------  -------  ---- --------- ------------",
            "1/g1   Gigabit - Level                 Full    1000     Auto Up        Inactive",
            "1/g12  Gigabit - Level                 Full    1000     Auto Up        Inactive",
            "2/xg1  Gigabit - Level                 Full    1000     Auto Up        Active",
            "2/xg2  Gigabit - Level                 Full    1000     Auto Up        Active",
            "Ch   Type                            Link",
            "                                     State",
            "---  ------------------------------  -----",
            "ch1  Link Aggregate                  Up",
            "ch10 Link Aggregate                  Down",
        ])

        flexmock(self.switch.page_reader).should_receive("do").with_args(self.mocked_ssh_client, "show running-config interface ethernet 1/g1").and_return([])
        flexmock(self.switch.page_reader).should_receive("do").with_args(self.mocked_ssh_client, "show running-config interface ethernet 1/g12").and_return([
            "switchport access vlan 1234"
        ])
        flexmock(self.switch.page_reader).should_receive("do").with_args(self.mocked_ssh_client, "show running-config interface ethernet 2/xg1").and_return([
            "shutdown",
            "switchport mode trunk",
            "switchport trunk allowed vlan add 900,1000-1001",
            "switchport trunk allowed vlan add 1003-1005",
        ])
        flexmock(self.switch.page_reader).should_receive("do").with_args(self.mocked_ssh_client, "show running-config interface ethernet 2/xg2").and_return([
            "switchport mode general",
            "switchport general allowed vlan add 900,1000-1001,1003-1005",
            "switchport general pvid 1500",
            "mtu 5000"
        ])
        flexmock(self.switch.page_reader).should_receive("do").with_args(self.mocked_ssh_client, "show running-config interface port-channel 1").and_return([])
        flexmock(self.switch.page_reader).should_receive("do").with_args(self.mocked_ssh_client, "show running-config interface port-channel 10").and_return([])

        i1_1, i1_12, i2_x1, i2_x2, ch1, ch10 = self.switch.get_interfaces()

        assert_that(i1_1.name, is_("ethernet 1/g1"))
        assert_that(i1_1.shutdown, is_(False))
        assert_that(i1_1.port_mode, is_(ACCESS))
        assert_that(i1_1.access_vlan, is_(none()))
        assert_that(i1_1.trunk_native_vlan, is_(none()))
        assert_that(i1_1.trunk_vlans, is_([]))

        assert_that(i1_12.name, is_("ethernet 1/g12"))
        assert_that(i1_12.shutdown, is_(False))
        assert_that(i1_12.port_mode, is_(ACCESS))
        assert_that(i1_12.access_vlan, is_(1234))
        assert_that(i1_12.trunk_native_vlan, is_(none()))
        assert_that(i1_12.trunk_vlans, is_([]))

        assert_that(i2_x1.name, is_("ethernet 2/xg1"))
        assert_that(i2_x1.shutdown, is_(True))
        assert_that(i2_x1.port_mode, is_(TRUNK))
        assert_that(i2_x1.access_vlan, is_(none()))
        assert_that(i2_x1.trunk_native_vlan, is_(none()))
        assert_that(i2_x1.trunk_vlans, is_([900, 1000, 1001, 1003, 1004, 1005]))
        assert_that(i2_x1.mtu, is_(None))

        assert_that(i2_x2.name, is_("ethernet 2/xg2"))
        assert_that(i2_x2.port_mode, is_(TRUNK))
        assert_that(i2_x2.trunk_native_vlan, is_(1500))
        assert_that(i2_x2.trunk_vlans, is_([900, 1000, 1001, 1003, 1004, 1005]))
        assert_that(i2_x2.mtu, is_(5000))

        assert_that(ch1.name, is_("port-channel 1"))
        assert_that(ch10.name, is_("port-channel 10"))

    def test_add_vlan(self):
        flexmock(self.switch.page_reader).should_receive("do").with_args(self.mocked_ssh_client, "show vlan id 1000").and_return([
            "ERROR: This VLAN does not exist."
        ])

        with self.configuring_and_committing():
            self.mocked_ssh_client.should_receive("do").with_args("vlan database").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("vlan 1000").once().ordered().and_return([
                "Warning: The use of large numbers of VLANs or interfaces may cause significant",
                "delays in applying the configuration."
            ])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        self.switch.add_vlan(1000)

    def test_add_vlan_and_name(self):
        flexmock(self.switch.page_reader).should_receive("do").with_args(self.mocked_ssh_client, "show vlan id 1000").and_return([
            "ERROR: This VLAN does not exist."
        ])

        with self.configuring_and_committing():
            self.mocked_ssh_client.should_receive("do").with_args("vlan database").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("vlan 1000").once().ordered().and_return([
                "Warning: The use of large numbers of VLANs or interfaces may cause significant",
                "delays in applying the configuration."
            ])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("interface vlan 1000").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("name shizzle").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        self.switch.add_vlan(1000, name="shizzle")

    def test_add_vlan_invalid_number(self):
        flexmock(self.switch.page_reader).should_receive("do").with_args(self.mocked_ssh_client, "show vlan id 5000").and_return([
            "                     ^",
            "Invalid input. Please specify an integer in the range 1 to 4093."
        ])

        with self.assertRaises(BadVlanNumber) as expect:
            self.switch.add_vlan(5000, name="Gertrude")

        assert_that(str(expect.exception), equal_to("Vlan number is invalid"))

    def test_add_vlan_and_bad_name(self):
        flexmock(self.switch.page_reader).should_receive("do").with_args(self.mocked_ssh_client, "show vlan id 1000").and_return([
            "ERROR: This VLAN does not exist."
        ])

        with self.configuring():
            self.mocked_ssh_client.should_receive("do").with_args("vlan database").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("vlan 1000").once().ordered().and_return([
                "Warning: The use of large numbers of VLANs or interfaces may cause significant",
                "delays in applying the configuration."
            ])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("interface vlan 1000").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("name Gertr dude").once().ordered().and_return([
                "                                      ^",
                "% Invalid input detected at '^' marker."
            ])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().and_return([])

        with self.assertRaises(BadVlanName) as expect:
            self.switch.add_vlan(1000, name="Gertr dude")

        assert_that(str(expect.exception), equal_to("Vlan name is invalid"))

    def test_add_vlan_fails_when_already_exist(self):
        flexmock(self.switch.page_reader).should_receive("do").with_args(self.mocked_ssh_client, "show vlan id 1000").and_return([
            "VLAN       Name                         Ports          Type      Authorization",
            "-----  ---------------                  -------------  -----     -------------",
            "1000                                                   Static    Required     "
        ])

        with self.assertRaises(VlanAlreadyExist) as expect:
            self.switch.add_vlan(1000)

        assert_that(str(expect.exception), equal_to("Vlan 1000 already exists"))

    def test_remove_vlan(self):
        with self.configuring_and_committing():
            self.mocked_ssh_client.should_receive("do").with_args("vlan database").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("no vlan 1000").once().ordered().and_return([
                "Warning: The use of large numbers of VLANs or interfaces may cause significant",
                "delays in applying the configuration."
                "If any of the VLANs being deleted are for access ports, the ports will be",
                "unusable until it is assigned a VLAN that exists."
            ])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        self.switch.remove_vlan(1000)

    def test_remove_unknown_vlan(self):
        with self.configuring():
            self.mocked_ssh_client.should_receive("do").with_args("vlan database").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("no vlan 1000").once().ordered().and_return([
                "Warning: The use of large numbers of VLANs or interfaces may cause significant",
                "delays in applying the configuration.",
                "These VLANs do not exist:  1000.",
            ])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        with self.assertRaises(UnknownVlan) as expect:
            self.switch.remove_vlan(1000)

        assert_that(str(expect.exception), equal_to("Vlan 1000 not found"))

    def test_reset_interface(self):
        with self.configuring_and_committing():
            self.mocked_ssh_client.should_receive("do").with_args("interface ethernet 1/g10").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("no switchport access vlan").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("no switchport mode").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("no mtu").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        flexmock(self.switch.page_reader).should_receive("do").with_args(self.mocked_ssh_client, "show running-config interface ethernet 1/g10").and_return([
            ""
        ])

        self.switch.reset_interface("ethernet 1/g10")

    def test_reset_interface_raises_when_data_is_left(self):
        with self.configuring_and_committing():
            self.mocked_ssh_client.should_receive("do").with_args("interface ethernet 1/g10").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("no switchport access vlan").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("no switchport mode").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("no mtu").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        flexmock(self.switch.page_reader).should_receive("do").with_args(self.mocked_ssh_client, "show running-config interface ethernet 1/g10").and_return([
            "shutdown",
            "description 'Configured by Netman'",
            "no lldp transmit",
        ])

        with self.assertRaises(InterfaceResetIncomplete) as ex:
            self.switch.reset_interface("ethernet 1/g10")

        self.assertEqual(str(ex.exception), "The interface reset has failed to remove these properties: " +
                                            "shutdown\ndescription 'Configured by Netman'\nno lldp transmit")

    def test_set_access_mode(self):
        with self.configuring_and_committing():
            self.mocked_ssh_client.should_receive("do").with_args("interface ethernet 1/g10").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("switchport mode access").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        self.switch.set_access_mode("ethernet 1/g10")

    def test_set_access_mode_invalid_interface(self):
        with self.configuring():
            self.mocked_ssh_client.should_receive("do").with_args("interface ethernet 1/g99").once().ordered().and_return([
                "An invalid interface has been used for this function."
            ])

        with self.assertRaises(UnknownInterface) as expect:
            self.switch.set_access_mode("ethernet 1/g99")

        assert_that(str(expect.exception), equal_to("Unknown interface ethernet 1/g99"))

    def test_set_bond_access_mode(self):
        with self.configuring_and_committing():
            self.mocked_ssh_client.should_receive("do").with_args("interface port-channel 10").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("switchport mode access").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        self.switch.set_bond_access_mode(10)

    def test_set_bond_access_mode_invalid_interface(self):
        with self.configuring():
            self.mocked_ssh_client.should_receive("do").with_args("interface port-channel 99999").once().ordered().and_return([
                "An invalid interface has been used for this function."
            ])

        with self.assertRaises(UnknownBond) as expect:
            self.switch.set_bond_access_mode(99999)

        assert_that(str(expect.exception), equal_to("Bond 99999 not found"))

    def test_set_trunk_mode(self):
        flexmock(self.switch.page_reader).should_receive("do").with_args(self.mocked_ssh_client, "show running-config interface ethernet 1/g10").and_return([
        ])

        with self.configuring_and_committing():
            self.mocked_ssh_client.should_receive("do").with_args("interface ethernet 1/g10").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("switchport mode trunk").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        self.switch.set_trunk_mode("ethernet 1/g10")

    def test_set_trunk_mode_stays_in_trunk(self):
        flexmock(self.switch.page_reader).should_receive("do").with_args(self.mocked_ssh_client, "show running-config interface ethernet 1/g10").and_return([
            "switchport mode trunk"
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure").never()

        self.switch.set_trunk_mode("ethernet 1/g10")

    def test_set_trunk_mode_stays_in_general(self):
        flexmock(self.switch.page_reader).should_receive("do").with_args(self.mocked_ssh_client, "show running-config interface ethernet 1/g10").and_return([
            "switchport mode general"
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure").never()

        self.switch.set_trunk_mode("ethernet 1/g10")

    def test_configure_set_trunk_mode_unknown_interface(self):
        flexmock(self.switch.page_reader).should_receive("do").with_args(self.mocked_ssh_client, "show running-config interface ethernet 1/g99").and_return([
            "ERROR: Invalid input!",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure").never()

        with self.assertRaises(UnknownInterface) as expect:
            self.switch.set_trunk_mode("ethernet 1/g99")

        assert_that(str(expect.exception), equal_to("Unknown interface ethernet 1/g99"))

    def test_set_bond_trunk_mode(self):
        flexmock(self.switch.page_reader).should_receive("do").with_args(self.mocked_ssh_client, "show running-config interface port-channel 10").and_return([
        ])

        with self.configuring_and_committing():
            self.mocked_ssh_client.should_receive("do").with_args("interface port-channel 10").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("switchport mode trunk").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        self.switch.set_bond_trunk_mode(10)

    def test_set_bond_trunk_mode_stays_in_bond_trunk(self):
        flexmock(self.switch.page_reader).should_receive("do").with_args(self.mocked_ssh_client, "show running-config interface port-channel 10").and_return([
            "switchport mode trunk"
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure").never()

        self.switch.set_bond_trunk_mode(10)

    def test_set_bond_trunk_mode_stays_in_general(self):
        flexmock(self.switch.page_reader).should_receive("do").with_args(self.mocked_ssh_client, "show running-config interface port-channel 10").and_return([
            "switchport mode general"
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure").never()

        self.switch.set_bond_trunk_mode(10)

    def test_configure_set_bond_trunk_mode_unknown_interface(self):
        flexmock(self.switch.page_reader).should_receive("do").with_args(self.mocked_ssh_client, "show running-config interface port-channel 999999").and_return([
            "ERROR: Invalid input!",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure").never()

        with self.assertRaises(UnknownBond) as expect:
            self.switch.set_bond_trunk_mode(999999)

        assert_that(str(expect.exception), equal_to("Bond 999999 not found"))

    def test_set_access_vlan(self):
        with self.configuring_and_committing():
            self.mocked_ssh_client.should_receive("do").with_args("interface ethernet 1/g10").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("switchport access vlan 1000").once().ordered().and_return([
                "Warning: The use of large numbers of VLANs or interfaces may cause significant",
                "delays in applying the configuration."
            ])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        self.switch.set_access_vlan("ethernet 1/g10", 1000)

    def test_set_access_vlan_invalid_interface(self):
        with self.configuring():
            self.mocked_ssh_client.should_receive("do").with_args("interface ethernet 1/g99").once().ordered().and_return([
                "An invalid interface has been used for this function."
            ])

        with self.assertRaises(UnknownInterface) as expect:
            self.switch.set_access_vlan("ethernet 1/g99", 1000)

        assert_that(str(expect.exception), equal_to("Unknown interface ethernet 1/g99"))

    def test_set_access_vlan_invalid_vlan(self):

        with self.configuring():
            self.mocked_ssh_client.should_receive("do").with_args("interface ethernet 1/g10").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("switchport access vlan 1000").once().ordered().and_return([
                "Warning: The use of large numbers of VLANs or interfaces may cause significant",
                "delays in applying the configuration.",
                "VLAN ID not found."
            ])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        with self.assertRaises(UnknownVlan) as expect:
            self.switch.set_access_vlan("ethernet 1/g10", 1000)

        assert_that(str(expect.exception), equal_to("Vlan 1000 not found"))

    def test_set_access_vlan_invalid_mode(self):
        with self.configuring():
            self.mocked_ssh_client.should_receive("do").with_args("interface ethernet 1/g10").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("switchport access vlan 1000").once().ordered().and_return([
                "Warning: The use of large numbers of VLANs or interfaces may cause significant",
                "delays in applying the configuration.",
                "Interface not in Access Mode."
            ])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        with self.assertRaises(InterfaceInWrongPortMode) as expect:
            self.switch.set_access_vlan("ethernet 1/g10", 1000)

        assert_that(str(expect.exception), equal_to("Operation cannot be performed on a trunk mode interface"))

    def test_unset_interface_access_vlan(self):
        with self.configuring_and_committing():
            self.mocked_ssh_client.should_receive("do").with_args("interface ethernet 1/g10").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("no switchport access vlan").once().ordered().and_return([
                "Warning: The use of large numbers of VLANs or interfaces may cause significant",
                "delays in applying the configuration."
            ])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        self.switch.unset_interface_access_vlan("ethernet 1/g10")

    def test_unset_interface_access_vlan_invalid_interface(self):
        with self.configuring():
            self.mocked_ssh_client.should_receive("do").with_args("interface ethernet 1/g99").once().ordered().and_return([
                "An invalid interface has been used for this function."
            ])

        with self.assertRaises(UnknownInterface) as expect:
            self.switch.unset_interface_access_vlan("ethernet 1/g99")

        assert_that(str(expect.exception), equal_to("Unknown interface ethernet 1/g99"))

    def test_set_interface_native_vlan_on_a_general_interface(self):

        flexmock(self.switch.page_reader).should_receive("do").with_args(self.mocked_ssh_client, "show running-config interface ethernet 1/g10").and_return([
            "switchport mode general"
        ])

        with self.configuring_and_committing():
            self.mocked_ssh_client.should_receive("do").with_args("interface ethernet 1/g10").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("switchport general pvid 1000").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        self.switch.set_interface_native_vlan("ethernet 1/g10", 1000)

    def test_set_interface_native_vlan_unknown_interface(self):
        flexmock(self.switch.page_reader).should_receive("do").with_args(self.mocked_ssh_client, "show running-config interface ethernet 1/g99").and_return([
            "ERROR: Invalid input!",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure").never()

        with self.assertRaises(UnknownInterface) as expect:
            self.switch.set_interface_native_vlan("ethernet 1/g99", 1000)

        assert_that(str(expect.exception), equal_to("Unknown interface ethernet 1/g99"))

    def test_set_interface_native_vlan_unknown_vlan(self):
        flexmock(self.switch.page_reader).should_receive("do").with_args(self.mocked_ssh_client, "show running-config interface ethernet 1/g10").and_return([
            "switchport mode general",
        ])

        with self.configuring():
            self.mocked_ssh_client.should_receive("do").with_args("interface ethernet 1/g10").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("switchport general pvid 1000").once().ordered().and_return([
                "Could not configure pvid."
            ])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        with self.assertRaises(UnknownVlan) as expect:
            self.switch.set_interface_native_vlan("ethernet 1/g10", 1000)

        assert_that(str(expect.exception), equal_to("Vlan 1000 not found"))

    def test_set_interface_native_vlan_on_an_unknown_mode_with_no_access_vlan_assume_not_set_and_set_port_mode(self):
        flexmock(self.switch.page_reader).should_receive("do").with_args(self.mocked_ssh_client, "show running-config interface ethernet 1/g10").and_return([
        ])

        with self.configuring_and_committing():
            self.mocked_ssh_client.should_receive("do").with_args("interface ethernet 1/g10").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("switchport mode general").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("switchport general pvid 1000").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        self.switch.set_interface_native_vlan("ethernet 1/g10", 1000)

    def test_set_interface_native_vlan_on_an_unknown_mode_with_an_access_vlan_assume_access_mode_and_fails(self):
        flexmock(self.switch.page_reader).should_receive("do").with_args(self.mocked_ssh_client, "show running-config interface ethernet 1/g10").and_return([
            "switchport access vlan 2000",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure").never()

        with self.assertRaises(InterfaceInWrongPortMode) as expect:
            self.switch.set_interface_native_vlan("ethernet 1/g10", 1000)

        assert_that(str(expect.exception), equal_to("Operation cannot be performed on a access mode interface"))

    def test_set_interface_native_vlan_on_a_trunk_mode_swithes_to_general(self):
        flexmock(self.switch.page_reader).should_receive("do").with_args(self.mocked_ssh_client, "show running-config interface ethernet 1/g10").and_return([
            "switchport mode trunk",
        ])

        with self.configuring_and_committing():
            self.mocked_ssh_client.should_receive("do").with_args("interface ethernet 1/g10").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("switchport mode general").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("switchport general pvid 1000").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        self.switch.set_interface_native_vlan("ethernet 1/g10", 1000)

    def test_set_interface_native_vlan_on_a_trunk_mode_swithes_to_general_and_copies_actual_allowed_vlans(self):
        flexmock(self.switch.page_reader).should_receive("do").with_args(self.mocked_ssh_client, "show running-config interface ethernet 1/g10").and_return([
            "switchport mode trunk",
            "switchport trunk allowed vlan add 1201-1203,1205",
        ])

        with self.configuring_and_committing():
            self.mocked_ssh_client.should_receive("do").with_args("interface ethernet 1/g10").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("switchport mode general").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("switchport general allowed vlan add 1201-1203,1205").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("switchport general pvid 1000").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        self.switch.set_interface_native_vlan("ethernet 1/g10", 1000)

    def test_unset_interface_native_vlan_reverts_to_trunk_mode(self):
        flexmock(self.switch.page_reader).should_receive("do").with_args(self.mocked_ssh_client, "show running-config interface ethernet 1/g10").and_return([
            "switchport mode general",
            "switchport general pvid 1000"
        ])

        with self.configuring_and_committing():
            self.mocked_ssh_client.should_receive("do").with_args("interface ethernet 1/g10").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("switchport mode trunk").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        self.switch.unset_interface_native_vlan("ethernet 1/g10")

    def test_unset_interface_native_vlan_reverts_to_trunk_mode_and_keeps_allowed_vlans_specs(self):
        flexmock(self.switch.page_reader).should_receive("do").with_args(self.mocked_ssh_client, "show running-config interface ethernet 1/g10").and_return([
            "switchport mode general",
            "switchport general pvid 1000",
            "switchport general allowed vlan add 1201-1203,1205",
        ])

        with self.configuring_and_committing():
            self.mocked_ssh_client.should_receive("do").with_args("interface ethernet 1/g10").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("switchport mode trunk").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("switchport trunk allowed vlan add 1201-1203,1205").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        self.switch.unset_interface_native_vlan("ethernet 1/g10")

    def test_unset_interface_native_vlan_inknown_interface(self):
        flexmock(self.switch.page_reader).should_receive("do").with_args(self.mocked_ssh_client, "show running-config interface ethernet 1/g99").and_return([
            "ERROR: Invalid input!",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure").never()

        with self.assertRaises(UnknownInterface) as expect:
            self.switch.unset_interface_native_vlan("ethernet 1/g99")

        assert_that(str(expect.exception), equal_to("Unknown interface ethernet 1/g99"))

    def test_unset_interface_native_vlan_not_set(self):
        flexmock(self.switch.page_reader).should_receive("do").with_args(self.mocked_ssh_client, "show running-config interface ethernet 1/g10").and_return([
            "switchport mode general"
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure").never()

        with self.assertRaises(NativeVlanNotSet) as expect:
            self.switch.unset_interface_native_vlan("ethernet 1/g10")

        assert_that(str(expect.exception), is_("Trunk native Vlan is not set on interface ethernet 1/g10"))

    def test_unset_bond_native_vlan_reverts_to_trunk_mode(self):
        flexmock(self.switch.page_reader).should_receive("do").with_args(self.mocked_ssh_client, "show running-config interface port-channel 10").and_return([
            "switchport mode general",
            "switchport general pvid 1000"
        ])

        with self.configuring_and_committing():
            self.mocked_ssh_client.should_receive("do").with_args("interface port-channel 10").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("switchport mode trunk").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        self.switch.unset_bond_native_vlan(10)

    def test_unset_bond_native_vlan_reverts_to_trunk_mode_and_keeps_allowed_vlans_specs(self):
        flexmock(self.switch.page_reader).should_receive("do").with_args(self.mocked_ssh_client, "show running-config interface port-channel 10").and_return([
            "switchport mode general",
            "switchport general pvid 1000",
            "switchport general allowed vlan add 1201-1203,1205",
        ])

        with self.configuring_and_committing():
            self.mocked_ssh_client.should_receive("do").with_args("interface port-channel 10").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("switchport mode trunk").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("switchport trunk allowed vlan add 1201-1203,1205").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        self.switch.unset_bond_native_vlan(10)

    def test_unset_bond_native_vlan_inknown_interface(self):
        flexmock(self.switch.page_reader).should_receive("do").with_args(self.mocked_ssh_client, "show running-config interface port-channel 99999").and_return([
            "ERROR: Invalid input!",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure").never()

        with self.assertRaises(UnknownBond) as expect:
            self.switch.unset_bond_native_vlan(99999)

        assert_that(str(expect.exception), equal_to("Bond 99999 not found"))

    def test_unset_bond_native_vlan_not_set(self):
        flexmock(self.switch.page_reader).should_receive("do").with_args(self.mocked_ssh_client, "show running-config interface port-channel 10").and_return([
            "switchport mode general"
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure").never()

        with self.assertRaises(NativeVlanNotSet) as expect:
            self.switch.unset_bond_native_vlan(10)

        assert_that(str(expect.exception), is_("Trunk native Vlan is not set on interface port-channel 10"))

    def test_set_bond_native_vlan_on_a_general_interface(self):
        flexmock(self.switch.page_reader).should_receive("do").with_args(self.mocked_ssh_client, "show running-config interface port-channel 10").and_return([
            "switchport mode general"
        ])

        with self.configuring_and_committing():
            self.mocked_ssh_client.should_receive("do").with_args("interface port-channel 10").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("switchport general pvid 1000").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        self.switch.set_bond_native_vlan(10, 1000)

    def test_set_bond_native_vlan_unknown_interface(self):
        flexmock(self.switch.page_reader).should_receive("do").with_args(self.mocked_ssh_client, "show running-config interface port-channel 99999").and_return([
            "ERROR: Invalid input!",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure").never()

        with self.assertRaises(UnknownBond) as expect:
            self.switch.set_bond_native_vlan(99999, 1000)

        assert_that(str(expect.exception), equal_to("Bond 99999 not found"))

    def test_set_bond_native_vlan_unknown_vlan(self):
        flexmock(self.switch.page_reader).should_receive("do").with_args(self.mocked_ssh_client, "show running-config interface port-channel 10").and_return([
            "switchport mode general",
        ])

        with self.configuring():
            self.mocked_ssh_client.should_receive("do").with_args("interface port-channel 10").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("switchport general pvid 1000").once().ordered().and_return([
                "Could not configure pvid."
            ])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        with self.assertRaises(UnknownVlan) as expect:
            self.switch.set_bond_native_vlan(10, 1000)

        assert_that(str(expect.exception), equal_to("Vlan 1000 not found"))

    def test_set_bond_native_vlan_on_an_unknown_mode_with_no_access_vlan_assume_not_set_and_set_port_mode(self):
        flexmock(self.switch.page_reader).should_receive("do").with_args(self.mocked_ssh_client, "show running-config interface port-channel 10").and_return([
        ])

        with self.configuring_and_committing():
            self.mocked_ssh_client.should_receive("do").with_args("interface port-channel 10").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("switchport mode general").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("switchport general pvid 1000").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        self.switch.set_bond_native_vlan(10, 1000)

    def test_set_bond_native_vlan_on_an_unknown_mode_with_an_access_vlan_assume_access_mode_and_fails(self):
        flexmock(self.switch.page_reader).should_receive("do").with_args(self.mocked_ssh_client, "show running-config interface port-channel 10").and_return([
            "switchport access vlan 2000",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure").never()

        with self.assertRaises(InterfaceInWrongPortMode) as expect:
            self.switch.set_bond_native_vlan(10, 1000)

        assert_that(str(expect.exception), equal_to("Operation cannot be performed on a access mode interface"))

    def test_set_bond_native_vlan_on_a_trunk_mode_swithes_to_general(self):
        flexmock(self.switch.page_reader).should_receive("do").with_args(self.mocked_ssh_client, "show running-config interface port-channel 10").and_return([
            "switchport mode trunk",
        ])

        with self.configuring_and_committing():
            self.mocked_ssh_client.should_receive("do").with_args("interface port-channel 10").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("switchport mode general").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("switchport general pvid 1000").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        self.switch.set_bond_native_vlan(10, 1000)

    def test_set_bond_native_vlan_on_a_trunk_mode_swithes_to_general_and_copies_actual_allowed_vlans(self):
        flexmock(self.switch.page_reader).should_receive("do").with_args(self.mocked_ssh_client, "show running-config interface port-channel 10").and_return([
            "switchport mode trunk",
            "switchport trunk allowed vlan add 1201-1203,1205",
        ])

        with self.configuring_and_committing():
            self.mocked_ssh_client.should_receive("do").with_args("interface port-channel 10").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("switchport mode general").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("switchport general allowed vlan add 1201-1203,1205").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("switchport general pvid 1000").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        self.switch.set_bond_native_vlan(10, 1000)

    def test_add_trunk_vlan(self):
        flexmock(self.switch.page_reader).should_receive("do").with_args(self.mocked_ssh_client, "show running-config interface ethernet 1/g10").and_return([
            "switchport mode trunk",
        ])

        with self.configuring_and_committing():
            self.mocked_ssh_client.should_receive("do").with_args("interface ethernet 1/g10").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("switchport trunk allowed vlan add 1000").once().ordered().and_return([
                "Warning: The use of large numbers of VLANs or interfaces may cause significant",
                "delays in applying the configuration."
            ])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        self.switch.add_trunk_vlan("ethernet 1/g10", 1000)

    def test_add_trunk_vlan_unknown_interface(self):
        flexmock(self.switch.page_reader).should_receive("do").with_args(self.mocked_ssh_client, "show running-config interface ethernet 1/g99").and_return([
            "ERROR: Invalid input!",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure").never()

        with self.assertRaises(UnknownInterface) as expect:
            self.switch.add_trunk_vlan("ethernet 1/g99", 1000)

        assert_that(str(expect.exception), equal_to("Unknown interface ethernet 1/g99"))

    def test_add_trunk_vlan_unknown_vlan(self):
        flexmock(self.switch.page_reader).should_receive("do").with_args(self.mocked_ssh_client, "show running-config interface ethernet 1/g10").and_return([
            "switchport mode trunk",
        ])

        with self.configuring():
            self.mocked_ssh_client.should_receive("do").with_args("interface ethernet 1/g10").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("switchport trunk allowed vlan add 1000").once().ordered().and_return([
                "Warning: The use of large numbers of VLANs or interfaces may cause significant",
                "delays in applying the configuration.",
                "          Failure Information",
                "---------------------------------------",
                "   VLANs failed to be configured : 1",
                "---------------------------------------",
                "   VLAN             Error",
                "---------------------------------------",
                "VLAN      1000 ERROR: This VLAN does not exist.",
            ])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        with self.assertRaises(UnknownVlan) as expect:
            self.switch.add_trunk_vlan("ethernet 1/g10", 1000)

        assert_that(str(expect.exception), equal_to("Vlan 1000 not found"))

    def test_add_trunk_vlan_to_general_mode(self):
        flexmock(self.switch.page_reader).should_receive("do").with_args(self.mocked_ssh_client, "show running-config interface ethernet 1/g10").and_return([
            "switchport mode general",
        ])

        with self.configuring_and_committing():
            self.mocked_ssh_client.should_receive("do").with_args("interface ethernet 1/g10").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("switchport general allowed vlan add 1000").once().ordered().and_return([
                "Warning: The use of large numbers of VLANs or interfaces may cause significant",
                "delays in applying the configuration."
            ])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        self.switch.add_trunk_vlan("ethernet 1/g10", 1000)

    def test_add_trunk_vlan_without_mode_and_access_vlan_assume_no_mode_set_trunk_mode(self):
        flexmock(self.switch.page_reader).should_receive("do").with_args(self.mocked_ssh_client, "show running-config interface ethernet 1/g10").and_return([
        ])

        with self.configuring_and_committing():
            self.mocked_ssh_client.should_receive("do").with_args("interface ethernet 1/g10").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("switchport mode trunk").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("switchport trunk allowed vlan add 1000").once().ordered().and_return([
                "Warning: The use of large numbers of VLANs or interfaces may cause significant",
                "delays in applying the configuration."
            ])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        self.switch.add_trunk_vlan("ethernet 1/g10", 1000)

    def test_add_trunk_vlan_without_mode_with_access_vlan_assume_access_mode_and_fails(self):
        flexmock(self.switch.page_reader).should_receive("do").with_args(self.mocked_ssh_client, "show running-config interface ethernet 1/g10").and_return([
            "switchport access vlan 2000",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure").never()

        with self.assertRaises(InterfaceInWrongPortMode) as expect:
            self.switch.add_trunk_vlan("ethernet 1/g10", 1000)

        assert_that(str(expect.exception), equal_to("Operation cannot be performed on a access mode interface"))

    def test_remove_trunk_vlan(self):
        flexmock(self.switch.page_reader).should_receive("do").with_args(self.mocked_ssh_client, "show running-config interface ethernet 1/g10").and_return([
            "switchport mode trunk",
            "switchport trunk allowed vlan add 1000",
        ])

        with self.configuring_and_committing():
            self.mocked_ssh_client.should_receive("do").with_args("interface ethernet 1/g10").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("switchport trunk allowed vlan remove 1000").once().ordered().and_return([
                "Warning: The use of large numbers of VLANs or interfaces may cause significant",
                "delays in applying the configuration."
            ])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        self.switch.remove_trunk_vlan("ethernet 1/g10", 1000)

    def test_remove_trunk_vlan_unknown_interface(self):
        flexmock(self.switch.page_reader).should_receive("do").with_args(self.mocked_ssh_client, "show running-config interface ethernet 1/g99").and_return([
            "ERROR: Invalid input!",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure").never()

        with self.assertRaises(UnknownInterface) as expect:
            self.switch.remove_trunk_vlan("ethernet 1/g99", 1000)

        assert_that(str(expect.exception), equal_to("Unknown interface ethernet 1/g99"))

    def test_remove_trunk_vlan_not_set_at_all(self):
        flexmock(self.switch.page_reader).should_receive("do").with_args(self.mocked_ssh_client, "show running-config interface ethernet 1/g10").and_return([
            "switchport mode trunk",
        ])

        with self.assertRaises(TrunkVlanNotSet) as expect:
            self.switch.remove_trunk_vlan("ethernet 1/g10", 1000)

        assert_that(str(expect.exception), equal_to("Trunk Vlan is not set on interface ethernet 1/g10"))

    def test_remove_trunk_vlan_not_set_in_ranges(self):
        flexmock(self.switch.page_reader).should_receive("do").with_args(self.mocked_ssh_client, "show running-config interface ethernet 1/g10").and_return([
            "switchport mode trunk",
            "switchport trunk allowed vlan add 999,1001",
        ])

        with self.assertRaises(TrunkVlanNotSet) as expect:
            self.switch.remove_trunk_vlan("ethernet 1/g10", 1000)

        assert_that(str(expect.exception), equal_to("Trunk Vlan is not set on interface ethernet 1/g10"))

    def test_remove_trunk_vlan_general_mode_and_in_range(self):
        flexmock(self.switch.page_reader).should_receive("do").with_args(self.mocked_ssh_client, "show running-config interface ethernet 1/g10").and_return([
            "switchport mode general",
            "switchport general allowed vlan add 999-1001",
        ])

        with self.configuring_and_committing():
            self.mocked_ssh_client.should_receive("do").with_args("interface ethernet 1/g10").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("switchport general allowed vlan remove 1000").once().ordered().and_return([
                "Warning: The use of large numbers of VLANs or interfaces may cause significant",
                "delays in applying the configuration."
            ])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        self.switch.remove_trunk_vlan("ethernet 1/g10", 1000)

    def test_add_bond_trunk_vlan(self):
        flexmock(self.switch.page_reader).should_receive("do").with_args(self.mocked_ssh_client, "show running-config interface port-channel 10").and_return([
            "switchport mode trunk",
        ])

        with self.configuring_and_committing():
            self.mocked_ssh_client.should_receive("do").with_args("interface port-channel 10").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("switchport trunk allowed vlan add 1000").once().ordered().and_return([
                "Warning: The use of large numbers of VLANs or interfaces may cause significant",
                "delays in applying the configuration."
            ])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        self.switch.add_bond_trunk_vlan(10, 1000)

    def test_add_bond_trunk_vlan_unknown_interface(self):
        flexmock(self.switch.page_reader).should_receive("do").with_args(self.mocked_ssh_client, "show running-config interface port-channel 99").and_return([
            "ERROR: Invalid input!",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure").never()

        with self.assertRaises(UnknownBond) as expect:
            self.switch.add_bond_trunk_vlan(99, 1000)

        assert_that(str(expect.exception), equal_to("Bond 99 not found"))

    def test_add_bond_trunk_vlan_unknown_vlan(self):
        flexmock(self.switch.page_reader).should_receive("do").with_args(self.mocked_ssh_client, "show running-config interface port-channel 10").and_return([
            "switchport mode trunk",
        ])

        with self.configuring():
            self.mocked_ssh_client.should_receive("do").with_args("interface port-channel 10").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("switchport trunk allowed vlan add 1000").once().ordered().and_return([
                "Warning: The use of large numbers of VLANs or interfaces may cause significant",
                "delays in applying the configuration.",
                "          Failure Information",
                "---------------------------------------",
                "   VLANs failed to be configured : 1",
                "---------------------------------------",
                "   VLAN             Error",
                "---------------------------------------",
                "VLAN      1000 ERROR: This VLAN does not exist.",
            ])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        with self.assertRaises(UnknownVlan) as expect:
            self.switch.add_bond_trunk_vlan(10, 1000)

        assert_that(str(expect.exception), equal_to("Vlan 1000 not found"))

    def test_add_bond_trunk_vlan_to_general_mode(self):
        flexmock(self.switch.page_reader).should_receive("do").with_args(self.mocked_ssh_client, "show running-config interface port-channel 10").and_return([
            "switchport mode general",
        ])

        with self.configuring_and_committing():
            self.mocked_ssh_client.should_receive("do").with_args("interface port-channel 10").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("switchport general allowed vlan add 1000").once().ordered().and_return([
                "Warning: The use of large numbers of VLANs or interfaces may cause significant",
                "delays in applying the configuration."
            ])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        self.switch.add_bond_trunk_vlan(10, 1000)

    def test_add_bond_trunk_vlan_without_mode_and_access_vlan_assume_no_mode_set_trunk_mode(self):
        flexmock(self.switch.page_reader).should_receive("do").with_args(self.mocked_ssh_client, "show running-config interface port-channel 10").and_return([
        ])

        with self.configuring_and_committing():
            self.mocked_ssh_client.should_receive("do").with_args("interface port-channel 10").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("switchport mode trunk").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("switchport trunk allowed vlan add 1000").once().ordered().and_return([
                "Warning: The use of large numbers of VLANs or interfaces may cause significant",
                "delays in applying the configuration."
            ])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        self.switch.add_bond_trunk_vlan(10, 1000)

    def test_add_bond_trunk_vlan_without_mode_with_access_vlan_assume_access_mode_and_fails(self):
        flexmock(self.switch.page_reader).should_receive("do").with_args(self.mocked_ssh_client, "show running-config interface port-channel 10").and_return([
            "switchport access vlan 2000",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure").never()

        with self.assertRaises(InterfaceInWrongPortMode) as expect:
            self.switch.add_bond_trunk_vlan(10, 1000)

        assert_that(str(expect.exception), equal_to("Operation cannot be performed on a access mode interface"))

    def test_remove_bond_trunk_vlan(self):
        flexmock(self.switch.page_reader).should_receive("do").with_args(self.mocked_ssh_client, "show running-config interface port-channel 10").and_return([
            "switchport mode trunk",
            "switchport trunk allowed vlan add 1000",
        ])

        with self.configuring_and_committing():
            self.mocked_ssh_client.should_receive("do").with_args("interface port-channel 10").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("switchport trunk allowed vlan remove 1000").once().ordered().and_return([
                "Warning: The use of large numbers of VLANs or interfaces may cause significant",
                "delays in applying the configuration."
            ])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        self.switch.remove_bond_trunk_vlan(10, 1000)

    def test_remove_bond_trunk_vlan_unknown_interface(self):
        flexmock(self.switch.page_reader).should_receive("do").with_args(self.mocked_ssh_client, "show running-config interface port-channel 99").and_return([
            "ERROR: Invalid input!",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure").never()

        with self.assertRaises(UnknownBond) as expect:
            self.switch.remove_bond_trunk_vlan(99, 1000)

        assert_that(str(expect.exception), equal_to("Bond 99 not found"))

    def test_remove_bond_trunk_vlan_not_set_at_all(self):
        flexmock(self.switch.page_reader).should_receive("do").with_args(self.mocked_ssh_client, "show running-config interface port-channel 10").and_return([
            "switchport mode trunk",
        ])

        with self.assertRaises(TrunkVlanNotSet) as expect:
            self.switch.remove_bond_trunk_vlan(10, 1000)

        assert_that(str(expect.exception), equal_to("Trunk Vlan is not set on interface port-channel 10"))

    def test_remove_bond_trunk_vlan_not_set_in_ranges(self):
        flexmock(self.switch.page_reader).should_receive("do").with_args(self.mocked_ssh_client, "show running-config interface port-channel 10").and_return([
            "switchport mode trunk",
            "switchport trunk allowed vlan add 999,1001",
        ])

        with self.assertRaises(TrunkVlanNotSet) as expect:
            self.switch.remove_bond_trunk_vlan(10, 1000)

        assert_that(str(expect.exception), equal_to("Trunk Vlan is not set on interface port-channel 10"))

    def test_remove_bond_trunk_vlan_general_mode_and_in_range(self):
        flexmock(self.switch.page_reader).should_receive("do").with_args(self.mocked_ssh_client, "show running-config interface port-channel 10").and_return([
            "switchport mode general",
            "switchport general allowed vlan add 999-1001",
        ])

        with self.configuring_and_committing():
            self.mocked_ssh_client.should_receive("do").with_args("interface port-channel 10").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("switchport general allowed vlan remove 1000").once().ordered().and_return([
                "Warning: The use of large numbers of VLANs or interfaces may cause significant",
                "delays in applying the configuration."
            ])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        self.switch.remove_bond_trunk_vlan(10, 1000)

    def test_edit_interface_spanning_tree_enable_edge(self):
        with self.configuring_and_committing():
            self.mocked_ssh_client.should_receive("do").with_args("interface ethernet 1/g10").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("spanning-tree portfast").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        self.switch.edit_interface_spanning_tree('ethernet 1/g10', edge=True)

    def test_edit_interface_spanning_tree_disable_edge(self):
        with self.configuring_and_committing():
            self.mocked_ssh_client.should_receive("do").with_args("interface ethernet 1/g10").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("no spanning-tree portfast").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        self.switch.edit_interface_spanning_tree('ethernet 1/g10', edge=False)

    def test_edit_interface_spanning_tree_optional_params(self):
        self.mocked_ssh_client.should_receive("do").with_args("configure").never()

        self.switch.edit_interface_spanning_tree("ethernet 1/g10")

    def test_set_interface_lldp_state(self):
        with self.configuring_and_committing():
            self.mocked_ssh_client.should_receive("do").with_args("interface ethernet 1/g10").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("lldp transmit").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("lldp receive").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("lldp med transmit-tlv capabilities").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("lldp med transmit-tlv network-policy").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        self.switch.set_interface_lldp_state("ethernet 1/g10", True)

    def test_disable_lldp(self):
        with self.configuring_and_committing():
            self.mocked_ssh_client.should_receive("do").with_args("interface ethernet 1/g10").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("no lldp transmit").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("no lldp receive").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("no lldp med transmit-tlv capabilities").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("no lldp med transmit-tlv network-policy").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        self.switch.set_interface_lldp_state("ethernet 1/g10", False)

    def test_set_interface_description(self):
        with self.configuring_and_committing():
            self.mocked_ssh_client.should_receive("do").with_args("interface ethernet 1/g10").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("description \"Hey\"").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        self.switch.set_interface_description("ethernet 1/g10", "Hey")

    def test_set_interface_description_invalid_interface(self):
        with self.configuring():
            self.mocked_ssh_client.should_receive("do").with_args("interface ethernet 1/g99").once().ordered().and_return([
                "An invalid interface has been used for this function."
            ])

        with self.assertRaises(UnknownInterface) as expect:
            self.switch.set_interface_description("ethernet 1/g99", "Hey")

        assert_that(str(expect.exception), equal_to("Unknown interface ethernet 1/g99"))

    def test_set_interface_description_invalid_description(self):
        with self.configuring():
            self.mocked_ssh_client.should_receive("do").with_args("interface ethernet 1/g10").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("description \"Hey \"you\"\"").once().ordered().and_return([
                "                       ^",
                "% Invalid input detected at '^' marker."
            ])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        with self.assertRaises(BadInterfaceDescription) as expect:
            self.switch.set_interface_description("ethernet 1/g10", 'Hey "you"')

        assert_that(str(expect.exception), equal_to("Invalid description : Hey \"you\""))

    def test_set_bond_description(self):
        with self.configuring_and_committing():
            self.mocked_ssh_client.should_receive("do").with_args("interface port-channel 10").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("description \"Hey\"").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        self.switch.set_bond_description(10, "Hey")

    def test_set_bond_description_invalid_bond(self):
        with self.configuring():
            self.mocked_ssh_client.should_receive("do").with_args("interface port-channel 99999").once().ordered().and_return([
                "An invalid interface has been used for this function."
            ])

        with self.assertRaises(UnknownBond) as expect:
            self.switch.set_bond_description(99999, "Hey")

        assert_that(str(expect.exception), equal_to("Bond 99999 not found"))

    def test_set_bond_description_invalid_description(self):
        with self.configuring():
            self.mocked_ssh_client.should_receive("do").with_args("interface port-channel 10").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("description \"Hey \"you\"\"").once().ordered().and_return([
                "                       ^",
                "% Invalid input detected at '^' marker."
            ])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        with self.assertRaises(BadInterfaceDescription) as expect:
            self.switch.set_bond_description(10, 'Hey "you"')

        assert_that(str(expect.exception), equal_to("Invalid description : Hey \"you\""))

    def test_set_interface_mtu(self):
        with self.configuring_and_committing():
            self.mocked_ssh_client.should_receive("do").with_args("interface ethernet 1/g10").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("mtu 1520").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        self.switch.set_interface_mtu("ethernet 1/g10", 1520)

    def test_unset_interface_mtu(self):
        with self.configuring_and_committing():
            self.mocked_ssh_client.should_receive("do").with_args("interface ethernet 1/g10").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("no mtu").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        self.switch.unset_interface_mtu("ethernet 1/g10")

    def test_set_interface_mtu_with_out_of_range_value_raises(self):
        with self.configuring():
            self.mocked_ssh_client.should_receive("do").with_args("interface ethernet 1/g10").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("mtu 9999").once().ordered().and_return([
                "                            ^",
                "Value is out of range. The valid range is 1518 to 9216."
            ])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        with self.assertRaises(InvalidMtuSize) as expect:
            self.switch.set_interface_mtu("ethernet 1/g10", 9999)

        assert_that(str(expect.exception), equal_to("MTU value is invalid : 9999"))

    def test_set_bond_mtu(self):
        with self.configuring_and_committing():
            self.mocked_ssh_client.should_receive("do").with_args("interface port-channel 10").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("mtu 1520").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        self.switch.set_bond_mtu(10, 1520)

    def test_set_bond_mtu_with_out_of_range_value_raises(self):
        with self.configuring():
            self.mocked_ssh_client.should_receive("do").with_args("interface port-channel 10").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("mtu 9999").once().ordered().and_return([
                "                            ^",
                "Value is out of range. The valid range is 1518 to 9216."
            ])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        with self.assertRaises(InvalidMtuSize) as expect:
            self.switch.set_bond_mtu(10, 9999)

        assert_that(str(expect.exception), equal_to("MTU value is invalid : 9999"))

    def test_unset_bond_mtu(self):
        with self.configuring_and_committing():
            self.mocked_ssh_client.should_receive("do").with_args("interface port-channel 10").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("no mtu").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        self.switch.unset_bond_mtu(10)

    def test_commit(self):
        self.mocked_ssh_client.should_receive("do").with_args("copy running-config startup-config", wait_for="? (y/n) ").once().ordered().and_return([])
        self.mocked_ssh_client.should_receive("send_key").with_args("y").once().ordered().and_return([])

        self.switch.commit_transaction()

    @contextmanager
    def configuring_and_committing(self):
        self.mocked_ssh_client.should_receive("do").with_args("configure").once().ordered().and_return([])

        yield

        self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

    @contextmanager
    def configuring(self):
        self.mocked_ssh_client.should_receive("do").with_args("configure").once().ordered().and_return([])

        yield

        self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])
