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

from flexmock import flexmock, flexmock_teardown
from hamcrest import assert_that, is_

from netman.core.objects.exceptions import NetmanException
from netman.core.objects.switch_base import SwitchBase
from netman.core.objects.switch_descriptor import SwitchDescriptor


class SwitchBaseTest(TestCase):

    def setUp(self):
        self.switch = flexmock(SwitchBase(SwitchDescriptor("cisco", "myswitch")))

    def tearDown(self):
        flexmock_teardown()

    def test_connecting_sets_an_internal_flag(self):
        self.switch.should_receive("_connect").once()

        self.switch.connect()

        assert_that(self.switch.connected, is_(True))

    def test_connection_failed_leaves_the_flag_off_and_raises(self):
        self.switch.should_receive("_connect").once().and_raise(NetmanException())

        with self.assertRaises(NetmanException):
            self.switch.connect()

        assert_that(self.switch.connected, is_(False))

    def test_disconnecting_unsets_an_internal_flag(self):
        self.switch.connected = True

        self.switch.should_receive("_disconnect").once()

        self.switch.disconnect()

        assert_that(self.switch.connected, is_(False))

    def test_disconnection_failed_leaves_the_flag_on_and_raises(self):
        self.switch.connected = True

        self.switch.should_receive("_disconnect").once().and_raise(NetmanException())

        with self.assertRaises(NetmanException):
            self.switch.disconnect()

        assert_that(self.switch.connected, is_(True))

    def test_start_transaction_sets_an_internal_flag(self):
        self.switch.should_receive("_start_transaction").once()

        self.switch.start_transaction()

        assert_that(self.switch.in_transaction, is_(True))

    def test_starting_transaction_failed_leaves_the_flag_off_and_raises(self):
        self.switch.should_receive("_start_transaction").once().and_raise(NetmanException())

        with self.assertRaises(NetmanException):
            self.switch.start_transaction()

        assert_that(self.switch.in_transaction, is_(False))

    def test_end_transaction_unsets_an_internal_flag(self):
        self.switch.in_transaction = True

        self.switch.should_receive("_end_transaction").once()

        self.switch.end_transaction()

        assert_that(self.switch.in_transaction, is_(False))

    def test_ending_transaction_failed_leaves_the_flag_on_and_raises(self):
        self.switch.in_transaction = True

        self.switch.should_receive("_end_transaction").once().and_raise(NetmanException())

        with self.assertRaises(NetmanException):
            self.switch.end_transaction()

        assert_that(self.switch.in_transaction, is_(True))
