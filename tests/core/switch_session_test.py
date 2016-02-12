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

from unittest import TestCase
import time

from flexmock import flexmock
from hamcrest import assert_that, is_
from mock import Mock
from netman.core.objects.exceptions import UnknownResource, \
    NetmanException, SessionAlreadyExists
from netman.core.objects.switch_descriptor import SwitchDescriptor
from netman.core.switch_sessions import SwitchSessionManager


class SwitchSessionManagerTest(TestCase):
    def setUp(self):
        self.switch_mock = flexmock()
        self.switch_mock.switch_descriptor = SwitchDescriptor('dell', "a_host")
        self.session_manager = SwitchSessionManager()

    def tearDown(self):
        for timer in self.session_manager.timers.values():
            timer.cancel()

    def test_open_session_generates_with_passed_session_id(self):
        self.session_manager.session_storage = flexmock()
        self.session_manager.session_storage.should_receive('add').with_args(
            'patate', self.switch_mock.switch_descriptor
        ).once()
        self.switch_mock.should_receive('connect').once()

        assert_that(self.session_manager.open_session(self.switch_mock, 'patate'), is_('patate'))
        assert_that(self.session_manager.get_switch_for_session('patate'), is_(self.switch_mock))

    def test_open_session_with_session_that_already_exists_raises_an_exception(self):
        self.session_manager.session_storage = flexmock()
        self.session_manager.session_storage.should_receive('add').with_args(
            'patate', self.switch_mock.switch_descriptor
        ).once()
        self.switch_mock.should_receive('connect').once()

        self.session_manager.open_session(self.switch_mock, 'patate')

        with self.assertRaises(SessionAlreadyExists):
            self.session_manager.open_session(self.switch_mock, 'patate')

    def test_close_session(self):
        self.session_manager.session_storage = flexmock()
        self.session_manager.session_storage.should_receive('add').with_args(
            'patate', self.switch_mock.switch_descriptor
        ).once()
        self.switch_mock.should_receive('connect').once()

        assert_that(self.session_manager.open_session(self.switch_mock, 'patate'), is_('patate'))
        assert_that(self.session_manager.get_switch_for_session('patate'), is_(self.switch_mock))

        self.switch_mock.should_receive('disconnect').once()
        self.session_manager.session_storage.should_receive('remove').with_args('patate')

        self.session_manager.close_session('patate')

        with self.assertRaises(UnknownResource):
            self.session_manager.get_switch_for_session('patate')

    def test_close_session_catches_exception_if_remote_remove_fails(self):
        self.session_manager.session_storage = flexmock()

        self.session_manager.session_storage.should_receive('add').with_args(
            'patate', self.switch_mock.switch_descriptor
        ).once().ordered()
        self.switch_mock.should_receive('connect').once()

        self.session_manager.open_session(self.switch_mock, 'patate')

        self.switch_mock.should_receive('disconnect').once()
        self.session_manager.session_storage.should_receive('remove').with_args('patate').and_raise(NetmanException)

        self.session_manager.close_session('patate')

    def test_session_should_close_itself_after_timeout(self):
        self.session_manager.session_inactivity_timeout = 0.01

        switch_mock = Mock()

        assert_that(self.session_manager.open_session(switch_mock, 'patate'), is_('patate'))
        assert_that(self.session_manager.get_switch_for_session('patate'), is_(switch_mock))

        time.sleep(0.02)

        assert_that(switch_mock.rollback_transaction.called, is_(False))

        with self.assertRaises(UnknownResource):
            self.session_manager.get_switch_for_session('patate')

    def test_session_timeout_should_reset_on_activity(self):
        self.session_manager.session_inactivity_timeout = 0.1

        switch_mock = Mock()

        assert_that(self.session_manager.open_session(switch_mock, 'patate'), is_('patate'))
        assert_that(self.session_manager.get_switch_for_session('patate'), is_(switch_mock))

        time.sleep(0.05)

        self.session_manager.keep_alive('patate')

        time.sleep(0.05)

        assert_that(switch_mock.rollback_transaction.called, is_(False))

        self.session_manager.keep_alive('patate')

        time.sleep(0.11)

        assert_that(switch_mock.rollback_transaction.called, is_(False))

        with self.assertRaises(UnknownResource):
            self.session_manager.get_switch_for_session('patate')

    def test_commit_transaction(self):
        self.session_manager.keep_alive = Mock()
        self.session_manager.session_storage = flexmock()

        self.session_manager.session_storage.should_receive('add').with_args(
            'patate', self.switch_mock.switch_descriptor
        ).once()
        self.switch_mock.should_receive('connect').once().ordered()

        session_id = self.session_manager.open_session(self.switch_mock, 'patate')

        self.switch_mock.should_receive('commit_transaction').once().ordered()

        self.assertEquals(session_id, 'patate')

        self.session_manager.commit_session(session_id)

        self.session_manager.keep_alive.assert_called_with(session_id)

    def test_rollback_session(self):
        self.session_manager.keep_alive = Mock()
        self.session_manager.session_storage = flexmock()

        self.session_manager.session_storage.should_receive('add').with_args(
            'patate', self.switch_mock.switch_descriptor
        ).once()
        self.switch_mock.should_receive('connect').once()

        session_id = self.session_manager.open_session(self.switch_mock, 'patate')

        self.assertEquals(session_id, 'patate')

        self.switch_mock.should_receive('rollback_transaction').once().ordered()

        self.session_manager.rollback_session(session_id)

        self.session_manager.keep_alive.assert_called_with(session_id)

    def test_unknown_session(self):
        with self.assertRaises(UnknownResource):
            self.session_manager.get_switch_for_session('patate')

    def test_add_session_catches_exception_if_remote_add_fails(self):
        self.session_manager.session_storage = flexmock()
        self.session_manager.session_storage.should_receive('add').with_args(
            'patate', self.switch_mock.switch_descriptor
        ).and_raise(NetmanException)
        self.switch_mock.should_receive('connect').once().ordered()

        self.session_manager.open_session(self.switch_mock, 'patate')

    def test_start_transaction(self):
        self.session_manager.keep_alive = Mock()
        self.session_manager.session_storage = flexmock()

        self.session_manager.session_storage.should_receive('add').with_args(
            'patate', self.switch_mock.switch_descriptor
        ).once()
        self.switch_mock.should_receive('connect').once().ordered()

        session_id = self.session_manager.open_session(self.switch_mock, 'patate')

        self.switch_mock.should_receive('start_transaction').once().ordered()

        self.assertEquals(session_id, 'patate')

        self.session_manager.start_transaction(session_id)

        self.session_manager.keep_alive.assert_called_with(session_id)

    def test_end_transaction(self):
        self.session_manager.keep_alive = Mock()
        self.session_manager.session_storage = flexmock()

        self.session_manager.session_storage.should_receive('add').with_args(
            'patate', self.switch_mock.switch_descriptor
        ).once()
        self.switch_mock.should_receive('connect').once().ordered()

        session_id = self.session_manager.open_session(self.switch_mock, 'patate')

        self.switch_mock.should_receive('end_transaction').once().ordered()

        self.assertEquals(session_id, 'patate')

        self.session_manager.end_transaction(session_id)

        self.session_manager.keep_alive.assert_called_with(session_id)
