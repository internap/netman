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
from hamcrest import assert_that, instance_of, is_, equal_to
from mock import Mock
from netaddr.ip import IPAddress

from netman.adapters.switches.brocade import Brocade, BackwardCompatibleBrocade
from netman.core.objects.flow_control_switch import FlowControlSwitch

from netman.adapters.switches import brocade_factory_ssh, brocade_factory_telnet
from netman.adapters.switches.util import SubShell
from netman.core.objects.interface_states import OFF, ON
from netman.core.objects.switch_descriptor import SwitchDescriptor
from tests import ignore_deprecation_warnings
from tests.adapters.switches.brocade_test import vlan_with_vif_display, vlan_display


@ignore_deprecation_warnings
def test_factory_ssh():
    lock = Mock()
    switch = brocade_factory_ssh(SwitchDescriptor(hostname='hostname', model='brocade', username='username', password='password', port=22), lock)

    assert_that(switch, instance_of(FlowControlSwitch))
    assert_that(switch.wrapped_switch, instance_of(Brocade))
    assert_that(switch.lock, is_(lock))
    assert_that(switch.switch_descriptor.hostname, equal_to("hostname"))
    assert_that(switch.switch_descriptor.model, equal_to("brocade"))
    assert_that(switch.switch_descriptor.username, equal_to("username"))
    assert_that(switch.switch_descriptor.password, equal_to("password"))
    assert_that(switch.switch_descriptor.port, equal_to(22))


@ignore_deprecation_warnings
def test_factory_telnet():
    lock = Mock()
    switch = brocade_factory_telnet(SwitchDescriptor(hostname='hostname', model='brocade', username='username', password='password', port=23), lock)

    assert_that(switch, instance_of(FlowControlSwitch))
    assert_that(switch.wrapped_switch, instance_of(Brocade))
    assert_that(switch.lock, is_(lock))
    assert_that(switch.switch_descriptor.hostname, equal_to("hostname"))
    assert_that(switch.switch_descriptor.model, equal_to("brocade"))
    assert_that(switch.switch_descriptor.username, equal_to("username"))
    assert_that(switch.switch_descriptor.password, equal_to("password"))
    assert_that(switch.switch_descriptor.port, equal_to(23))


class BrocadeBackwardCompatibilityTest(unittest.TestCase):

    def setUp(self):
        self.switch = BackwardCompatibleBrocade(SwitchDescriptor("brocade", "host"), None)
        self.shell_mock = flexmock()
        self.switch.shell = self.shell_mock

        SubShell.debug = True

    def tearDown(self):
        flexmock_teardown()

    @ignore_deprecation_warnings
    def test_set_access_vlan_accepts_no_ethernet(self):
        self.shell_mock.should_receive("do").with_args("show vlan 2999").once().ordered().and_return(
            vlan_display(2999)
        )

        self.shell_mock.should_receive("do").with_args("configure terminal").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("vlan 2999").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("untagged ethernet 1/4").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()

        self.switch.set_access_vlan("1/4", vlan=2999)

    @ignore_deprecation_warnings
    def test_unset_interface_access_vlan_accepts_no_ethernet(self):
        self.shell_mock.should_receive("do").with_args("show vlan brief | include ethe 1/4").once().ordered().and_return([
            "1202     your-name-                                        1202  -  Untagged Ports : ethe 1/10"
        ])

        self.shell_mock.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.shell_mock.should_receive("do").with_args("vlan 1202").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("no untagged ethernet 1/4").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()

        self.switch.unset_interface_access_vlan("1/4")

    @ignore_deprecation_warnings
    def test_set_access_mode_accepts_no_ethernet(self):
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

        self.switch.set_access_mode("1/4")

    @ignore_deprecation_warnings
    def test_set_trunk_mode_accepts_no_ethernet(self):
        self.shell_mock.should_receive("do").with_args("show vlan ethernet 1/4").once().ordered().and_return([
            "VLAN: 1  Untagged"
        ])

        self.shell_mock.should_receive("do").with_args("configure terminal").never()

        self.switch.set_trunk_mode("1/4")

    @ignore_deprecation_warnings
    def test_add_trunk_vlan_accepts_no_ethernet(self):
        self.shell_mock.should_receive("do").with_args("show vlan 2999").once().ordered().and_return(
            vlan_display(2999)
        )

        self.shell_mock.should_receive("do").with_args("configure terminal").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("vlan 2999").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("tagged ethernet 1/1").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()

        self.switch.add_trunk_vlan("1/1", vlan=2999)

    @ignore_deprecation_warnings
    def test_remove_trunk_vlan_accepts_no_ethernet(self):
        self.shell_mock.should_receive("do").with_args("show vlan 2999").once().ordered().and_return(
            vlan_display(2999)
        )

        self.shell_mock.should_receive("do").with_args("configure terminal").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("vlan 2999").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("no tagged ethernet 1/11").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()

        self.switch.remove_trunk_vlan("1/11", vlan=2999)

    @ignore_deprecation_warnings
    def test_set_interface_state_off_accepts_no_ethernet(self):
        self.shell_mock.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.shell_mock.should_receive("do").with_args("interface ethernet 1/4").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("disable").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()

        self.switch.set_interface_state("1/4", OFF)

    @ignore_deprecation_warnings
    def test_set_interface_state_on_accepts_no_ethernet(self):
        self.shell_mock.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.shell_mock.should_receive("do").with_args("interface ethernet 1/4").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("enable").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()

        self.switch.set_interface_state("1/4", ON)

    @ignore_deprecation_warnings
    def test_set_interface_native_vlan_backward_compatibility(self):
        self.shell_mock.should_receive("do").with_args("show vlan 2999").once().ordered().and_return(
            vlan_display(2999)
        )

        self.shell_mock.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.shell_mock.should_receive("do").with_args("vlan 2999").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("untagged ethernet 1/4").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()

        self.switch.set_interface_native_vlan("1/4", vlan=2999)

    @ignore_deprecation_warnings
    def test_unset_interface_native_vlan_on_trunk_accepts_no_ethernet(self):
        self.shell_mock.should_receive("do").with_args("show vlan brief | include ethe 1/4").once().ordered().and_return([
            "1202     your-name-                                        1202  -  Untagged Ports : ethe 1/10"
        ])

        self.shell_mock.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.shell_mock.should_receive("do").with_args("vlan 1202").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("no untagged ethernet 1/4").and_return([]).once().ordered()
        self.shell_mock.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()

        self.switch.unset_interface_native_vlan("1/4")

    @ignore_deprecation_warnings
    def test_add_vrrp_accepts_no_ethernet(self):
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
                                   track_id="1/1", track_decrement=50)

    @ignore_deprecation_warnings
    def test_reset_interfaces_accepts_no_ethernet(self):
        self.shell_mock.should_receive("do").with_args("show vlan ethernet 1/4").once().ordered().and_return([])

        self.shell_mock.should_receive("do").with_args("configure terminal").once().ordered().and_return([])
        self.shell_mock.should_receive("do").with_args("no interface ethernet 1/4").once().ordered().and_return([])
        self.shell_mock.should_receive("do").with_args("exit").once().ordered()

        self.switch.reset_interface("1/4")
