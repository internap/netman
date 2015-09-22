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

from hamcrest import assert_that, equal_to, instance_of, is_, is_not
import mock

from netman.adapters.switches import cisco, brocade, juniper, dell
from netman.core.objects.switch_base import SwitchBase
from netman.adapters.switches.remote import RemoteSwitch
from netman.core.objects.switch_descriptor import SwitchDescriptor
from netman.core.switch_factory import SwitchFactory


class SwitchFactoryTest(unittest.TestCase):

    def setUp(self):
        self.semaphore_mocks = {}
        self.factory = SwitchFactory(switch_source=None, lock_factory=MockLockFactory(self.semaphore_mocks))

    def test_get_connection_to_anonymous_switch(self):
        class FakeCiscoSwitch(SwitchBase):
            pass

        my_semaphore = mock.Mock()
        self.semaphore_mocks['hostname'] = my_semaphore
        expected_switch = FakeCiscoSwitch(SwitchDescriptor(model='some_model', hostname='hello'))
        factory_mock = mock.Mock()
        factory_mock.return_value = expected_switch
        self.factory.factories['some_model'] = factory_mock

        switch = self.factory.get_anonymous_switch(hostname='hostname', model='some_model', username='username',
                                                   password='password', port=22)

        factory_mock.assert_called_with(SwitchDescriptor(hostname='hostname', model='some_model', username='username',
                                                         password='password', port=22), lock=my_semaphore)
        assert_that(switch, is_(expected_switch))

    def test_factories_are_well_wired(self):

        assert_that(self.factory.factories, is_({
            "cisco": cisco.factory,
            "brocade": brocade.factory,
            "juniper": juniper.standard_factory,
            "juniper_qfx_copper": juniper.qfx_copper_factory,
            "dell": dell.factory_ssh,
            "dell_ssh": dell.factory_ssh,
            "dell_telnet": dell.factory_telnet
        }))

    def test_two_get_connections_on_the_same_switch_should_give_the_same_semaphore(self):
        semaphores = []

        self.semaphore_mocks['hostname'] = mock.Mock()

        self.factory.factories['juniper'] = lambda switch_descriptor, lock: semaphores.append(lock)

        self.factory.get_anonymous_switch(hostname='hostname', model='juniper', username='username', password='password', port=22)
        self.factory.get_anonymous_switch(hostname='hostname', model='juniper', username='username', password='password', port=22)

        assert_that(semaphores[0], is_(semaphores[1]))

    def test_two_get_connections_on_different_switches_should_give_different_semaphores(self):
        semaphores = []

        self.semaphore_mocks['hostname1'] = mock.Mock()
        self.semaphore_mocks['hostname2'] = mock.Mock()

        self.factory.factories['juniper'] = lambda switch_descriptor, lock: semaphores.append(lock)

        self.factory.get_anonymous_switch(hostname='hostname1', model='juniper', username='username', password='password', port=22)
        self.factory.get_anonymous_switch(hostname='hostname2', model='juniper', username='username', password='password', port=22)

        assert_that(semaphores[0], is_not(semaphores[1]))

    def test_get_connection_to_anonymous_remote_switch(self):
        switch = self.factory.get_anonymous_switch(hostname='hostname', model='juniper', username='username',
                                                   password='password', port=22,
                                                   netman_server='https://netman.url.example.org:4443')

        assert_that(switch, instance_of(RemoteSwitch))
        assert_that(switch.switch_descriptor.hostname, equal_to("hostname"))
        assert_that(switch.switch_descriptor.model, equal_to("juniper"))
        assert_that(switch.switch_descriptor.username, equal_to("username"))
        assert_that(switch.switch_descriptor.password, equal_to("password"))
        assert_that(switch.switch_descriptor.port, equal_to(22))
        assert_that(switch.switch_descriptor.netman_server, equal_to('https://netman.url.example.org:4443'))

    def test_get_switch_by_descriptor(self):
        class FakeJuniperSwitch(SwitchBase):
            pass
        my_semaphore = mock.Mock()
        self.semaphore_mocks['hello'] = my_semaphore

        expected_switch = FakeJuniperSwitch(SwitchDescriptor(model='juniper', hostname='hello'))
        factory_mock = mock.Mock()
        factory_mock.return_value = expected_switch
        self.factory.factories['juniper'] = factory_mock

        descriptor = SwitchDescriptor(model='juniper', hostname='hello')
        switch = self.factory.get_switch_by_descriptor(descriptor)

        factory_mock.assert_called_with(descriptor, lock=my_semaphore)
        assert_that(switch, is_(expected_switch))


class MockLockFactory(object):

    def __init__(self, mock_dict):
        self.mock_dict = mock_dict

    def new_lock(self, name, timeout=0):
        return self.mock_dict.pop(name)
