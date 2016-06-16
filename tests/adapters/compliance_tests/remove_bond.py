from hamcrest import is_, has_item, not_
from hamcrest.core import assert_that
from netman.core.objects.exceptions import UnknownBond
from tests.adapters.compliance_test_case import ComplianceTestCase


class RemoveBondTest(ComplianceTestCase):
    _dev_sample = "juniper"

    def setUp(self):
        super(RemoveBondTest, self).setUp()
        self.client.add_bond(42)

    def tearDown(self):
        self.janitor.remove_bond(42)
        super(RemoveBondTest, self).tearDown()

    def test_removes_the_bond(self):
        self.client.remove_bond(42)

        with self.assertRaises(UnknownBond):
            assert_that(self.client.get_bond(42))

    def test_removes_bond_from_get_bonds(self):
        self.client.remove_bond(42)

        assert_that(self.client.get_bonds(), not_(has_item(42)))

    def test_raises_when_bond_does_not_exist(self):
        try:
            self.client.remove_bond(42)
        except UnknownBond:
            self.fail("should know this bond")

        with self.assertRaises(UnknownBond):
            self.client.remove_bond(42)

    def test_remove_its_members_from_the_bond(self):
        self.try_to.add_interface_to_bond(self.test_port, 42)

        self.client.remove_bond(42)
        
        interface = self.client.get_interface(self.test_port)
        assert_that(interface.bond_master, is_(None))

    def test_raises_on_out_of_range_bond_number(self):
        with self.assertRaises(UnknownBond):
            self.client.remove_bond(999)



