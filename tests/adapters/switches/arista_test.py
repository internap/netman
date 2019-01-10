import unittest

import mock
import pyeapi
from flexmock import flexmock, flexmock_teardown
from hamcrest import assert_that, has_length, equal_to, is_, contains_string
from netaddr import IPNetwork, IPAddress
from pyeapi.eapilib import CommandError

from netman.adapters.switches import arista
from netman.adapters.switches.arista import Arista, parse_vlan_ranges
from netman.core.objects.exceptions import BadVlanNumber, VlanAlreadyExist, BadVlanName, UnknownVlan, \
    UnknownIP, IPNotAvailable, IPAlreadySet, UnknownInterface, UnknownDhcpRelayServer, DhcpRelayServerAlreadyExists, \
    UnknownBond, VarpAlreadyExistsForVlan, VarpDoesNotExistForVlan, BadLoadIntervalNumber, BadMplsIpState
from netman.core.objects.interface import Interface
from netman.core.objects.interface_states import ON, OFF
from netman.core.objects.port_modes import TRUNK
from netman.core.objects.switch_descriptor import SwitchDescriptor
from netman.core.objects.vlan import Vlan
from tests import ignore_deprecation_warnings
from tests.fixtures.arista import vlan_data, result_payload, interface_vlan_data, show_interfaces, interface_address, \
    switchport_data, interface_data


class AristaTest(unittest.TestCase):
    def setUp(self):
        self.switch = Arista(SwitchDescriptor(model='arista', hostname="my.hostname"), transport="Eytch tea tea pee")
        self.switch.node = flexmock()

    def tearDown(self):
        flexmock_teardown()

    def test_get_vlans(self):
        vlans_payload = {'vlans': {'1': vlan_data(name='default'),
                                   '123': vlan_data(name='VLAN0123'),
                                   '456': vlan_data(name='Patate'),
                                   '789': vlan_data(name="new_interface_vlan_without_ip"),
                                   '1234': vlan_data(name="interface_with_removed_ip"),
                                   '1235': vlan_data(name="vlan_with_load_interval"),
                                   '1236': vlan_data(name="vlan_with_no_mpls_ip")}}

        interfaces_payload = show_interfaces(
            interface_vlan_data(name="Vlan456", interfaceAddress=[interface_address(
                primaryIp={'address': '192.168.11.1', 'maskLen': 29},
                secondaryIpsOrderedList=[
                    {'address': '192.168.13.1', 'maskLen': 29},
                    {'address': '192.168.12.1', 'maskLen': 29}
                ]
            )]),
            interface_vlan_data(name="Vlan789", interfaceAddress=[interface_address(
                primaryIp={'address': '0.0.0.0', 'maskLen': 0},
                secondaryIpsOrderedList=[]
            )]),
            interface_vlan_data(name="Vlan1234", interfaceAddress=[]),
        )

        self.switch.node.should_receive("enable") \
            .with_args(["show vlan", "show interfaces"], strict=True) \
            .and_return([result_payload(result=vlans_payload),
                         result_payload(result=interfaces_payload)])

        self.switch.node.should_receive("get_config").with_args(
            params="interfaces Vlan1 Vlan123 Vlan1234 Vlan1235 Vlan1236 Vlan456 Vlan789").once() \
            .and_return(['interface Vlan123',
                         '   ip helper-address 10.10.30.200',
                         '   ip helper-address 10.10.30.201',
                         'interface Vlan456',
                         '   ip virtual-router address 10.10.77.1',
                         '   ip virtual-router address 10.10.77.200/28',
                         'interface Vlan789',
                         '   ip virtual-router address 10.10.77.3',
                         '   ip helper-address 10.10.30.203',
                         '   ip helper-address 10.10.30.204',
                         '   ip helper-address 10.10.30.205',
                         'interface Vlan1234',
                         'interface Vlan1235',
                         '   load-interval 30',
                         'interface Vlan1236',
                         '   no mpls ip'])

        vlan1, vlan123, vlan456, vlan789, vlan1234, vlan1235, vlan1236 = self.switch.get_vlans()

        assert_that(vlan1.number, equal_to(1))
        assert_that(vlan1.name, equal_to('default'))
        assert_that(vlan1.ips, has_length(0))

        assert_that(vlan123.number, equal_to(123))
        assert_that(vlan123.name, equal_to(None))
        assert_that(vlan123.ips, has_length(0))
        dhcp_ip1, dhcp_ip2 = vlan123.dhcp_relay_servers
        assert_that(dhcp_ip1, is_(IPAddress('10.10.30.200')))
        assert_that(dhcp_ip2, is_(IPAddress('10.10.30.201')))
        assert_that(vlan123.varp_ips, has_length(0))

        assert_that(vlan456.number, equal_to(456))
        assert_that(vlan456.name, equal_to('Patate'))
        assert_that(vlan456.name, equal_to('Patate'))
        ip11, ip13, ip12 = vlan456.ips
        assert_that(ip11, is_(IPNetwork("192.168.11.1/29")))
        assert_that(ip13, is_(IPNetwork("192.168.13.1/29")))
        assert_that(ip12, is_(IPNetwork("192.168.12.1/29")))
        assert_that(vlan456.dhcp_relay_servers, has_length(0))
        varp1, varp2 = vlan456.varp_ips
        assert_that(varp1, is_(IPNetwork("10.10.77.1/32")))
        assert_that(varp2, is_(IPNetwork("10.10.77.200/28")))

        assert_that(vlan789.ips, has_length(0))
        dhcp_ip1, dhcp_ip2, dhcp_ip3 = vlan789.dhcp_relay_servers
        assert_that(dhcp_ip1, is_(IPAddress('10.10.30.203')))
        assert_that(dhcp_ip2, is_(IPAddress('10.10.30.204')))
        assert_that(dhcp_ip3, is_(IPAddress('10.10.30.205')))
        assert_that(vlan789.varp_ips, has_length(1))
        varp_ip = vlan789.varp_ips[0]
        assert_that(varp_ip, is_(IPNetwork('10.10.77.3/32')))

        assert_that(vlan1234.ips, has_length(0))
        assert_that(vlan1234.dhcp_relay_servers, has_length(0))
        assert_that(vlan1234.varp_ips, has_length(0))

        assert_that(vlan1235.number, equal_to(1235))
        assert_that(vlan1235.load_interval, equal_to(30))
        assert_that(vlan1235.mpls_ip, equal_to(True))

        assert_that(vlan1236.number, equal_to(1236))
        assert_that(vlan1236.mpls_ip, equal_to(False))

    def test_get_vlan(self):
        vlans_payload = {'vlans': {'456': vlan_data(name='Patate')}}

        interfaces_payload = show_interfaces(
            interface_vlan_data(name="Vlan456", interfaceAddress=[interface_address(
                primaryIp={'address': '192.168.11.1', 'maskLen': 29},
                secondaryIpsOrderedList=[
                    {'address': '192.168.13.1', 'maskLen': 29},
                    {'address': '192.168.12.1', 'maskLen': 29}
                ]
            )])
        )

        self.switch.node.should_receive("enable") \
            .with_args(["show vlan 456", "show interfaces Vlan456"], strict=True) \
            .and_return([result_payload(result=vlans_payload),
                         result_payload(result=interfaces_payload)])

        self.switch.node.should_receive("get_config").with_args(params="interfaces Vlan456").once() \
            .and_return(['interface Vlan456',
                         '   ip helper-address 10.10.30.200',
                         '   ip virtual-router address 10.10.77.1',
                         '   ip helper-address 10.10.30.201',
                         '   ip virtual-router address 10.10.77.2/28',
                         '   load-interval 30',
                         '   no mpls ip'])

        vlan = self.switch.get_vlan(456)

        assert_that(vlan.number, equal_to(456))
        assert_that(vlan.name, equal_to('Patate'))
        assert_that(vlan.load_interval, equal_to(30))
        assert_that(vlan.mpls_ip, equal_to(False))
        ip11, ip13, ip12 = vlan.ips
        assert_that(ip11, is_(IPNetwork("192.168.11.1/29")))
        assert_that(ip13, is_(IPNetwork("192.168.13.1/29")))
        assert_that(ip12, is_(IPNetwork("192.168.12.1/29")))
        varp1, varp2 = vlan.varp_ips
        assert_that(varp1, is_(IPNetwork("10.10.77.1/32")))
        assert_that(varp2, is_(IPNetwork("10.10.77.2/28")))

        helper_addr1, helper_addr2 = vlan.dhcp_relay_servers
        assert_that(helper_addr1, is_(IPAddress('10.10.30.200')))
        assert_that(helper_addr2, is_(IPAddress('10.10.30.201')))

    def test_get_vlan_invalid_ip_does_not_fail(self):
        vlans_payload = {'vlans': {'456': vlan_data(name='Patate')}}

        interfaces_payload = show_interfaces(
            interface_vlan_data(name="Vlan456")
        )

        self.switch.node.should_receive("enable") \
            .with_args(["show vlan 456", "show interfaces Vlan456"], strict=True) \
            .and_return([result_payload(result=vlans_payload),
                         result_payload(result=interfaces_payload)])

        self.switch.node.should_receive("get_config").with_args(params="interfaces Vlan456").once() \
            .and_return(['interface Vlan456',
                         '   ip helper-address say_what',
                         '   ip helper-address 10.10.30.201'])

        vlan = self.switch.get_vlan(456)

        assert_that(vlan.number, equal_to(456))
        assert_that(vlan.dhcp_relay_servers, has_length(1))
        assert_that(vlan.dhcp_relay_servers[0], is_(IPAddress('10.10.30.201')))

    def test_get_vlan_doesnt_exist(self):
        self.switch.node.should_receive("enable") \
            .with_args(["show vlan 111", "show interfaces Vlan111"], strict=True) \
            .and_raise(CommandError(1000, "CLI command 2 of 3 'show vlan 111' failed: could not run command",
                                    command_error="VLAN 111 not found in current VLAN database"))

        with self.assertRaises(UnknownVlan):
            self.switch.get_vlan(111)

    def test_get_vlan_incorrect(self):
        self.switch.node.should_receive("enable") \
            .with_args(["show vlan 5001", "show interfaces Vlan5001"], strict=True) \
            .and_raise(CommandError(1002, "CLI command 2 of 3 'show vlan 5001' failed: could not run command",
                                    command_error="Invalid input (at token 2: '5001')"))

        with self.assertRaises(BadVlanNumber):
            self.switch.get_vlan(5001)

    def test_get_vlan_without_interface(self):
        self.switch.node.should_receive("enable") \
            .with_args(["show vlan 456", "show interfaces Vlan456"], strict=True) \
            .and_raise(CommandError(1002, "CLI command 3 of 3 'show interfaces Vlan456' failed: invalid command",
                                    command_error="Interface does not exist",
                                    output=[
                                        {},
                                        {'vlans': {'456': vlan_data(name='Patate')}},
                                        {'errors': ['Interface does not exist']}
                                    ]))

        self.switch.node.should_receive("get_config").with_args(params="interfaces Vlan456").once() \
            .and_return(['interface Vlan456'])

        vlan = self.switch.get_vlan(456)

        assert_that(vlan.number, equal_to(456))
        assert_that(vlan.name, equal_to('Patate'))
        assert_that(vlan.ips, has_length(0))

    def test_get_vlan_unknown_error(self):
        self.switch.node.should_receive("enable") \
            .with_args(["show vlan 456", "show interfaces Vlan456"], strict=True) \
            .and_raise(CommandError(1002, "CLI command 3 of 3 'show interfaces Vlan456' failed: invalid command",
                                    command_error="This is unexpected"))

        with self.assertRaises(CommandError):
            self.switch.get_vlan(456)

    def test_add_vlan(self):
        self.switch.node.should_receive("enable").with_args(["show vlan 123"], strict=True) \
            .and_raise(CommandError(1000, 'msg'))

        self.switch.node.should_receive("config").with_args(["vlan 123"]).once()

        self.switch.add_vlan(123)

    def test_add_vlan_with_name(self):
        self.switch.node.should_receive("enable").with_args(["show vlan 123"], strict=True) \
            .and_raise(CommandError(1000, 'msg'))

        self.switch.node.should_receive("config").with_args(["vlan 123", "name gertrude"]).once()

        self.switch.add_vlan(123, "gertrude")

    def test_add_vlan_bad_vlan_number(self):
        with self.assertRaises(BadVlanNumber):
            self.switch.add_vlan(12334)

    def test_add_vlan_already_exits(self):
        self.switch.node.should_receive("enable").with_args(["show vlan 123"], strict=True).once() \
            .and_return(result_payload(result=[{'vlans': {'123': vlan_data(name='VLAN0123')}}]))

        with self.assertRaises(VlanAlreadyExist):
            self.switch.add_vlan(123)

    def test_add_vlan_bad_vlan_name(self):
        self.switch.node.should_receive("enable").with_args(["show vlan 123"], strict=True) \
            .and_raise(CommandError(1000, 'msg'))

        self.switch.node.should_receive("config") \
            .with_args(["vlan 123", "name gertrude invalid name"]) \
            .and_raise(CommandError(1000, "CLI command 4 of 4 'gertrude invalid name' failed: invalid command",
                                    command_error="Invalid input (at token 2: 'invalid')"))

        with self.assertRaises(BadVlanName):
            self.switch.add_vlan(123, "gertrude invalid name")

    def test_remove_vlan(self):
        self.switch.node.should_receive("enable").with_args(["show vlan 123"], strict=True).once()
        self.switch.node.should_receive("config").with_args(["no interface Vlan123", "no vlan 123"]).once()

        self.switch.remove_vlan(123)

    def test_remove_vlan_unknown_vlan(self):
        self.switch.node.should_receive("enable").with_args(["show vlan 123"], strict=True).once().and_raise(
            CommandError(1000, 'msg'))

        with self.assertRaises(UnknownVlan):
            self.switch.remove_vlan(123)

    def test_add_ip(self):
        self.switch = flexmock(spec=self.switch)
        self.switch.should_receive("get_vlan").with_args(123) \
            .and_return(Vlan(123))
        self.switch.node.should_receive("config").with_args(["interface vlan 123",
                                                             "ip address 1.2.3.4/29"]).once()

        self.switch.add_ip_to_vlan(123, IPNetwork("1.2.3.4/29"))

    def test_add_ip_no_interface(self):
        self.switch = flexmock(spec=self.switch)
        self.switch.should_receive("get_vlan").with_args(123) \
            .and_raise(UnknownInterface())
        self.switch.should_receive("get_vlan").with_args(123).and_return(Vlan(123))
        self.switch.node.should_receive("config").with_args(["interface vlan 123",
                                                             "ip address 1.2.3.4/29"]).once()

        self.switch.add_ip_to_vlan(123, IPNetwork("1.2.3.4/29"))

    def test_add_another_ip(self):
        self.switch = flexmock(spec=self.switch)
        self.switch.should_receive("get_vlan").with_args(123) \
            .and_return(Vlan(123, ips=[IPNetwork("1.1.1.1/29")]))
        self.switch.node.should_receive("config").with_args(["interface vlan 123",
                                                             "ip address 1.2.3.4/29 secondary"]).once()

        self.switch.add_ip_to_vlan(123, IPNetwork("1.2.3.4/29"))

    def test_add_unavailable_ip_raises(self):
        self.switch = flexmock(spec=self.switch)
        self.switch.should_receive("get_vlan").with_args(123) \
            .and_return(Vlan(123))
        self.switch.node.should_receive("config").with_args(["interface vlan 123", "ip address 1.2.3.4/29"]) \
            .once().and_raise(CommandError(1000, 'Address 1.2.3.4/29 is already assigned to interface Vlan456'))

        with self.assertRaises(IPNotAvailable) as e:
            self.switch.add_ip_to_vlan(123, IPNetwork("1.2.3.4/29"))

            assert_that(str(e), equal_to("IP 1.2.3.4/29 is not available in this vlan: "
                                         "Address 1.2.3.4/29 is already assigned to interface Vlan456"))

    def test_add_an_ip_already_present_in_the_same_port_raises(self):
        flexmock(self.switch).should_receive("get_vlan").with_args(123) \
            .and_return(Vlan(123, ips=[IPNetwork("1.2.3.4/29")]))

        with self.assertRaises(IPAlreadySet):
            self.switch.add_ip_to_vlan(123, IPNetwork("1.2.3.4/29"))

    def test_add_an_ip_already_present_in_the_same_port_secondary_raises(self):
        flexmock(self.switch).should_receive("get_vlan").with_args(123) \
            .and_return(Vlan(123, ips=[IPNetwork("1.2.3.4/29"), IPNetwork("1.2.3.5/29")]))

        with self.assertRaises(IPAlreadySet):
            self.switch.add_ip_to_vlan(123, IPNetwork("1.2.3.5/29"))

    def test_add_ip_to_unknown_vlan(self):
        flexmock(self.switch).should_receive("get_vlan").with_args(123).and_raise(UnknownVlan(123))

        with self.assertRaises(UnknownVlan):
            self.switch.add_ip_to_vlan(123, IPNetwork("1.2.3.5/29"))

    def test_remove_lonely_ip(self):
        flexmock(self.switch).should_receive("get_vlan").with_args(123) \
            .and_return(Vlan(123, ips=[IPNetwork("1.1.1.1/29")]))
        self.switch.node.should_receive("config").with_args(["interface Vlan123",
                                                             "no ip address 1.1.1.1/29"]).once()

        self.switch.remove_ip_from_vlan(123, IPNetwork("1.1.1.1/29"))

    def test_remove_secondary_ip(self):
        flexmock(self.switch).should_receive("get_vlan").with_args(123) \
            .and_return(Vlan(123, ips=[IPNetwork("1.1.1.1/29"), IPNetwork("1.1.2.1/29")]))
        self.switch.node.should_receive("config").with_args(["interface Vlan123",
                                                             "no ip address 1.1.2.1/29 secondary"]).once()

        self.switch.remove_ip_from_vlan(123, IPNetwork("1.1.2.1/29"))

    def test_cant_remove_unknown_ip(self):
        flexmock(self.switch).should_receive("get_vlan").with_args(123) \
            .and_return(Vlan(123, ips=[IPNetwork("1.1.2.1/29"), IPNetwork("1.1.3.1/29")]))

        with self.assertRaises(UnknownIP) as expect:
            self.switch.remove_ip_from_vlan(123, IPNetwork("1.1.1.1/29"))

        assert_that(str(expect.exception), contains_string("IP 1.1.1.1/29 not found"))

    def test_remove_a_primary_ip_that_have_secondary_ips(self):
        flexmock(self.switch).should_receive("get_vlan").with_args(123) \
            .and_return(Vlan(123, ips=[IPNetwork("1.1.1.1/29"), IPNetwork("1.1.2.1/29"), IPNetwork("1.1.3.1/29")]))
        self.switch.node.should_receive("config").with_args(["interface Vlan123",
                                                             "ip address 1.1.2.1/29"]).once()

        self.switch.remove_ip_from_vlan(123, IPNetwork("1.1.1.1/29"))

    def test_cant_remove_known_ip_with_wrong_netmask(self):
        flexmock(self.switch).should_receive("get_vlan").with_args(123) \
            .and_return(Vlan(123, ips=[IPNetwork("1.1.1.1/29"), IPNetwork("1.1.2.1/29")]))

        with self.assertRaises(UnknownIP) as expect:
            self.switch.remove_ip_from_vlan(123, IPNetwork("1.1.1.1/30"))

        assert_that(str(expect.exception), contains_string("IP 1.1.1.1/30 not found"))

    def test_remove_ip_from_unknown_vlan(self):
        flexmock(self.switch).should_receive("get_vlan").with_args(123) \
            .and_raise(UnknownVlan(123))

        with self.assertRaises(UnknownVlan):
            self.switch.remove_ip_from_vlan(123, IPNetwork("1.1.1.1/30"))

    def test_transactions_commit_write_memory(self):
        self.switch.node.should_receive("enable").with_args("write memory").once()

        self.switch.commit_transaction()

    def test_transactions_rollback_does_nothing(self):
        self.switch.rollback_transaction()

    def test_get_interface(self):
        interface_payload = result_payload(result={
            'interfaces': {
                'Ethernet1': interface_data(
                    name="Ethernet1",
                    lineProtocolStatus="up",
                    autoNegotiate="off",
                    mtu=1234
                )
            }
        })

        switchport_payload = result_payload(result={
            'switchports': {
                'Ethernet1': {
                    'enabled': True,
                    'switchportInfo': switchport_data(
                        mode="trunk",
                        trunkAllowedVlans="800-802,804",
                        trunkingNativeVlanId=1
                    )
                }
            }
        })

        self.switch.node.should_receive("enable") \
            .with_args(["show interfaces Ethernet1", "show interfaces Ethernet1 switchport"], strict=True) \
            .and_return([interface_payload, switchport_payload])

        interface = self.switch.get_interface("Ethernet1")

        assert_that(interface.name, equal_to("Ethernet1"))
        assert_that(interface.shutdown, equal_to(False))
        assert_that(interface.port_mode, equal_to(TRUNK))
        assert_that(interface.trunk_vlans, equal_to([800, 801, 802, 804]))
        assert_that(interface.auto_negotiation, equal_to(OFF))
        assert_that(interface.mtu, equal_to(1234))

    def test_get_interface_no_interface_raises(self):
        self.switch.node.should_receive("enable") \
            .with_args(["show interfaces InvalidInterface", "show interfaces InvalidInterface switchport"], strict=True) \
            .and_raise(CommandError(1002,
                                    "CLI command 4 of 4 'show interfaces InvalidInterface' failed: invalid command",
                                    command_error="Invalid input (at token 0: 'show')"))

        with self.assertRaises(UnknownInterface):
            self.switch.get_interface("InvalidInterface")

    def test_get_interface_unsupported_interface_raises(self):
        interface_payload = result_payload(result={
            'interfaces': {
                'UndesiredInterface': interface_data(name="UndesiredInterface", )
            }
        })
        switchport_payload = result_payload(result={'switchports': {}})
        self.switch.node.should_receive("enable") \
            .with_args(["show interfaces Unsupported1", "show interfaces Unsupported1 switchport"], strict=True) \
            .and_return([interface_payload, switchport_payload])

        with self.assertRaises(UnknownInterface):
            self.switch.get_interface("Unsupported1")

    def test_get_interfaces(self):
        interface_payload = result_payload(result={
            'interfaces': {
                'Ethernet1': interface_data(
                    name="Ethernet1",
                    lineProtocolStatus="up",
                    autoNegotiate="off",
                    mtu=1234
                ),
                'Ethernet2': interface_data(
                    name="Ethernet2",
                    lineProtocolStatus="down",
                    autoNegotiate="on"
                )}})

        switchport_payload = result_payload(result={
            'switchports': {
                'Ethernet1': {
                    'enabled': True,
                    'switchportInfo': switchport_data(
                        mode="trunk",
                        trunkAllowedVlans="800-802,804",
                        trunkingNativeVlanId=1
                    )
                }
            }
        })

        self.switch.node.should_receive("enable") \
            .with_args(["show interfaces", "show interfaces switchport"], strict=True) \
            .and_return([interface_payload, switchport_payload])

        if1, if2 = sorted(self.switch.get_interfaces(), key=lambda i: i.name)

        assert_that(if1.name, equal_to("Ethernet1"))
        assert_that(if1.shutdown, equal_to(False))
        assert_that(if1.port_mode, equal_to(TRUNK))
        assert_that(if1.trunk_vlans, equal_to([800, 801, 802, 804]))
        assert_that(if1.auto_negotiation, equal_to(OFF))
        assert_that(if1.mtu, equal_to(1234))

        assert_that(if2.name, equal_to("Ethernet2"))
        assert_that(if2.shutdown, equal_to(True))
        assert_that(if2.trunk_vlans, equal_to([]))
        assert_that(if2.auto_negotiation, equal_to(ON))

    def parse_range_test(self):
        result = parse_vlan_ranges(None)
        assert_that(list(result), equal_to(range(1, 4094)))

        result = parse_vlan_ranges("NONE")
        assert_that(list(result), equal_to([]))

        result = parse_vlan_ranges("ALL")
        assert_that(list(result), equal_to(range(1, 4094)))

        result = parse_vlan_ranges("1")
        assert_that(list(result), equal_to([1]))

        result = parse_vlan_ranges("2-5")
        assert_that(list(result), equal_to([2, 3, 4, 5]))

        result = parse_vlan_ranges("1,3-5,7")
        assert_that(list(result), equal_to([1, 3, 4, 5, 7]))

    def test_set_trunk_mode_initial(self):
        self.switch.node.should_receive("config").with_args([
            "interface Ethernet1",
            "switchport mode trunk",
            "switchport trunk allowed vlan none"
        ]).once()

        self.switch.set_trunk_mode("Ethernet1")

    def test_set_trunk_mode_initial_invalid_interface_raises(self):
        self.switch.node.should_receive("config") \
            .with_args(["interface Invalid_Ethernet",
                        "switchport mode trunk",
                        "switchport trunk allowed vlan none"]) \
            .and_raise(CommandError(1002, "CLI command 3 of 6 'interface Invalid_Ethernet' failed: invalid command",
                                    command_error="Invalid input (at token 1: 'Invalid_Ethernet')"))

        with self.assertRaises(UnknownInterface):
            self.switch.set_trunk_mode("Invalid_Ethernet")

    def test_add_trunk_vlan(self):
        self.switch = flexmock(self.switch)
        self.switch.should_receive("get_vlan").with_args(800).and_return(Vlan(800))
        self.switch.node.should_receive("config") \
            .with_args(["interface Ethernet1",
                        "switchport trunk allowed vlan add 800"]).once()

        self.switch.add_trunk_vlan("Ethernet1", vlan=800)

    def test_add_trunk_vlan_invalid_vlan_raises(self):
        self.switch = flexmock(self.switch)
        self.switch.should_receive("get_vlan").with_args(800).and_raise(UnknownVlan(800))

        with self.assertRaises(UnknownVlan):
            self.switch.add_trunk_vlan("Ethernet1", vlan=800)

    def test_add_trunk_vlan_invalid_interface_raises(self):
        self.switch = flexmock(self.switch)
        self.switch.should_receive("get_vlan").with_args(800).and_return(Vlan(800))
        self.switch.node.should_receive("config") \
            .with_args(["interface Invalid_Ethernet",
                        "switchport trunk allowed vlan add 800"]) \
            .and_raise(UnknownInterface("Invalid_Ethernet"))

        with self.assertRaises(UnknownInterface):
            self.switch.add_trunk_vlan("Invalid_Ethernet", vlan=800)

    def test_remove_trunk_vlan(self):
        interface_payload = result_payload(result={'interfaces': {'Ethernet1': interface_data(
            name="Ethernet1",
            lineProtocolStatus="up",
            autoNegotiate="off",
            mtu=1234
        )}})
        switchport_payload = result_payload(result={'switchports': {'Ethernet1': {'enabled': True,
                                                                                  'switchportInfo': switchport_data(
                                                                                      mode="trunk",
                                                                                      trunkAllowedVlans="800-802,804",
                                                                                      trunkingNativeVlanId=1
                                                                                  )}}})
        self.switch.node.should_receive("enable") \
            .with_args(["show interfaces Ethernet1", "show interfaces Ethernet1 switchport"], strict=True) \
            .and_return([interface_payload, switchport_payload])
        self.switch.node.should_receive("config") \
            .with_args(["interface Ethernet1", "switchport trunk allowed vlan remove 800"])

        self.switch.remove_trunk_vlan("Ethernet1", 800)

    def test_remove_trunk_vlan_invalid_vlan_raises(self):
        self.switch = flexmock(self.switch)
        self.switch.should_receive("get_interface") \
            .with_args("Ethernet1") \
            .and_return(Interface(name="Ethernet1", trunk_vlans=[], port_mode="trunk"))

        with self.assertRaises(UnknownVlan):
            self.switch.remove_trunk_vlan("Ethernet1", vlan=800)

    def test_remove_trunk_vlan_invalid_interface_raises(self):
        self.switch = flexmock(self.switch)
        self.switch.should_receive("get_interface") \
            .with_args("Ethernet1") \
            .and_raise(UnknownInterface("Ethernet1"))

        with self.assertRaises(UnknownInterface):
            self.switch.remove_trunk_vlan("Ethernet1", vlan=800)

    def test_remove_trunk_vlan_no_port_mode_still_working(self):
        self.switch = flexmock(self.switch)
        self.switch.should_receive("get_interface") \
            .with_args("Ethernet1") \
            .and_return(Interface(name="Ethernet1", trunk_vlans=[800], port_mode=None))
        self.switch.node.should_receive("config") \
            .with_args(["interface Ethernet1", "switchport trunk allowed vlan remove 800"])

        self.switch.remove_trunk_vlan("Ethernet1", 800)

    def test_add_dhcp_relay_server(self):
        vlans_payload = {'vlans': {'123': vlan_data(name='Patate')}}

        interfaces_payload = show_interfaces(
            interface_vlan_data(name="Vlan123")
        )

        self.switch.node.should_receive("enable") \
            .with_args(["show vlan 123", "show interfaces Vlan123"], strict=True) \
            .and_return([result_payload(result=vlans_payload),
                         result_payload(result=interfaces_payload)])

        self.switch.node.should_receive("get_config").once() \
            .with_args(params="interfaces Vlan123") \
            .and_return(['interface Vlan123',
                         '   ip helper-address 10.10.30.200',
                         '   ip helper-address 10.10.30.201'])

        self.switch.node.should_receive("config").once() \
            .with_args(['interface Vlan123',
                        'ip helper-address 10.10.30.202'])

        self.switch.add_dhcp_relay_server(123, IPAddress('10.10.30.202'))

    def test_add_same_dhcp_relay_server_fails(self):
        vlans_payload = {'vlans': {'123': vlan_data(name='Patate')}}

        interfaces_payload = show_interfaces(
            interface_vlan_data(name="Vlan123")
        )

        self.switch.node.should_receive("enable") \
            .with_args(["show vlan 123", "show interfaces Vlan123"], strict=True) \
            .and_return([result_payload(result=vlans_payload),
                         result_payload(result=interfaces_payload)])

        self.switch.node.should_receive("get_config").once() \
            .with_args(params="interfaces Vlan123") \
            .and_return(['interface Vlan123',
                         '   ip helper-address 10.10.30.200',
                         '   ip helper-address 10.10.30.201'])

        with self.assertRaises(DhcpRelayServerAlreadyExists):
            self.switch.add_dhcp_relay_server(123, IPAddress('10.10.30.201'))

    def test_remove_dhcp_relay_server(self):
        vlans_payload = {'vlans': {'123': vlan_data(name='Patate')}}

        interfaces_payload = show_interfaces(
            interface_vlan_data(name="Vlan123")
        )

        self.switch.node.should_receive("enable") \
            .with_args(["show vlan 123", "show interfaces Vlan123"], strict=True) \
            .and_return([result_payload(result=vlans_payload),
                         result_payload(result=interfaces_payload)])

        self.switch.node.should_receive("get_config").once() \
            .with_args(params="interfaces Vlan123") \
            .and_return(['interface Vlan123',
                         '   ip helper-address 10.10.30.200',
                         '   ip helper-address 10.10.30.202'])

        self.switch.node.should_receive("config").once() \
            .with_args(['interface Vlan123',
                        'no ip helper-address 10.10.30.202'])

        self.switch.remove_dhcp_relay_server(123, IPAddress('10.10.30.202'))

    def test_remove_non_existent_dhcp_relay_server_fails(self):
        vlans_payload = {'vlans': {'123': vlan_data(name='Patate')}}

        interfaces_payload = show_interfaces(
            interface_vlan_data(name="Vlan123")
        )

        self.switch.node.should_receive("enable") \
            .with_args(["show vlan 123", "show interfaces Vlan123"], strict=True) \
            .and_return([result_payload(result=vlans_payload),
                         result_payload(result=interfaces_payload)])

        self.switch.node.should_receive("get_config").once() \
            .with_args(params="interfaces Vlan123") \
            .and_return(['interface Vlan123',
                         '   ip helper-address 10.10.30.200',
                         '   ip helper-address 10.10.30.202'])

        with self.assertRaises(UnknownDhcpRelayServer):
            self.switch.remove_dhcp_relay_server(123, IPAddress('10.10.30.222'))

    def test_set_bond_trunk_mode_initial(self):
        self.switch.node.should_receive("config").with_args([
            "interface Port-Channel1",
            "switchport mode trunk",
            "switchport trunk allowed vlan none"
        ]).once()

        self.switch.set_bond_trunk_mode(1)

    def test_set_bond_trunk_mode_initial_invalid_interface_raises(self):
        self.switch.node.should_receive("config") \
            .with_args(["interface Port-Channel9999",
                        "switchport mode trunk",
                        "switchport trunk allowed vlan none"]) \
            .and_raise(CommandError(1002, "CLI command 3 of 6 'interface Port-Channel9999' failed: invalid command",
                                    command_error="Invalid input (at token 1: 'Port-Channel9999')"))

        with self.assertRaises(UnknownBond):
            self.switch.set_bond_trunk_mode(9999)

    def test_add_bond_trunk_vlan(self):
        self.switch = flexmock(self.switch)
        self.switch.should_receive("get_vlan").with_args(800).and_return(Vlan(800))
        self.switch.node.should_receive("config") \
            .with_args(["interface Port-Channel1",
                        "switchport trunk allowed vlan add 800"]).once()

        self.switch.add_bond_trunk_vlan(1, vlan=800)

    def test_add_bond_trunk_vlan_invalid_vlan_raises(self):
        self.switch = flexmock(self.switch)
        self.switch.should_receive("get_vlan").with_args(800).and_raise(UnknownVlan(800))

        with self.assertRaises(UnknownVlan):
            self.switch.add_bond_trunk_vlan(1, vlan=800)

    def test_add_bond_trunk_vlan_invalid_interface_raises(self):
        self.switch = flexmock(self.switch)
        self.switch.should_receive("get_vlan").with_args(800).and_return(Vlan(800))
        self.switch.node.should_receive("config") \
            .with_args(["interface Port-Channel9999",
                        "switchport trunk allowed vlan add 800"]) \
            .and_raise(CommandError(1002, "CLI command 3 of 6 'interface Port-Channel9999' failed: invalid command",
                                    command_error="Invalid input (at token 1: 'Port-Channel9999')"))

        with self.assertRaises(UnknownBond):
            self.switch.add_bond_trunk_vlan(9999, vlan=800)

    def test_remove_bond_trunk_vlan(self):
        self.switch = flexmock(self.switch)
        self.switch.should_receive("get_interface") \
            .with_args("Port-Channel1") \
            .and_return(Interface(name="Port-Channel1", trunk_vlans=[800], port_mode="trunk"))
        self.switch.node.should_receive("config") \
            .with_args(["interface Port-Channel1", "switchport trunk allowed vlan remove 800"])

        self.switch.remove_bond_trunk_vlan(1, 800)

    def test_remove_bond_trunk_vlan_invalid_vlan_raises(self):
        self.switch = flexmock(self.switch)
        self.switch.should_receive("get_interface") \
            .with_args("Port-Channel1") \
            .and_return(Interface(name="Port-Channel1", trunk_vlans=[], port_mode="trunk"))

        with self.assertRaises(UnknownVlan):
            self.switch.remove_bond_trunk_vlan(1, vlan=800)

    def test_remove_bond_trunk_vlan_invalid_interface_raises(self):
        self.switch = flexmock(self.switch)
        self.switch.should_receive("get_interface") \
            .with_args("Port-Channel9999") \
            .and_raise(UnknownInterface("Port-Channel9999"))

        with self.assertRaises(UnknownBond):
            self.switch.remove_bond_trunk_vlan(9999, vlan=800)

    def test_add_varp_ip(self):
        vlans_payload = {'vlans': {'123': vlan_data(name='Patate')}}

        interfaces_payload = show_interfaces(
            interface_vlan_data(name="Vlan123")
        )

        self.switch.node.should_receive("enable") \
            .with_args(["show vlan 123", "show interfaces Vlan123"], strict=True) \
            .and_return([result_payload(result=vlans_payload),
                         result_payload(result=interfaces_payload)])

        self.switch.node.should_receive("get_config").once() \
            .with_args(params="interfaces Vlan123") \
            .and_return(['interface Vlan123'])

        self.switch.node.should_receive("config").once() \
            .with_args(['interface Vlan123',
                        'ip virtual-router address 10.10.20.12/28'])

        self.switch.add_vlan_varp_ip(123, IPNetwork('10.10.20.12/28'))

    def test_add_varp_ip_unknown_vlan_raises(self):
        self.switch.node.should_receive("enable").once() \
            .with_args(["show vlan 111", "show interfaces Vlan111"], strict=True) \
            .and_raise(CommandError(1000, "CLI command 2 of 3 'show vlan 111' failed: could not run command",
                                    command_error="VLAN 111 not found in current VLAN database"))

        with self.assertRaises(UnknownVlan):
            self.switch.add_vlan_varp_ip(111, IPNetwork('10.10.20.12/28'))

    def test_add_existing_varp_ip_to_same_vlan_raises(self):
        vlans_payload = {'vlans': {'123': vlan_data(name='Patate')}}

        interfaces_payload = show_interfaces(
            interface_vlan_data(name="Vlan123")
        )

        self.switch.node.should_receive("enable") \
            .with_args(["show vlan 123", "show interfaces Vlan123"], strict=True) \
            .and_return([result_payload(result=vlans_payload),
                         result_payload(result=interfaces_payload)])

        self.switch.node.should_receive("get_config").once() \
            .with_args(params="interfaces Vlan123") \
            .and_return(['interface Vlan123',
                         '   ip virtual-router address 10.10.20.12/28'])

        with self.assertRaises(VarpAlreadyExistsForVlan):
            self.switch.add_vlan_varp_ip(123, IPNetwork('10.10.20.12/28'))

    def test_add_varp_conflicting_ip_raises(self):
        vlans_payload = {'vlans': {'123': vlan_data(name='Patate')}}

        interfaces_payload = show_interfaces(
            interface_vlan_data(name="Vlan123")
        )

        self.switch.node.should_receive("enable") \
            .with_args(["show vlan 123", "show interfaces Vlan123"], strict=True) \
            .and_return([result_payload(result=vlans_payload),
                         result_payload(result=interfaces_payload)])

        self.switch.node.should_receive("get_config").once() \
            .with_args(params="interfaces Vlan123") \
            .and_return(['interface Vlan123'])

        self.switch.node.should_receive("config").once() \
            .with_args(['interface Vlan123',
                        'ip virtual-router address 10.10.20.12/28']) \
            .and_raise(CommandError(1000,
                                    "Error [1000]: CLI command 4 of 4 "
                                    "'ip virtual-router address 10.10.20.1/28' failed: could not run command "
                                    "[Address 10.10.20.1 is already assigned to interface Vlan20]"))

        with self.assertRaises(IPNotAvailable):
            self.switch.add_vlan_varp_ip(123, IPNetwork('10.10.20.12/28'))

    def test_add_varp_other_eapi_error_raises(self):
        vlans_payload = {'vlans': {'123': vlan_data(name='Patate')}}

        interfaces_payload = show_interfaces(
            interface_vlan_data(name="Vlan123")
        )

        self.switch.node.should_receive("enable") \
            .with_args(["show vlan 123", "show interfaces Vlan123"], strict=True) \
            .and_return([result_payload(result=vlans_payload),
                         result_payload(result=interfaces_payload)])

        self.switch.node.should_receive("get_config").once() \
            .with_args(params="interfaces Vlan123") \
            .and_return(['interface Vlan123'])

        self.switch.node.should_receive("config").once() \
            .with_args(['interface Vlan123',
                        'ip virtual-router address 10.10.20.12/28']) \
            .and_raise(CommandError(1000, "Communication Error"))

        with self.assertRaises(CommandError):
            self.switch.add_vlan_varp_ip(123, IPNetwork('10.10.20.12/28'))

    def test_remove_varp_ip(self):
        vlans_payload = {'vlans': {'123': vlan_data(name='Patate')}}

        interfaces_payload = show_interfaces(
            interface_vlan_data(name="Vlan123")
        )

        self.switch.node.should_receive("enable") \
            .with_args(["show vlan 123", "show interfaces Vlan123"], strict=True) \
            .and_return([result_payload(result=vlans_payload),
                         result_payload(result=interfaces_payload)])

        self.switch.node.should_receive("get_config").once() \
            .with_args(params="interfaces Vlan123") \
            .and_return(['interface Vlan123',
                         '   ip virtual-router address 10.10.20.12/28'])

        self.switch.node.should_receive("config").once() \
            .with_args(['interface Vlan123',
                        'no ip virtual-router address 10.10.20.12/28'])

        self.switch.remove_vlan_varp_ip(123, IPNetwork('10.10.20.12/28'))

    def test_remove_varp_unknown_ip_raises(self):
        vlans_payload = {'vlans': {'123': vlan_data(name='Patate')}}

        interfaces_payload = show_interfaces(
            interface_vlan_data(name="Vlan123")
        )

        self.switch.node.should_receive("enable") \
            .with_args(["show vlan 123", "show interfaces Vlan123"], strict=True) \
            .and_return([result_payload(result=vlans_payload),
                         result_payload(result=interfaces_payload)])

        self.switch.node.should_receive("get_config").once() \
            .with_args(params="interfaces Vlan123") \
            .and_return(['interface Vlan123'])

        with self.assertRaises(VarpDoesNotExistForVlan):
            self.switch.remove_vlan_varp_ip(123, IPNetwork('10.10.20.12/28'))

    def test_remove_varp_ip_unknown_vlan_raises(self):
        self.switch.node.should_receive("enable").once() \
            .with_args(["show vlan 111", "show interfaces Vlan111"], strict=True) \
            .and_raise(CommandError(1000, "CLI command 2 of 3 'show vlan 111' failed: could not run command",
                                    command_error="VLAN 111 not found in current VLAN database"))

        with self.assertRaises(UnknownVlan):
            self.switch.remove_vlan_varp_ip(111, IPNetwork('10.10.20.12/28'))

    def test_set_vlan_load_interval(self):
        self.switch = flexmock(spec=self.switch)
        self.switch.should_receive("get_vlan").with_args(123) \
            .and_return(Vlan(123))
        self.switch.node.should_receive("config").with_args(["interface Vlan123",
                                                             "load-interval 30"]).once()

        self.switch.set_vlan_load_interval(123, 30)

    def test_set_vlan_load_interval_unknown_vlan_raises(self):
        self.switch = flexmock(self.switch)
        self.switch.should_receive("get_vlan").with_args(123).and_raise(UnknownVlan(123))

        with self.assertRaises(UnknownVlan):
            self.switch.set_vlan_load_interval(123, 30)

    def test_set_vlan_load_interval_with_bad_number_raises(self):
        self.switch = flexmock(spec=self.switch)
        self.switch.should_receive("get_vlan").with_args(123) \
            .and_return(Vlan(123))
        self.switch.node.should_receive("config").with_args(["interface Vlan123", "load-interval 800"]) \
            .and_raise(CommandError(1002, "CLI command 4 of 4 'load-interval 800' failed: invalid command",
                                    command_error="Invalid input"))

        with self.assertRaises(BadLoadIntervalNumber):
            self.switch.set_vlan_load_interval(123, 800)

    def test_unset_vlan_load_interval(self):
        self.switch = flexmock(spec=self.switch)
        self.switch.should_receive("get_vlan").with_args(123) \
            .and_return(Vlan(123))
        self.switch.node.should_receive("config").with_args(["interface Vlan123",
                                                             "no load-interval"]).once()

        self.switch.unset_vlan_load_interval(123)

    def test_unset_vlan_load_interval_unknown_vlan_raises(self):
        self.switch = flexmock(self.switch)
        self.switch.should_receive("get_vlan").with_args(123).and_raise(UnknownVlan(123))

        with self.assertRaises(UnknownVlan):
            self.switch.unset_vlan_load_interval(123)

    def test_set_vlan_mpls_ip_state_false(self):
        self.switch = flexmock(spec=self.switch)
        self.switch.should_receive("get_vlan").with_args(123) \
            .and_return(Vlan(123))
        self.switch.node.should_receive("config").with_args(["interface Vlan123",
                                                             "no mpls ip"]).once()

        self.switch.set_vlan_mpls_ip_state(123, False)

    def test_set_vlan_mpls_ip_state_true(self):
        self.switch = flexmock(spec=self.switch)
        self.switch.should_receive("get_vlan").with_args(123) \
            .and_return(Vlan(123))
        self.switch.node.should_receive("config").with_args(["interface Vlan123",
                                                             "mpls ip"]).once()

        self.switch.set_vlan_mpls_ip_state(123, True)

    def test_set_vlan_mpls_ip_with_invalid_state_raises(self):
        self.switch = flexmock(spec=self.switch)
        self.switch.should_receive("get_vlan").with_args(123) \
            .and_return(Vlan(123))

        with self.assertRaises(BadMplsIpState):
            self.switch.set_vlan_mpls_ip_state(123, 30)

    def test_set_vlan_mpls_ip_unknown_vlan_raises(self):
        self.switch = flexmock(self.switch)
        self.switch.should_receive("get_vlan").with_args(123).and_raise(UnknownVlan(123))

        with self.assertRaises(UnknownVlan):
            self.switch.set_vlan_mpls_ip_state(123, False)


class AristaFactoryTest(unittest.TestCase):
    def tearDown(self):
        flexmock_teardown()

    def test_arista_instance_with_proper_transport(self):
        pyeapi_client_node = mock.sentinel

        flexmock(pyeapi).should_receive('connect').once() \
            .with_args(host="1.2.3.4",
                       username="you sir name",
                       password="paw sword",
                       port=8888,
                       transport="trololo",
                       return_node=True,
                       timeout=300) \
            .and_return(pyeapi_client_node)

        switch = Arista(
            SwitchDescriptor(model='arista',
                             hostname="1.2.3.4",
                             username="you sir name",
                             password="paw sword",
                             port=8888),
            transport="trololo"
        )

        switch._connect()

        assert_that(switch.node, is_(pyeapi_client_node))

    def test_arista_uses_command_timeout(self):
        arista.default_command_timeout = 500

        pyeapi_client_node = mock.sentinel

        flexmock(pyeapi).should_receive('connect').once() \
            .with_args(host="1.2.3.4",
                       username=None,
                       password=None,
                       port=None,
                       transport="trololo",
                       return_node=True,
                       timeout=500) \
            .and_return(pyeapi_client_node)

        switch = Arista(
            SwitchDescriptor(model='arista',
                             hostname="1.2.3.4"),
            transport="trololo"
        )

        switch._connect()

    @ignore_deprecation_warnings
    def test_factory_transport_auto_detection_http(self):
        switch_descriptor = SwitchDescriptor(model="arista", hostname='http://hostname')

        instance = mock.sentinel
        flexmock(arista).should_receive("Arista").once() \
            .with_args(switch_descriptor, transport="http") \
            .and_return(mock.sentinel)

        assert_that(arista.eapi(switch_descriptor), is_(instance))

        assert_that(switch_descriptor.hostname, is_("hostname"))

    @ignore_deprecation_warnings
    def test_factory_transport_auto_detection_https(self):
        switch_descriptor = SwitchDescriptor(model="arista", hostname='https://hostname')

        instance = mock.sentinel
        flexmock(arista).should_receive("Arista").once() \
            .with_args(switch_descriptor, transport="https") \
            .and_return(mock.sentinel)

        assert_that(arista.eapi(switch_descriptor), is_(instance))

        assert_that(switch_descriptor.hostname, is_("hostname"))

    @ignore_deprecation_warnings
    def test_factory_transport_auto_detection_assumes_https_if_not_specified(self):
        switch_descriptor = SwitchDescriptor(model="arista", hostname='hostname')

        instance = mock.sentinel
        flexmock(arista).should_receive("Arista").once() \
            .with_args(switch_descriptor, transport="https") \
            .and_return(mock.sentinel)

        assert_that(arista.eapi(switch_descriptor), is_(instance))

        assert_that(switch_descriptor.hostname, is_("hostname"))
