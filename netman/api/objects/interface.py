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

from netman.api.objects import Serializable
from netman.core.objects.interface import Interface
from netman.core.objects.port_modes import ACCESS, TRUNK, DYNAMIC, BOND_MEMBER

serialized_port_mode = {
    ACCESS: "access",
    TRUNK: "trunk",
    DYNAMIC: "dynamic",
    BOND_MEMBER: "bond_member"
}


class SerializableInterface(Serializable):
    def __init__(self, src):
        super(SerializableInterface, self).__init__(['name', 'shutdown', 'bond_master', 'port_mode', 'access_vlan', 'trunk_native_vlan', 'trunk_vlans'])

        self.name = src.name
        self.shutdown = src.shutdown
        self.bond_master = src.bond_master
        self.port_mode = serialized_port_mode[src.port_mode]
        self.access_vlan = src.access_vlan
        self.trunk_native_vlan = src.trunk_native_vlan
        self.trunk_vlans = sorted(src.trunk_vlans)

    @classmethod
    def to_core(cls, **serialized):
        return Interface(
            port_mode=dict((v, k) for k, v in serialized_port_mode.iteritems())[serialized.pop('port_mode')],
            ** serialized
        )
