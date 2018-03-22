from hamcrest import assert_that, is_

from adapters.compliance_test_case import ComplianceTestCase
from netman.core.objects.exceptions import UnknownVlan
from tests import has_message


class SetVlanNtpStateTest(ComplianceTestCase):
    _dev_sample = "cisco"

    def setUp(self):
        super(SetVlanNtpStateTest, self).setUp()
        self.client.add_vlan(2999, name="my-test-vlan")

    def test_disables_ntp_when_given_false(self):
        self.try_to.set_vlan_ntp_state(2999, False)
        vlan = self.get_vlan_from_list(2999)
        assert_that(vlan.ntp, is_(False))

    def test_enables_ntp_when_given_true(self):
        self.try_to.set_vlan_ntp_state(2999, True)
        vlan = self.get_vlan_from_list(2999)
        assert_that(vlan.ntp, is_(True))

    def test_raises_UnknownVlan_when_operating_on_a_vlan_that_does_not_exist(self):
        with self.assertRaises(UnknownVlan) as expect:
            self.client.set_vlan_ntp_state(2000, False)

        assert_that(expect.exception, has_message("Vlan 2000 not found"))

    def tearDown(self):
        self.janitor.remove_vlan(2999)
        super(SetVlanNtpStateTest, self).tearDown()
