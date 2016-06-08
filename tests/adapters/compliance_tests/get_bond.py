from hamcrest import assert_that, equal_to
from tests.adapters.compliance_test_case import ComplianceTestCase


class GetBondTest(ComplianceTestCase):
    _dev_sample = "juniper"

    def test_get_bond_and_get_bonds_return_the_same(self):
        self.client.add_bond(42)

        bond_from_get_bond = self.client.get_bond(42)
        bond_from_get_bonds = [bond for bond in self.client.get_bonds() if bond.number == 42][0]

        assert_that(bond_from_get_bond, equal_to(bond_from_get_bonds))

        self.janitor.remove_bond(42)
