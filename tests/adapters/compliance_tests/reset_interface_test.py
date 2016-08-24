from hamcrest import assert_that, is_

from netman.core.objects.exceptions import UnknownInterface
from netman.core.objects.interface_states import ON, OFF
from netman.core.objects.port_modes import ACCESS
from tests.adapters.compliance_test_case import ComplianceTestCase


class ResetInterfaceTest(ComplianceTestCase):
    _dev_sample = "juniper"

    def setUp(self):
        super(ResetInterfaceTest, self).setUp()
        self.interface_before = self.try_to.get_interface(self.test_port)

    def tearDown(self):
        self.janitor.remove_vlan(90)
        self.janitor.remove_bond(42)
        super(ResetInterfaceTest, self).tearDown()

    def test_reverts_trunk_vlans(self):
        self.try_to.add_vlan(90)

        self.try_to.set_trunk_mode(self.test_port)
        self.try_to.add_trunk_vlan(self.test_port, 90)

        self.client.reset_interface(self.test_port)

        assert_that(self.client.get_interface(self.test_port).trunk_vlans, is_(self.interface_before.trunk_vlans))

    def test_reverts_trunk_native_vlan(self):
        self.try_to.add_vlan(90)

        self.try_to.set_trunk_mode(self.test_port)
        self.try_to.set_interface_native_vlan(self.test_port, 90)

        self.client.reset_interface(self.test_port)

        assert_that(self.client.get_interface(self.test_port).trunk_native_vlan,
                    is_(self.interface_before.trunk_native_vlan))

    def test_reverts_port_mode(self):
        if self.interface_before.port_mode == ACCESS:
            self.try_to.set_trunk_mode(self.test_port)
        else:
            self.try_to.set_access_mode(self.test_port)

        self.client.reset_interface(self.test_port)

        assert_that(self.try_to.get_interface(self.test_port).port_mode, is_(self.interface_before.port_mode))

    def test_reverts_bond_master(self):
        self.try_to.add_bond(42)

        self.try_to.add_interface_to_bond(self.test_port, 42)

        self.client.reset_interface(self.test_port)

        actual_interface = self.try_to.get_interface(self.test_port)
        assert_that(actual_interface.bond_master, is_(self.interface_before.bond_master))

    def test_reverts_port_shutdown(self):
        if not self.interface_before.shutdown or self.interface_before.shutdown is OFF:
            self.try_to.set_interface_state(self.test_port, ON)
        else:
            self.try_to.set_interface_state(self.test_port, OFF)

        self.client.reset_interface(self.test_port)

        assert_that(self.client.get_interface(self.test_port).shutdown, is_(self.interface_before.shutdown))

    def test_reset_interface_mtu(self):
        self.try_to.set_interface_mtu(self.test_port, 4000)

        self.client.reset_interface(self.test_port)

        assert_that(self.client.get_interface(self.test_port).mtu, is_(self.interface_before.mtu))

    def test_raises_on_unknown_interface(self):
        with self.assertRaises(UnknownInterface):
            self.client.reset_interface('nonexistent 2/99')
