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
from fake_switches.dell10g.dell_core import Dell10GSwitchCore
from fake_switches.juniper.juniper_core import JuniperSwitchCore
from fake_switches.juniper_qfx_copper.juniper_qfx_copper_core import JuniperQfxCopperSwitchCore
from fake_switches.ssh_service import SwitchSshService
from fake_switches.switch_configuration import Port
from fake_switches.telnet_service import SwitchTelnetService
from netman.core.objects.switch_descriptor import SwitchDescriptor

available_models = [
    {
        "switch_descriptor": SwitchDescriptor(
            model="cisco",
            hostname="127.0.0.1",
            port=11002,
            username="root",
            password="root",
        ),
        "test_port_name": "FastEthernet0/3",
        "test_vrrp_track_id": "101",
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
        "switch_descriptor": SwitchDescriptor(
            model="brocade",
            hostname="127.0.0.1",
            port=11003,
            username="root",
            password="root",
        ),
        "test_port_name": "ethernet 1/3",
        "test_vrrp_track_id": "ethernet 1/1",
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
        "switch_descriptor": SwitchDescriptor(
            model="brocade_telnet",
            hostname="127.0.0.1",
            port=11012,
            username="root",
            password="root",
        ),
        "test_port_name": "ethernet 1/3",
        "test_vrrp_track_id": "ethernet 1/1",
        "core_class": BrocadeSwitchCore,
        "service_class": SwitchTelnetService,
        "ports": [
            Port("ethernet 1/1"),
            Port("ethernet 1/2"),
            Port("ethernet 1/3"),
            Port("ethernet 1/4")
        ]
    },
    {
        "switch_descriptor": SwitchDescriptor(
            model="juniper",
            hostname="127.0.0.1",
            port=11004,
            username="root",
            password="root",
        ),
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
        "switch_descriptor": SwitchDescriptor(
            model="juniper_qfx_copper",
            hostname="127.0.0.1",
            port=11005,
            username="root",
            password="root",
        ),
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
        "switch_descriptor": SwitchDescriptor(
            model="dell",
            hostname="127.0.0.1",
            port=11006,
            username="root",
            password="root",
        ),
        "test_port_name": "ethernet 2/g2",
        "core_class": DellSwitchCore,
        "service_class": SwitchSshService,
        "ports": [
            Port("ethernet 1/g1"),
            Port("ethernet 1/g2"),
            Port("ethernet 1/xg1"),
            Port("ethernet 2/g1"),
            Port("ethernet 2/g2"),
            Port("ethernet 2/xg1")
        ]
    },
    {
        "switch_descriptor": SwitchDescriptor(
            model="dell_telnet",
            hostname="127.0.0.1",
            port=11007,
            username="root",
            password="root",
        ),
        "test_port_name": "ethernet 2/g2",
        "core_class": DellSwitchCore,
        "service_class": SwitchTelnetService,
        "ports": [
            Port("ethernet 1/g1"),
            Port("ethernet 1/g2"),
            Port("ethernet 1/xg1"),
            Port("ethernet 2/g1"),
            Port("ethernet 2/g2"),
            Port("ethernet 2/xg1")
        ]
    },
    {
        "switch_descriptor": SwitchDescriptor(
            model="dell10g",
            hostname="127.0.0.1",
            port=11008,
            username="root",
            password="root",
        ),
        "test_port_name": "tengigabitethernet 1/0/1",
        "core_class": Dell10GSwitchCore,
        "service_class": SwitchSshService,
        "ports": [
            Port("tengigabitethernet 1/0/1"),
            Port("tengigabitethernet 1/0/2"),
            Port("tengigabitethernet 2/0/1"),
            Port("tengigabitethernet 2/0/2"),
        ]
    },
    {
        "switch_descriptor": SwitchDescriptor(
            model="dell10g_telnet",
            hostname="127.0.0.1",
            port=11009,
            username="root",
            password="root",
        ),
        "test_port_name": "tengigabitethernet 1/0/1",
        "core_class": Dell10GSwitchCore,
        "service_class": SwitchTelnetService,
        "ports": [
            Port("tengigabitethernet 1/0/1"),
            Port("tengigabitethernet 1/0/2"),
            Port("tengigabitethernet 2/0/1"),
            Port("tengigabitethernet 2/0/2"),
        ]
    }
]


