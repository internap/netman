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
from netman.core.objects.interface_states import ON, OFF
from tests import has_message
from tests.adapters.compliance_test_case import ComplianceTestCase


class SetInterfaceStateTest(ComplianceTestCase):
    _dev_sample = "juniper"

    def test_can_open_an_interface(self):
        self.client.set_interface_state(self.test_port, state=ON)
        interface = self.client.get_interface(self.test_port)

        assert_that(interface.shutdown, is_(False))

    def test_can_shutdown_an_interface(self):
        self.client.set_interface_state(self.test_port, state=OFF)
        interface = self.client.get_interface(self.test_port)

        assert_that(interface.shutdown, is_(True))

    def test_fails_if_the_interface_does_not_exist(self):
        with self.assertRaises(UnknownInterface) as expect:
            self.client.set_interface_state('ge-0/0/128', state=ON)

        assert_that(expect.exception, has_message("Unknown interface ge-0/0/128"))

    def test_set_an_interface_twice_works(self):
        self.try_to.set_interface_state(self.test_port, ON)
        self.try_to.set_interface_state(self.test_port, ON)

        self.try_to.set_interface_state(self.test_port, OFF)
        self.try_to.set_interface_state(self.test_port, OFF)

    def tearDown(self):
        self.janitor.unset_interface_state(self.test_port)
        super(SetInterfaceStateTest, self).tearDown()
