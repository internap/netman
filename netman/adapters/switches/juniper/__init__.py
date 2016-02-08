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

from netman.adapters.switches.juniper import standard
from netman.adapters.switches.juniper import qfx_copper

from netman.adapters.switches.juniper.base import Juniper
from netman.core.objects.switch_transactional import FlowControlSwitch


def standard_factory(switch_descriptor, lock):
    warnings.warn("Use SwitchFactory.get_switch_by_descriptor directly to instanciate a switch", DeprecationWarning)

    return FlowControlSwitch(wrapped_switch=standard.netconf(switch_descriptor), lock=lock)


def qfx_copper_factory(switch_descriptor, lock):
    warnings.warn("Use SwitchFactory.get_switch_by_descriptor directly to instanciate a switch", DeprecationWarning)

    return FlowControlSwitch(wrapped_switch=qfx_copper.netconf(switch_descriptor), lock=lock)
