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

from netman.core.objects.port_modes import ACCESS, TRUNK
from netman.adapters.switches import dell
from netman.adapters.switches.dell import Dell
from netman.core.objects.switch_transactional import SwitchTransactional
from netman.core.objects.exceptions import UnknownInterface, BadVlanNumber, \
    BadVlanName, UnknownVlan, InterfaceInWrongPortMode, NativeVlanNotSet, TrunkVlanNotSet
from netman.core.objects.switch_descriptor import SwitchDescriptor


def test_factory():
    lock = mock.Mock()
    switch = dell.factory_ssh(SwitchDescriptor(hostname='hostname', model='dell', username='username', password='password', port=22), lock)

    assert_that(switch, instance_of(SwitchTransactional))
    assert_that(switch.impl, instance_of(Dell))
    assert_that(switch.lock, is_(lock))
    assert_that(switch.switch_descriptor.hostname, equal_to("hostname"))
    assert_that(switch.switch_descriptor.model, equal_to("dell"))
    assert_that(switch.switch_descriptor.username, equal_to("username"))
    assert_that(switch.switch_descriptor.password, equal_to("password"))
    assert_that(switch.switch_descriptor.port, equal_to(22))


class DellTest(unittest.TestCase):

    def setUp(self):
        self.lock = mock.Mock()
        self.switch = dell.factory_ssh(SwitchDescriptor(model='dell', hostname="my.hostname", password="the_password"), self.lock)

    def tearDown(self):
        flexmock_teardown()

    def command_setup(self):
        self.mocked_ssh_client = flexmock()
        self.switch.impl.shell = self.mocked_ssh_client

    def test_switch_has_a_logger_configured_with_the_switch_name(self):
        assert_that(self.switch.logger.name, is_(Dell.__module__ + ".my.hostname"))

    @mock.patch("netman.adapters.shell.ssh.SshClient")
    def test_connect(self, ssh_client_class_mock):
        self.switch = Dell(
            SwitchDescriptor(hostname="my.hostname", username="the_user", password="the_password", model="dell"),
            shell_factory=ssh_client_class_mock)

        self.mocked_ssh_client = flexmock()
        ssh_client_class_mock.return_value = self.mocked_ssh_client
        self.mocked_ssh_client.should_receive("do").with_args("enable", wait_for=":").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("the_password").and_return([]).once().ordered()

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
            self.mocked_ssh_client.should_receive("do").with_args("interface ethernet 1/g4").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("shutdown").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        self.switch.shutdown_interface("ethernet 1/g4")

    def test_shutdown_interface_invalid_interface_raises(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("configure").once().ordered().and_return([])
        self.mocked_ssh_client.should_receive("do").with_args("interface ethernet 99/g99").once().ordered().and_return([
            "An invalid interface has been used for this function."
        ])
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).once().ordered()

        with self.assertRaises(UnknownInterface) as expect:
            self.switch.shutdown_interface("ethernet 99/g99")

        assert_that(str(expect.exception), equal_to("Unknown interface ethernet 99/g99"))

    def test_openup_interface(self):
        self.command_setup()

        with self.configuring_and_committing():
            self.mocked_ssh_client.should_receive("do").with_args("interface ethernet 1/g4").and_return([]).once().ordered()
            self.mocked_ssh_client.should_receive("do").with_args("no shutdown").and_return([]).once().ordered()
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().and_return([])

        self.switch.openup_interface("ethernet 1/g4")

    def test_openup_interface_invalid_interface_raises(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("configure").once().ordered().and_return([])
        self.mocked_ssh_client.should_receive("do").with_args("interface ethernet 99/g99").once().ordered().and_return([
            "An invalid interface has been used for this function."
        ])
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).once().ordered()

        with self.assertRaises(UnknownInterface) as expect:
            self.switch.openup_interface("ethernet 99/g99")

        assert_that(str(expect.exception), equal_to("Unknown interface ethernet 99/g99"))

    def test_get_vlans(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show vlan", wait_for=("--More-- or (q)uit", "#"), include_last_line=True).once().ordered().and_return([
            "VLAN       Name                         Ports          Type      Authorization",
            "-----  ---------------                  -------------  -----     -------------",
            "1      Default                          ch2-3,ch5-6,   Default   Required",
            "                                        ch8-48,",
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

    def test_get_vlans_multipage(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show vlan", wait_for=("--More-- or (q)uit", "#"), include_last_line=True).once().ordered().and_return([
            "VLAN       Name                         Ports          Type      Authorization",
            "-----  ---------------                  -------------  -----     -------------",
            "1      Default                          ch2-3,ch5-6,   Default   Required",
            "                                        ch8-48,",
            "                                        1/g2-1/g3,",
            "2                                       ch1            Static    Required",
            "3                                       ch1            Static    Required",
            "4                                       ch1            Static    Required",
            "--More-- or (q)uit"
        ])

        self.mocked_ssh_client.should_receive("send_key").with_args("m", wait_for=("--More-- or (q)uit", "#"), include_last_line=True).once().ordered().and_return([
            "VLAN       Name                         Ports          Type      Authorization",
            "-----  ---------------                  -------------  -----     -------------",
            "5                                       ch1            Static    Required",
            "6                                       ch1            Static    Required",
            "7                                       ch1            Static    Required",
            "--More-- or (q)uit"
        ])

        self.mocked_ssh_client.should_receive("send_key").with_args("m", wait_for=("--More-- or (q)uit", "#"), include_last_line=True).once().ordered().and_return([
            "VLAN       Name                         Ports          Type      Authorization",
            "-----  ---------------                  -------------  -----     -------------",
            "8                                       ch1            Static    Required",
            "9                                       ch1            Static    Required",
            "10                                      ch1            Static    Required",
        ])

        vlans = self.switch.get_vlans()

        assert_that(vlans, has_length(10))

    def test_get_interfaces(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show interfaces status", wait_for=("--More-- or (q)uit", "#"), include_last_line=True).and_return([
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

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface ethernet 1/g1").and_return([])
        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface ethernet 1/g12").and_return([
            "switchport access vlan 1234"
        ])
        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface ethernet 2/xg1").and_return([
            "shutdown",
            "switchport mode trunk",
            "switchport trunk allowed vlan add 900,1000-1001,1003-1005",
        ])
        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface ethernet 2/xg2").and_return([
            "switchport mode general",
            "switchport general allowed vlan add 900,1000-1001,1003-1005",
            "switchport general pvid 1500",
        ])
        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface port-channel 1").and_return([])
        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface port-channel 10").and_return([])

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

        assert_that(i2_x2.name, is_("ethernet 2/xg2"))
        assert_that(i2_x2.port_mode, is_(TRUNK))
        assert_that(i2_x2.trunk_native_vlan, is_(1500))
        assert_that(i2_x2.trunk_vlans, is_([900, 1000, 1001, 1003, 1004, 1005]))

        assert_that(ch1.name, is_("port-channel 1"))
        assert_that(ch10.name, is_("port-channel 10"))

    def test_get_interfaces_multipage(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show interfaces status", wait_for=("--More-- or (q)uit", "#"), include_last_line=True).once().ordered().and_return([
            "Port   Type                            Duplex  Speed    Neg  Link  Flow Control",
            "                                                             State Status",
            "-----  ------------------------------  ------  -------  ---- --------- ------------",
            "1/g1   Gigabit - Level                 Full    1000     Auto Up        Inactive",
            "1/g2   Gigabit - Level                 Full    1000     Auto Up        Inactive",
            "--More-- or (q)uit",
        ])

        self.mocked_ssh_client.should_receive("send_key").with_args("m", wait_for=("--More-- or (q)uit", "#"), include_last_line=True).once().ordered().and_return([
            "1/g3   Gigabit - Level                 Full    1000     Auto Up        Inactive",
            "1/g4   Gigabit - Level                 Full    1000     Auto Up        Inactive",
            "--More-- or (q)uit",
        ])

        self.mocked_ssh_client.should_receive("send_key").with_args("m", wait_for=("--More-- or (q)uit", "#"), include_last_line=True).once().ordered().and_return([
            "1/g5   Gigabit - Level                 Full    1000     Auto Up        Inactive",
            "Ch   Type                            Link",
            "                                     State",
            "---  ------------------------------  -----",
            "ch1  Link Aggregate                  Up",
            "ch2  Link Aggregate                  Down",
            "--More-- or (q)uit",
        ])

        self.mocked_ssh_client.should_receive("send_key").with_args("m", wait_for=("--More-- or (q)uit", "#"), include_last_line=True).once().ordered().and_return([
            "ch3  Link Aggregate                  Down",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface ethernet 1/g1").ordered().and_return([])
        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface ethernet 1/g2").ordered().and_return([])
        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface ethernet 1/g3").ordered().and_return([])
        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface ethernet 1/g4").ordered().and_return([])
        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface ethernet 1/g5").ordered().and_return([])
        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface port-channel 1").ordered().and_return([])
        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface port-channel 2").ordered().and_return([])
        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface port-channel 3").ordered().and_return([])

        assert_that(self.switch.get_interfaces(), has_length(8))

    def test_add_vlan(self):
        self.command_setup()

        with self.configuring_and_committing():
            self.mocked_ssh_client.should_receive("do").with_args("vlan database").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("vlan 1000").once().ordered().and_return([
                "Warning: The use of large numbers of VLANs or interfaces may cause significant",
                "delays in applying the configuration."
            ])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        self.switch.add_vlan(1000)

    def test_add_vlan_and_name(self):
        self.command_setup()

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
        self.command_setup()

        with self.configuring():
            self.mocked_ssh_client.should_receive("do").with_args("vlan database").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("vlan 5000").once().ordered().and_return([
                "Warning: The use of large numbers of VLANs or interfaces may cause significant",
                "delays in applying the configuration.",
                "          Failure Information",
                "---------------------------------------",
                "   VLANs failed to be configured : 1",
                "---------------------------------------",
                "   VLAN             Error",
                "---------------------------------------",
                "VLAN      5000 ERROR: VLAN ID is out of range",
            ])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        with self.assertRaises(BadVlanNumber) as expect:
            self.switch.add_vlan(5000, name="Gertrude")

        assert_that(str(expect.exception), equal_to("Vlan number is invalid"))

    def test_add_vlan_and_bad_name(self):
        self.command_setup()

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

    def test_remove_vlan(self):
        self.command_setup()

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
        self.command_setup()

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

    def test_set_access_mode(self):
        self.command_setup()

        with self.configuring_and_committing():
            self.mocked_ssh_client.should_receive("do").with_args("interface ethernet 1/g10").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("switchport mode access").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        self.switch.set_access_mode("ethernet 1/g10")

    def test_set_access_mode_invalid_interface(self):
        self.command_setup()

        with self.configuring():
            self.mocked_ssh_client.should_receive("do").with_args("interface ethernet 1/g99").once().ordered().and_return([
                "An invalid interface has been used for this function."
            ])

        with self.assertRaises(UnknownInterface) as expect:
            self.switch.set_access_mode("ethernet 1/g99")

        assert_that(str(expect.exception), equal_to("Unknown interface ethernet 1/g99"))

    def test_set_trunk_mode(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface ethernet 1/g10").and_return([
        ])

        with self.configuring_and_committing():
            self.mocked_ssh_client.should_receive("do").with_args("interface ethernet 1/g10").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("switchport mode trunk").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        self.switch.set_trunk_mode("ethernet 1/g10")

    def test_set_trunk_mode_stays_in_trunk(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface ethernet 1/g10").and_return([
            "switchport mode trunk"
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure").never()
        self.mocked_ssh_client.should_receive("do").with_args("copy running-config startup-config", wait_for="? (y/n) ").once().ordered().and_return([])
        self.mocked_ssh_client.should_receive("send_key").with_args("y").once().ordered().and_return([])

        self.switch.set_trunk_mode("ethernet 1/g10")

    def test_set_trunk_mode_stays_in_general(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface ethernet 1/g10").and_return([
            "switchport mode general"
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure").never()
        self.mocked_ssh_client.should_receive("do").with_args("copy running-config startup-config", wait_for="? (y/n) ").once().ordered().and_return([])
        self.mocked_ssh_client.should_receive("send_key").with_args("y").once().ordered().and_return([])

        self.switch.set_trunk_mode("ethernet 1/g10")

    def test_configure_set_trunk_mode_unknown_interface(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface ethernet 1/g99").and_return([
            "ERROR: Invalid input!",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure").never()

        with self.assertRaises(UnknownInterface) as expect:
            self.switch.set_trunk_mode("ethernet 1/g99")

        assert_that(str(expect.exception), equal_to("Unknown interface ethernet 1/g99"))

    def test_set_access_vlan(self):
        self.command_setup()

        with self.configuring_and_committing():
            self.mocked_ssh_client.should_receive("do").with_args("interface ethernet 1/g10").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("switchport access vlan 1000").once().ordered().and_return([
                "Warning: The use of large numbers of VLANs or interfaces may cause significant",
                "delays in applying the configuration."
            ])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        self.switch.set_access_vlan("ethernet 1/g10", 1000)

    def test_set_access_vlan_invalid_interface(self):
        self.command_setup()

        with self.configuring():
            self.mocked_ssh_client.should_receive("do").with_args("interface ethernet 1/g99").once().ordered().and_return([
                "An invalid interface has been used for this function."
            ])

        with self.assertRaises(UnknownInterface) as expect:
            self.switch.set_access_vlan("ethernet 1/g99", 1000)

        assert_that(str(expect.exception), equal_to("Unknown interface ethernet 1/g99"))

    def test_set_access_vlan_invalid_vlan(self):
        self.command_setup()

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
        self.command_setup()

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

    def test_remove_access_vlan(self):
        self.command_setup()

        with self.configuring_and_committing():
            self.mocked_ssh_client.should_receive("do").with_args("interface ethernet 1/g10").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("no switchport access vlan").once().ordered().and_return([
                "Warning: The use of large numbers of VLANs or interfaces may cause significant",
                "delays in applying the configuration."
            ])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        self.switch.remove_access_vlan("ethernet 1/g10")

    def test_remove_access_vlan_invalid_interface(self):
        self.command_setup()

        with self.configuring():
            self.mocked_ssh_client.should_receive("do").with_args("interface ethernet 1/g99").once().ordered().and_return([
                "An invalid interface has been used for this function."
            ])

        with self.assertRaises(UnknownInterface) as expect:
            self.switch.remove_access_vlan("ethernet 1/g99")

        assert_that(str(expect.exception), equal_to("Unknown interface ethernet 1/g99"))

    def test_configure_native_vlan_on_a_general_interface(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface ethernet 1/g10").and_return([
            "switchport mode general"
        ])

        with self.configuring_and_committing():
            self.mocked_ssh_client.should_receive("do").with_args("interface ethernet 1/g10").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("switchport general pvid 1000").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        self.switch.configure_native_vlan("ethernet 1/g10", 1000)

    def test_configure_native_vlan_unknown_interface(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface ethernet 1/g99").and_return([
            "ERROR: Invalid input!",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure").never()

        with self.assertRaises(UnknownInterface) as expect:
            self.switch.configure_native_vlan("ethernet 1/g99", 1000)

        assert_that(str(expect.exception), equal_to("Unknown interface ethernet 1/g99"))

    def test_configure_native_vlan_unknown_vlan(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface ethernet 1/g10").and_return([
            "switchport mode general",
        ])

        with self.configuring():
            self.mocked_ssh_client.should_receive("do").with_args("interface ethernet 1/g10").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("switchport general pvid 1000").once().ordered().and_return([
                "Could not configure pvid."
            ])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        with self.assertRaises(UnknownVlan) as expect:
            self.switch.configure_native_vlan("ethernet 1/g10", 1000)

        assert_that(str(expect.exception), equal_to("Vlan 1000 not found"))

    def test_configure_native_vlan_on_an_unknown_mode_with_no_access_vlan_assume_not_set_and_set_port_mode(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface ethernet 1/g10").and_return([
        ])

        with self.configuring_and_committing():
            self.mocked_ssh_client.should_receive("do").with_args("interface ethernet 1/g10").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("switchport mode general").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("switchport general pvid 1000").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        self.switch.configure_native_vlan("ethernet 1/g10", 1000)

    def test_configure_native_vlan_on_an_unknown_mode_with_an_access_vlan_assume_access_mode_and_fails(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface ethernet 1/g10").and_return([
            "switchport access vlan 2000",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure").never()

        with self.assertRaises(InterfaceInWrongPortMode) as expect:
            self.switch.configure_native_vlan("ethernet 1/g10", 1000)

        assert_that(str(expect.exception), equal_to("Operation cannot be performed on a access mode interface"))

    def test_configure_native_vlan_on_a_trunk_mode_swithes_to_general(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface ethernet 1/g10").and_return([
            "switchport mode trunk",
        ])

        with self.configuring_and_committing():
            self.mocked_ssh_client.should_receive("do").with_args("interface ethernet 1/g10").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("switchport mode general").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("switchport general pvid 1000").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        self.switch.configure_native_vlan("ethernet 1/g10", 1000)

    def test_configure_native_vlan_on_a_trunk_mode_swithes_to_general_and_copies_actual_allowed_vlans(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface ethernet 1/g10").and_return([
            "switchport mode trunk",
            "switchport trunk allowed vlan add 1201-1203,1205",
        ])

        with self.configuring_and_committing():
            self.mocked_ssh_client.should_receive("do").with_args("interface ethernet 1/g10").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("switchport mode general").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("switchport general allowed vlan add 1201-1203,1205").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("switchport general pvid 1000").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        self.switch.configure_native_vlan("ethernet 1/g10", 1000)

    def test_remove_native_vlan_reverts_to_trunk_mode(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface ethernet 1/g10").and_return([
            "switchport mode general",
            "switchport general pvid 1000"
        ])

        with self.configuring_and_committing():
            self.mocked_ssh_client.should_receive("do").with_args("interface ethernet 1/g10").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("switchport mode trunk").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        self.switch.remove_native_vlan("ethernet 1/g10")

    def test_remove_native_vlan_reverts_to_trunk_mode_and_keeps_allowed_vlans_specs(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface ethernet 1/g10").and_return([
            "switchport mode general",
            "switchport general pvid 1000",
            "switchport general allowed vlan add 1201-1203,1205",
        ])

        with self.configuring_and_committing():
            self.mocked_ssh_client.should_receive("do").with_args("interface ethernet 1/g10").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("switchport mode trunk").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("switchport trunk allowed vlan add 1201-1203,1205").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        self.switch.remove_native_vlan("ethernet 1/g10")

    def test_remove_native_vlan_inknown_interface(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface ethernet 1/g99").and_return([
            "ERROR: Invalid input!",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure").never()

        with self.assertRaises(UnknownInterface) as expect:
            self.switch.remove_native_vlan("ethernet 1/g99")

        assert_that(str(expect.exception), equal_to("Unknown interface ethernet 1/g99"))

    def test_remove_native_vlan_not_set(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface ethernet 1/g10").and_return([
            "switchport mode general"
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure").never()

        with self.assertRaises(NativeVlanNotSet) as expect:
            self.switch.remove_native_vlan("ethernet 1/g10")

        assert_that(str(expect.exception), is_("Trunk native Vlan is not set on interface ethernet 1/g10"))

    def test_add_trunk_vlan(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface ethernet 1/g10").and_return([
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
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface ethernet 1/g99").and_return([
            "ERROR: Invalid input!",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure").never()

        with self.assertRaises(UnknownInterface) as expect:
            self.switch.add_trunk_vlan("ethernet 1/g99", 1000)

        assert_that(str(expect.exception), equal_to("Unknown interface ethernet 1/g99"))

    def test_add_trunk_vlan_unknown_vlan(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface ethernet 1/g10").and_return([
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
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface ethernet 1/g10").and_return([
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
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface ethernet 1/g10").and_return([
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
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface ethernet 1/g10").and_return([
            "switchport access vlan 2000",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure").never()

        with self.assertRaises(InterfaceInWrongPortMode) as expect:
            self.switch.add_trunk_vlan("ethernet 1/g10", 1000)

        assert_that(str(expect.exception), equal_to("Operation cannot be performed on a access mode interface"))

    def test_remove_trunk_vlan(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface ethernet 1/g10").and_return([
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
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface ethernet 1/g99").and_return([
            "ERROR: Invalid input!",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure").never()

        with self.assertRaises(UnknownInterface) as expect:
            self.switch.remove_trunk_vlan("ethernet 1/g99", 1000)

        assert_that(str(expect.exception), equal_to("Unknown interface ethernet 1/g99"))

    def test_remove_trunk_vlan_not_set_at_all(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface ethernet 1/g10").and_return([
            "switchport mode trunk",
        ])

        with self.assertRaises(TrunkVlanNotSet) as expect:
            self.switch.remove_trunk_vlan("ethernet 1/g10", 1000)

        assert_that(str(expect.exception), equal_to("Trunk Vlan is not set on interface ethernet 1/g10"))

    def test_remove_trunk_vlan_not_set_in_ranges(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface ethernet 1/g10").and_return([
            "switchport mode trunk",
            "switchport trunk allowed vlan add 999,1001",
        ])

        with self.assertRaises(TrunkVlanNotSet) as expect:
            self.switch.remove_trunk_vlan("ethernet 1/g10", 1000)

        assert_that(str(expect.exception), equal_to("Trunk Vlan is not set on interface ethernet 1/g10"))

    def test_remove_trunk_vlan_general_mode_and_in_range(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface ethernet 1/g10").and_return([
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

    def test_edit_interface_spanning_tree_enable_edge(self):
        self.command_setup()

        with self.configuring_and_committing():
            self.mocked_ssh_client.should_receive("do").with_args("interface ethernet 1/g10").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("spanning-tree portfast").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        self.switch.edit_interface_spanning_tree('ethernet 1/g10', edge=True)

    def test_edit_interface_spanning_tree_disable_edge(self):
        self.command_setup()

        with self.configuring_and_committing():
            self.mocked_ssh_client.should_receive("do").with_args("interface ethernet 1/g10").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("no spanning-tree portfast").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        self.switch.edit_interface_spanning_tree('ethernet 1/g10', edge=False)

    def test_edit_interface_spanning_tree_optional_params(self):
        self.command_setup()

        self.mocked_ssh_client.should_receive("do").with_args("configure").never()

        self.mocked_ssh_client.should_receive("do").with_args("copy running-config startup-config", wait_for="? (y/n) ").once().ordered().and_return([])
        self.mocked_ssh_client.should_receive("send_key").with_args("y").once().ordered().and_return([])

        self.switch.edit_interface_spanning_tree("ethernet 1/g10")

    def test_enable_lldp(self):
        self.command_setup()

        with self.configuring_and_committing():
            self.mocked_ssh_client.should_receive("do").with_args("interface ethernet 1/g10").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("lldp transmit").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("lldp receive").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("lldp med transmit-tlv capabilities").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("lldp med transmit-tlv network-policy").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        self.switch.enable_lldp("ethernet 1/g10", True)

    def test_disable_lldp(self):
        self.command_setup()

        with self.configuring_and_committing():
            self.mocked_ssh_client.should_receive("do").with_args("interface ethernet 1/g10").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("no lldp transmit").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("no lldp receive").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("no lldp med transmit-tlv capabilities").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("no lldp med transmit-tlv network-policy").once().ordered().and_return([])
            self.mocked_ssh_client.should_receive("do").with_args("exit").once().ordered().and_return([])

        self.switch.enable_lldp("ethernet 1/g10", False)

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
