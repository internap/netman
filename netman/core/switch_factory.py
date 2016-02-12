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
from netman.core.objects.flow_control_switch import FlowControlSwitch

from netman.adapters.switches import cisco, juniper, dell, dell10g, brocade
from netman.adapters.switches.remote import RemoteSwitch
from netman.core.objects.switch_descriptor import SwitchDescriptor

factories = {
    "cisco": cisco.ssh,
    "brocade": brocade.ssh,
    "brocade_ssh": brocade.ssh,
    "brocade_telnet": brocade.telnet,
    "juniper": juniper.standard.netconf,
    "juniper_qfx_copper": juniper.qfx_copper.netconf,
    "dell": dell.ssh,
    "dell_ssh": dell.ssh,
    "dell_telnet": dell.telnet,
    "dell10g": dell10g.ssh,
    "dell10g_ssh": dell10g.ssh,
    "dell10g_telnet": dell10g.telnet,
}


class RealSwitchFactory(object):

    def get_switch(self, hostname):
        raise NotImplemented()

    def get_anonymous_switch(self, **kwargs):
        return self.get_switch_by_descriptor(SwitchDescriptor(**kwargs))

    def get_switch_by_descriptor(self, switch_descriptor):
        if switch_descriptor.netman_server:
            return RemoteSwitch(switch_descriptor)
        return factories[switch_descriptor.model](switch_descriptor)


class FlowControlSwitchFactory(RealSwitchFactory):

    def __init__(self, switch_source, lock_factory):
        self.switch_source = switch_source
        self.lock_factory = lock_factory
        self.locks = {}

    def get_switch_by_descriptor(self, switch_descriptor):
        real_switch = super(FlowControlSwitchFactory, self).get_switch_by_descriptor(switch_descriptor)
        return FlowControlSwitch(real_switch, lock=self._get_lock(switch_descriptor))

    def _get_lock(self, switch_descriptor):
        key = switch_descriptor.hostname
        if key not in self.locks:
            self.locks[key] = self.lock_factory.new_lock(key)
        return self.locks[key]


SwitchFactory = FlowControlSwitchFactory
