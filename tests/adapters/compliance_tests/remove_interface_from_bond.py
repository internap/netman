from hamcrest import assert_that, is_, has_item, not_
from netman.core.objects.exceptions import InterfaceNotInBond
from tests.adapters.compliance_test_case import ComplianceTestCase


class RemoveInterfaceFromBondTest(ComplianceTestCase):
    _dev_sample = "juniper"

    def setUp(self):
        super(RemoveInterfaceFromBondTest, self).setUp()
        self.interface_before = self.client.get_interface(self.test_port)
        self.client.add_bond(42)
        self.client.add_interface_to_bond(self.test_port, 42)

    def tearDown(self):
        self.janitor.remove_interface_from_bond(self.test_port)
        self.janitor.remove_bond(42)
        super(RemoveInterfaceFromBondTest, self).tearDown()

    def test_removes_interface_from_bond(self):
        self.client.remove_interface_from_bond(self.test_port)
        bond = self.client.get_bond(42)

        assert_that(bond.members, not_(has_item(self.test_port)))

    def test_removes_interface_bond_master(self):
        self.client.remove_interface_from_bond(self.test_port)
        interface = self.client.get_interface(self.test_port)

        assert_that(interface.bond_master, is_(None))

    def test_raises_if_interface_not_existent(self):
        with self.assertRaises(InterfaceNotInBond):
            self.client.remove_interface_from_bond(self.test_ports[1].name)

    def test_resets_the_interface_port_mode(self):
        self.client.remove_interface_from_bond(self.test_port)

        interface = self.client.get_interface(self.test_port)
        assert_that(self.interface_before.port_mode, is_(interface.port_mode))
