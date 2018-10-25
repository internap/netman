import unittest

import pyeapi
from flexmock import flexmock, flexmock_teardown
from hamcrest import assert_that, has_length, equal_to, is_, contains_string
from netaddr import IPNetwork
from pyeapi.client import Node
from pyeapi.eapilib import CommandError

from netman.adapters.switches.arista import Arista
from netman.core.objects.exceptions import BadVlanNumber, VlanAlreadyExist, BadVlanName, UnknownVlan, \
    UnknownIP, IPNotAvailable, IPAlreadySet, UnknownInterface
from netman.core.objects.switch_descriptor import SwitchDescriptor
from netman.core.objects.vlan import Vlan
from tests.fixtures.arista import vlan_data, result_payload, interface_vlan_data, show_interfaces, interface_address


class AristaTest(unittest.TestCase):

    def setUp(self):
        self.switch = Arista(SwitchDescriptor(model='arista', hostname="my.hostname"))
        self.switch.node = flexmock()

    def tearDown(self):
        flexmock_teardown()

    def test_arista_instance_with_proper_transport_http(self):
        arista_eapi = flexmock(pyeapi)
        arista_eapi.should_receive('connect').with_args(host="127.0.0.1", transport="http",
                                                        username=None, return_node=True,
                                                        password=None, port=None).once() \
            .and_return(flexmock(Node(connection=None)))

        switch = Arista(SwitchDescriptor(model='arista', hostname="http://127.0.0.1"))
        switch._connect()

    def test_arista_instance_with_proper_default_transport(self):
        arista_eapi = flexmock(pyeapi)
        arista_eapi.should_receive('connect').with_args(host="127.0.0.1", transport="https",
                                                        username=None, return_node=True,
                                                        password=None, port=None).once() \
            .and_return(flexmock(Node(connection=None)))

        switch = Arista(SwitchDescriptor(model='arista', hostname="127.0.0.1"))
        switch._connect()

    def test_get_vlans(self):
        vlans_payload = {'vlans': {'1': vlan_data(name='default'),
                                   '123': vlan_data(name='VLAN0123'),
                                   '456': vlan_data(name='Patate'),
                                   '789': vlan_data(name="new_interface_vlan_without_ip"),
                                   '1234': vlan_data(name="interface_with_removed_ip")}}

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

        vlan1, vlan123, vlan456, vlan789, vlan1234 = self.switch.get_vlans()

        assert_that(vlan1.number, equal_to(1))
        assert_that(vlan1.name, equal_to('default'))
        assert_that(vlan1.ips, has_length(0))

        assert_that(vlan123.number, equal_to(123))
        assert_that(vlan123.name, equal_to(None))
        assert_that(vlan123.ips, has_length(0))

        assert_that(vlan456.number, equal_to(456))
        assert_that(vlan456.name, equal_to('Patate'))
        ip11, ip13, ip12 = vlan456.ips
        assert_that(ip11, is_(IPNetwork("192.168.11.1/29")))
        assert_that(ip13, is_(IPNetwork("192.168.13.1/29")))
        assert_that(ip12, is_(IPNetwork("192.168.12.1/29")))

        assert_that(vlan789.ips, has_length(0))

        assert_that(vlan1234.ips, has_length(0))

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

        vlan = self.switch.get_vlan(456)

        assert_that(vlan.number, equal_to(456))
        assert_that(vlan.name, equal_to('Patate'))
        ip11, ip13, ip12 = vlan.ips
        assert_that(ip11, is_(IPNetwork("192.168.11.1/29")))
        assert_that(ip13, is_(IPNetwork("192.168.13.1/29")))
        assert_that(ip12, is_(IPNetwork("192.168.12.1/29")))

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
