# Copyright 2019 Internap.
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

from hamcrest import assert_that, is_, empty
from netaddr import IPNetwork

from netman.core.objects.exceptions import UnknownIP, BadVlanNumber
from tests.adapters.compliance_test_case import ComplianceTestCase


class RemoveIpFromVlanTest(ComplianceTestCase):
    _dev_sample = "cisco"

    def setUp(self):
        super(RemoveIpFromVlanTest, self).setUp()
        self.try_to.add_vlan(1000, name="some_name")
        self.try_to.add_ip_to_vlan(1000, IPNetwork("10.10.10.2/29"))

    def tearDown(self):
        self.janitor.remove_ip_from_vlan(1000, IPNetwork("10.10.10.2/29"))
        self.janitor.remove_vlan(1000)

        super(RemoveIpFromVlanTest, self).tearDown()

    def test_unassigns(self):
        self.client.remove_ip_from_vlan(1000, IPNetwork("10.10.10.2/29"))
        assert_that(self.client.get_vlan(1000).ips, is_(empty()))

    def test_raise_bad_vlan_number(self):
        with self.assertRaises(BadVlanNumber):
            self.client.remove_ip_from_vlan(0, IPNetwork("10.10.10.2/29"))

    def test_raise_unknown_ip(self):
        with self.assertRaises(UnknownIP):
            self.client.remove_ip_from_vlan(1000, IPNetwork("1.1.1.1/31"))
