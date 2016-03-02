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

from hamcrest import assert_that, is_
from netman.core.objects.exceptions import UnknownInterface

from tests.adapters.configured_test_case import ConfiguredTestCase


class UnsetInterfaceStateTest(ConfiguredTestCase):
    _dev_sample = "juniper"

    def test_unsetting_an_interface(self):
        self.try_to.unset_interface_state(self.test_ports[0].name)
        self.try_to.unset_interface_state(self.test_ports[1].name)

        interface_1 = self.client.get_interface(self.test_ports[0].name)
        interface_2 = self.client.get_interface(self.test_ports[1].name)

        assert_that(self.test_ports[0].name, is_(interface_1.name))
        assert_that(self.test_ports[1].name, is_(interface_2.name))
        assert_that(interface_1.shutdown, is_(interface_2.shutdown))

    def test_fails_with_unknown_interface(self):
        with self.assertRaises(UnknownInterface):
            self.client.unset_interface_state('ethernet 1/nonexistent2000')

    def tearDown(self):
        super(UnsetInterfaceStateTest, self).tearDown()
