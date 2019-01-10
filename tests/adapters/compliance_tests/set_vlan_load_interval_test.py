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


from hamcrest import assert_that, is_, contains_string

from netman.core.objects.exceptions import BadLoadIntervalNumber, UnknownVlan
from tests import has_message
from tests.adapters.compliance_test_case import ComplianceTestCase


class SetVlanLoadIntervalTest(ComplianceTestCase):
    _dev_sample = "arista_http"

    def test_sets_load_interval_for_the_vlan(self):
        self.client.add_vlan(1000)

        self.client.set_vlan_load_interval(1000, 30)

        vlan = self.client.get_vlan(1000)
        assert_that(vlan.load_interval, is_(30))

    def test_fails_if_the_value_is_not_within_the_supported_range(self):
        self.client.add_vlan(1000)

        with self.assertRaises(BadLoadIntervalNumber) as expect:
            self.client.set_vlan_load_interval(1000, 800)

        assert_that(str(expect.exception), contains_string("Load interval number is invalid"))

    def test_fails_if_the_vlan_does_not_exist(self):
        with self.assertRaises(UnknownVlan) as expect:
            self.client.set_vlan_load_interval(1000, 30)

        assert_that(expect.exception, has_message("Vlan 1000 not found"))

    def tearDown(self):
        self.janitor.remove_vlan(1000)
        super(SetVlanLoadIntervalTest, self).tearDown()
