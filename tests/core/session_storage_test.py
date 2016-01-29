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
from hamcrest import assert_that, is_, none
from netman.adapters.memory_session_storage import MemorySessionStorage
from netman.core.objects.exceptions import SessionAlreadyExists, UnknownSession
import mock


class SessionStorageTest(TestCase):
    def setUp(self):
        self.session_source = MemorySessionStorage()
        self.switch_descriptor = mock.Mock()

    def test_add_session(self):
        self.session_source.add('some_session', self.switch_descriptor)
        assert_that(self.session_source.get('some_session'),
                    is_(self.switch_descriptor))

    def test_get_session(self):
        self.session_source.add('some_session', self.switch_descriptor)
        assert_that(self.session_source.get('some_session'), is_(self.switch_descriptor))

    def test_get_nonexistent_session_is_none(self):
        assert_that(self.session_source.get('nonexistent_session'), is_(none()))

    def test_remove_session(self):
        self.session_source.add('some_session', self.switch_descriptor)
        self.session_source.remove('some_session')
        assert_that(self.session_source.get('some_session'), is_(none()))

    def test_add_session_that_already_exists_fails(self):
        self.session_source.add('some_session', self.switch_descriptor)
        with self.assertRaises(SessionAlreadyExists):
            self.session_source.add('some_session', self.switch_descriptor)

    def test_remove_nonexistent_session_fails(self):
        self.session_source.add('other_session', self.switch_descriptor)
        with self.assertRaises(UnknownSession):
            self.session_source.remove('some_session')
