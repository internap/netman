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

from netman.api.objects import vrrp_group
from netman.core.objects.access_groups import IN, OUT
from netman.core.objects.vlan import Vlan


def to_api(vlan):
    return dict(
        number=vlan.number,
        name=vlan.name,
        ips=sorted([{'address': ipn.ip.format(), 'mask': ipn.prefixlen} for ipn in vlan.ips], key=lambda i: i['address']),
        vrrp_groups=sorted([vrrp_group.to_api(group) for group in vlan.vrrp_groups], key=lambda i: i['id']),
        vrf_forwarding=vlan.vrf_forwarding,
        access_groups={
            "in": vlan.access_groups[IN],
            "out": vlan.access_groups[OUT]
        },
        dhcp_relay_servers=[str(server) for server in vlan.dhcp_relay_servers],
        icmp_redirects=vlan.icmp_redirects,
    )


def to_core(serialized):
    access_groups = serialized.pop('access_groups')
    ips = serialized.pop('ips')
    vrrp_groups = serialized.pop('vrrp_groups')
    dhcp_relay_servers = serialized.pop('dhcp_relay_servers')
    return Vlan(
        access_group_in=access_groups['in'],
        access_group_out=access_groups['out'],
        ips=[IPNetwork('{address}/{mask}'.format(**ip)) for ip in ips],
        vrrp_groups=[vrrp_group.to_core(group) for group in vrrp_groups],
        dhcp_relay_servers=[IPAddress(i) for i in dhcp_relay_servers],
        **serialized
    )
