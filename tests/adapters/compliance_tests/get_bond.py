from hamcrest import assert_that, equal_to
from netman.core.objects.exceptions import UnknownBond
from tests.adapters.compliance_test_case import ComplianceTestCase


class GetBondTest(ComplianceTestCase):
    _dev_sample = "juniper"

    def setUp(self):
        super(GetBondTest, self).setUp()
        self.client.add_bond(42)
        self.client.add_vlan(99)

    def tearDown(self):
        self.janitor.remove_bond(42)
        self.janitor.remove_vlan(99)
        super(GetBondTest, self).tearDown()

    def test_get_bond_and_get_bonds_return_the_same_for_sport_speed(self):
        self.try_to.set_bond_link_speed(42, '1g')

        from_get_bond, from_get_bonds = self._get_bond_results(42)

        assert_that(from_get_bond.link_speed, equal_to(from_get_bonds.link_speed))

    def test_get_bond_and_get_bonds_return_the_same_on_access_mode(self):
        self.try_to.set_bond_access_mode(42)

        from_get_bond, from_get_bonds = self._get_bond_results(42)

        assert_that(from_get_bond.port_mode, equal_to(from_get_bonds.port_mode))

    def test_get_bond_and_get_bonds_return_the_same_on_trunk_mode(self):
        self.try_to.add_vlan(100)
        self.try_to.set_bond_trunk_mode(42)
        self.try_to.set_bond_native_vlan(42, 99)
        self.try_to.add_bond_trunk_vlan(42, 100)

        from_get_bond, from_get_bonds = self._get_bond_results(42)

        assert_that(from_get_bond.port_mode, equal_to(from_get_bonds.port_mode))
        assert_that(from_get_bond.trunk_vlans, equal_to(from_get_bonds.trunk_vlans))
        assert_that(from_get_bond.trunk_native_vlan, equal_to(from_get_bonds.trunk_native_vlan))

        self.janitor.remove_vlan(100)

    def _get_bond_results(self, bond_number):
        return self.client.get_bond(bond_number), \
               [bond for bond in self.client.get_bonds() if bond.number == bond_number][0]

    def test_raises_when_bond_does_not_exist(self):
        with self.assertRaises(UnknownBond):
            self.client.get_bond(999)
