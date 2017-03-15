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
from hamcrest import assert_that, equal_to, is_
from netman.adapters.switches.cisco import Cisco
from netman.adapters.switches.util import SubShell
from netman.core.objects.exceptions import UnknownVlan, InvalidUnicastRPFMode, UnsupportedOperation
from netman.core.objects.switch_descriptor import SwitchDescriptor
from netman.core.objects.unicast_rpf_modes import STRICT


class CiscoUnicastRPFTest(unittest.TestCase):

    def setUp(self):
        self.switch = Cisco(SwitchDescriptor(model='cisco', hostname="my.hostname"))
        SubShell.debug = True
        self.mocked_ssh_client = flexmock()
        self.switch.ssh = self.mocked_ssh_client

    def tearDown(self):
        flexmock_teardown()

    def test_switch_has_a_logger_configured_with_the_switch_name(self):
        assert_that(self.switch.logger.name, is_(Cisco.__module__ + ".my.hostname"))

    def test_set_vlan_unicast_rpf_mode_strict(self):
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
        self.mocked_ssh_client.should_receive("do").with_args("ip verify unicast source reachable-via rx").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()

        self.switch.set_vlan_unicast_rpf_mode(1234, STRICT)

    def test_set_vlan_unicast_rpf_mode_unknown_mode(self):
        with self.assertRaises(InvalidUnicastRPFMode) as expect:
            self.switch.set_vlan_unicast_rpf_mode(1234, "shizzle")

        assert_that(str(expect.exception), equal_to("Unknown Unicast RPF mode: \"shizzle\""))

    def test_set_vlan_unicast_rpf_mode_unknown_mode_raises_when_not_supported(self):
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
        self.mocked_ssh_client.should_receive("do").with_args("ip verify unicast source reachable-via rx").and_return([
            "% ip verify configuration not supported on interface Vl1234",
            " - verification not supported by hardware",
            "% ip verify configuration not supported on interface Vl1234",
            " - verification not supported by hardware",
            "%Restoring the original configuration failed on Vlan1234 - Interface Support Failure"
        ]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()

        with self.assertRaises(UnsupportedOperation) as expect:
            self.switch.set_vlan_unicast_rpf_mode(1234, STRICT)

        assert_that(str(expect.exception), equal_to(
            "Operation \"Unicast RPF Mode Strict\" is not supported on this equipment: "
            "% ip verify configuration not supported on interface Vl1234\n"
            " - verification not supported by hardware\n"
            "% ip verify configuration not supported on interface Vl1234\n"
            " - verification not supported by hardware\n"
            "%Restoring the original configuration failed on Vlan1234 - Interface Support Failure"))

    def test_set_vlan_unicast_rpf_mode_strict_without_interface_creates_it(self):
        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface vlan 1234").once().ordered().and_return([
            "                                  ^",
            "% Invalid input detected at '^' marker.",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan 1234 | begin vlan").once().ordered().and_return([
            "vlan 1234",
            "end",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([
            "Enter configuration commands, one per line.  End with CNTL/Z."
        ])
        self.mocked_ssh_client.should_receive("do").with_args("interface vlan 1234").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("no shutdown").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("ip verify unicast source reachable-via rx").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()
        self.switch.set_vlan_unicast_rpf_mode(1234, STRICT)

    def test_set_vlan_unicast_rpf_mode_strict_unknown_vlan(self):
        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface vlan 1234").once().ordered().and_return([
            "                                  ^",
            "% Invalid input detected at '^' marker.",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan 1234 | begin vlan").once().ordered().and_return([
        ])

        with self.assertRaises(UnknownVlan) as expect:
            self.switch.set_vlan_unicast_rpf_mode(1234, STRICT)

        assert_that(str(expect.exception), equal_to("Vlan 1234 not found"))

    def test_unset_vlan_unicast_rpf_mode_strict(self):
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
        self.mocked_ssh_client.should_receive("do").with_args("no ip verify unicast").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()

        self.switch.unset_vlan_unicast_rpf_mode(1234)

    def test_unset_vlan_unicast_rpf_mode_strict_without_interface_creates_it(self):
        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface vlan 1234").once().ordered().and_return([
            "                                  ^",
            "% Invalid input detected at '^' marker.",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan 1234 | begin vlan").once().ordered().and_return([
            "vlan 1234",
            "end",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("configure terminal").once().ordered().and_return([
            "Enter configuration commands, one per line.  End with CNTL/Z."
        ])
        self.mocked_ssh_client.should_receive("do").with_args("interface vlan 1234").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("no shutdown").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("no ip verify unicast").and_return([]).once().ordered()
        self.mocked_ssh_client.should_receive("do").with_args("exit").and_return([]).twice().ordered().ordered()
        self.switch.unset_vlan_unicast_rpf_mode(1234)

    def test_unset_vlan_unicast_rpf_mode_strict_unknown_vlan(self):
        self.mocked_ssh_client.should_receive("do").with_args("show running-config interface vlan 1234").once().ordered().and_return([
            "                                  ^",
            "% Invalid input detected at '^' marker.",
        ])

        self.mocked_ssh_client.should_receive("do").with_args("show running-config vlan 1234 | begin vlan").once().ordered().and_return([
        ])

        with self.assertRaises(UnknownVlan) as expect:
            self.switch.unset_vlan_unicast_rpf_mode(1234)

        assert_that(str(expect.exception), equal_to("Vlan 1234 not found"))
