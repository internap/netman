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

from netaddr import IPNetwork, IPAddress

from netman.api.objects import Serializable
from netman.api.objects.vrrp_group import SerializableVrrpGroup
from netman.core.objects.access_groups import IN, OUT
from netman.core.objects.vlan import Vlan


class SerializableVlan(Serializable):
    def __init__(self, src):
        super(SerializableVlan, self).__init__(['number', 'name', 'ips', 'vrrp_groups', 'vrf_forwarding',
                                                'access_groups', 'dhcp_relay_servers'])

        self.number = src.number
        self.name = src.name
        self.ips = sorted([{'address': ipn.ip.format(), 'mask': ipn.prefixlen} for ipn in src.ips], key=lambda i: i['address'])
        self.vrrp_groups = sorted([SerializableVrrpGroup(group) for group in src.vrrp_groups], key=lambda i: i.id)
        self.vrf_forwarding = src.vrf_forwarding
        self.access_groups = {
            "in": src.access_groups[IN],
            "out": src.access_groups[OUT]
        }
        self.dhcp_relay_servers = [str(server) for server in src.dhcp_relay_servers]

    @classmethod
    def to_core(cls, **serialized):
        access_groups = serialized.pop('access_groups')
        ips = serialized.pop('ips')
        vrrp_groups = serialized.pop('vrrp_groups')
        dhcp_relay_servers = serialized.pop('dhcp_relay_servers')
        return Vlan(
            access_group_in=access_groups['in'],
            access_group_out=access_groups['out'],
            ips=[IPNetwork('{address}/{mask}'.format(**ip)) for ip in ips],
            vrrp_groups=[SerializableVrrpGroup.to_core(**group) for group in vrrp_groups],
            dhcp_relay_servers=[IPAddress(i) for i in dhcp_relay_servers],
            ** serialized
        )
