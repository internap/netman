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
from tests.adapters.configured_test_case import ConfiguredTestCase


class GetInterfaceTest(ConfiguredTestCase):
    _dev_sample = "juniper"

    def test_returns_an_interface(self):
        interface = self.client.get_interface(self.test_ports[0].name)
        assert_that(interface.name, is_(self.test_ports[0].name))

    def test_fails_when_nonexistent_interface(self):
        with self.assertRaises(UnknownInterface):
            self.client.get_interface('ethernet 1/nonexistent2000')

    def tearDown(self):
        super(GetInterfaceTest, self).tearDown()
