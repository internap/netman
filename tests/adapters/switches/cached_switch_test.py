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
from netaddr import IPAddress, IPNetwork

from netman.adapters.switches.cached import CachedSwitch
from netman.core.objects.access_groups import IN, OUT
from netman.core.objects.bond import Bond
from netman.core.objects.interface import Interface
from netman.core.objects.interface_states import OFF, ON
from netman.core.objects.port_modes import ACCESS, TRUNK, BOND_MEMBER
from netman.core.objects.switch_descriptor import SwitchDescriptor
from netman.core.objects.unicast_rpf_modes import STRICT
from netman.core.objects.vlan import Vlan
from netman.core.objects.vrrp_group import VrrpGroup

from tests import ExactIpNetwork


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

    def test_get_vlan(self):
        a_vlan = Vlan(1, 'first')

        self.real_switch_mock.should_receive("get_vlan").with_args(1).once().and_return(
            a_vlan)
        assert_that(self.switch.get_vlan(1), is_(a_vlan))
        assert_that(self.switch.get_vlan(1), is_(a_vlan))

    def test_get_vlan_after_list(self):
        all_vlans = [Vlan(1, 'first'), Vlan(2, 'second')]

        self.real_switch_mock.should_receive("get_vlans").once().and_return(
            all_vlans)
        assert_that(self.switch.get_vlans(), is_(all_vlans))

        assert_that(self.switch.get_vlan(1), is_(all_vlans[0]))
        assert_that(self.switch.get_vlan(2), is_(all_vlans[1]))

    def test_get_vlan_interfaces(self):
        vlan_interfaces = ["port-channel 1", "port-channel 3", "ethernet 0/2"]

        self.real_switch_mock.should_receive("get_vlan_interfaces").with_args(1).once().and_return(
                vlan_interfaces)
        assert_that(self.switch.get_vlan_interfaces(1), is_(vlan_interfaces))
        assert_that(self.switch.get_vlan_interfaces(1), is_(vlan_interfaces))

    def test_access_new_vlan_after_vlan_list(self):
        all_vlans = [Vlan(1, 'first'), Vlan(2, 'second')]
        vlan3 = Vlan(3, 'third', ips=[IPNetwork("2.2.2.2/24")])

        self.real_switch_mock.should_receive("get_vlans").once().and_return(all_vlans)

        self.real_switch_mock.should_receive("add_ip_to_vlan").once().with_args(3, ExactIpNetwork("2.2.2.2/24"))
        self.real_switch_mock.should_receive("get_vlan").with_args(3).once().and_return(vlan3)

        assert_that(self.switch.get_vlans(), is_(all_vlans))

        self.switch.add_ip_to_vlan(3, IPNetwork("2.2.2.2/24"))

        assert_that(self.switch.get_vlan(3), is_(vlan3))

    def test_get_vlans(self):
        all_vlans = [Vlan(1, 'first'), Vlan(2, 'second')]

        self.real_switch_mock.should_receive("get_vlans").once().and_return(
            all_vlans)
        assert_that(self.switch.get_vlans(), is_(all_vlans))
        assert_that(self.switch.get_vlans(), is_(all_vlans))

    def test_add_vlan_first(self):
        all_vlans = [Vlan(1), Vlan(2), Vlan(123, name='allo')]

        self.real_switch_mock.should_receive("add_vlan").once().with_args(123, name='allo')
        self.switch.add_vlan(123, 'allo')

        self.real_switch_mock.should_receive("get_vlans").once().and_return(
            all_vlans)
        assert_that(self.switch.get_vlans(), is_(all_vlans))
        assert_that(self.switch.get_vlans(), is_(all_vlans))

    def test_add_vlan(self):
        self.real_switch_mock.should_receive("add_vlan").once().with_args(123)
        self.switch.add_vlan(123)
        self.real_switch_mock.should_receive("get_vlan").once().with_args(123).and_return(Vlan(number=123, name=""))

        assert_that(self.switch.get_vlan(123).name, is_(""))

    def test_after_get_vlans_was_cached_adding_new_vlans_will_trigger_single_get_vlans_to_fill_the_gaps(self):
        all_vlans = [Vlan(1)]

        self.real_switch_mock.should_receive("get_vlans").once().ordered().and_return(all_vlans)
        assert_that(self.switch.get_vlans(), is_(all_vlans))

        self.real_switch_mock.should_receive("add_vlan").once().with_args(10)
        self.switch.add_vlan(10)
        self.real_switch_mock.should_receive("add_vlan").once().with_args(11)
        self.switch.add_vlan(11)
        self.real_switch_mock.should_receive("add_vlan").once().with_args(12)
        self.switch.add_vlan(12)

        self.real_switch_mock.should_receive("get_vlan").with_args(10).once().and_return(Vlan(10))
        self.real_switch_mock.should_receive("get_vlan").with_args(11).once().and_return(Vlan(11))
        self.real_switch_mock.should_receive("get_vlan").with_args(12).once().and_return(Vlan(12))
        assert_that(self.switch.get_vlans(), is_([Vlan(1), Vlan(10), Vlan(11), Vlan(12)]))
        assert_that(self.switch.get_vlans(), is_([Vlan(1), Vlan(10), Vlan(11), Vlan(12)]))

    def test_add_vlan_after_get_vlans(self):
        all_vlans = [Vlan(1), Vlan(2)]

        self.real_switch_mock.should_receive("get_vlans").once().ordered().and_return(
            all_vlans)
        assert_that(self.switch.get_vlans(), is_(all_vlans))
        assert_that(self.switch.get_vlans(), is_(all_vlans))

        self.real_switch_mock.should_receive("add_vlan").once().with_args(123, name='allo')
        self.switch.add_vlan(123, 'allo')

        self.real_switch_mock.should_receive("get_vlan").once().ordered().and_return(Vlan(123, name='allo'))
        assert_that(self.switch.get_vlans(), is_(all_vlans+[Vlan(123, name='allo')]))
        assert_that(self.switch.get_vlans(), is_(all_vlans+[Vlan(123, name='allo')]))

    def test_remove_vlan(self):
        self.real_switch_mock.should_receive("get_vlans").once().and_return(
            [Vlan(1), Vlan(2)])
        self.switch.get_vlans()

        self.real_switch_mock.should_receive("remove_vlan").once().with_args(1)
        self.switch.remove_vlan(1)

        assert_that(self.switch.get_vlans(), is_([Vlan(2)]))

    def test_remove_vlan_alone(self):
        self.real_switch_mock.should_receive("remove_vlan").once().with_args(1)
        self.switch.remove_vlan(1)

    def test_get_interfaces(self):
        all_interfaces = [Interface('xe-1/0/1'), Interface('xe-1/0/2')]

        self.real_switch_mock.should_receive("get_interfaces").once() \
            .and_return(all_interfaces)
        assert_that(self.switch.get_interfaces(), is_(all_interfaces))
        assert_that(self.switch.get_interfaces(), is_(all_interfaces))

    def test_get_interface(self):
        interface = Interface('xe-1/0/1')

        self.real_switch_mock.should_receive("get_interface").with_args("xe-1/0/1").once() \
            .and_return(interface)
        assert_that(self.switch.get_interface('xe-1/0/1'), is_(interface))
        assert_that(self.switch.get_interface('xe-1/0/1'), is_(interface))

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

    def test_reset_interface_invalidate_cache(self):
        self.real_switch_mock.should_receive("get_interface").with_args("eth0").once().\
            and_return([Interface('eth0')])
        self.switch.get_interface('eth0')

        self.real_switch_mock.should_receive("reset_interface").with_args('eth0')
        self.switch.reset_interface('eth0')

        self.real_switch_mock.should_receive("get_interface").with_args("eth0").once(). \
            and_return([Interface('eth0')])
        self.switch.get_interface('eth0')

    def test_unset_interface_access_vlan(self):
        self.real_switch_mock.should_receive("get_interfaces").once().and_return(
            [Interface('eth0', access_vlan=123)])
        self.switch.get_interfaces()

        self.real_switch_mock.should_receive("unset_interface_access_vlan").once() \
            .with_args('eth0')

        self.switch.unset_interface_access_vlan('eth0')

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
            is_([Interface('eth0', port_mode=TRUNK)])
        )

    def test_set_access_mode(self):
        self.real_switch_mock.should_receive("get_interfaces").once().and_return(
            [Interface('eth0', trunk_native_vlan=1200, trunk_vlans=[1, 2, 3])])
        self.switch.get_interfaces()

        self.real_switch_mock.should_receive("set_access_mode").once() \
            .with_args('eth0')

        self.switch.set_access_mode('eth0')

        assert_that(
            self.switch.get_interfaces(),
            is_([Interface('eth0', port_mode=ACCESS,
                           trunk_native_vlan=None, trunk_vlans=[])])
        )

    def test_add_trunk_vlan(self):
        self.real_switch_mock.should_receive("get_interfaces").once() \
            .and_return([Interface('xe-1/0/2')])
        assert_that(self.switch.get_interfaces(), is_([Interface('xe-1/0/2')]))

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

    def test_remove_trunk_vlan_on_interface_not_in_cache(self):
        self.real_switch_mock.should_receive("remove_trunk_vlan").once() \
            .with_args('xe-1/0/2', 1)

        self.switch.remove_trunk_vlan('xe-1/0/2', 1)

    def test_set_interface_state_off(self):
        self.real_switch_mock.should_receive("get_interfaces").once() \
            .and_return([Interface('xe-1/0/2', shutdown=False)])
        self.switch.get_interfaces()

        self.real_switch_mock.should_receive("set_interface_state").once() \
            .with_args('xe-1/0/2', OFF)

        self.switch.set_interface_state('xe-1/0/2', OFF)

        assert_that(
            self.switch.get_interfaces(),
            is_([Interface('xe-1/0/2', shutdown=True)]))

    def test_set_interface_state_on(self):
        self.real_switch_mock.should_receive("get_interfaces").once() \
            .and_return([Interface('xe-1/0/2')])
        self.switch.get_interfaces()

        self.real_switch_mock.should_receive("set_interface_state").once() \
            .with_args('xe-1/0/2', ON)

        self.switch.set_interface_state('xe-1/0/2', ON)

        assert_that(
            self.switch.get_interfaces(),
            is_([Interface('xe-1/0/2', shutdown=False)]))

    def test_unset_interface_state(self):
        self.real_switch_mock.should_receive("get_interfaces").once().and_return([Interface('xe-1/0/2')])
        self.switch.get_interfaces()

        self.real_switch_mock.should_receive("unset_interface_state").once().with_args('xe-1/0/2')

        self.real_switch_mock.should_receive("get_interface").once() \
            .with_args('xe-1/0/2').and_return(Interface('xe-1/0/2', shutdown=False))

        self.switch.unset_interface_state('xe-1/0/2')

        assert_that(self.switch.get_interface('xe-1/0/2').shutdown, is_(False))

    def test_set_interface_auto_negotiation_state_off(self):
        self.real_switch_mock.should_receive("get_interfaces").once() \
            .and_return([Interface('xe-1/0/2', auto_negotiation=True)])
        self.switch.get_interfaces()

        self.real_switch_mock.should_receive("set_interface_auto_negotiation_state").once() \
            .with_args('xe-1/0/2', OFF)

        self.switch.set_interface_auto_negotiation_state('xe-1/0/2', OFF)

        assert_that(
            self.switch.get_interfaces(),
            is_([Interface('xe-1/0/2', auto_negotiation=False)]))

    def test_set_interface_auto_negotiation_state_on(self):
        self.real_switch_mock.should_receive("get_interfaces").once() \
            .and_return([Interface('xe-1/0/2')])
        self.switch.get_interfaces()

        self.real_switch_mock.should_receive("set_interface_auto_negotiation_state").once() \
            .with_args('xe-1/0/2', ON)

        self.switch.set_interface_auto_negotiation_state('xe-1/0/2', ON)

        assert_that(
            self.switch.get_interfaces(),
            is_([Interface('xe-1/0/2', auto_negotiation=True)]))

    def test_unset_interface_auto_negotiation_state(self):
        self.real_switch_mock.should_receive("get_interfaces").once()\
            .and_return([Interface('xe-1/0/2', auto_negotiation=False)])
        self.switch.get_interfaces()

        self.real_switch_mock.should_receive("unset_interface_auto_negotiation_state").once().with_args('xe-1/0/2')

        self.switch.unset_interface_auto_negotiation_state('xe-1/0/2')

        assert_that(self.switch.get_interface('xe-1/0/2').auto_negotiation, is_(None))

    def test_set_interface_native_vlan(self):
        self.real_switch_mock.should_receive("get_interfaces").once() \
            .and_return([Interface('xe-1/0/2')])
        self.switch.get_interfaces()

        self.real_switch_mock.should_receive("set_interface_native_vlan").once() \
            .with_args('xe-1/0/2', 20)

        self.switch.set_interface_native_vlan('xe-1/0/2', 20)

        assert_that(
            self.switch.get_interfaces(),
            is_([Interface('xe-1/0/2', trunk_native_vlan=20)]))

    def test_unset_interface_native_vlan(self):
        self.real_switch_mock.should_receive("get_interfaces").once() \
            .and_return([Interface('xe-1/0/2', trunk_native_vlan=20)])
        self.switch.get_interfaces()

        self.real_switch_mock.should_receive("unset_interface_native_vlan").once() \
            .with_args('xe-1/0/2')

        self.switch.unset_interface_native_vlan('xe-1/0/2')

        assert_that(
            self.switch.get_interfaces(),
            is_([Interface('xe-1/0/2', trunk_native_vlan=None)]))

    def test_add_ip_to_vlan(self):
        self.real_switch_mock.should_receive("get_vlans").once() \
            .and_return([Vlan(2)])
        self.switch.get_vlans()

        self.real_switch_mock.should_receive("add_ip_to_vlan").once() \
            .with_args(2, ExactIpNetwork("2.2.2.2/24"))

        self.switch.add_ip_to_vlan(2, IPNetwork("2.2.2.2/24"))

        assert_that(
            self.switch.get_vlans(),
            is_([Vlan(2, ips=[ExactIpNetwork("2.2.2.2/24")])]))

    def test_remove_ip_from_vlan(self):
        self.real_switch_mock.should_receive("get_vlans").once() \
            .and_return([Vlan(2, ips=[IPNetwork("2.2.2.2/24"),
                                      IPNetwork("1.1.1.1/24"),
                                      IPNetwork("1.1.1.2/24"),
                                      IPNetwork("1.1.1.3/24"),
                                      IPNetwork("1.1.1.4/24")])])
        self.switch.get_vlans()

        self.real_switch_mock.should_receive("remove_ip_from_vlan").once() \
            .with_args(2, ExactIpNetwork("1.1.1.2/24"))

        self.switch.remove_ip_from_vlan(2, IPNetwork("1.1.1.2/24"))

        assert_that(
            self.switch.get_vlans(),
            is_([Vlan(2, ips=[ExactIpNetwork("2.2.2.2/24"),
                              ExactIpNetwork("1.1.1.1/24"),
                              ExactIpNetwork("1.1.1.3/24"),
                              ExactIpNetwork("1.1.1.4/24")])]))

    def test_set_vlan_access_group(self):
        self.real_switch_mock.should_receive("get_vlans").once() \
            .and_return([Vlan(123)])
        self.switch.get_vlans()

        self.real_switch_mock.should_receive("set_vlan_access_group").once() \
            .with_args(123, IN, 'vlan-access-group')

        self.switch.set_vlan_access_group(123, IN, 'vlan-access-group')

        assert_that(
            self.switch.get_vlans(),
            is_([Vlan(123, access_group_in='vlan-access-group')]))

    def test_unset_vlan_access_group(self):
        self.real_switch_mock.should_receive("get_vlans").once() \
            .and_return([Vlan(123, access_group_out='vlan-access-group')])
        self.switch.get_vlans()

        self.real_switch_mock.should_receive("unset_vlan_access_group").once() \
            .with_args(123, OUT)

        self.switch.unset_vlan_access_group(123, OUT)

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

    def test_unset_vlan_vrf(self):
        self.real_switch_mock.should_receive("get_vlans").once() \
            .and_return([Vlan(123, vrf_forwarding='vrf-name')])
        self.switch.get_vlans()

        self.real_switch_mock.should_receive("unset_vlan_vrf").once() \
            .with_args(123)

        self.switch.unset_vlan_vrf(123)

        assert_that(
            self.switch.get_vlans(),
            is_([Vlan(123, vrf_forwarding=None)]))

    def test_set_interface_description(self):
        self.real_switch_mock.should_receive("set_interface_description").once() \
            .with_args('xe-1/0/2', 'interface-description')
        self.switch.set_interface_description('xe-1/0/2', 'interface-description')

    def test_unset_interface_description(self):
        self.real_switch_mock.should_receive("unset_interface_description").once() \
            .with_args('xe-1/0/2')
        self.switch.unset_interface_description('xe-1/0/2')

    def test_set_interface_spanning_tree(self):
        self.real_switch_mock.should_receive("edit_interface_spanning_tree").once() \
            .with_args('xe-1/0/2', edge=None)

        self.switch.edit_interface_spanning_tree('xe-1/0/2')

    def test_add_bond_first(self):
        all_bonds = [Bond(1), Bond(2), Bond(123)]

        self.real_switch_mock.should_receive("add_bond").once().with_args(123)
        self.switch.add_bond(123)

        self.real_switch_mock.should_receive("get_bond").once().and_return(Bond(123))
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

        self.real_switch_mock.should_receive("get_bond").once().and_return(Bond(123))
        assert_that(self.switch.get_bond(123).number, is_(123))

        assert_that(
            self.switch.get_bonds(),
            is_(all_bonds+[Bond(123)]))

    def test_remove_bond(self):
        self.real_switch_mock.should_receive("get_bonds").once().and_return(
            [Bond(1), Bond(2)])
        self.switch.get_bonds()

        self.real_switch_mock.should_receive("remove_bond").once().with_args(2)
        self.switch.remove_bond(2)

        assert_that(self.switch.get_bonds(), is_([Bond(1)]))

    def test_remove_bond_alone(self):
        self.real_switch_mock.should_receive("remove_bond").once().with_args(2)
        self.switch.remove_bond(2)

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
            .and_return([Bond(1)])
        self.real_switch_mock.should_receive("get_interfaces").once() \
            .and_return([Interface('xe-1/0/2')])

        self.switch.get_bonds()
        self.switch.get_interfaces()

        self.real_switch_mock.should_receive("add_interface_to_bond").once() \
            .with_args('xe-1/0/2', 1)

        self.switch.add_interface_to_bond('xe-1/0/2', 1)

        self.real_switch_mock.should_receive("get_interfaces").once() \
            .and_return([Interface('xe-1/0/2', bond_master=1, port_mode=BOND_MEMBER)])

        assert_that(
            self.switch.get_bonds(),
            is_([Bond(1, members=['xe-1/0/2'])]))
        assert_that(
            self.switch.get_interfaces(),
            is_([Interface('xe-1/0/2', bond_master=1, port_mode=BOND_MEMBER)]))

    def test_remove_interface_from_bond(self):
        self.real_switch_mock.should_receive("get_bonds").once() \
            .and_return([Bond(1, members=['xe-1/0/2'])])
        self.real_switch_mock.should_receive("get_interfaces").once() \
            .and_return([Interface('xe-1/0/2', bond_master=1)])

        self.switch.get_bonds()
        self.switch.get_interfaces()

        self.real_switch_mock.should_receive("remove_interface_from_bond").once() \
            .with_args('xe-1/0/2')

        self.switch.remove_interface_from_bond('xe-1/0/2')

        self.real_switch_mock.should_receive("get_interfaces").once() \
            .and_return([Interface('xe-1/0/2', bond_master=None, port_mode=ACCESS)])

        assert_that(
            self.switch.get_bonds(),
            is_([Bond(1, members=[])]))
        assert_that(
            self.switch.get_interfaces(),
            is_([Interface('xe-1/0/2', bond_master=None, port_mode=ACCESS)]))

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

    def test_unset_bond_description(self):
        self.real_switch_mock.should_receive("unset_bond_description").once() \
            .with_args(312)
        self.switch.unset_bond_description(312)

    def test_set_bond_trunk_mode(self):
        self.real_switch_mock.should_receive("get_bonds").once().and_return(
            [Bond(1)])
        self.switch.get_bonds()

        self.real_switch_mock.should_receive("set_bond_trunk_mode").once() \
            .with_args(1)

        self.switch.set_bond_trunk_mode(1)

        assert_that(
            self.switch.get_bonds(),
            is_([Bond(1, port_mode=TRUNK)])
        )

    def test_set_bond_access_mode(self):
        self.real_switch_mock.should_receive("get_bonds").once().and_return(
            [Bond(1)])
        self.switch.get_bonds()

        self.real_switch_mock.should_receive("set_bond_access_mode").once() \
            .with_args(1)

        self.switch.set_bond_access_mode(1)

        assert_that(
            self.switch.get_bonds(),
            is_([Bond(1, port_mode=ACCESS)])
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
        all_bonds = [Bond(1),
                     Bond(2)]

        self.real_switch_mock.should_receive("get_bonds").once().and_return(
            all_bonds)
        assert_that(self.switch.get_bonds(), is_(all_bonds))

        self.real_switch_mock.should_receive("add_bond_trunk_vlan").once() \
            .with_args(1, 2)

        self.switch.add_bond_trunk_vlan(1, 2)

        assert_that(
            self.switch.get_bond(1),
            is_(Bond(1, trunk_vlans=[2]))
        )
        assert_that(
            self.switch.get_bonds(),
            is_([
                Bond(1, trunk_vlans=[2]),
                Bond(2)
            ])
        )

    def test_remove_bond_trunk_vlan(self):
        all_bonds = [Bond(1, trunk_vlans=[2]),
                     Bond(2)]

        self.real_switch_mock.should_receive("get_bonds").once().and_return(
            all_bonds)
        assert_that(self.switch.get_bonds(), is_(all_bonds))

        self.real_switch_mock.should_receive("remove_bond_trunk_vlan").once() \
            .with_args(1, 2)

        self.switch.remove_bond_trunk_vlan(1, 2)

        assert_that(
            self.switch.get_bond(1),
            is_(Bond(1, trunk_vlans=[]))
        )
        assert_that(
            self.switch.get_bonds(),
            is_([
                Bond(1, trunk_vlans=[]),
                Bond(2)
            ])
        )

    def test_remove_bond_trunk_vlan_on_bond_not_in_cache(self):
        self.real_switch_mock.should_receive("remove_bond_trunk_vlan").once() \
            .with_args(1, 2)

        self.switch.remove_bond_trunk_vlan(1, 2)

    def test_set_bond_native_vlan(self):
        self.real_switch_mock.should_receive("get_bonds").once() \
            .and_return([Bond(2)])
        self.switch.get_bonds()

        self.real_switch_mock.should_receive("set_bond_native_vlan").once() \
            .with_args(2, 20)

        self.switch.set_bond_native_vlan(2, 20)

        assert_that(
            self.switch.get_bonds(),
            is_([Bond(2, trunk_native_vlan=20)]))

    def test_unset_bond_native_vlan(self):
        self.real_switch_mock.should_receive("get_bonds").once() \
            .and_return([Bond(2, trunk_native_vlan=20)])
        self.switch.get_bonds()

        self.real_switch_mock.should_receive("unset_bond_native_vlan").once() \
            .with_args(2)

        self.switch.unset_bond_native_vlan(2)

        assert_that(
            self.switch.get_bonds(),
            is_([Bond(2, trunk_native_vlan=None)]))

    def test_edit_bond_spanning_tree(self):
        self.real_switch_mock.should_receive("edit_bond_spanning_tree").once() \
            .with_args(2, edge=None)

        self.switch.edit_bond_spanning_tree(2)

    def test_add_vrrp_group(self):
        self.real_switch_mock.should_receive("get_vlans").once() \
            .and_return([Vlan(1)])
        self.switch.get_vlans()

        self.real_switch_mock.should_receive("add_vrrp_group").once() \
            .with_args(1, 2, ips=None, priority=23, hello_interval=None,
                       dead_interval=None, track_id=None, track_decrement=None)

        self.switch.add_vrrp_group(1, 2, priority=23)

        assert_that(
            self.switch.get_vlans(),
            is_([Vlan(1, vrrp_groups=[VrrpGroup(id=2, priority=23)])]))

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
            .with_args(2, IPAddress("1.2.3.4"))

        self.switch.add_dhcp_relay_server(2, IPAddress("1.2.3.4"))

        assert_that(
            self.switch.get_vlans(),
            is_([Vlan(2, dhcp_relay_servers=[IPAddress("1.2.3.4")])]))

    def test_set_interface_lldp_state(self):
        self.real_switch_mock.should_receive("set_interface_lldp_state").once() \
            .with_args('xe-1/0/2', True)

        self.switch.set_interface_lldp_state('xe-1/0/2', True)

    def test_set_vlan_arp_routing_state(self):
        self.real_switch_mock.should_receive("get_vlans").once() \
            .and_return([Vlan(2)])
        self.switch.get_vlans()

        self.real_switch_mock.should_receive('set_vlan_arp_routing_state').once() \
            .with_args(2, OFF)

        self.switch.set_vlan_arp_routing_state(2, OFF)

        assert_that(
            self.switch.get_vlans(),
            is_([Vlan(2, arp_routing=False)]))

    def test_set_vlan_icmp_redirects_state(self):
        self.real_switch_mock.should_receive("get_vlans").once() \
            .and_return([Vlan(2)])
        self.switch.get_vlans()

        self.real_switch_mock.should_receive('set_vlan_icmp_redirects_state').once() \
            .with_args(2, False)

        self.switch.set_vlan_icmp_redirects_state(2, False)

        assert_that(
            self.switch.get_vlans(),
            is_([Vlan(2, icmp_redirects=False)]))

    def test_set_vlan_unicast_rpf_mode(self):
        self.real_switch_mock.should_receive("get_vlans").once() \
            .and_return([Vlan(2)])
        self.switch.get_vlans()

        self.real_switch_mock.should_receive('set_vlan_unicast_rpf_mode').once() \
            .with_args(2, STRICT)

        self.switch.set_vlan_unicast_rpf_mode(2, STRICT)

        assert_that(
            self.switch.get_vlans(),
            is_([Vlan(2, unicast_rpf_mode=STRICT)]))

    def test_unset_vlan_unicast_rpf_mode(self):
        self.real_switch_mock.should_receive("get_vlans").once() \
            .and_return([Vlan(2, unicast_rpf_mode=STRICT)])
        self.switch.get_vlans()

        self.real_switch_mock.should_receive('unset_vlan_unicast_rpf_mode').once() \
            .with_args(2)

        self.switch.unset_vlan_unicast_rpf_mode(2)

        assert_that(
            self.switch.get_vlans(),
            is_([Vlan(2, unicast_rpf_mode=None)]))

    def test_get_versions(self):
        self.real_switch_mock.should_receive("get_versions").once().and_return({"v": "1.0"})

        result1 = self.switch.get_versions()
        result2 = self.switch.get_versions()

        assert_that(result1, is_({"v": "1.0"}))
        assert_that(result2, is_({"v": "1.0"}))

    def test_set_interface_mtu(self):
        self.real_switch_mock.should_receive("get_interfaces").once() \
            .and_return([Interface('xe-1/0/2')])
        self.switch.get_interfaces()

        self.real_switch_mock.should_receive("set_interface_mtu").once() \
            .with_args('xe-1/0/2', 5000)

        self.switch.set_interface_mtu('xe-1/0/2', 5000)

        assert_that(
            self.switch.get_interfaces(),
            is_([Interface('xe-1/0/2', mtu=5000)]))

    def test_unset_interface_mtu(self):
        self.real_switch_mock.should_receive("get_interfaces").once() \
            .and_return([Interface('xe-1/0/2', mtu=5000)])
        self.switch.get_interfaces()

        self.real_switch_mock.should_receive("unset_interface_mtu").once() \
            .with_args('xe-1/0/2')

        self.switch.unset_interface_mtu('xe-1/0/2')

        assert_that(
            self.switch.get_interfaces(),
            is_([Interface('xe-1/0/2', mtu=None)]))

    def test_set_bond_mtu(self):
        self.real_switch_mock.should_receive("get_bonds").once() \
            .and_return([Bond('xe-1/0/2')])
        self.switch.get_bonds()

        self.real_switch_mock.should_receive("set_bond_mtu").once() \
            .with_args('xe-1/0/2', 5000)

        self.switch.set_bond_mtu('xe-1/0/2', 5000)

        assert_that(
            self.switch.get_bonds(),
            is_([Bond('xe-1/0/2', mtu=5000)]))

    def test_unset_bond_mtu(self):
        self.real_switch_mock.should_receive("get_bonds").once() \
            .and_return([Bond('xe-1/0/2', mtu=5000)])
        self.switch.get_bonds()

        self.real_switch_mock.should_receive("unset_bond_mtu").once() \
            .with_args('xe-1/0/2')

        self.switch.unset_bond_mtu('xe-1/0/2')

        assert_that(
            self.switch.get_bonds(),
            is_([Bond('xe-1/0/2', mtu=None)]))
