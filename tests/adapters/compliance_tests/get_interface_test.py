# Copyright 2016 Internap.
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

from hamcrest import assert_that, is_

from netman.core.objects.exceptions import UnknownInterface
from netman.core.objects.interface_states import ON
from tests import has_message
from tests.adapters.compliance_test_case import ComplianceTestCase


class GetInterfaceTest(ComplianceTestCase):
    _dev_sample = "juniper"

    def setUp(self):
        super(GetInterfaceTest, self).setUp()

    def test_returns_an_interface(self):
        interface = self.client.get_interface(self.test_ports[0].name)
        assert_that(interface.name, is_(self.test_ports[0].name))

    def test_get_interface_and_get_interfaces_are_same(self):
        self.client.add_vlan(1000, name="vlan1000")
        self.client.add_vlan(2000, name="vlan2000")
        expected = self.test_ports[0]

        self.try_to.set_access_vlan(expected.name, 1000)
        self.try_to.set_trunk_mode(expected.name)
        self.try_to.set_interface_state(expected.name, ON)
        self.try_to.set_interface_native_vlan(expected.name, 2000)
        self.try_to.set_interface_auto_negotiation_state(expected.name, ON)
        self.try_to.set_interface_mtu(expected.name, 5000)

        interface_from_single = self.client.get_interface(expected.name)
        interfaces = [inte for inte in self.client.get_interfaces() if inte.name == expected.name]
        interface_from_multiple = interfaces[0]

        assert_that(interface_from_single.name, is_(interface_from_multiple.name))
        assert_that(interface_from_single.port_mode, is_(interface_from_multiple.port_mode))
        assert_that(interface_from_single.shutdown, is_(interface_from_multiple.shutdown))
        assert_that(interface_from_single.trunk_native_vlan, is_(interface_from_multiple.trunk_native_vlan))
        assert_that(interface_from_single.trunk_vlans, is_(interface_from_multiple.trunk_vlans))
        assert_that(interface_from_single.auto_negotiation, is_(interface_from_multiple.auto_negotiation))
        assert_that(interface_from_single.mtu, is_(interface_from_multiple.mtu))

    def test_getinterface_nonexistent_raises(self):
        with self.assertRaises(UnknownInterface)as expect:
            self.client.get_interface('ethernet 1/nonexistent2000')

        assert_that(expect.exception, has_message("Unknown interface ethernet 1/nonexistent2000"))

    def tearDown(self):
        self.janitor.unset_interface_access_vlan(self.test_ports[0].name)
        self.janitor.unset_interface_native_vlan(self.test_ports[0].name)
        self.janitor.set_access_mode(self.test_ports[0].name)

        self.janitor.remove_vlan(1000)
        self.janitor.remove_vlan(2000)
        super(GetInterfaceTest, self).tearDown()
