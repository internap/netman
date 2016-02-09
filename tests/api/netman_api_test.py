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

from hamcrest import assert_that
from mock import Mock

from netman.adapters.threading_lock_factory import ThreadingLockFactory
from netman.core.switch_factory import SwitchFactory
from pkg_resources import Distribution

from netman.api.netman_api import NetmanApi
from tests.api import matches_fixture
from tests.api.base_api_test import BaseApiTest


class NetmanApiTest(BaseApiTest):
    def test_get_info(self):
        get_distribution_mock = Mock()
        get_distribution_mock.return_value = Distribution(version="1.1.111.dev111111111")

        NetmanApi(SwitchFactory(None, ThreadingLockFactory()),
                  get_distribution_callback=get_distribution_mock).hook_to(self.app)

        data, code = self.get("/netman/info")

        assert_that(data, matches_fixture("get_info.json"))
