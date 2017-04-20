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
import types
from contextlib import contextmanager
from functools import wraps

from netman.core.objects.switch_base import SwitchOperations


def do_not_wrap_with_flow_control(fn):
    setattr(fn, "_do_not_wrap_with_flow_control", True)
    return fn


class FlowControlSwitch(SwitchOperations):
    """
    Wrap your switch with this to handle auto-connections and auto-transactions

    fc_switch = FlowControlSwitch(myswitch)

    with fc_switch.transaction(): #will lock, connect and transaction
        fc_switch.add_vlan(1000)

    OR

    fc_switch.start_transaction() # will auto connect
    fc_switch.add_vlan()
    fc_switch.end_transaction() # will auto disconnect since it auto connected

    OR

    fc_switch.add_vlan(1000) #will auto lock, connect and transaction

    """
    def __init__(self, wrapped_switch, lock):
        self.wrapped_switch = wrapped_switch
        self.lock = lock
        self._has_auto_connected = False

    def __new__(cls, *args, **kwargs):
        obj = super(FlowControlSwitch, cls).__new__(cls, *args, **kwargs)

        for member in dir(cls):
            if not member.startswith("_"):
                _wrap_method_with_flow_control(cls, obj, member)

        return obj

    @do_not_wrap_with_flow_control
    @contextmanager
    def transaction(self):
        with self._locked_context(), self._connected_context(), self._transaction_context():
            yield

    @do_not_wrap_with_flow_control
    def start_transaction(self):
        if self.wrapped_switch.in_transaction:
            return

        self.lock.acquire()
        try:
            if not self.wrapped_switch.connected:
                self.wrapped_switch.connect()
                self._has_auto_connected = True

            self.wrapped_switch.start_transaction()
        except Exception:
            try:
                if self._has_auto_connected:
                    self.wrapped_switch.disconnect()
                    self._has_auto_connected = False
            finally:
                self.lock.release()
            raise

    @do_not_wrap_with_flow_control
    def end_transaction(self):
        try:
            self.wrapped_switch.end_transaction()
        finally:
            try:
                if self._has_auto_connected:
                    self.wrapped_switch.disconnect()
                    self._has_auto_connected = False
            finally:
                self.lock.release()

    @contextmanager
    def _connected_context(self):
        if self.wrapped_switch.connected:
            yield
        else:
            self.wrapped_switch.connect()
            try:
                yield
            finally:
                self.wrapped_switch.disconnect()

    @contextmanager
    def _transaction_context(self):
        if self.wrapped_switch.in_transaction:
            yield
        else:
            self.wrapped_switch.start_transaction()
            try:
                yield
                self.wrapped_switch.commit_transaction()
            except Exception:
                self.wrapped_switch.rollback_transaction()
                raise
            finally:
                self.wrapped_switch.end_transaction()

    @contextmanager
    def _locked_context(self):
        if self.wrapped_switch.in_transaction:
            yield
        else:
            self.lock.acquire()
            try:
                yield
            finally:
                self.lock.release()

    @do_not_wrap_with_flow_control
    def connect(self):
        self.wrapped_switch.connect()

    @do_not_wrap_with_flow_control
    def disconnect(self):
        self.wrapped_switch.disconnect()

    @do_not_wrap_with_flow_control
    def commit_transaction(self):
        self.wrapped_switch.commit_transaction()

    @do_not_wrap_with_flow_control
    def rollback_transaction(self):
        self.wrapped_switch.rollback_transaction()

    @property
    def switch_descriptor(self):
        return self.wrapped_switch.switch_descriptor


def _wrap_method_with_flow_control(cls, obj, method_name):
    original = getattr(cls, method_name)
    if not callable(original) or isinstance(original, property) or hasattr(original, "_do_not_wrap_with_flow_control"):
        return

    if method_name.startswith("get_"):
        @wraps(original)
        def wrapped(self, *args, **kwargs):
            with self._connected_context():
                return getattr(self.wrapped_switch, method_name)(*args, **kwargs)
    else:
        @wraps(original)
        def wrapped(self, *args, **kwargs):
            with self.transaction():
                return getattr(self.wrapped_switch, method_name)(*args, **kwargs)

    setattr(obj, method_name, types.MethodType(wrapped, obj))
