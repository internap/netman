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

from netman.adapters.switches.juniper.base import Juniper
from netman.adapters.switches.juniper.standard import JuniperCustomStrategies
from netman.adapters.switches.juniper.qfx_copper import JuniperQfxCopperCustomStrategies
from netman.core.objects.switch_transactional import SwitchTransactional


def standard_factory(switch_descriptor, lock):
    return SwitchTransactional(
        impl=Juniper(
            switch_descriptor=switch_descriptor,
            custom_strategies=JuniperCustomStrategies()
        ),
        lock=lock
    )


def qfx_copper_factory(switch_descriptor, lock):
    return SwitchTransactional(
        impl=Juniper(
            switch_descriptor=switch_descriptor,
            custom_strategies=JuniperQfxCopperCustomStrategies()
        ),
        lock=lock
    )
