# Copyright 2020 Internap.
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


class MacAddress(Model):
    def __init__(self, vlan, mac_address, interface, type):
        self.mac_address = mac_address
        self.interface = interface
        self.vlan = vlan
        self.type = type
