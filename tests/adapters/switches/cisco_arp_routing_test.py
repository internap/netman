# Copyright 2017 Internap.
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
from hamcrest import assert_that, equal_to

from netman.adapters.switches.cisco import Cisco
from netman.adapters.switches.util import SubShell
from netman.core.objects.exceptions import UnknownVlan
from netman.core.objects.interface_states import OFF, ON
from netman.core.objects.switch_descriptor import SwitchDescriptor


class CiscoArpRoutingTest(unittest.TestCase):
    def setUp(self):
        self.switch = Cisco(SwitchDescriptor(model='cisco', hostname="my.hostname"))
        SubShell.debug = True
        self.mocked_ssh_client = flexmock()
        self.switch.ssh = self.mocked_ssh_client

    def tearDown(self):
        flexmock_teardown()

    def test_set_vlan_arp_routing_state_disable(self):
        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface vlan 1234")\
            .once()\
            .ordered()\
            .and_return(["Building configuration...",
                         "Current configuration : 41 bytes",
                         "!",
                         "interface Vlan1234",
                         " no ip address",
                         "end"])

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([
            "Enter configuration commands, one per line.  End with CNTL/Z."
        ])
        self.mocked_ssh_client.should_receive("do").with_args("interface vlan 1234").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("no shutdown").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("no ip proxy-arp").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()

        self.switch.set_vlan_arp_routing_state(1234, OFF)

    def test_set_vlan_arp_routing_state_enable(self):
        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface vlan 1234").once().ordered()\
            .and_return([
                "Building configuration...",
                "Current configuration : 41 bytes",
                "!",
                "interface Vlan1234",
                " no ip address",
                "end"])

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([
            "Enter configuration commands, one per line.  End with CNTL/Z."
        ])
        self.mocked_ssh_client.should_receive("do").with_args("interface vlan 1234").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("no shutdown").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("ip proxy-arp").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()

        self.switch.set_vlan_arp_routing_state(1234, ON)

    def test_set_vlan_arp_routing_state_without_interface_creates_it(self):
        self.mocked_ssh_client.should_receive("do").with_args(
            "show running-config interface vlan 1234").once().ordered().and_return([
                "                                  ^",
                "% Invalid input detected at '^' marker."])

        self.mocked_ssh_client.should_receive("do").with_args(
            "show running-config vlan 1234 | begin vlan")\
            .once().ordered().and_return(["vlan 1234", "end"])

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([
            "Enter configuration commands, one per line.  End with CNTL/Z."
        ])
        self.mocked_ssh_client.should_receive("do").with_args("interface vlan 1234").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("no shutdown").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("no ip proxy-arp").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()
        self.switch.set_vlan_arp_routing_state(1234, OFF)

    def test_set_vlan_arp_routing_state_unknown_vlan(self):
        self.mocked_ssh_client.should_receive("do").with_args(
            "show running-config interface vlan 1234")\
            .once().ordered().and_return(["                                  ^",
                                          "% Invalid input detected at '^' marker."])

        self.mocked_ssh_client.should_receive("do").with_args(
            "show running-config vlan 1234 | begin vlan").once().ordered().and_return([])

        with self.assertRaises(UnknownVlan) as expect:
            self.switch.set_vlan_arp_routing_state(1234, OFF)

        assert_that(str(expect.exception), equal_to("Vlan 1234 not found"))
