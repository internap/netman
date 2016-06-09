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

from hamcrest import assert_that, greater_than
from tests.adapters.compliance_test_case import ComplianceTestCase


class GetVersionsTest(ComplianceTestCase):
    _dev_sample = "cisco"

    def test_returns_a_dictionary_of_various_hardware_and_software_versions(self):
        versions = self.client.get_versions()

        assert_that(isinstance(versions, dict))
        assert_that(len(versions), greater_than(0))
