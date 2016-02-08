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

from netman.core.objects.interface import BaseInterface, Interface


class Bond(BaseInterface):
    def __init__(self, number=None, link_speed=None, members=None, **interface):
        super(Bond, self).__init__(**interface)
        self.number = number
        self.link_speed = link_speed
        self.members = members or []

    @property
    def interface(self):
        warnings.warn('Deprecated: Use directly the members of Bond instead.', DeprecationWarning)
        return Interface(
            shutdown=self.shutdown,
            port_mode=self.port_mode,
            access_vlan=self.access_vlan,
            trunk_native_vlan=self.trunk_native_vlan,
            trunk_vlans=self.trunk_vlans,
        )
