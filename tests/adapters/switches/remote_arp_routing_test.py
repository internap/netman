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

import unittest

from flexmock import flexmock, flexmock_teardown

from netman.adapters.switches.remote import RemoteSwitch
from netman.core.objects.interface_states import OFF, ON
from netman.core.objects.switch_descriptor import SwitchDescriptor
from tests.adapters.switches.remote_test import Reply


class RemoteSwitchARPRoutingTest(unittest.TestCase):
    netman_url = 'http://netman.example.org:1234'

    def setUp(self):
        self.switch = RemoteSwitch(SwitchDescriptor(
            model="juniper", hostname="toto", username="tutu",
            password="titi", port=1234, netman_server=self.netman_url))

        self.requests_mock = flexmock()
        self.switch.requests = self.requests_mock
        self.headers = {
            'Netman-Port': "1234",
            'Netman-Model': 'juniper',
            'Netman-Password': 'titi',
            'Netman-Username': 'tutu',
            'Netman-Max-Version': "2",
            'Netman-Verbose-Errors': 'yes',
        }

    def tearDown(self):
        flexmock_teardown()

    def test_set_vlan_arp_routing_state_OFF_should_send_false(self):
        self.requests_mock.should_receive("put").once().with_args(
            url=self.netman_url+'/switches/toto/vlans/2000/arp-routing',
            headers=self.headers,
            data='false'
        ).and_return(
            Reply(
                content='',
                status_code=204))

        self.switch.set_vlan_arp_routing_state(2000, OFF)

    def test_set_vlan_arp_routing_state_ON_should_send_true(self):
        self.requests_mock.should_receive("put").once().with_args(
            url=self.netman_url+'/switches/toto/vlans/2000/arp-routing',
            headers=self.headers,
            data='true'
        ).and_return(
            Reply(
                content='',
                status_code=204))

        self.switch.set_vlan_arp_routing_state(2000, ON)
