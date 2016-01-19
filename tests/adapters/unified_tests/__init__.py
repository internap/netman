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

from tests.adapters.model_list import available_models
from tests.adapters.unified_tests.bond_management_test import BondManagementTest
from tests.adapters.unified_tests.interface_management_test import InterfaceManagementTest
from tests.adapters.unified_tests.ip_management_test import IpManagementTest
from tests.adapters.unified_tests.vlan_management_test import VlanManagementTest
from tests.adapters.unified_tests.vrrp_test import VrrpTest
from tests.adapters.unified_tests.dhcp_relay_server_test import DhcpRelayServerTest


test_classes = [
    BondManagementTest,
    InterfaceManagementTest,
    IpManagementTest,
    VlanManagementTest,
    VrrpTest,
    DhcpRelayServerTest
]


current_module = globals()
for specs in available_models:
    for test_class in test_classes:
        class_name = "{}{}".format(specs["switch_descriptor"].model.capitalize(), test_class.__name__)
        current_module[class_name] = type(class_name, (test_class,), {"__test__": True, "switch_specs": specs})


