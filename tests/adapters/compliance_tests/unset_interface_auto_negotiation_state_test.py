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
from netman.core.objects.interface_states import ON
from tests import has_message
from tests.adapters.compliance_test_case import ComplianceTestCase


class UnsetInterfaceAutoNegotiationStateTest(ComplianceTestCase):
    _dev_sample = "juniper_qfx_copper"

    def test_removes_the_state_completely(self):
        self.try_to.set_interface_auto_negotiation_state(self.test_port, state=ON)

        self.client.unset_interface_auto_negotiation_state(self.test_port)
        interface = self.client.get_interface(self.test_port)

        assert_that(interface.auto_negotiation, is_(None))

    def test_fails_if_the_interface_does_not_exist(self):
        with self.assertRaises(UnknownInterface) as expect:
            self.client.unset_interface_auto_negotiation_state('ge-0/0/128')

        assert_that(expect.exception, has_message("Unknown interface ge-0/0/128"))
