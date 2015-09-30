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

from netman.adapters.switches import cisco, juniper, brocade, remote, dell
from netman.core.objects.switch_descriptor import SwitchDescriptor


class SwitchFactory(object):

    def __init__(self, switch_source, lock_factory):
        self.switch_source = switch_source
        self.lock_factory = lock_factory

        self.factories = {
            "cisco": cisco.factory,
            "brocade": brocade.factory,
            "juniper": juniper.standard_factory,
            "juniper_qfx_copper": juniper.qfx_copper_factory,
            "dell": dell.factory_ssh,
            "dell_ssh": dell.factory_ssh,
            "dell_telnet": dell.factory_telnet,
        }

        self.locks = {}

    def get_switch(self, hostname):
        raise NotImplemented()

    def get_anonymous_switch(self, **kwargs):
        return self.get_switch_by_descriptor(SwitchDescriptor(**kwargs))

    def get_switch_by_descriptor(self, switch_descriptor):
        if switch_descriptor.netman_server:
            return remote.factory(switch_descriptor)
        return self.factories[switch_descriptor.model](
            switch_descriptor,
            lock=self.get_lock(switch_descriptor))

    def get_lock(self, switch_descriptor):
        key = switch_descriptor.hostname
        if key not in self.locks:
            self.locks[key] = self.lock_factory.new_lock(key)
        return self.locks[key]
