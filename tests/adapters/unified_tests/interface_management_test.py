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

from hamcrest import assert_that, equal_to

from tests.adapters.unified_tests.configured_test_case import ConfiguredTestCase, skip_on_switches


class InterfaceManagementTest(ConfiguredTestCase):
    __test__ = False

    @skip_on_switches("juniper", "juniper_qfx_copper")
    def test_shutdown_interface(self):
        response = self.put("/switches/{switch}/interfaces/{port}/shutdown", raw_data='true')
        assert_that(response.status_code, equal_to(204))

    @skip_on_switches("juniper", "juniper_qfx_copper")
    def test_openup_interface(self):
        response = self.put("/switches/{switch}/interfaces/{port}/shutdown", raw_data='false')
        assert_that(response.status_code, equal_to(204))

    @skip_on_switches("cisco", "brocade")
    def test_edit_spanning_tree(self):
        response = self.put("/switches/{switch}/interfaces/{port}/spanning-tree", data={"edge": True})
        assert_that(response.status_code, equal_to(204))

    @skip_on_switches("cisco", "brocade")
    def test_enable_lldp(self):
        response = self.put("/switches/{switch}/interfaces/{port}/lldp", raw_data='true')
        assert_that(response.status_code, equal_to(204))

    @skip_on_switches("cisco", "brocade")
    def test_disable_lldp(self):
        response = self.put("/switches/{switch}/interfaces/{port}/lldp", raw_data='false')
        assert_that(response.status_code, equal_to(204))
