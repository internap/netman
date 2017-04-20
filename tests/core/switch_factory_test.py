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

import unittest

from hamcrest import assert_that, instance_of, is_, is_not
import mock
from netman.core.objects.flow_control_switch import FlowControlSwitch

from netman.core import switch_factory

from netman.core.objects.switch_base import SwitchBase
from netman.adapters.switches.remote import RemoteSwitch
from netman.core.objects.switch_descriptor import SwitchDescriptor
from netman.core.switch_factory import SwitchFactory


class SwitchFactoryTest(unittest.TestCase):

    def setUp(self):
        self.semaphore_mocks = {}
        self.factory = SwitchFactory(switch_source=None, lock_factory=MockLockFactory(self.semaphore_mocks))

        switch_factory.factories['test_model'] = _FakeSwitch

    def tearDown(self):
        switch_factory.factories.pop('test_model')

    def test_get_connection_to_anonymous_switch(self):
        my_semaphore = mock.Mock()
        self.semaphore_mocks['hostname'] = my_semaphore

        switch = self.factory.get_anonymous_switch(hostname='hostname', model='test_model', username='username',
                                                   password='password', port=22)

        assert_that(switch, is_(instance_of(FlowControlSwitch)))
        assert_that(switch.wrapped_switch, is_(instance_of(_FakeSwitch)))
        assert_that(switch.lock, is_(my_semaphore))
        assert_that(switch.wrapped_switch.switch_descriptor, is_(
                SwitchDescriptor(hostname='hostname', model='test_model', username='username',
                                 password='password', port=22)))

    def test_two_get_connections_on_the_same_switch_should_give_the_same_semaphore(self):
        self.semaphore_mocks['hostname'] = mock.Mock()

        switch1 = self.factory.get_anonymous_switch(hostname='hostname', model='test_model')
        switch2 = self.factory.get_anonymous_switch(hostname='hostname', model='test_model')

        assert_that(switch1.lock, is_(switch2.lock))

    def test_two_get_connections_on_different_switches_should_give_different_semaphores(self):
        self.semaphore_mocks['hostname1'] = mock.Mock()
        self.semaphore_mocks['hostname2'] = mock.Mock()

        switch1 = self.factory.get_anonymous_switch(hostname='hostname1', model='test_model')
        switch2 = self.factory.get_anonymous_switch(hostname='hostname2', model='test_model')

        assert_that(switch1.lock, is_not(switch2.lock))

    def test_get_connection_to_anonymous_remote_switch(self):
        my_semaphore = mock.Mock()
        self.semaphore_mocks['hostname'] = my_semaphore
        switch = self.factory.get_anonymous_switch(hostname='hostname', model='test_model', username='username',
                                                   password='password', port=22,
                                                   netman_server='https://netman.url.example.org:4443')

        assert_that(switch, is_(instance_of(FlowControlSwitch)))
        assert_that(switch.wrapped_switch, is_(instance_of(RemoteSwitch)))
        assert_that(switch.lock, is_(my_semaphore))
        assert_that(switch.wrapped_switch.switch_descriptor, is_(
                SwitchDescriptor(hostname='hostname', model='test_model', username='username',
                                 password='password', port=22,
                                 netman_server='https://netman.url.example.org:4443')))

    def test_get_switch_by_descriptor(self):
        my_semaphore = mock.Mock()
        self.semaphore_mocks['hostname'] = my_semaphore

        switch = self.factory.get_switch_by_descriptor(SwitchDescriptor(model='test_model', hostname='hostname'))

        assert_that(switch, is_(instance_of(FlowControlSwitch)))
        assert_that(switch.wrapped_switch, is_(instance_of(_FakeSwitch)))
        assert_that(switch.lock, is_(my_semaphore))
        assert_that(switch.wrapped_switch.switch_descriptor,
                    is_(SwitchDescriptor(model='test_model', hostname='hostname')))


class MockLockFactory(object):

    def __init__(self, mock_dict):
        self.mock_dict = mock_dict

    def new_lock(self, name, timeout=0):
        return self.mock_dict.pop(name)


class _FakeSwitch(SwitchBase):
    pass
