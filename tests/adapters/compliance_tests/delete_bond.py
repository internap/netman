from hamcrest import is_, empty
from hamcrest.core import assert_that
from netman.core.objects.exceptions import UnknownBond
from tests.adapters.compliance_test_case import ComplianceTestCase


class DeleteBondTest(ComplianceTestCase):
    _dev_sample = "juniper"

    def test_bond_is_deleted(self):
        self.client.add_bond(42)
        self.client.remove_bond(42)

        assert_that(self.client.get_bonds(), empty())

        with self.assertRaises(UnknownBond):
            assert_that(self.client.get_bond(42))

    def test_delete_twice_raises(self):
        self.client.add_bond(42)

        try:
            self.client.remove_bond(42)
        except UnknownBond:
            self.fail("should know this bond")

        with self.assertRaises(UnknownBond):
            self.client.remove_bond(42)

    def test_deletes_bond_members(self):
        self.client.add_bond(42)
        self.try_to.add_interface_to_bond(self.test_port, 42)

        self.client.remove_bond(42)
        
        interface = self.client.get_interface(self.test_port)
        assert_that(interface.bond_master, is_(None))

    def test_nonexistent_raises(self):
        with self.assertRaises(UnknownBond):
            self.client.remove_bond(999)



