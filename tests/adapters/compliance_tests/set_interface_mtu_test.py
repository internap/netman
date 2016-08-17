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


from hamcrest import assert_that, is_, contains_string

from netman.core.objects.exceptions import UnknownInterface, InvalidMtuSize
from tests import has_message
from tests.adapters.compliance_test_case import ComplianceTestCase


class SetInterfaceMtuTest(ComplianceTestCase):
    _dev_sample = "juniper"

    def test_sets_the_mtu_for_the_interface(self):
        self.client.set_interface_mtu(self.test_port, 5000)
        interface = self.client.get_interface(self.test_port)

        assert_that(interface.mtu, is_(5000))

    def test_fails_if_the_value_is_not_within_the_supported_range(self):
        with self.assertRaises(InvalidMtuSize) as expect:
            self.client.set_interface_mtu(self.test_port, 1)

        assert_that(str(expect.exception), contains_string("MTU value is invalid"))

    def test_fails_if_the_interface_does_not_exist(self):
        with self.assertRaises(UnknownInterface) as expect:
            self.client.set_interface_mtu('ge-0/0/128', 5000)

        assert_that(expect.exception, has_message("Unknown interface ge-0/0/128"))

    def tearDown(self):
        self.janitor.unset_interface_mtu(self.test_port)
        super(SetInterfaceMtuTest, self).tearDown()
