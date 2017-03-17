# Copyright 2017 Internap.
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

from flexmock import flexmock, flexmock_teardown
from hamcrest import assert_that, equal_to

from netman.api.api_utils import RegexConverter
from netman.api.switch_api import SwitchApi
from netman.api.switch_session_api import SwitchSessionApi
from netman.core.objects.exceptions import UnknownSession
from netman.core.objects.interface_states import ON, OFF
from tests.api.base_api_test import BaseApiTest


class SwitchApiARPRoutingTest(BaseApiTest):
    def setUp(self):
        super(SwitchApiARPRoutingTest, self).setUp()
        self.app.url_map.converters['regex'] = RegexConverter

        self.switch_factory = flexmock()
        self.switch_mock = flexmock()
        self.session_manager = flexmock()

        self.session_manager.should_receive("get_switch_for_session").and_raise(UnknownSession("patate"))

        SwitchApi(self.switch_factory, self.session_manager).hook_to(self.app)
        SwitchSessionApi(self.switch_factory, self.session_manager).hook_to(self.app)

    def tearDown(self):
        flexmock_teardown()

    def test_enable_arp_routing(self):
        self.switch_factory.should_receive('get_switch').with_args('my.switch').and_return(self.switch_mock).once().ordered()
        self.switch_mock.should_receive('connect').once().ordered()
        self.switch_mock.should_receive('set_vlan_arp_routing_state').with_args(2500, ON).once().ordered()
        self.switch_mock.should_receive('disconnect').once().ordered()

        result, code = self.put("/switches/my.switch/vlans/2500/arp-routing", raw_data='true')

        assert_that(code, equal_to(204))

    def test_disable_arp_routing(self):
        self.switch_factory.should_receive('get_switch').with_args('my.switch').and_return(self.switch_mock).once().ordered()
        self.switch_mock.should_receive('connect').once().ordered()
        self.switch_mock.should_receive('set_vlan_arp_routing_state').with_args(2500, OFF).once().ordered()
        self.switch_mock.should_receive('disconnect').once().ordered()

        result, code = self.put("/switches/my.switch/vlans/2500/arp-routing", raw_data='false')

        assert_that(code, equal_to(204))

    def test_arp_routing_invalid_argument(self):
        self.switch_factory.should_receive('get_switch').with_args('my.switch').and_return(self.switch_mock).never()
        self.switch_mock.should_receive('connect').never()
        self.switch_mock.should_receive('set_vlan_arp_routing_state').never()
        self.switch_mock.should_receive('disconnect').never()

        result, code = self.put("/switches/my.switch/vlans/2500/arp-routing", raw_data='invalid')

        assert_that(code, equal_to(400))
        assert_that(result, equal_to({'error': 'Unreadable content "invalid". Should be either "true" or "false"'}))
