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
from hamcrest import assert_that, equal_to

from netman.core.objects.exceptions import UnknownVlan
from tests.adapters.compliance_test_case import ComplianceTestCase


class RemoveVlanTest(ComplianceTestCase):
    _dev_sample = "brocade"

    def setUp(self):
        super(RemoveVlanTest, self).setUp()
        self.client.add_vlan(1000)

    def tearDown(self):
        self.janitor.remove_vlan(1000)
        super(RemoveVlanTest, self).tearDown()

    def test_removes_vlan_from_get_vlan(self):
        self.client.remove_vlan(1000)

        with self.assertRaises(UnknownVlan):
            self.client.get_vlan(1000)

    def test_removes_vlan_raise_when_vlan_is_already_removed(self):
        self.client.remove_vlan(1000)

        with self.assertRaises(UnknownVlan):
            self.client.remove_vlan(1000)

    def test_removes_vlan_is_removed_from_list(self):
        vlan_count = len(self.client.get_vlans())
        self.client.remove_vlan(1000)

        assert_that(len(self.client.get_vlans()), equal_to(vlan_count - 1))
