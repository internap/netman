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

from hamcrest import assert_that, is_
from netaddr import IPNetwork

from netman.core.objects.exceptions import IPAlreadySet, IPNotAvailable
from tests import has_message
from tests.adapters.compliance_test_case import ComplianceTestCase


class AddIpToVlanTest(ComplianceTestCase):
    _dev_sample = "cisco"

    def setUp(self):
        super(AddIpToVlanTest, self).setUp()
        self.client.add_vlan(1000, name="vlan_name")

    def tearDown(self):
        self.janitor.remove_vlan(1000)
        self.janitor.remove_vlan(2000)
        super(AddIpToVlanTest, self).tearDown()

    def test_add_ip_to_vlan(self):
        self.client.add_ip_to_vlan(1000, IPNetwork("10.10.10.2/29"))

        assert_that(self.client.get_vlan(1000).ips[0], is_(IPNetwork("10.10.10.2/29")))
        assert_that(self.client.get_vlan(1000).icmp_redirects, is_(True))

    def test_add_two_ip_to_vlan_put_no_redirects(self):
        self.client.add_ip_to_vlan(1000, IPNetwork("10.10.10.2/29"))
        self.client.add_ip_to_vlan(1000, IPNetwork("10.10.11.2/29"))

        assert_that(self.client.get_vlan(1000).ips[0], is_(IPNetwork("10.10.10.2/29")))
        assert_that(self.client.get_vlan(1000).ips[1], is_(IPNetwork("10.10.11.2/29")))
        assert_that(self.client.get_vlan(1000).icmp_redirects, is_(False))

    def test_add_ip_to_vlan_raise_IPAlreadySet(self):
        ip = "10.10.10.2/29"
        self.client.add_ip_to_vlan(1000, IPNetwork(ip))

        with self.assertRaises(IPAlreadySet) as expect:
            self.client.add_ip_to_vlan(1000, IPNetwork(ip))

        assert_that(expect.exception, has_message("IP {0} is already present in this vlan as {0}".format(ip)))

    def test_add_ip_to_vlan_raise_IPNotAvailable(self):
        self.client.add_vlan(2000, name="vlan_name2")
        ip = "10.10.10.2/29"
        self.client.add_ip_to_vlan(2000, IPNetwork(ip))

        with self.assertRaises(IPNotAvailable) as expect:
            self.client.add_ip_to_vlan(1000, IPNetwork(ip))

        assert_that(
            expect.exception, has_message(
                "IP {} is not available in this vlan: % {} overlaps with secondary address on Vlan{}".format(
                    ip, "10.10.10.0", 2000
                )
            )
        )
