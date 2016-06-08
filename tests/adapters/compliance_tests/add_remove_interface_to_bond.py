from hamcrest import is_, assert_that, has_item
from netman.core.objects.exceptions import InterfaceNotInBond
from tests.adapters.compliance_test_case import ComplianceTestCase


class AddRemoveInterfaceToBond(ComplianceTestCase):
    _dev_sample = "juniper"

    def test_add_remove_interface(self):
        self.client.add_bond(42)
        self.client.add_interface_to_bond(self.test_port, 42)

        interface = self.client.get_interface(self.test_port)
        assert_that(interface.bond_master, is_(42))

        self.client.remove_interface_from_bond(self.test_port)

        interface = self.client.get_interface(self.test_port)
        assert_that(interface.bond_master, is_(None))

        self.janitor.remove_bond(42)

    def test_remove_interface_not_existent(self):
        with self.assertRaises(InterfaceNotInBond):
            self.client.remove_interface_from_bond(self.test_ports[1].name)
