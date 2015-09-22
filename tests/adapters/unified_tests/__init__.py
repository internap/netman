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

from fake_switches.brocade.brocade_core import BrocadeSwitchCore
from fake_switches.cisco.cisco_core import CiscoSwitchCore
from fake_switches.dell.dell_core import DellSwitchCore
from fake_switches.juniper.juniper_core import JuniperSwitchCore
from fake_switches.juniper.juniper_qfx_copper_core import JuniperQfxCopperSwitchCore
from fake_switches.ssh_service import SwitchSshService
from fake_switches.switch_configuration import Port
from fake_switches.telnet_service import SwitchTelnetService

from tests.adapters.unified_tests.bond_management_test import BondManagementTest
from tests.adapters.unified_tests.interface_management_test import InterfaceManagementTest
from tests.adapters.unified_tests.ip_management_test import IpManagementTest
from tests.adapters.unified_tests.vlan_management_test import VlanManagementTest
from tests.adapters.unified_tests.vrrp_test import VrrpTest
from tests.adapters.unified_tests.dhcp_relay_server_test import DhcpRelayServerTest

available_models = [
    {
        "model": "cisco",
        "hostname": "127.0.0.1",
        "port": 11002,
        "username": "root",
        "password": "root",
        "test_port_name": "FastEthernet0/3",
        "core_class": CiscoSwitchCore,
        "service_class": SwitchSshService,
        "ports": [
            Port("FastEthernet0/1"),
            Port("FastEthernet0/2"),
            Port("FastEthernet0/3"),
            Port("FastEthernet0/4"),
        ]
    },
    {
        "model": "brocade",
        "hostname": "127.0.0.1",
        "port": 11003,
        "username": "root",
        "password": "root",
        "test_port_name": "1/3",
        "core_class": BrocadeSwitchCore,
        "service_class": SwitchSshService,
        "ports": [
            Port("ethernet 1/1"),
            Port("ethernet 1/2"),
            Port("ethernet 1/3"),
            Port("ethernet 1/4")
        ]
    },
    {
        "model": "juniper",
        "hostname": "127.0.0.1",
        "port": 11004,
        "username": "root",
        "password": "root",
        "test_port_name": "ge-0/0/3",
        "core_class": JuniperSwitchCore,
        "service_class": SwitchSshService,
        "ports": [
            Port("ge-0/0/1"),
            Port("ge-0/0/2"),
            Port("ge-0/0/3"),
            Port("ge-0/0/4")
        ]
    },
    {
        "model": "juniper_qfx_copper",
        "hostname": "127.0.0.1",
        "port": 11005,
        "username": "root",
        "password": "root",
        "test_port_name": "ge-0/0/3",
        "core_class": JuniperQfxCopperSwitchCore,
        "service_class": SwitchSshService,
        "ports": [
            Port("ge-0/0/1"),
            Port("ge-0/0/2"),
            Port("ge-0/0/3"),
            Port("ge-0/0/4")
        ]
    },
    {
        "model": "dell",
        "hostname": "127.0.0.1",
        "port": 11006,
        "username": "root",
        "password": "root",
        "test_port_name": "ethernet 2/g2",
        "core_class": DellSwitchCore,
        "service_class": SwitchSshService,
        "ports": [
            Port("ethernet 1/g1"),
            Port("ethernet 1/g2"),
            Port("ethernet 2/g1"),
            Port("ethernet 2/g2"),
            Port("ethernet 1/xg1"),
            Port("ethernet 2/xg1")
        ]
    },
    {
        "model": "dell_telnet",
        "hostname": "127.0.0.1",
        "port": 11007,
        "username": "root",
        "password": "root",
        "test_port_name": "ethernet 2/g2",
        "core_class": DellSwitchCore,
        "service_class": SwitchTelnetService,
        "ports": [
            Port("ethernet 1/g1"),
            Port("ethernet 1/g2"),
            Port("ethernet 2/g1"),
            Port("ethernet 2/g2"),
            Port("ethernet 1/xg1"),
            Port("ethernet 2/xg1")
        ]
    }
]

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
        class_name = "{}{}".format(specs["model"].capitalize(), test_class.__name__)
        current_module[class_name] = type(class_name, (test_class,), {"__test__": True, "switch_specs": specs})


