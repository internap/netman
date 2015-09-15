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
import mock

from netman.core.objects.exceptions import UnknownResource, \
    OperationNotCompleted, NetmanException, SessionAlreadyExists
from netman.core.switch_sessions import SwitchSessionManager


class SwitchSessionManagerTest(TestCase):
    def setUp(self):
        self.switch_mock = flexmock()
        self.session_manager = SwitchSessionManager()

    def tearDown(self):
        for timer in self.session_manager.timers.values():
            timer.cancel()

    def test_open_session_generates_with_passed_session_id(self):
        self.switch_mock.should_receive('connect').once().ordered()
        self.switch_mock.should_receive('start_transaction').once().ordered()
        self.switch_mock.should_receive('disconnect').never()

        assert_that(self.session_manager.open_session(self.switch_mock, 'patate'), is_('patate'))
        assert_that(self.session_manager.get_switch_for_session('patate'), is_(self.switch_mock))

    def test_open_session_with_session_that_already_exists_raises_an_exception(self):

        self.switch_mock.should_receive('connect').never()
        self.switch_mock.should_receive('start_transaction').never()
        self.switch_mock.should_receive('disconnect').never()

        self.session_manager.sessions['i_already_exist_buddy'] = 'stuff'

        with self.assertRaises(SessionAlreadyExists):
            self.session_manager.open_session(self.switch_mock, 'i_already_exist_buddy')

    def test_open_failing_session_closes_connection(self):
        self.switch_mock.should_receive('connect').once().ordered()
        self.switch_mock.should_receive('start_transaction').once().ordered().and_raise(NetmanException())
        self.switch_mock.should_receive('disconnect').once().ordered()

        with self.assertRaises(NetmanException):
            self.session_manager.open_session(self.switch_mock, 'patate')

    def test_close_session(self):

        self.switch_mock.should_receive('connect').once().ordered()
        self.switch_mock.should_receive('start_transaction').once().ordered()

        assert_that(self.session_manager.open_session(self.switch_mock, 'patate'), is_('patate'))
        assert_that(self.session_manager.get_switch_for_session('patate'), is_(self.switch_mock))

        self.switch_mock.should_receive('end_transaction').once().ordered()
        self.switch_mock.should_receive('disconnect').once().ordered()

        self.session_manager.close_session('patate')

        with self.assertRaises(UnknownResource):
            self.session_manager.get_switch_for_session('patate')

    def test_session_should_close_itself_after_timeout(self):
        self.session_manager.session_inactivity_timeout = 0.5

        switch_mock = mock.Mock()

        assert_that(self.session_manager.open_session(switch_mock, 'patate'), is_('patate'))
        assert_that(self.session_manager.get_switch_for_session('patate'), is_(switch_mock))

        switch_mock.connect.assert_called_with()
        switch_mock.start_transaction.assert_called_with()

        time.sleep(0.6)

        switch_mock.rollback_transaction.assert_called_with()
        switch_mock.end_transaction.assert_called_with()
        switch_mock.disconnect.assert_called_with()

        with self.assertRaises(UnknownResource):
            self.session_manager.get_switch_for_session('patate')

    def test_session_timeout_should_reset_on_activity(self):
        self.session_manager.session_inactivity_timeout = 1

        switch_mock = mock.Mock()

        assert_that(self.session_manager.open_session(switch_mock, 'patate'), is_('patate'))
        assert_that(self.session_manager.get_switch_for_session('patate'), is_(switch_mock))

        switch_mock.connect.assert_called_with()
        switch_mock.start_transaction.assert_called_with()

        time.sleep(0.5)

        self.session_manager.keep_alive('patate')

        time.sleep(0.5)

        assert_that(switch_mock.rollback_transaction.called, is_(False))
        assert_that(switch_mock.end_transaction.called, is_(False))
        assert_that(switch_mock.disconnect.called, is_(False))

        self.session_manager.keep_alive('patate')

        time.sleep(1.1)

        switch_mock.rollback_transaction.assert_called_with()
        switch_mock.end_transaction.assert_called_with()
        switch_mock.disconnect.assert_called_with()

        with self.assertRaises(UnknownResource):
            self.session_manager.get_switch_for_session('patate')

    def test_commit_session(self):
        self.session_manager.keep_alive = mock.Mock()

        self.switch_mock.should_receive('connect').once().ordered()
        self.switch_mock.should_receive('start_transaction').once().ordered()

        session_id = self.session_manager.open_session(self.switch_mock, 'patate')

        self.switch_mock.should_receive('commit_transaction').once().ordered()

        self.assertEquals(session_id, 'patate')

        self.session_manager.commit_session(session_id)

        self.session_manager.keep_alive.assert_called_with(session_id)

    def test_rollback_session(self):
        self.session_manager.keep_alive = mock.Mock()

        self.switch_mock.should_receive('connect').once().ordered()
        self.switch_mock.should_receive('start_transaction').once().ordered()

        session_id = self.session_manager.open_session(self.switch_mock, 'patate')

        self.assertEquals(session_id, 'patate')

        self.switch_mock.should_receive('rollback_transaction').once().ordered()

        self.session_manager.rollback_session(session_id)

        self.session_manager.keep_alive.assert_called_with(session_id)

    def test_unknown_session(self):
        with self.assertRaises(UnknownResource):
            self.session_manager.get_switch_for_session('patate')

    def test_close_session_with_error(self):

        self.switch_mock.should_receive('connect').once().ordered()
        self.switch_mock.should_receive('start_transaction').once().ordered()

        self.session_manager.open_session(self.switch_mock, 'patate')

        self.switch_mock.should_receive('end_transaction').and_raise(OperationNotCompleted()).once().ordered()
        self.switch_mock.should_receive('disconnect').once().ordered()

        with self.assertRaises(OperationNotCompleted):
            self.session_manager.close_session('patate')

        with self.assertRaises(UnknownResource):
            self.session_manager.get_switch_for_session('patate')
