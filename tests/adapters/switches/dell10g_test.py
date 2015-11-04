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

from contextlib import contextmanager
import unittest

from hamcrest import assert_that, equal_to, is_, instance_of, has_length, none
import mock
from flexmock import flexmock, flexmock_teardown
from netman.adapters.shell.telnet import TelnetClient
from netman.adapters.shell.ssh import SshClient
from netman.adapters.switches.util import SubShell
from netman.core.objects.port_modes import ACCESS, TRUNK
from netman.adapters.switches import dell10g
from netman.adapters.switches.dell10g import Dell10G
from netman.core.objects.switch_transactional import SwitchTransactional
from netman.core.objects.exceptions import UnknownInterface, BadVlanNumber, \
    BadVlanName, UnknownVlan, InterfaceInWrongPortMode, NativeVlanNotSet, TrunkVlanNotSet, VlanAlreadyExist
from netman.core.objects.switch_descriptor import SwitchDescriptor


def test_factory_ssh():
    lock = mock.Mock()
    descriptor = SwitchDescriptor(hostname='hostname', model='dell10g', username='username', password='password', port=22)
    switch = dell10g.factory_ssh(descriptor, lock)

    assert_that(switch, instance_of(SwitchTransactional))
    assert_that(switch.impl, instance_of(Dell10G))
    assert_that(switch.impl.shell_factory, equal_to(SshClient))
    assert_that(switch.lock, is_(lock))
    assert_that(switch.switch_descriptor, is_(descriptor))


def test_factory_telnet():
    lock = mock.Mock()
    descriptor = SwitchDescriptor(hostname='hostname', model='dell10g', username='username', password='password', port=22)
    switch = dell10g.factory_telnet(descriptor, lock)

    assert_that(switch, instance_of(SwitchTransactional))
    assert_that(switch.impl, instance_of(Dell10G))
    assert_that(switch.impl.shell_factory, equal_to(TelnetClient))
    assert_that(switch.lock, is_(lock))
    assert_that(switch.switch_descriptor, is_(descriptor))


class Dell10GTest(unittest.TestCase):

    def setUp(self):
        self.lock = mock.Mock()
        self.switch = dell10g.factory_ssh(SwitchDescriptor(model='dell', hostname="my.hostname", password="the_password"), self.lock)
        SubShell.debug = True

    def tearDown(self):
        flexmock_teardown()

    def command_setup(self):
        self.mocked_ssh_client = flexmock()
        self.switch.impl.shell = self.mocked_ssh_client

    def test_switch_has_a_logger_configured_with_the_switch_name(self):
        assert_that(self.switch.logger.name, is_(Dell10G.__module__ + ".my.hostname"))

    @mock.patch("netman.adapters.shell.ssh.SshClient")
    def test_connect(self, ssh_client_class_mock):
        self.switch = Dell10G(
            SwitchDescriptor(hostname="my.hostname", username="the_user", password="the_password", model="dell"),
            shell_factory=ssh_client_class_mock)

        self.mocked_ssh_client = flexmock()
        ssh_client_class_mock.return_value = self.mocked_ssh_client
        self.mocked_ssh_client.should_receive("do").with_args("enable", wait_for=":").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("the_password").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("terminal length 0").and_return([]).once().ordered()

        self.switch.connect()

        ssh_client_class_mock.assert_called_with(
            host="my.hostname",
            username="the_user",
            password="the_password",
            port=22
        )

    def test_disconnect(self):
        logger = flexmock()
        self.switch.impl.logger = logger
        logger.should_receive("debug")

        mocked_ssh_client = flexmock()
        self.switch.impl.shell = mocked_ssh_client
        mocked_ssh_client.should_receive("quit").with_args("quit").once().ordered()

        logger.should_receive("info").with_args("FULL TRANSACTION LOG").once()

        self.switch.impl.shell.full_log = "FULL TRANSACTION LOG"
        self.switch.disconnect()

    def test_shutdown_interface(self):
        self.command_setup()

        with self.configuring_and_committing():
            self.mocked_ssh_client.should_receive("do").with_args("interface tengigabitethernet 1/0/4").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("shutdown").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        self.switch.shutdown_interface("tengigabitethernet 1/0/4")

    def test_shutdown_interface_invalid_interface_raises(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("configure").once().ordered().and_return([])
        self.mocked_ssh_client.should_receive("do").with_args("interface tengigabitethernet 1/0/99").once().ordered().and_return([
            "An invalid interface has been used for this function."
        ])
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).once().ordered()

        with self.assertRaises(UnknownInterface) as expect:
            self.switch.shutdown_interface("tengigabitethernet 1/0/99")

        assert_that(str(expect.exception), equal_to("Unknown interface tengigabitethernet 1/0/99"))

    def test_openup_interface(self):
        self.command_setup()

        with self.configuring_and_committing():
            self.mocked_ssh_client.should_receive("do").with_args("interface tengigabitethernet 1/0/4").and_return([]).once().ordered()
            self.mocked_ssh_client.should_receive("do").with_args("no shutdown").and_return([]).once().ordered()
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().and_return([])

        self.switch.openup_interface("tengigabitethernet 1/0/4")

    def test_openup_interface_invalid_interface_raises(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("configure").once().ordered().and_return([])
        self.mocked_ssh_client.should_receive("do").with_args("interface tengigabitethernet 1/0/99").once().ordered().and_return([
            "An invalid interface has been used for this function."
        ])
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).once().ordered()

        with self.assertRaises(UnknownInterface) as expect:
            self.switch.openup_interface("tengigabitethernet 1/0/99")

        assert_that(str(expect.exception), equal_to("Unknown interface tengigabitethernet 1/0/99"))

    def test_get_vlans(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show vlan").once().ordered().and_return([

            "VLAN   Name                             Ports          Type",
            "-----  ---------------                  -------------  --------------",
            "1      default                          Po1-15,Po18,   Default",
            "                                        Po23-26,",
            "                                        Po28-128,",
            "                                        Te1/0/51-56",
            "20     your-name-is-way-too-long-for-th Po27           Static",
            "300    VLAN0300                         Po27,          Static",
            "                                        Te1/0/2-4,",
            "                                        Te1/0/6-8,",
            "                                        Te1/0/41-46",
            "2000   meh                              Po27           Static",
            "4000   VLAN4000                         Po27           Static",
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

    def test_get_interfaces(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show interfaces status").and_return([
            "Port      Description               Vlan  Duplex Speed   Neg  Link   Flow Ctrl",
            "                                                              State  Status",
            "--------- ------------------------- ----- ------ ------- ---- ------ ---------",
            "Te0/0/1   longer name than whats al       Full   10000   Auto Up     Active",
            "Te0/0/12                                  Full   10000   Auto Up     Active",
            "Te1/0/1                                   Full   10000   Auto Up     Active",
            "Te1/0/2                                   Full   10000   Auto Up     Active",
            "Port    Description                    Vlan  Link",
            "Channel                                      State",
            "------- ------------------------------ ----- -------",
            "Po43                                   trnk  Up",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface tengigabitethernet 0/0/1").and_return([])
        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface tengigabitethernet 0/0/12").and_return([
            "switchport access vlan 1234"
        ])
        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface tengigabitethernet 1/0/1").and_return([
            "shutdown",
            "switchport mode trunk",
            "switchport trunk allowed vlan 900,1000-1001,1003-1005",
        ])
        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface tengigabitethernet 1/0/2").and_return([
            "switchport mode general",
            "switchport general allowed vlan add 900,1000-1001,1003-1005",
            "switchport general pvid 1500",
        ])
        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface port-channel 43").and_return([])

        i1_1, i1_12, i2_x1, i2_x2, po43 = self.switch.get_interfaces()

        assert_that(i1_1.name, is_("tengigabitethernet 0/0/1"))
        assert_that(i1_1.shutdown, is_(False))
        assert_that(i1_1.port_mode, is_(ACCESS))
        assert_that(i1_1.access_vlan, is_(none()))
        assert_that(i1_1.trunk_native_vlan, is_(none()))
        assert_that(i1_1.trunk_vlans, is_([]))

        assert_that(i1_12.name, is_("tengigabitethernet 0/0/12"))
        assert_that(i1_12.shutdown, is_(False))
        assert_that(i1_12.port_mode, is_(ACCESS))
        assert_that(i1_12.access_vlan, is_(1234))
        assert_that(i1_12.trunk_native_vlan, is_(none()))
        assert_that(i1_12.trunk_vlans, is_([]))

        assert_that(i2_x1.name, is_("tengigabitethernet 1/0/1"))
        assert_that(i2_x1.shutdown, is_(True))
        assert_that(i2_x1.port_mode, is_(TRUNK))
        assert_that(i2_x1.access_vlan, is_(none()))
        assert_that(i2_x1.trunk_native_vlan, is_(none()))
        assert_that(i2_x1.trunk_vlans, is_([900, 1000, 1001, 1003, 1004, 1005]))

        assert_that(i2_x2.name, is_("tengigabitethernet 1/0/2"))
        assert_that(i2_x2.port_mode, is_(TRUNK))
        assert_that(i2_x2.trunk_native_vlan, is_(1500))
        assert_that(i2_x2.trunk_vlans, is_([900, 1000, 1001, 1003, 1004, 1005]))

        assert_that(po43.name, is_("port-channel 43"))

    def test_add_vlan(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show vlan id 1000").and_return([
            "ERROR: This VLAN does not exist."
        ])

        with self.configuring_and_committing():
            self.mocked_ssh_client.should_receive("do").with_args("vlan 1000").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        self.switch.add_vlan(1000)

    def test_add_vlan_and_name(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show vlan id 1000").and_return([
            "ERROR: This VLAN does not exist."
        ])

        with self.configuring_and_committing():
            self.mocked_ssh_client.should_receive("do").with_args("vlan 1000").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("name shizzle").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        self.switch.add_vlan(1000, name="shizzle")

    def test_add_vlan_invalid_number(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show vlan id 5000").and_return([
            "                     ^",
            "Invalid input. Please specify an integer in the range 1 to 4093."
        ])

        with self.assertRaises(BadVlanNumber) as expect:
            self.switch.add_vlan(5000, name="Gertrude")

        assert_that(str(expect.exception), equal_to("Vlan number is invalid"))

    def test_add_vlan_and_bad_name(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show vlan id 1000").and_return([
            "ERROR: This VLAN does not exist."
        ])

        with self.configuring():
            self.mocked_ssh_client.should_receive("do").with_args("vlan 1000").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("name Gertr dude").once().ordered().and_return([
                "                                      ^",
                "% Invalid input detected at '^' marker."
            ])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().and_return([])

        with self.assertRaises(BadVlanName) as expect:
            self.switch.add_vlan(1000, name="Gertr dude")

        assert_that(str(expect.exception), equal_to("Vlan name is invalid"))


    def test_add_vlan_fails_when_already_exist(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show vlan id 1000").and_return([
            "VLAN       Name                         Ports          Type      Authorization",
            "-----  ---------------                  -------------  -----     -------------",
            "1000                                                   Static    Required     "
        ])

        with self.assertRaises(VlanAlreadyExist) as expect:
            self.switch.add_vlan(1000)

        assert_that(str(expect.exception), equal_to("Vlan 1000 already exists"))

    def test_remove_vlan(self):
        self.command_setup()

        with self.configuring_and_committing():
            self.mocked_ssh_client.should_receive("do").with_args("no vlan 1000").once().ordered().and_return([])

        self.switch.remove_vlan(1000)

    def test_remove_unknown_vlan(self):
        self.command_setup()

        with self.configuring():
            self.mocked_ssh_client.should_receive("do").with_args("no vlan 1000").once().ordered().and_return([
                "These VLANs do not exist:  1000.",
            ])

        with self.assertRaises(UnknownVlan) as expect:
            self.switch.remove_vlan(1000)

        assert_that(str(expect.exception), equal_to("Vlan 1000 not found"))

    def test_set_access_mode(self):
        self.command_setup()

        with self.configuring_and_committing():
            self.mocked_ssh_client.should_receive("do").with_args("interface tengigabitethernet 1/0/10").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("no switchport trunk allowed vlan").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("no switchport general allowed vlan").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("no switchport general pvid").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("switchport mode access").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        self.switch.set_access_mode("tengigabitethernet 1/0/10")

    def test_set_access_mode_invalid_interface(self):
        self.command_setup()

        with self.configuring():
            self.mocked_ssh_client.should_receive("do").with_args("interface tengigabitethernet 1/0/99").once().ordered().and_return([
                "An invalid interface has been used for this function."
            ])

        with self.assertRaises(UnknownInterface) as expect:
            self.switch.set_access_mode("tengigabitethernet 1/0/99")

        assert_that(str(expect.exception), equal_to("Unknown interface tengigabitethernet 1/0/99"))

    def test_set_trunk_mode(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface tengigabitethernet 1/0/10").and_return([
        ])

        with self.configuring_and_committing():
            self.mocked_ssh_client.should_receive("do").with_args("interface tengigabitethernet 1/0/10").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("no switchport access vlan").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("switchport mode trunk").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        self.switch.set_trunk_mode("tengigabitethernet 1/0/10")

    def test_set_trunk_mode_stays_in_trunk(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface tengigabitethernet 1/0/10").and_return([
            "switchport mode trunk"
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure").never()
        self.mocked_ssh_client.should_receive("do").with_args("copy running-config startup-config", wait_for="? (y/n) ").once().ordered().and_return([])
        self.mocked_ssh_client.should_receive("send_key").with_args("y").once().ordered().and_return([])

        self.switch.set_trunk_mode("tengigabitethernet 1/0/10")

    def test_set_trunk_mode_stays_in_general(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface tengigabitethernet 1/0/10").and_return([
            "switchport mode general"
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure").never()
        self.mocked_ssh_client.should_receive("do").with_args("copy running-config startup-config", wait_for="? (y/n) ").once().ordered().and_return([])
        self.mocked_ssh_client.should_receive("send_key").with_args("y").once().ordered().and_return([])

        self.switch.set_trunk_mode("tengigabitethernet 1/0/10")

    def test_configure_set_trunk_mode_unknown_interface(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface tengigabitethernet 1/0/99").and_return([
            "An invalid interface has been used for this function",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure").never()

        with self.assertRaises(UnknownInterface) as expect:
            self.switch.set_trunk_mode("tengigabitethernet 1/0/99")

        assert_that(str(expect.exception), equal_to("Unknown interface tengigabitethernet 1/0/99"))

    def test_set_access_vlan(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface tengigabitethernet 1/0/10").and_return([
        ])

        with self.configuring_and_committing():
            self.mocked_ssh_client.should_receive("do").with_args("interface tengigabitethernet 1/0/10").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("switchport access vlan 1000").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        self.switch.set_access_vlan("tengigabitethernet 1/0/10", 1000)

    def test_set_access_vlan_invalid_interface(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface tengigabitethernet 1/0/99").and_return([
            "An invalid interface has been used for this function."
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure").never()

        with self.assertRaises(UnknownInterface) as expect:
            self.switch.set_access_vlan("tengigabitethernet 1/0/99", 1000)

        assert_that(str(expect.exception), equal_to("Unknown interface tengigabitethernet 1/0/99"))

    def test_set_access_vlan_invalid_vlan(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface tengigabitethernet 1/0/10").and_return([
            "switchport mode access"
        ])

        with self.configuring():
            self.mocked_ssh_client.should_receive("do").with_args("interface tengigabitethernet 1/0/10").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("switchport access vlan 1000").once().ordered().and_return([
                "VLAN ID not found."
            ])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        with self.assertRaises(UnknownVlan) as expect:
            self.switch.set_access_vlan("tengigabitethernet 1/0/10", 1000)

        assert_that(str(expect.exception), equal_to("Vlan 1000 not found"))

    def test_set_access_vlan_invalid_mode_trunk(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface tengigabitethernet 1/0/10").and_return([
            "switchport mode trunk"
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure").never()

        with self.assertRaises(InterfaceInWrongPortMode) as expect:
            self.switch.set_access_vlan("tengigabitethernet 1/0/10", 1000)

        assert_that(str(expect.exception), equal_to("Operation cannot be performed on a trunk mode interface"))

    def test_set_access_vlan_invalid_mode_general(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface tengigabitethernet 1/0/10").and_return([
            "switchport mode general"
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure").never()

        with self.assertRaises(InterfaceInWrongPortMode) as expect:
            self.switch.set_access_vlan("tengigabitethernet 1/0/10", 1000)

        assert_that(str(expect.exception), equal_to("Operation cannot be performed on a general mode interface"))

    def test_remove_access_vlan(self):
        self.command_setup()

        with self.configuring_and_committing():
            self.mocked_ssh_client.should_receive("do").with_args("interface tengigabitethernet 1/0/10").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("no switchport access vlan").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        self.switch.remove_access_vlan("tengigabitethernet 1/0/10")

    def test_remove_access_vlan_invalid_interface(self):
        self.command_setup()

        with self.configuring():
            self.mocked_ssh_client.should_receive("do").with_args("interface tengigabitethernet 1/0/99").once().ordered().and_return([
                "An invalid interface has been used for this function."
            ])

        with self.assertRaises(UnknownInterface) as expect:
            self.switch.remove_access_vlan("tengigabitethernet 1/0/99")

        assert_that(str(expect.exception), equal_to("Unknown interface tengigabitethernet 1/0/99"))

    def test_configure_native_vlan_on_a_general_interface(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface tengigabitethernet 1/0/10").and_return([
            "switchport mode general"
        ])

        with self.configuring_and_committing():
            self.mocked_ssh_client.should_receive("do").with_args("interface tengigabitethernet 1/0/10").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("switchport general pvid 1000").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        self.switch.configure_native_vlan("tengigabitethernet 1/0/10", 1000)

    def test_configure_native_vlan_unknown_interface(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface tengigabitethernet 1/0/99").and_return([
            "An invalid interface has been used for this function",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure").never()

        with self.assertRaises(UnknownInterface) as expect:
            self.switch.configure_native_vlan("tengigabitethernet 1/0/99", 1000)

        assert_that(str(expect.exception), equal_to("Unknown interface tengigabitethernet 1/0/99"))

    def test_configure_native_vlan_unknown_vlan(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface tengigabitethernet 1/0/10").and_return([
            "switchport mode general",
        ])

        with self.configuring():
            self.mocked_ssh_client.should_receive("do").with_args("interface tengigabitethernet 1/0/10").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("switchport general pvid 1000").once().ordered().and_return([
                "Could not configure pvid."
            ])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        with self.assertRaises(UnknownVlan) as expect:
            self.switch.configure_native_vlan("tengigabitethernet 1/0/10", 1000)

        assert_that(str(expect.exception), equal_to("Vlan 1000 not found"))

    def test_configure_native_vlan_on_an_unknown_mode_with_no_access_vlan_assume_not_set_and_set_port_mode(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface tengigabitethernet 1/0/10").and_return([
        ])

        with self.configuring_and_committing():
            self.mocked_ssh_client.should_receive("do").with_args("interface tengigabitethernet 1/0/10").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("switchport mode general").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("switchport general pvid 1000").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        self.switch.configure_native_vlan("tengigabitethernet 1/0/10", 1000)

    def test_configure_native_vlan_on_an_unknown_mode_with_an_access_vlan_assume_access_mode_and_fails(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface tengigabitethernet 1/0/10").and_return([
            "switchport access vlan 2000",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure").never()

        with self.assertRaises(InterfaceInWrongPortMode) as expect:
            self.switch.configure_native_vlan("tengigabitethernet 1/0/10", 1000)

        assert_that(str(expect.exception), equal_to("Operation cannot be performed on a access mode interface"))

    def test_configure_native_vlan_on_a_trunk_mode_swithes_to_general(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface tengigabitethernet 1/0/10").and_return([
            "switchport mode trunk",
        ])

        with self.configuring_and_committing():
            self.mocked_ssh_client.should_receive("do").with_args("interface tengigabitethernet 1/0/10").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("switchport mode general").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("switchport general pvid 1000").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        self.switch.configure_native_vlan("tengigabitethernet 1/0/10", 1000)

    def test_configure_native_vlan_on_a_trunk_mode_swithes_to_general_and_copies_actual_allowed_vlans(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface tengigabitethernet 1/0/10").and_return([
            "switchport mode trunk",
            "switchport trunk allowed vlan 1201-1203,1205",
        ])

        with self.configuring_and_committing():
            self.mocked_ssh_client.should_receive("do").with_args("interface tengigabitethernet 1/0/10").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("switchport mode general").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("switchport general allowed vlan 1201-1203,1205").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("switchport general pvid 1000").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        self.switch.configure_native_vlan("tengigabitethernet 1/0/10", 1000)

    def test_remove_native_vlan_reverts_to_trunk_mode(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface tengigabitethernet 1/0/10").and_return([
            "switchport mode general",
            "switchport general pvid 1000"
        ])

        with self.configuring_and_committing():
            self.mocked_ssh_client.should_receive("do").with_args("interface tengigabitethernet 1/0/10").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("switchport mode trunk").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        self.switch.remove_native_vlan("tengigabitethernet 1/0/10")

    def test_remove_native_vlan_reverts_to_trunk_mode_and_keeps_allowed_vlans_specs(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface tengigabitethernet 1/0/10").and_return([
            "switchport mode general",
            "switchport general pvid 1000",
            "switchport general allowed vlan add 1201-1203,1205",
        ])

        with self.configuring_and_committing():
            self.mocked_ssh_client.should_receive("do").with_args("interface tengigabitethernet 1/0/10").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("switchport mode trunk").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("switchport trunk allowed vlan add 1201-1203,1205").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        self.switch.remove_native_vlan("tengigabitethernet 1/0/10")

    def test_remove_native_vlan_inknown_interface(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface tengigabitethernet 1/0/99").and_return([
            "An invalid interface has been used for this function",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure").never()

        with self.assertRaises(UnknownInterface) as expect:
            self.switch.remove_native_vlan("tengigabitethernet 1/0/99")

        assert_that(str(expect.exception), equal_to("Unknown interface tengigabitethernet 1/0/99"))

    def test_remove_native_vlan_not_set(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface tengigabitethernet 1/0/10").and_return([
            "switchport mode general"
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure").never()

        with self.assertRaises(NativeVlanNotSet) as expect:
            self.switch.remove_native_vlan("tengigabitethernet 1/0/10")

        assert_that(str(expect.exception), is_("Trunk native Vlan is not set on interface tengigabitethernet 1/0/10"))

    def test_add_trunk_vlan(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface tengigabitethernet 1/0/10").and_return([
            "switchport mode trunk",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("show vlan").and_return([
            "VLAN   Name                             Ports          Type",
            "-----  ---------------                  -------------  --------------",
            "1      default                                         Default",
            "1000   VLAN1000                                        Static",
        ])

        with self.configuring_and_committing():
            self.mocked_ssh_client.should_receive("do").with_args("interface tengigabitethernet 1/0/10").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("switchport trunk allowed vlan 1000").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        self.switch.add_trunk_vlan("tengigabitethernet 1/0/10", 1000)

    def test_add_trunk_vlan_when_theres_already_one(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface tengigabitethernet 1/0/10").and_return([
            "switchport mode trunk",
            "switchport trunk allowed vlan 900"
        ])

        self.mocked_ssh_client.should_receive("do").with_args("show vlan").and_return([
            "VLAN   Name                             Ports          Type",
            "-----  ---------------                  -------------  --------------",
            "1      default                                         Default",
            "1000   VLAN1000                                        Static",
        ])

        with self.configuring_and_committing():
            self.mocked_ssh_client.should_receive("do").with_args("interface tengigabitethernet 1/0/10").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("switchport trunk allowed vlan add 1000").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        self.switch.add_trunk_vlan("tengigabitethernet 1/0/10", 1000)

    def test_add_trunk_vlan_unknown_interface(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface tengigabitethernet 1/0/99").and_return([
            "An invalid interface has been used for this function",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure").never()

        with self.assertRaises(UnknownInterface) as expect:
            self.switch.add_trunk_vlan("tengigabitethernet 1/0/99", 1000)

        assert_that(str(expect.exception), equal_to("Unknown interface tengigabitethernet 1/0/99"))

    def test_add_trunk_vlan_unknown_vlan(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface tengigabitethernet 1/0/10").and_return([
            "switchport mode trunk",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("show vlan").and_return([
            "VLAN   Name                             Ports          Type",
            "-----  ---------------                  -------------  --------------",
            "1      default                                         Default",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure").never()

        with self.assertRaises(UnknownVlan) as expect:
            self.switch.add_trunk_vlan("tengigabitethernet 1/0/10", 1000)

        assert_that(str(expect.exception), equal_to("Vlan 1000 not found"))

    def test_add_trunk_vlan_to_general_mode(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface tengigabitethernet 1/0/10").and_return([
            "switchport mode general",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("show vlan").and_return([
            "VLAN   Name                             Ports          Type",
            "-----  ---------------                  -------------  --------------",
            "1      default                                         Default",
            "1000   VLAN1000                                        Static",
        ])

        with self.configuring_and_committing():
            self.mocked_ssh_client.should_receive("do").with_args("interface tengigabitethernet 1/0/10").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("switchport general allowed vlan add 1000").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        self.switch.add_trunk_vlan("tengigabitethernet 1/0/10", 1000)

    def test_add_trunk_vlan_without_mode_and_access_vlan_assume_no_mode_set_trunk_mode(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface tengigabitethernet 1/0/10").and_return([
        ])

        self.mocked_ssh_client.should_receive("do").with_args("show vlan").and_return([
            "VLAN   Name                             Ports          Type",
            "-----  ---------------                  -------------  --------------",
            "1      default                                         Default",
            "1000   VLAN1000                                        Static",
        ])

        with self.configuring_and_committing():
            self.mocked_ssh_client.should_receive("do").with_args("interface tengigabitethernet 1/0/10").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("switchport mode trunk").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("switchport trunk allowed vlan 1000").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        self.switch.add_trunk_vlan("tengigabitethernet 1/0/10", 1000)

    def test_add_trunk_vlan_without_mode_with_access_vlan_assume_access_mode_and_fails(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface tengigabitethernet 1/0/10").and_return([
            "switchport access vlan 2000",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure").never()

        with self.assertRaises(InterfaceInWrongPortMode) as expect:
            self.switch.add_trunk_vlan("tengigabitethernet 1/0/10", 1000)

        assert_that(str(expect.exception), equal_to("Operation cannot be performed on a access mode interface"))

    def test_remove_trunk_vlan(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface tengigabitethernet 1/0/10").and_return([
            "switchport mode trunk",
            "switchport trunk allowed vlan 1000",
        ])

        with self.configuring_and_committing():
            self.mocked_ssh_client.should_receive("do").with_args("interface tengigabitethernet 1/0/10").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("switchport trunk allowed vlan remove 1000").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        self.switch.remove_trunk_vlan("tengigabitethernet 1/0/10", 1000)

    def test_remove_trunk_vlan_unknown_interface(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface tengigabitethernet 1/0/99").and_return([
            "An invalid interface has been used for this function",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure").never()

        with self.assertRaises(UnknownInterface) as expect:
            self.switch.remove_trunk_vlan("tengigabitethernet 1/0/99", 1000)

        assert_that(str(expect.exception), equal_to("Unknown interface tengigabitethernet 1/0/99"))

    def test_remove_trunk_vlan_not_set_at_all(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface tengigabitethernet 1/0/10").and_return([
            "switchport mode trunk",
        ])

        with self.assertRaises(TrunkVlanNotSet) as expect:
            self.switch.remove_trunk_vlan("tengigabitethernet 1/0/10", 1000)

        assert_that(str(expect.exception), equal_to("Trunk Vlan is not set on interface tengigabitethernet 1/0/10"))

    def test_remove_trunk_vlan_not_set_in_ranges(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface tengigabitethernet 1/0/10").and_return([
            "switchport mode trunk",
            "switchport trunk allowed vlan 999,1001",
        ])

        with self.assertRaises(TrunkVlanNotSet) as expect:
            self.switch.remove_trunk_vlan("tengigabitethernet 1/0/10", 1000)

        assert_that(str(expect.exception), equal_to("Trunk Vlan is not set on interface tengigabitethernet 1/0/10"))

    def test_remove_trunk_vlan_general_mode_and_in_range(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface tengigabitethernet 1/0/10").and_return([
            "switchport mode general",
            "switchport general allowed vlan add 999-1001",
        ])

        with self.configuring_and_committing():
            self.mocked_ssh_client.should_receive("do").with_args("interface tengigabitethernet 1/0/10").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("switchport general allowed vlan remove 1000").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        self.switch.remove_trunk_vlan("tengigabitethernet 1/0/10", 1000)

    def test_edit_interface_spanning_tree_enable_edge(self):
        self.command_setup()

        with self.configuring_and_committing():
            self.mocked_ssh_client.should_receive("do").with_args("interface tengigabitethernet 1/0/10").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("spanning-tree portfast").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        self.switch.edit_interface_spanning_tree('tengigabitethernet 1/0/10', edge=True)

    def test_edit_interface_spanning_tree_disable_edge(self):
        self.command_setup()

        with self.configuring_and_committing():
            self.mocked_ssh_client.should_receive("do").with_args("interface tengigabitethernet 1/0/10").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("no spanning-tree portfast").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        self.switch.edit_interface_spanning_tree('tengigabitethernet 1/0/10', edge=False)

    def test_edit_interface_spanning_tree_optional_params(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("configure").never()

        self.mocked_ssh_client.should_receive("do").with_args("copy running-config startup-config", wait_for="? (y/n) ").once().ordered().and_return([])
        self.mocked_ssh_client.should_receive("send_key").with_args("y").once().ordered().and_return([])

        self.switch.edit_interface_spanning_tree("tengigabitethernet 1/0/10")

    def test_enable_lldp(self):
        self.command_setup()

        with self.configuring_and_committing():
            self.mocked_ssh_client.should_receive("do").with_args("interface tengigabitethernet 1/0/10").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("lldp transmit").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("lldp receive").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("lldp med transmit-tlv capabilities").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("lldp med transmit-tlv network-policy").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        self.switch.enable_lldp("tengigabitethernet 1/0/10", True)

    def test_disable_lldp(self):
        self.command_setup()

        with self.configuring_and_committing():
            self.mocked_ssh_client.should_receive("do").with_args("interface tengigabitethernet 1/0/10").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("no lldp transmit").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("no lldp receive").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("no lldp med transmit-tlv capabilities").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("no lldp med transmit-tlv network-policy").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        self.switch.enable_lldp("tengigabitethernet 1/0/10", False)

    @contextmanager
    def configuring_and_committing(self):
        self.mocked_ssh_client.should_receive("do").with_args("configure").once().ordered().and_return([])

        yield

        self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])
        self.mocked_ssh_client.should_receive("do").with_args("copy running-config startup-config", wait_for="? (y/n) ").once().ordered().and_return([])
        self.mocked_ssh_client.should_receive("send_key").with_args("y").once().ordered().and_return([])

    @contextmanager
    def configuring(self):
        self.mocked_ssh_client.should_receive("do").with_args("configure").once().ordered().and_return([])

        yield

        self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])
