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
from hamcrest import assert_that, is_
from netman.adapters.memory_session_storage import MemorySessionStorage
from netman.core.objects.exceptions import SessionAlreadyExists
import mock


class SessionStorageTest(TestCase):
    def setUp(self):
        self.session_source = MemorySessionStorage()
        self.switch = mock.Mock()

    def test_add_session(self):
        self.session_source.add_session(self.switch, 'some_session')
        assert_that(self.session_source.sessions['some_session'], is_(self.switch))

    def test_get_session(self):
        self.session_source.sessions['some_session'] = self.switch
        assert_that(self.session_source.get_session('some_session'), is_(self.switch))

    def test_get_nonexistent_session_is_none(self):
        assert_that(self.session_source.get_session('nonexistent_session'), is_(None))

    def test_remove_session(self):
        self.session_source.sessions['some_session'] = self.switch
        self.session_source.remove_session('some_session')
        assert_that(self.session_source.sessions.get('some_session'), is_(None))

    def test_add_session_that_already_exists_fails(self):
        self.session_source.add_session(self.switch, 'some_session')
        with self.assertRaises(SessionAlreadyExists):
            self.session_source.add_session(self.switch, 'some_session')


