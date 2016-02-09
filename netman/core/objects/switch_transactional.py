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
import warnings
from functools import wraps

from netman.core.objects.flow_control_switch import FlowControlSwitch


def transactional(fn):
    warnings.warn("Deprecated, make your own annotation this one will disappear", DeprecationWarning)
    @wraps(fn)
    def wrapper(self, *args, **kwargs):
        if self.in_transaction:
            return fn(self, *args, **kwargs)
        else:
            with self.transaction():
                return fn(self, *args, **kwargs)

    return wrapper


class SwitchTransactional(FlowControlSwitch):
    def __init__(self, impl, lock):
        warnings.warn("Deprecated, use FlowControlSwitch instead", DeprecationWarning)
        super(SwitchTransactional, self).__init__(impl, lock)

    @property
    def in_transaction(self):
        return self.wrapped_switch.in_transaction
