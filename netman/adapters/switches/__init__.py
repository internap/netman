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
from netman.adapters.shell.ssh import SshClient
from netman.adapters.shell.telnet import TelnetClient

from netman.adapters.switches.backward_compatible_brocade import BackwardCompatibleBrocade
from netman.core.objects.switch_transactional import SwitchTransactional


def brocade_factory_ssh(switch_descriptor, lock):
    return SwitchTransactional(
        impl=BackwardCompatibleBrocade(switch_descriptor=switch_descriptor, shell_factory=SshClient),
        lock=lock
    )

def brocade_factory_telnet(switch_descriptor, lock):
    return SwitchTransactional(
        impl=BackwardCompatibleBrocade(switch_descriptor=switch_descriptor, shell_factory=TelnetClient),
        lock=lock
    )
