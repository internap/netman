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

class SwitchDescriptor(object):
    def __init__(self, model, hostname, username=None, password=None, port=None,
                 default_vrf=None, default_lan_acl_in=None, default_lan_acl_out=None,
                 trunked_interfaces=None, parking_vlan=None, netman_server=None, default_port_speed=None,
                 vrrp_tracking_object=None):
        self.model = model
        self.hostname = hostname
        self.username = username
        self.password = password
        self.port = port

        self.default_vrf = default_vrf
        self.default_lan_acl_in = default_lan_acl_in
        self.default_lan_acl_out = default_lan_acl_out
        self.default_port_speed = default_port_speed
        self.trunked_interfaces = trunked_interfaces
        self.parking_vlan = parking_vlan
        self.netman_server = netman_server
        self.vrrp_tracking_object = vrrp_tracking_object

    def __eq__(self, other):
        return isinstance(other, SwitchDescriptor) and self.__dict__ == other.__dict__
