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

from netman.api.objects import base_interface, interface, Serializer, \
    Serializers
from netman.api.objects import sub_dict
from netman.core.objects.bond import Bond
from netman.core.objects.interface import Interface


__all__ = ['to_api', 'to_core']


class V2(Serializer):
    since_version = 2

    def to_api(self, bond):
        return dict(
            number=bond.number,
            link_speed=bond.link_speed,
            members=bond.members,
            **base_interface.to_api(bond)
        )

    def to_core(self, api_bond):
        params = dict(vars(base_interface.to_core(api_bond)))
        params.update(sub_dict(api_bond, 'number', 'link_speed', 'members'))
        return Bond(**params)


class V1(Serializer):
    since_version = 1

    def to_api(self, bond):
        return dict(
            number=bond.number,
            link_speed=bond.link_speed,
            members=bond.members,
            interface=interface.to_api(Interface(
                shutdown=bond.shutdown,
                port_mode=bond.port_mode,
                access_vlan=bond.access_vlan,
                trunk_native_vlan=bond.trunk_native_vlan,
                trunk_vlans=bond.trunk_vlans,
                mtu=bond.mtu
            ))
        )

    def to_core(self, api_bond):
        params = dict(vars(base_interface.to_core(api_bond['interface'])))
        params.update(sub_dict(api_bond, 'number', 'link_speed', 'members'))
        return Bond(**params)


serializers = Serializers(V1(), V2())

to_api = serializers.to_api
to_core = serializers.to_core
