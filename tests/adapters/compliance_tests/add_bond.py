from hamcrest import is_, assert_that
from netman.core.objects.exceptions import BondAlreadyExist, BadBondNumber
from tests.adapters.compliance_test_case import ComplianceTestCase


class AddBondTest(ComplianceTestCase):
    _dev_sample = "juniper"

    def test_creates_the_bond(self):
        self.client.add_bond(42)

        bond_from_get_bond = self.client.get_bond(42)

        assert_that(bond_from_get_bond.number, is_(42))

        self.janitor.remove_bond(42)

    def test_raises_if_bond_already_exists(self):
        self.client.add_bond(42)

        with self.assertRaises(BondAlreadyExist):
            self.client.add_bond(42)

        self.janitor.remove_bond(42)

    def test_raises_if_bond_number_is_out_of_range(self):
        with self.assertRaises(BadBondNumber):
            self.client.add_bond(1000)
