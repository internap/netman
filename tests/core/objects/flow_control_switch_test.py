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
from netman.core.objects.flow_control_switch import FlowControlSwitch
from netman.core.objects.switch_base import SwitchBase
from netman.core.objects.switch_descriptor import SwitchDescriptor


class FlowControlSwitchTest(TestCase):

    def setUp(self):
        self.wrapped_switch = flexmock(SwitchBase(SwitchDescriptor("cisco", "name")))
        self.lock = flexmock()
        self.switch = FlowControlSwitch(self.wrapped_switch, self.lock)

    def tearDown(self):
        flexmock_teardown()

    def test_a_get_method_connects_and_executes(self):
        self.wrapped_switch.should_receive("_connect").once().ordered()
        self.wrapped_switch.should_receive("get_vlan").once().ordered().with_args(1000)
        self.wrapped_switch.should_receive("_disconnect").once().ordered()

        self.switch.get_vlan(1000)

    def test_a_get_method_still_dc_if_raising(self):
        self.wrapped_switch.should_receive("_connect").once().ordered()
        self.wrapped_switch.should_receive("get_vlan").once().ordered().with_args(1000).and_raise(NetmanException)
        self.wrapped_switch.should_receive("_disconnect").once().ordered()

        with self.assertRaises(NetmanException):
            self.switch.get_vlan(1000)

    def test_a_get_method_connect_fail_gives_up(self):
        self.wrapped_switch.should_receive("_connect").once().ordered().and_raise(NetmanException)

        with self.assertRaises(NetmanException):
            self.switch.get_vlan(1000)

    def test_a_get_method_does_not_connect_if_already_connected(self):
        self.wrapped_switch.connected = True

        self.wrapped_switch.should_receive("get_vlan").once().ordered().with_args(1000)

        self.switch.get_vlan(1000)

    def test_an_operation_method_locks_connects_and_executes_in_a_transaction(self):

        self.lock.should_receive("acquire").once().ordered()
        self.wrapped_switch.should_receive("_connect").once().ordered()
        self.wrapped_switch.should_receive("_start_transaction").once().ordered()
        self.wrapped_switch.should_receive("add_vlan").once().ordered().with_args(1000)
        self.wrapped_switch.should_receive("commit_transaction").once().ordered()
        self.wrapped_switch.should_receive("_end_transaction").once().ordered()
        self.wrapped_switch.should_receive("_disconnect").once().ordered()
        self.lock.should_receive("release").once().ordered()

        self.switch.add_vlan(1000)

    def test_an_operation_method_unlocks_and_rollback_if_raising(self):

        self.lock.should_receive("acquire").once().ordered()
        self.wrapped_switch.should_receive("_connect").once().ordered()
        self.wrapped_switch.should_receive("_start_transaction").once().ordered()
        self.wrapped_switch.should_receive("add_vlan").once().ordered().with_args(1000).and_raise(NetmanException)
        self.wrapped_switch.should_receive("rollback_transaction").once().ordered()
        self.wrapped_switch.should_receive("_end_transaction").once().ordered()
        self.wrapped_switch.should_receive("_disconnect").once().ordered()
        self.lock.should_receive("release").once().ordered()

        with self.assertRaises(NetmanException):
            self.switch.add_vlan(1000)

    def test_an_operation_method_failing_to_start_transaction_rollbacks_unlocks_dc(self):

        self.lock.should_receive("acquire").once().ordered()
        self.wrapped_switch.should_receive("_connect").once().ordered()
        self.wrapped_switch.should_receive("_start_transaction").once().ordered().and_raise(NetmanException)
        self.wrapped_switch.should_receive("_disconnect").once().ordered()
        self.lock.should_receive("release").once().ordered()

        with self.assertRaises(NetmanException):
            self.switch.add_vlan(1000)

    def test_an_operation_method_failing_to_end_transaction_unlocks_dc(self):

        self.lock.should_receive("acquire").once().ordered()
        self.wrapped_switch.should_receive("_connect").once().ordered()
        self.wrapped_switch.should_receive("_start_transaction").once().ordered()
        self.wrapped_switch.should_receive("add_vlan").once().ordered().with_args(1000)
        self.wrapped_switch.should_receive("commit_transaction").once().ordered()
        self.wrapped_switch.should_receive("_end_transaction").once().ordered().and_raise(NetmanException)
        self.wrapped_switch.should_receive("_disconnect").once().ordered()
        self.lock.should_receive("release").once().ordered()

        with self.assertRaises(NetmanException):
            self.switch.add_vlan(1000)

    def test_an_operation_method_failing_to_commit_transaction_unlocks_dc(self):

        self.lock.should_receive("acquire").once().ordered()
        self.wrapped_switch.should_receive("_connect").once().ordered()
        self.wrapped_switch.should_receive("_start_transaction").once().ordered()
        self.wrapped_switch.should_receive("add_vlan").once().ordered().with_args(1000)
        self.wrapped_switch.should_receive("commit_transaction").once().ordered().and_raise(NetmanException)
        self.wrapped_switch.should_receive("rollback_transaction").once().ordered()
        self.wrapped_switch.should_receive("_end_transaction").once().ordered()
        self.wrapped_switch.should_receive("_disconnect").once().ordered()
        self.lock.should_receive("release").once().ordered()

        with self.assertRaises(NetmanException):
            self.switch.add_vlan(1000)

    def test_an_operation_method_failing_to_disconnect_unlocks(self):

        self.lock.should_receive("acquire").once().ordered()
        self.wrapped_switch.should_receive("_connect").once().ordered()
        self.wrapped_switch.should_receive("_start_transaction").once().ordered()
        self.wrapped_switch.should_receive("add_vlan").once().ordered().with_args(1000)
        self.wrapped_switch.should_receive("commit_transaction").once().ordered()
        self.wrapped_switch.should_receive("_end_transaction").once().ordered()
        self.wrapped_switch.should_receive("_disconnect").once().ordered().and_raise(NetmanException)
        self.lock.should_receive("release").once().ordered()

        with self.assertRaises(NetmanException):
            self.switch.add_vlan(1000)

    def test_an_operation_method_failing_to_connect_unlocks(self):

        self.lock.should_receive("acquire").once().ordered()
        self.wrapped_switch.should_receive("_connect").once().ordered().and_raise(NetmanException)
        self.lock.should_receive("release").once().ordered()

        with self.assertRaises(NetmanException):
            self.switch.add_vlan(1000)

    def test_an_operation_method_failing_to_lock_gives_up(self):

        self.lock.should_receive("acquire").once().ordered().and_raise(NetmanException)

        with self.assertRaises(NetmanException):
            self.switch.add_vlan(1000)

    def test_an_operation_method_already_connected_locks_and_executes_in_a_transaction(self):
        self.wrapped_switch.connected = True

        self.lock.should_receive("acquire").once().ordered()
        self.wrapped_switch.should_receive("_connect").never()
        self.wrapped_switch.should_receive("_start_transaction").once().ordered()
        self.wrapped_switch.should_receive("add_vlan").once().ordered().with_args(1000)
        self.wrapped_switch.should_receive("commit_transaction").once().ordered()
        self.wrapped_switch.should_receive("_end_transaction").once().ordered()
        self.wrapped_switch.should_receive("_disconnect").never()
        self.lock.should_receive("release").once().ordered()

        self.switch.add_vlan(1000)

    def test_an_operation_method_already_connected_and_in_transaction_just_executes(self):
        self.wrapped_switch.connected = True
        self.wrapped_switch.in_transaction = True

        self.wrapped_switch.should_receive("add_vlan").once().ordered().with_args(1000)

        self.switch.add_vlan(1000)

    def test_transaction_context_locks_connect_and_execute(self):

        self.lock.should_receive("acquire").once().ordered()
        self.wrapped_switch.should_receive("_connect").once().ordered()
        self.wrapped_switch.should_receive("_start_transaction").once().ordered()
        self.wrapped_switch.should_receive("add_vlan").once().ordered().with_args(1000)
        self.wrapped_switch.should_receive("commit_transaction").once().ordered()
        self.wrapped_switch.should_receive("_end_transaction").once().ordered()
        self.wrapped_switch.should_receive("_disconnect").once().ordered()
        self.lock.should_receive("release").once().ordered()

        with self.switch.transaction():
            self.switch.add_vlan(1000)

    def test_transaction_context_unlocks_rollback_and_dc_if_fails(self):

        self.lock.should_receive("acquire").once().ordered()
        self.wrapped_switch.should_receive("_connect").once().ordered()
        self.wrapped_switch.should_receive("_start_transaction").once().ordered()
        self.wrapped_switch.should_receive("add_vlan").once().ordered().with_args(1000).and_raise(NetmanException)
        self.wrapped_switch.should_receive("rollback_transaction").once().ordered()
        self.wrapped_switch.should_receive("_end_transaction").once().ordered()
        self.wrapped_switch.should_receive("_disconnect").once().ordered()
        self.lock.should_receive("release").once().ordered()

        with self.assertRaises(NetmanException):
            with self.switch.transaction():
                self.switch.add_vlan(1000)

    def test_transaction_context_already_connected_only_locks_connect_and_execute(self):
        self.wrapped_switch.connected = True

        self.lock.should_receive("acquire").once().ordered()
        self.wrapped_switch.should_receive("_start_transaction").once().ordered()
        self.wrapped_switch.should_receive("add_vlan").once().ordered().with_args(1000)
        self.wrapped_switch.should_receive("commit_transaction").once().ordered()
        self.wrapped_switch.should_receive("_end_transaction").once().ordered()
        self.lock.should_receive("release").once().ordered()

        with self.switch.transaction():
            self.switch.add_vlan(1000)

    def test_transaction_context_already_in_transaction_only_executes(self):
        self.wrapped_switch.connected = True
        self.wrapped_switch.in_transaction = True

        self.wrapped_switch.should_receive("add_vlan").once().ordered().with_args(1000)

        with self.switch.transaction():
            self.switch.add_vlan(1000)

    def test_switch_contract_compliance_start_transaction(self):

        self.lock.should_receive("acquire").once().ordered()
        self.wrapped_switch.should_receive("_connect").once().ordered()
        self.wrapped_switch.should_receive("_start_transaction").once().ordered()

        self.switch.start_transaction()

    def test_switch_contract_compliance_start_transaction_failing_to_start_rollback_dc_unlocks(self):

        self.lock.should_receive("acquire").once().ordered()
        self.wrapped_switch.should_receive("_connect").once().ordered()
        self.wrapped_switch.should_receive("_start_transaction").once().ordered().and_raise(NetmanException)
        self.wrapped_switch.should_receive("_disconnect").once().ordered()
        self.lock.should_receive("release").once().ordered()

        with self.assertRaises(NetmanException):
            self.switch.start_transaction()

    def test_switch_contract_compliance_start_transaction_failing_to_connect_unlocks(self):

        self.lock.should_receive("acquire").once().ordered()
        self.wrapped_switch.should_receive("_connect").once().ordered().and_raise(NetmanException)
        self.lock.should_receive("release").once().ordered()

        with self.assertRaises(NetmanException):
            self.switch.start_transaction()

    def test_switch_contract_compliance_start_transaction_failing_to_lock_gives_up(self):

        self.lock.should_receive("acquire").once().ordered().and_raise(NetmanException)

        with self.assertRaises(NetmanException):
            self.switch.start_transaction()

    def test_switch_contract_compliance_start_transaction_already_connected_don_t_connect(self):
        self.wrapped_switch.connected = True

        self.lock.should_receive("acquire").once().ordered()
        self.wrapped_switch.should_receive("_start_transaction").once().ordered()

        self.switch.start_transaction()

    def test_switch_contract_compliance_start_transaction_already_in_transaction_does_nothing(self):
        self.wrapped_switch.connected = True
        self.wrapped_switch.in_transaction = True

        self.switch.start_transaction()

    def test_switch_contract_compliance_end_transaction(self):
        self.lock.should_receive("acquire").once().ordered()
        self.wrapped_switch.should_receive("_connect").once().ordered()
        self.wrapped_switch.should_receive("_start_transaction").once().ordered()

        self.switch.start_transaction()

        self.wrapped_switch.should_receive("_end_transaction").once().ordered()
        self.wrapped_switch.should_receive("_disconnect").once().ordered()
        self.lock.should_receive("release").once().ordered()

        self.switch.end_transaction()

    def test_switch_contract_compliance_end_transaction_dont_dc_for_a_legit_connection_after_a_managed_one(self):
        self.lock.should_receive("acquire").once().ordered()
        self.wrapped_switch.should_receive("_connect").once().ordered()
        self.wrapped_switch.should_receive("_start_transaction").once().ordered()

        self.switch.start_transaction()

        self.wrapped_switch.should_receive("_end_transaction").once().ordered()
        self.wrapped_switch.should_receive("_disconnect").once().ordered()
        self.lock.should_receive("release").once().ordered()

        self.switch.end_transaction()

        self.wrapped_switch.connected = True

        self.wrapped_switch.should_receive("_end_transaction").once().ordered()
        self.lock.should_receive("release").once().ordered()

        self.switch.end_transaction()

    def test_switch_contract_compliance_end_transaction_if_not_connected_by_start_dont_dc(self):
        self.wrapped_switch.connected = True

        self.lock.should_receive("acquire").once().ordered()
        self.wrapped_switch.should_receive("_start_transaction").once().ordered()

        self.switch.start_transaction()

        self.wrapped_switch.should_receive("_end_transaction").once().ordered()
        self.lock.should_receive("release").once().ordered()

        self.switch.end_transaction()

    def test_switch_contract_compliance_end_transaction_failing_end_unlocks_and_dc(self):
        self.lock.should_receive("acquire").once().ordered()
        self.wrapped_switch.should_receive("_connect").once().ordered()
        self.wrapped_switch.should_receive("_start_transaction").once().ordered()

        self.switch.start_transaction()

        self.wrapped_switch.should_receive("_end_transaction").once().ordered().and_raise(NetmanException)
        self.wrapped_switch.should_receive("_disconnect").once().ordered()
        self.lock.should_receive("release").once().ordered()

        with self.assertRaises(NetmanException):
            self.switch.end_transaction()

    def test_switch_contract_compliance_end_transaction_failing_dc_unlocks(self):
        self.lock.should_receive("acquire").once().ordered()
        self.wrapped_switch.should_receive("_connect").once().ordered()
        self.wrapped_switch.should_receive("_start_transaction").once().ordered()

        self.switch.start_transaction()

        self.wrapped_switch.should_receive("_end_transaction").once().ordered()
        self.wrapped_switch.should_receive("_disconnect").once().ordered().and_raise(NetmanException)
        self.lock.should_receive("release").once().ordered()

        with self.assertRaises(NetmanException):
            self.switch.end_transaction()

    def test_switch_contract_compliance_connect(self):
        self.wrapped_switch.should_receive("connect").once().ordered()
        self.switch.connect()

    def test_switch_contract_compliance_disconnect(self):
        self.wrapped_switch.should_receive("disconnect").once().ordered()
        self.switch.disconnect()

    def test_switch_contract_compliance_commit_transaction(self):
        self.wrapped_switch.should_receive("commit_transaction").once().ordered()
        self.switch.commit_transaction()

    def test_switch_contract_compliance_rollback_transaction(self):
        self.wrapped_switch.should_receive("rollback_transaction").once().ordered()
        self.switch.rollback_transaction()

    def test_switch_contract_compliance_switch_descriptor(self):
        assert_that(self.switch.switch_descriptor, is_(self.wrapped_switch.switch_descriptor))
