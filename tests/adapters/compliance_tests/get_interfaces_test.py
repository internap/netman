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
from fake_switches.switch_configuration import AggregatedPort
from hamcrest import assert_that, is_
from netaddr import IPNetwork

from tests.adapters.compliance_test_case import ComplianceTestCase


class GetInterfacesTest(ComplianceTestCase):
    _dev_sample = "juniper"

    def test_lists_all_physical_interfaces(self):

        interfaces = self.client.get_interfaces()

        assert_that([i.name for i in interfaces], is_(self._all_physical_test_ports()))

    def test_does_not_list_bonds(self):
        self.try_to.add_bond(1)

        interfaces = self.client.get_interfaces()

        assert_that([i.name for i in interfaces], is_(self._all_physical_test_ports()))

    def _all_physical_test_ports(self):
        return [p.name for p in self.test_ports if not isinstance(p, AggregatedPort)]

    def test_does_not_list_interface_vlans(self):
        self.client.add_vlan(1000)
        self.try_to.add_ip_to_vlan(1000, IPNetwork("1.1.1.1/27"))

        interfaces = self.client.get_interfaces()

        assert_that([i.name for i in interfaces], is_(self._all_physical_test_ports()))

    def tearDown(self):
        self.janitor.remove_bond(1)
        self.janitor.remove_vlan(1000)
        super(GetInterfacesTest, self).tearDown()
