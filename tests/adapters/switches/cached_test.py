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

import unittest

from hamcrest import assert_that, is_
from flexmock import flexmock, flexmock_teardown
from netman.adapters.switches.cached import CachedSwitch
from netman.core.objects.bond import Bond
from netman.core.objects.interface import Interface
from netman.core.objects.vlan import Vlan
from netman.core.objects.switch_descriptor import SwitchDescriptor
from netman.core.objects.vrrp_group import VrrpGroup
from netman.core.objects import access_groups, port_modes


class CacheSwitchTest(unittest.TestCase):
    def setUp(self):
        self.real_switch_mock = flexmock()
        self.real_switch_mock.switch_descriptor = SwitchDescriptor(
            'model', 'hostname')
        self.switch = CachedSwitch(self.real_switch_mock)

    def tearDown(self):
        flexmock_teardown()

    def test_connect(self):
        self.real_switch_mock.should_receive("connect").once()
        self.switch.connect()

    def test_disconnect(self):
        self.real_switch_mock.should_receive("disconnect").once()
        self.switch.disconnect()

    def test_start_transaction(self):
        self.real_switch_mock.should_receive("start_transaction").once()
        self.switch.start_transaction()

    def test_commit_transaction(self):
        self.real_switch_mock.should_receive("commit_transaction").once()
        self.switch.commit_transaction()

    def test_rollback_transaction(self):
        self.real_switch_mock.should_receive("rollback_transaction").once()
        self.switch.rollback_transaction()

    def test_end_transaction(self):
        self.real_switch_mock.should_receive("end_transaction").once()
        self.switch.end_transaction()

    def test_get_vlans(self):
        all_vlans = [Vlan(1, 'first'), Vlan(2, 'second')]

        self.real_switch_mock.should_receive("get_vlans").once().and_return(
            all_vlans)
        assert_that(self.switch.get_vlans(), is_(all_vlans))
        assert_that(self.switch.get_vlans(), is_(all_vlans))

    def test_add_vlan_first(self):
        all_vlans = [Vlan(1), Vlan(2), Vlan(123, name='allo')]

        self.real_switch_mock.should_receive("add_vlan").once().with_args(123, 'allo')
        self.switch.add_vlan(123, 'allo')

        self.real_switch_mock.should_receive("get_vlans").once().and_return(
            all_vlans)
        assert_that(self.switch.get_vlans(), is_(all_vlans))
        assert_that(self.switch.get_vlans(), is_(all_vlans))

    def test_add_vlan_after_get_vlans(self):
        all_vlans = [Vlan(1), Vlan(2)]

        self.real_switch_mock.should_receive("get_vlans").once().and_return(
            all_vlans)
        assert_that(self.switch.get_vlans(), is_(all_vlans))
        assert_that(self.switch.get_vlans(), is_(all_vlans))

        self.real_switch_mock.should_receive("add_vlan").once().with_args(123, 'allo')
        self.switch.add_vlan(123, 'allo')

        assert_that(self.switch.get_vlans(), is_(all_vlans+[Vlan(123, name='allo')]))

    def test_remove_vlan(self):
        self.real_switch_mock.should_receive("get_vlans").once().and_return(
            [Vlan(1), Vlan(2)])
        self.switch.get_vlans()

        self.real_switch_mock.should_receive("remove_vlan").once().with_args(1)
        self.switch.remove_vlan(1)

        assert_that(self.switch.get_vlans(), is_([Vlan(2)]))

    def test_get_interfaces(self):
        all_interfaces = [Interface('xe-1/0/1'), Interface('xe-1/0/2')]

        self.real_switch_mock.should_receive("get_interfaces").once() \
            .and_return(all_interfaces)
        assert_that(self.switch.get_interfaces(), is_(all_interfaces))
        assert_that(self.switch.get_interfaces(), is_(all_interfaces))

    def test_set_access_vlan(self):
        self.real_switch_mock.should_receive("get_interfaces").once().and_return(
            [Interface('eth0')])
        self.switch.get_interfaces()

        self.real_switch_mock.should_receive("set_access_vlan").once() \
            .with_args('eth0', 123)

        self.switch.set_access_vlan('eth0', 123)

        assert_that(
            self.switch.get_interfaces(),
            is_([Interface('eth0', access_vlan=123)])
        )

    def test_remove_access_vlan(self):
        self.real_switch_mock.should_receive("get_interfaces").once().and_return(
            [Interface('eth0', access_vlan=123)])
        self.switch.get_interfaces()

        self.real_switch_mock.should_receive("remove_access_vlan").once() \
            .with_args('eth0')

        self.switch.remove_access_vlan('eth0')

        assert_that(
            self.switch.get_interfaces(),
            is_([Interface('eth0')])
        )

    def test_set_trunk_mode(self):
        self.real_switch_mock.should_receive("get_interfaces").once().and_return(
            [Interface('eth0')])
        self.switch.get_interfaces()

        self.real_switch_mock.should_receive("set_trunk_mode").once() \
            .with_args('eth0')

        self.switch.set_trunk_mode('eth0')

        assert_that(
            self.switch.get_interfaces(),
            is_([Interface('eth0', port_mode=port_modes.TRUNK)])
        )

    def test_set_access_mode(self):
        self.real_switch_mock.should_receive("get_interfaces").once().and_return(
            [Interface('eth0')])
        self.switch.get_interfaces()

        self.real_switch_mock.should_receive("set_access_mode").once() \
            .with_args('eth0')

        self.switch.set_access_mode('eth0')

        assert_that(
            self.switch.get_interfaces(),
            is_([Interface('eth0', port_mode=port_modes.ACCESS)])
        )

    def test_add_trunk_vlan(self):
        self.real_switch_mock.should_receive("get_interfaces").once() \
            .and_return([Interface('xe-1/0/2')])
        self.switch.get_interfaces()

        self.real_switch_mock.should_receive("add_trunk_vlan").once() \
            .with_args('xe-1/0/2', 1)

        self.switch.add_trunk_vlan('xe-1/0/2', 1)

        assert_that(
            self.switch.get_interfaces(),
            is_([Interface('xe-1/0/2', trunk_vlans=[1])]))

    def test_remove_trunk_vlan(self):
        self.real_switch_mock.should_receive("get_interfaces").once() \
            .and_return([Interface('xe-1/0/2', trunk_vlans=[1])])
        self.switch.get_interfaces()

        self.real_switch_mock.should_receive("remove_trunk_vlan").once() \
            .with_args('xe-1/0/2', 1)

        self.switch.remove_trunk_vlan('xe-1/0/2', 1)

        assert_that(
            self.switch.get_interfaces(),
            is_([Interface('xe-1/0/2', trunk_vlans=[])]))

    def test_shutdown_interface(self):
        self.real_switch_mock.should_receive("get_interfaces").once() \
            .and_return([Interface('xe-1/0/2', shutdown=False)])
        self.switch.get_interfaces()

        self.real_switch_mock.should_receive("shutdown_interface").once() \
            .with_args('xe-1/0/2')

        self.switch.shutdown_interface('xe-1/0/2')

        assert_that(
            self.switch.get_interfaces(),
            is_([Interface('xe-1/0/2', shutdown=True)]))

    def test_openup_interface(self):
        self.real_switch_mock.should_receive("get_interfaces").once() \
            .and_return([Interface('xe-1/0/2')])
        self.switch.get_interfaces()

        self.real_switch_mock.should_receive("openup_interface").once() \
            .with_args('xe-1/0/2')

        self.switch.openup_interface('xe-1/0/2')

        assert_that(
            self.switch.get_interfaces(),
            is_([Interface('xe-1/0/2', shutdown=False)]))

    def test_configure_native_vlan(self):
        self.real_switch_mock.should_receive("get_interfaces").once() \
            .and_return([Interface('xe-1/0/2')])
        self.switch.get_interfaces()

        self.real_switch_mock.should_receive("configure_native_vlan").once() \
            .with_args('xe-1/0/2', 20)

        self.switch.configure_native_vlan('xe-1/0/2', 20)

        assert_that(
            self.switch.get_interfaces(),
            is_([Interface('xe-1/0/2', trunk_native_vlan=20)]))

    def test_remove_native_vlan(self):
        self.real_switch_mock.should_receive("get_interfaces").once() \
            .and_return([Interface('xe-1/0/2', trunk_native_vlan=20)])
        self.switch.get_interfaces()

        self.real_switch_mock.should_receive("remove_native_vlan").once() \
            .with_args('xe-1/0/2')

        self.switch.remove_native_vlan('xe-1/0/2')

        assert_that(
            self.switch.get_interfaces(),
            is_([Interface('xe-1/0/2', trunk_native_vlan=None)]))

    def test_add_ip_to_vlan(self):
        self.real_switch_mock.should_receive("get_vlans").once() \
            .and_return([Vlan(2)])
        self.switch.get_vlans()

        self.real_switch_mock.should_receive("add_ip_to_vlan").once() \
            .with_args(2, '127.0.0.1')

        self.switch.add_ip_to_vlan(2, '127.0.0.1')

        assert_that(
            self.switch.get_vlans(),
            is_([Vlan(2, ips=['127.0.0.1'])]))

    def test_remove_ip_from_vlan(self):
        self.real_switch_mock.should_receive("get_vlans").once() \
            .and_return([Vlan(2, ips=['127.0.0.1'])])
        self.switch.get_vlans()

        self.real_switch_mock.should_receive("remove_ip_from_vlan").once() \
            .with_args(2, '127.0.0.1')

        self.switch.remove_ip_from_vlan(2, '127.0.0.1')

        assert_that(
            self.switch.get_vlans(),
            is_([Vlan(2, ips=[])]))

    def test_set_vlan_access_group(self):
        self.real_switch_mock.should_receive("get_vlans").once() \
            .and_return([Vlan(123)])
        self.switch.get_vlans()

        self.real_switch_mock.should_receive("set_vlan_access_group").once() \
            .with_args(123, access_groups.IN, 'vlan-access-group')

        self.switch.set_vlan_access_group(123, access_groups.IN, 'vlan-access-group')

        assert_that(
            self.switch.get_vlans(),
            is_([Vlan(123, access_group_in='vlan-access-group')]))

    def test_remove_vlan_access_group(self):
        self.real_switch_mock.should_receive("get_vlans").once() \
            .and_return([Vlan(123, access_group_out='vlan-access-group')])
        self.switch.get_vlans()

        self.real_switch_mock.should_receive("remove_vlan_access_group").once() \
            .with_args(123, access_groups.OUT)

        self.switch.remove_vlan_access_group(123, access_groups.OUT)

        assert_that(
            self.switch.get_vlans(),
            is_([Vlan(123, access_group_out=None)]))

    def test_set_vlan_vrf(self):
        self.real_switch_mock.should_receive("get_vlans").once() \
            .and_return([Vlan(123)])
        self.switch.get_vlans()

        self.real_switch_mock.should_receive("set_vlan_vrf").once() \
            .with_args(123, 'vrf-name')

        self.switch.set_vlan_vrf(123, 'vrf-name')

        assert_that(
            self.switch.get_vlans(),
            is_([Vlan(123, vrf_forwarding='vrf-name')]))

    def test_remove_vlan_vrf(self):
        self.real_switch_mock.should_receive("get_vlans").once() \
            .and_return([Vlan(123, vrf_forwarding='vrf-name')])
        self.switch.get_vlans()

        self.real_switch_mock.should_receive("remove_vlan_vrf").once() \
            .with_args(123)

        self.switch.remove_vlan_vrf(123)

        assert_that(
            self.switch.get_vlans(),
            is_([Vlan(123, vrf_forwarding=None)]))


    def test_set_interface_description(self):
        self.real_switch_mock.should_receive("set_interface_description").once() \
            .with_args('xe-1/0/2', 'interface-description')
        self.switch.set_interface_description('xe-1/0/2', 'interface-description')

    def test_remove_interface_description(self):
        self.real_switch_mock.should_receive("remove_interface_description").once() \
            .with_args('xe-1/0/2')
        self.switch.remove_interface_description('xe-1/0/2')

    def test_edit_interface_spanning_tree(self):
        self.real_switch_mock.should_receive("edit_interface_spanning_tree").once() \
            .with_args('xe-1/0/2', None)

        self.switch.edit_interface_spanning_tree('xe-1/0/2')

    def test_add_bond_first(self):
        all_bonds = [Bond(1), Bond(2), Bond(123)]

        self.real_switch_mock.should_receive("add_bond").once().with_args(123)
        self.switch.add_bond(123)
        assert_that(self.switch.get_bond(123).number, is_(123))

        self.real_switch_mock.should_receive("get_bonds").once().and_return(
            all_bonds)
        assert_that(self.switch.get_bonds(), is_(all_bonds))
        assert_that(self.switch.get_bonds(), is_(all_bonds))

    def test_add_bond_after_get_bonds(self):
        all_bonds = [Bond(1), Bond(2)]

        self.real_switch_mock.should_receive("get_bonds").once().and_return(
            all_bonds)
        assert_that(self.switch.get_bonds(), is_(all_bonds))
        assert_that(self.switch.get_bonds(), is_(all_bonds))

        self.real_switch_mock.should_receive("add_bond").once().with_args(123)
        self.switch.add_bond(123)
        assert_that(self.switch.get_bond(123).number, is_(123))

        assert_that(self.switch.get_bonds(), is_(all_bonds+[Bond(123)]))

    def test_remove_bond(self):
        self.real_switch_mock.should_receive("get_bonds").once().and_return(
            [Bond(1), Bond(2)])
        self.switch.get_bonds()

        self.real_switch_mock.should_receive("remove_bond").once().with_args(2)
        self.switch.remove_bond(2)

        assert_that(self.switch.get_bonds(), is_([Bond(1)]))

    def test_get_bonds(self):
        all_bonds = [Bond(1), Bond(2)]

        self.real_switch_mock.should_receive("get_bonds").once().and_return(
            all_bonds)
        assert_that(self.switch.get_bonds(), is_(all_bonds))
        assert_that(self.switch.get_bonds(), is_(all_bonds))

    def test_get_bond(self):
        bond = Bond(2)
        all_bonds = [Bond(1), bond]

        self.real_switch_mock.should_receive("get_bond").once().with_args(2) \
            .and_return(bond)
        assert_that(self.switch.get_bond(2), is_(bond))
        assert_that(self.switch.get_bond(2), is_(bond))

        self.real_switch_mock.should_receive("get_bonds").once().and_return(
            all_bonds)
        assert_that(self.switch.get_bonds(), is_(all_bonds))
        assert_that(self.switch.get_bonds(), is_(all_bonds))

    def test_add_interface_to_bond(self):
        self.real_switch_mock.should_receive("get_bonds").once() \
            .and_return([Bond(1, interface=Interface())])
        self.real_switch_mock.should_receive("get_interfaces").once() \
            .and_return([Interface('xe-1/0/2')])

        self.switch.get_bonds()
        self.switch.get_interfaces()

        self.real_switch_mock.should_receive("add_interface_to_bond").once() \
            .with_args('xe-1/0/2', 1)

        self.switch.add_interface_to_bond('xe-1/0/2', 1)

        assert_that(
            self.switch.get_bonds(),
            is_([Bond(1, interface=Interface(), members=['xe-1/0/2'])]))
        assert_that(
            self.switch.get_interfaces(),
            is_([Interface('xe-1/0/2', bond_master=1)]))

    def test_remove_interface_from_bond(self):
        self.real_switch_mock.should_receive("get_bonds").once() \
            .and_return([Bond(1, interface=Interface(), members=['xe-1/0/2'])])
        self.real_switch_mock.should_receive("get_interfaces").once() \
            .and_return([Interface('xe-1/0/2', bond_master=1)])

        self.switch.get_bonds()
        self.switch.get_interfaces()

        self.real_switch_mock.should_receive("remove_interface_from_bond").once() \
            .with_args('xe-1/0/2')

        self.switch.remove_interface_from_bond('xe-1/0/2')

        assert_that(
            self.switch.get_bonds(),
            is_([Bond(1, interface=Interface(), members=[])]))
        assert_that(
            self.switch.get_interfaces(),
            is_([Interface('xe-1/0/2', bond_master=None)]))

    def test_set_bond_link_speed(self):
        self.real_switch_mock.should_receive("get_bonds").once().and_return(
            [Bond(1)])
        self.switch.get_bonds()

        self.real_switch_mock.should_receive("set_bond_link_speed").once() \
            .with_args(1, 'super-fast')

        self.switch.set_bond_link_speed(1, 'super-fast')

        assert_that(
            self.switch.get_bonds(),
            is_([Bond(1, link_speed='super-fast')])
        )

    def test_set_bond_description(self):
        self.real_switch_mock.should_receive("set_bond_description").once() \
            .with_args(312, 'bond-description')
        self.switch.set_bond_description(312, 'bond-description')

    def test_remove_bond_description(self):
        self.real_switch_mock.should_receive("remove_bond_description").once() \
            .with_args(312)
        self.switch.remove_bond_description(312)

    def test_set_bond_trunk_mode(self):
        self.real_switch_mock.should_receive("get_bonds").once().and_return(
            [Bond(1, interface=Interface())])
        self.switch.get_bonds()

        self.real_switch_mock.should_receive("set_bond_trunk_mode").once() \
            .with_args(1)

        self.switch.set_bond_trunk_mode(1)

        assert_that(
            self.switch.get_bonds(),
            is_([Bond(1, interface=Interface(port_mode=port_modes.TRUNK))])
        )

    def test_set_bond_access_mode(self):
        self.real_switch_mock.should_receive("get_bonds").once().and_return(
            [Bond(1, interface=Interface())])
        self.switch.get_bonds()

        self.real_switch_mock.should_receive("set_bond_access_mode").once() \
            .with_args(1)

        self.switch.set_bond_access_mode(1)

        assert_that(
            self.switch.get_bonds(),
            is_([Bond(1, interface=Interface(port_mode=port_modes.ACCESS))])
        )

    def test_add_bond_trunk_vlan_first(self):
        self.real_switch_mock.should_receive("add_bond_trunk_vlan").once() \
            .with_args(1, 2)

        self.switch.add_bond_trunk_vlan(1, 2)

        self.real_switch_mock.should_receive("get_bond").once().with_args(1) \
            .and_return(Bond(1))
        assert_that(self.switch.get_bond(1), is_(Bond(1)))
        assert_that(self.switch.get_bond(1), is_(Bond(1)))

    def test_add_bond_trunk_vlan_after_get_bonds(self):
        all_bonds = [Bond(1, interface=Interface()),
                     Bond(2, interface=Interface())]

        self.real_switch_mock.should_receive("get_bonds").once().and_return(
            all_bonds)
        assert_that(self.switch.get_bonds(), is_(all_bonds))

        self.real_switch_mock.should_receive("add_bond_trunk_vlan").once() \
            .with_args(1, 2)

        self.switch.add_bond_trunk_vlan(1, 2)

        assert_that(
            self.switch.get_bond(1),
            is_(Bond(1, interface=Interface(trunk_vlans=[2])))
        )
        assert_that(
            self.switch.get_bonds(),
            is_([
                Bond(1, interface=Interface(trunk_vlans=[2])),
                Bond(2, interface=Interface())
            ])
        )

    def test_remove_bond_trunk_vlan(self):
        all_bonds = [Bond(1, interface=Interface(trunk_vlans=[2])),
                     Bond(2, interface=Interface())]

        self.real_switch_mock.should_receive("get_bonds").once().and_return(
            all_bonds)
        assert_that(self.switch.get_bonds(), is_(all_bonds))

        self.real_switch_mock.should_receive("remove_bond_trunk_vlan").once() \
            .with_args(1, 2)

        self.switch.remove_bond_trunk_vlan(1, 2)

        assert_that(
            self.switch.get_bond(1),
            is_(Bond(1, interface=Interface(trunk_vlans=[])))
        )
        assert_that(
            self.switch.get_bonds(),
            is_([
                Bond(1, interface=Interface(trunk_vlans=[])),
                Bond(2, interface=Interface())
            ])
        )

    def test_configure_bond_native_vlan(self):
        self.real_switch_mock.should_receive("get_bonds").once() \
            .and_return([Bond(2, interface=Interface())])
        self.switch.get_bonds()

        self.real_switch_mock.should_receive("configure_bond_native_vlan").once() \
            .with_args(2, 20)

        self.switch.configure_bond_native_vlan(2, 20)

        assert_that(
            self.switch.get_bonds(),
            is_([Bond(2, interface=Interface(trunk_native_vlan=20))]))

    def test_remove_bond_native_vlan(self):
        self.real_switch_mock.should_receive("get_bonds").once() \
            .and_return([Bond(2, interface=Interface(trunk_native_vlan=20))])
        self.switch.get_bonds()

        self.real_switch_mock.should_receive("remove_bond_native_vlan").once() \
            .with_args(2)

        self.switch.remove_bond_native_vlan(2)

        assert_that(
            self.switch.get_bonds(),
            is_([Bond(2, interface=Interface(trunk_native_vlan=None))]))

    def test_edit_bond_spanning_tree(self):
        self.real_switch_mock.should_receive("edit_bond_spanning_tree").once() \
            .with_args(2, None)

        self.switch.edit_bond_spanning_tree(2)

    def test_add_vrrp_group(self):
        self.real_switch_mock.should_receive("get_vlans").once() \
            .and_return([Vlan(1)])
        self.switch.get_vlans()

        self.real_switch_mock.should_receive("add_vrrp_group").once() \
            .with_args(1, 2, None, None, None, None, None, None)

        self.switch.add_vrrp_group(1, 2)

        assert_that(
            self.switch.get_vlans(),
            is_([Vlan(1, vrrp_groups=[VrrpGroup(id=2)])]))

    def test_remove_vrrp_group(self):
        self.real_switch_mock.should_receive("get_vlans").once() \
            .and_return([Vlan(1, vrrp_groups=[VrrpGroup(id=2)])])
        self.switch.get_vlans()

        self.real_switch_mock.should_receive("remove_vrrp_group").once() \
            .with_args(1, 2)

        self.switch.remove_vrrp_group(1, 2)

        assert_that(
            self.switch.get_vlans(),
            is_([Vlan(1, vrrp_groups=[])]))

    def test_add_dhcp_relay_server(self):
        self.real_switch_mock.should_receive("get_vlans").once() \
            .and_return([Vlan(2)])
        self.switch.get_vlans()

        self.real_switch_mock.should_receive("add_dhcp_relay_server").once() \
            .with_args(2, '127.0.0.1')

        self.switch.add_dhcp_relay_server(2, '127.0.0.1')

        assert_that(
            self.switch.get_vlans(),
            is_([Vlan(2, dhcp_relay_servers=['127.0.0.1'])]))

    def test_enable_lldp(self):
        self.real_switch_mock.should_receive("enable_lldp").once() \
            .with_args('xe-1/0/2', True)

        self.switch.enable_lldp('xe-1/0/2', True)
