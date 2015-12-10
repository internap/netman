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
import logging

from netman.adapters.switches.brocade import Brocade
import re


class BackwardCompatibleBrocade(Brocade):
    def __init__(self, switch_descriptor, shell_factory):
        super(BackwardCompatibleBrocade, self).__init__(switch_descriptor, shell_factory)

        self.logger = logging.getLogger(
            "{module}.{hostname}".format(module=Brocade.__module__,
                                         hostname=self.switch_descriptor.hostname))

    def add_trunk_vlan(self, interface_id, vlan):
        return super(BackwardCompatibleBrocade, self).add_trunk_vlan(_add_ethernet(interface_id), vlan)

    def shutdown_interface(self, interface_id):
        return super(BackwardCompatibleBrocade, self).shutdown_interface(_add_ethernet(interface_id))

    def set_trunk_mode(self, interface_id):
        return super(BackwardCompatibleBrocade, self).set_trunk_mode(_add_ethernet(interface_id))

    def set_access_vlan(self, interface_id, vlan):
        return super(BackwardCompatibleBrocade, self).set_access_vlan(_add_ethernet(interface_id), vlan)

    def set_access_mode(self, interface_id):
        return super(BackwardCompatibleBrocade, self).set_access_mode(_add_ethernet(interface_id))

    def remove_trunk_vlan(self, interface_id, vlan):
        super(BackwardCompatibleBrocade, self).remove_trunk_vlan(_add_ethernet(interface_id), vlan)

    def remove_native_vlan(self, interface_id):
        return super(BackwardCompatibleBrocade, self).remove_native_vlan(_add_ethernet(interface_id))

    def remove_access_vlan(self, interface_id):
        return super(BackwardCompatibleBrocade, self).remove_access_vlan(_add_ethernet(interface_id))

    def openup_interface(self, interface_id):
        return super(BackwardCompatibleBrocade, self).openup_interface(_add_ethernet(interface_id))

    def interface(self, interface_id):
        return super(BackwardCompatibleBrocade, self).interface(_add_ethernet(interface_id))

    def configure_native_vlan(self, interface_id, vlan):
        return super(BackwardCompatibleBrocade, self).configure_native_vlan(_add_ethernet(interface_id), vlan)

    def add_vrrp_group(self, vlan_number, group_id, ips=None, priority=None, hello_interval=None, dead_interval=None,
                       track_id=None, track_decrement=None):
        return super(BackwardCompatibleBrocade, self).add_vrrp_group(vlan_number, group_id, ips, priority,
                                                                     hello_interval, dead_interval,
                                                                     _add_ethernet(track_id), track_decrement)


def _add_ethernet(interface_id):
    if interface_id is not None and re.match("^\d.*", interface_id):
        return "ethernet {}".format(interface_id)
    return interface_id
