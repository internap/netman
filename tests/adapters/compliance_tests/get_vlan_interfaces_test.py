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

from hamcrest import assert_that, contains_inanyorder

from netman.core.objects.exceptions import UnknownVlan
from tests import has_message
from tests.adapters.compliance_test_case import ComplianceTestCase


class GetVlanInterfacesTest(ComplianceTestCase):
    _dev_sample = "cisco"

    def setUp(self):
        super(GetVlanInterfacesTest, self).setUp()

    def test_returns_vlan_interfaces(self):
        self.client.add_vlan(1000, name="vlan1000")

        self.try_to.set_access_mode(self.test_ports[0].name)
        self.try_to.set_access_vlan(self.test_ports[0].name, 1000)

        self.try_to.set_trunk_mode(self.test_ports[1].name)
        self.try_to.add_trunk_vlan(self.test_ports[1].name, 1000)

        # At this time, interface_native_vlan is not supported on get_vlan_interfaces

        assert_that(self.client.get_vlan_interfaces(1000),
                    contains_inanyorder(self.test_ports[0].name, self.test_ports[1].name))

    def test_fails_when_the_vlan_does_not_exist(self):
        with self.assertRaises(UnknownVlan)as expect:
            self.client.get_vlan_interfaces(2000)

        assert_that(expect.exception, has_message("Vlan 2000 not found"))

    def tearDown(self):
        self.janitor.unset_interface_access_vlan(self.test_ports[0].name)

        self.janitor.remove_trunk_vlan(self.test_ports[1].name, 1000)
        self.janitor.set_access_mode(self.test_ports[1].name)

        self.janitor.remove_vlan(1000)

        super(GetVlanInterfacesTest, self).tearDown()
