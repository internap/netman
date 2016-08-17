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

from netman.api.objects import sub_dict, Serializer, Serializers
from netman.core.objects.interface import BaseInterface
from netman.core.objects.port_modes import ACCESS, TRUNK, DYNAMIC, BOND_MEMBER

__all__ = ['to_api', 'to_core']


serialized_port_mode = {
    ACCESS: "access",
    TRUNK: "trunk",
    DYNAMIC: "dynamic",
    BOND_MEMBER: "bond_member"
}


class V1(Serializer):
    since_version = 1

    def to_core(self, serialized):
        return BaseInterface(
            port_mode=dict((v, k) for k, v in serialized_port_mode.iteritems())[serialized.pop('port_mode')],
            **sub_dict(serialized, 'shutdown', 'access_vlan', 'trunk_native_vlan', 'trunk_vlans', 'mtu')
        )

    def to_api(self, base_interface):
        return dict(
            shutdown=base_interface.shutdown,
            port_mode=serialized_port_mode[base_interface.port_mode],
            access_vlan=base_interface.access_vlan,
            trunk_native_vlan=base_interface.trunk_native_vlan,
            trunk_vlans=sorted(base_interface.trunk_vlans),
            mtu=base_interface.mtu
        )


serializers = Serializers(V1())

to_api = serializers.to_api
to_core = serializers.to_core
