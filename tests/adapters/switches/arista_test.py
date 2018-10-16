import unittest

from flexmock import flexmock, flexmock_teardown
from hamcrest import assert_that, has_length, equal_to, is_
from pyeapi.api.vlans import Vlans
from pyeapi.eapilib import CommandError

from netman.adapters.switches.arista import Arista
from netman.core.objects.exceptions import BadVlanNumber, VlanAlreadyExist, BadVlanName, UnknownVlan, \
    OperationNotCompleted
from netman.core.objects.switch_descriptor import SwitchDescriptor
from tests.fixtures.arista import vlans_payload, vlan_data


class AristaTest(unittest.TestCase):

    def setUp(self):
        self.switch = Arista(SwitchDescriptor(model='arista', hostname="my.hostname"))
        self.switch.conn = flexmock()
        self.switch.node = flexmock()

    def tearDown(self):
        flexmock_teardown()

    def test_get_vlans(self):
        four_vlans_payload = vlans_payload(result=[{'vlans': {'1': vlan_data(name='default'),
                                                              '123': vlan_data(name='VLAN0123'),
                                                              '456': vlan_data(name='Patate'),
                                                              '4444': vlan_data(name='VLAN4444')}}])

        self.switch.conn.should_receive("execute").with_args("show vlan").once().and_return(four_vlans_payload)

        vlan_list = self.switch.get_vlans()
        vlan_list = sorted(vlan_list, key=lambda x: x.number)

        assert_that(vlan_list, has_length(4))
        assert_that(vlan_list[0].number, equal_to(1))
        assert_that(vlan_list[0].name, equal_to("default"))

    def test_get_vlans_with_default_name_returns_no_name(self):
        my_vlan = {u'status': u'active', u'interfaces': {}, u'dynamic': False, u'name': u'VLAN0123'}

        self.switch.conn.should_receive("execute").with_args("show vlan").once() \
                        .and_return(vlans_payload(result=[{'vlans': {'123': my_vlan}}]))

        vlan_list = self.switch.get_vlans()
        vlan_list = sorted(vlan_list, key=lambda x: x.number)

        assert_that(vlan_list[0].number, equal_to(123))
        assert_that(vlan_list[0].name, equal_to(None))

    def test_get_vlan_doesnt_exist(self):
        self.switch.conn.should_receive("execute").with_args("show vlan 111").and_raise(CommandError(1000, 'msg'))

        with self.assertRaises(UnknownVlan):
            self.switch.get_vlan(111)

    def test_get_vlan(self):
        self.switch.conn.should_receive("execute").with_args("show vlan 123").once() \
                        .and_return(vlans_payload(result=[{'vlans': {'123': vlan_data(name='My-Vlan-Name')}}]))

        vlan = self.switch.get_vlan(123)

        assert_that(vlan.number, is_(123))
        assert_that(vlan.name, is_('My-Vlan-Name'))

    def test_add_vlan(self):
        vlan = flexmock(spec=Vlans)

        self.switch.conn.should_receive("execute").with_args("show vlan 123").once().and_raise(
            CommandError(1000, 'msg'))
        vlan.should_receive("configure_vlan").with_args(123, []).once().and_return(True)

        self.switch.add_vlan(123)

    def test_add_vlan_with_name(self):
        vlan = flexmock(spec=Vlans)

        self.switch.conn.should_receive("execute").with_args("show vlan 123").once().and_raise(
            CommandError(1000, 'msg'))
        vlan.should_receive("configure_vlan").with_args(123, ["name gertrude"]).once().and_return(True)

        self.switch.add_vlan(123, "gertrude")

    def test_add_vlan_bad_vlan_number(self):
        with self.assertRaises(BadVlanNumber):
            self.switch.add_vlan(12334)

    def test_add_vlan_already_exits(self):
        self.switch.conn.should_receive("execute").with_args("show vlan 123").once()\
                        .and_return(vlans_payload(result=[{'vlans': {'123': vlan_data(name='VLAN0123')}}]))

        with self.assertRaises(VlanAlreadyExist):
            self.switch.add_vlan(123)

    def test_add_vlan_bad_vlan_name(self):
        vlan = flexmock(spec=Vlans)

        self.switch.conn.should_receive("execute").with_args("show vlan 123").once().and_raise(
            CommandError(1000, 'msg'))
        vlan.should_receive("configure_vlan").with_args(123, ["name gertrude_invalid_name"]).once().and_return(False)

        with self.assertRaises(BadVlanName):
            self.switch.add_vlan(123, "gertrude_invalid_name")

    def test_remove_vlan(self):
        vlan = flexmock(spec=Vlans)

        self.switch.conn.should_receive("execute").with_args("show vlan 123").once()
        vlan.should_receive("delete").with_args(123).once().and_return(True)

        self.switch.remove_vlan(123)

    def test_remove_vlan_unknown_vlan(self):
        self.switch.conn.should_receive("execute").with_args("show vlan 123").once().and_raise(
            CommandError(1000, 'msg'))

        with self.assertRaises(UnknownVlan):
            self.switch.remove_vlan(123)

    def test_remove_vlan_unable_to_remove(self):
        vlan = flexmock(spec=Vlans)

        self.switch.conn.should_receive("execute").with_args("show vlan 123").once()
        vlan.should_receive("delete").with_args(123).once().and_return(False)

        with self.assertRaises(OperationNotCompleted):
            self.switch.remove_vlan(123)
