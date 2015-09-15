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

from flexmock import flexmock
from hamcrest import assert_that, is_

from netman.core.objects.exceptions import NetmanException
from netman.core.objects.switch_descriptor import SwitchDescriptor
from netman.core.objects.switch_transactional import transactional, \
    SwitchTransactional


class SwitchTransactionalTest(TestCase):

    def setUp(self):
        self.switch_impl = flexmock()
        self.switch_impl.switch_descriptor = SwitchDescriptor(model='', hostname='')
        self.lock = flexmock()
        self.switch = SwitchTransactional(self.switch_impl, self.lock)

    def test_transactional_annotation_does_nothing_in_a_transaction(self):

        self.lock.should_receive("acquire").with_args().once().ordered()
        self.switch_impl.should_receive("start_transaction").with_args().once().ordered()

        with self.switch.transaction():
            assert_that(self.switch.in_transaction, is_(True))

            result = transactional_method(self.switch)
            assert_that(result, is_("Good"))

            result = transactional_method(self.switch)
            assert_that(result, is_("Good"))

            self.switch_impl.should_receive("commit_transaction").with_args().once().ordered()
            self.switch_impl.should_receive("end_transaction").with_args().once().ordered()
            self.lock.should_receive("release").with_args().once().ordered()

        assert_that(self.switch.in_transaction, is_(False))

    def test_lock_is_released_if_start_transaction_fails(self):

        self.lock.should_receive("acquire").with_args().once().ordered()
        self.switch_impl.should_receive("start_transaction").with_args().and_raise(NetmanException()).once().ordered()
        self.lock.should_receive("release").with_args().once().ordered()

        with self.assertRaises(NetmanException):
            with self.switch.transaction():
                pass

        assert_that(self.switch.in_transaction, is_(False))

    def test_transactional_annotation_runs_the_method_in_a_transaction_when_not_in_one(self):

        self.lock.should_receive("acquire").with_args().once().ordered()
        self.switch_impl.should_receive("start_transaction").with_args().once().ordered()
        self.switch_impl.should_receive("commit_transaction").with_args().once().ordered()
        self.switch_impl.should_receive("end_transaction").with_args().once().ordered()
        self.lock.should_receive("release").with_args().once().ordered()

        result = transactional_method(self.switch)

        assert_that(self.switch.in_transaction, is_(False))

        assert_that(result, is_("Good"))

    def test_lock_is_released_if_start_transaction_fails_using_annotation(self):

        self.lock.should_receive("acquire").with_args().once().ordered()
        self.switch_impl.should_receive("start_transaction").with_args().and_raise(NetmanException()).once().ordered()
        self.lock.should_receive("release").with_args().once().ordered()

        with self.assertRaises(NetmanException):
            transactional_method(self.switch)

        assert_that(self.switch.in_transaction, is_(False))


@transactional
def transactional_method(self):
    if self.in_transaction is False:
        raise AssertionError("I'm not in a transaction")
    return "Good"
