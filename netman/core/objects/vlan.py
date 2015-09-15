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

from netman.core.objects.access_groups import OUT, IN


class Vlan(object):
    def __init__(self, number=None, name=None, ips=None, vrrp_groups=None, vrf_forwarding=None, access_group_in=None,
                 access_group_out=None, dhcp_relay_servers=None):
        self.number = number
        self.name = name
        self.access_groups = {IN: access_group_in, OUT: access_group_out}
        self.vrf_forwarding = vrf_forwarding
        self.ips = ips or []
        self.vrrp_groups = vrrp_groups or []
        self.dhcp_relay_servers = dhcp_relay_servers or []
