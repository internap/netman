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

from netaddr import IPAddress

from netman.core.objects.vrrp_group import VrrpGroup


def to_api(vrrp):
    return dict(
        id=vrrp.id,
        ips=sorted([str(i) for i in vrrp.ips]),
        priority=vrrp.priority,
        track_id=vrrp.track_id,
        track_decrement=vrrp.track_decrement,
        hello_interval=vrrp.hello_interval,
        dead_interval=vrrp.dead_interval,
    )


def to_core(serialized):
    return VrrpGroup(
        ips=[IPAddress(ip) for ip in serialized.pop('ips')],
        ** serialized
    )
