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

from netman.core.objects import Model


class BaseInterface(Model):
    def __init__(self, shutdown=None, port_mode=None, access_vlan=None,
                 trunk_native_vlan=None, trunk_vlans=None, mtu=None):
        self.shutdown = shutdown
        self.port_mode = port_mode
        self.access_vlan = access_vlan
        self.trunk_native_vlan = trunk_native_vlan
        self.trunk_vlans = trunk_vlans or []
        self.mtu = mtu


class Interface(BaseInterface):
    def __init__(self, name=None, bond_master=None, auto_negotiation=None, **interface):
        super(Interface, self).__init__(**interface)
        self.name = name
        self.bond_master = bond_master
        self.auto_negotiation = auto_negotiation
