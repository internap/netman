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

from netman.core.objects import Model


class SwitchDescriptor(Model):
    def __init__(self, model, hostname, username=None, password=None, port=None, netman_server=None, **kwargs):
        self.model = model
        self.hostname = hostname
        self.username = username
        self.password = password
        self.port = port
        self.netman_server = netman_server

        self._deprecated_values = {}
        for m in _deprecated_members:
            if m in kwargs:
                setattr(self, m, kwargs.get(m))


_deprecated_members = ["default_vrf", "default_lan_acl_in", "default_lan_acl_out", "default_port_speed",
                       "trunked_interfaces", "parking_vlan", "vrrp_tracking_object"]


def _deprecation_warning(member):
    warnings.warn("Deprecated member {} is not used by Netman, define it elsewhere for your needs".format(member),
                  DeprecationWarning)


def _add_deprecated_property(m):
    def get_that(switch_descriptor):
        _deprecation_warning(m)
        return switch_descriptor._deprecated_values.get(m)

    def set_that(switch_descriptor, value):
        _deprecation_warning(m)
        switch_descriptor._deprecated_values[m] = value

    setattr(SwitchDescriptor, m, property(get_that, set_that))


for m in _deprecated_members:
    _add_deprecated_property(m)
