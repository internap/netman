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
from netaddr import IPNetwork, IPAddress

from netman.core.objects.access_groups import IN, OUT
from netman.core.objects.exceptions import UnknownVlan
from netman.core.objects.interface_states import ON
from tests.adapters.configured_test_case import ConfiguredTestCase


class GetVlanInterfacesTest(ConfiguredTestCase):
    _dev_sample = "cisco"

    def setUp(self):
        super(GetVlanInterfacesTest, self).setUp()

    def test_returns_vlan_interfaces(self):
        self.client.add_vlan(1000, name="vlan1000")

        self.try_to.set_trunk_mode(self.test_ports[0].name)
        self.try_to.set_interface_native_vlan(self.test_ports[0].name, 1000)

        self.try_to.set_access_mode(self.test_ports[1].name)
        self.try_to.set_access_vlan(self.test_ports[1].name, 1000)

        self.try_to.set_trunk_mode(self.test_ports[2].name)
        self.try_to.add_trunk_vlan(self.test_ports[2].name, 1000)

        assert_that(self.client.get_vlan_interfaces(1000),
                    is_([self.test_ports[0].name, self.test_ports[1].name, self.test_ports[2].name]))

    def test_fails_when_the_vlan_does_not_exist(self):
        with self.assertRaises(UnknownVlan):
            self.client.get_vlan_interfaces(2000)

    def tearDown(self):
        self.janitor.remove_vlan(1000)
        super(GetVlanInterfacesTest, self).tearDown()
