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


class Interface(object):
    def __init__(self, name=None, shutdown=None, port_mode=None, access_vlan=None, trunk_native_vlan=None,
                 trunk_vlans=None, bond_master=None):
        self.name = name
        self.shutdown = shutdown
        self.port_mode = port_mode
        self.access_vlan = access_vlan
        self.trunk_native_vlan = trunk_native_vlan
        self.trunk_vlans = trunk_vlans or []
        self.bond_master = bond_master
