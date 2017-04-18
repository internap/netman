from hamcrest import is_, assert_that, empty, none
from netman.core.objects.exceptions import UnknownInterface
from netman.core.objects.port_modes import BOND_MEMBER
from tests.adapters.compliance_test_case import ComplianceTestCase


class AddInterfaceToBondTest(ComplianceTestCase):
    _dev_sample = "juniper"

    def setUp(self):
        super(AddInterfaceToBondTest, self).setUp()
        self.client.add_bond(42)

    def tearDown(self):
        self.janitor.remove_bond(42)
        super(AddInterfaceToBondTest, self).tearDown()

    def test_sets_the_interface_bond_master(self):
        self.client.add_interface_to_bond(self.test_port, 42)
        interface = self.client.get_interface(self.test_port)

        assert_that(interface.bond_master, is_(42))

        self.janitor.remove_interface_from_bond(self.test_port)

    def test_sets_the_interface_port_mode_to_bond_members(self):
        self.client.add_interface_to_bond(self.test_port, 42)
        interface = self.client.get_interface(self.test_port)

        assert_that(interface.port_mode, is_(BOND_MEMBER))

        self.janitor.remove_interface_from_bond(self.test_port)

    def test_raises_on_invalid_interface(self):
        with self.assertRaises(UnknownInterface):
            self.client.add_interface_to_bond("nonexistent 1/42", 42)

    def test_resets_the_interface_trunk_vlans(self):
        self.client.add_vlan(90)
        self.client.set_trunk_mode(self.test_port)
        self.client.add_trunk_vlan(self.test_port, 90)

        self.client.add_interface_to_bond(self.test_port, 42)
        interface = self.client.get_interface(self.test_port)

        assert_that(interface.trunk_vlans, is_(empty()))
        self.janitor.remove_vlan(90)
        self.janitor.remove_interface_from_bond(self.test_port)
        self.janitor.set_access_mode(self.test_port)

    def test_resets_the_interface_trunk_native_vlan(self):
        self.client.add_vlan(90)
        self.client.set_trunk_mode(self.test_port)
        self.client.set_interface_native_vlan(self.test_port, 90)

        self.client.add_interface_to_bond(self.test_port, 42)
        interface = self.client.get_interface(self.test_port)

        assert_that(interface.trunk_native_vlan, is_(none()))
        self.janitor.remove_vlan(90)
        self.janitor.remove_interface_from_bond(self.test_port)
        self.janitor.set_access_mode(self.test_port)

    def test_resets_the_interface_access_vlan(self):
        self.client.add_vlan(90)
        self.client.set_access_mode(self.test_port)
        self.client.set_access_vlan(self.test_port, 90)

        self.client.add_interface_to_bond(self.test_port, 42)
        interface = self.client.get_interface(self.test_port)

        assert_that(interface.access_vlan, is_(none()))
        self.janitor.remove_vlan(90)
