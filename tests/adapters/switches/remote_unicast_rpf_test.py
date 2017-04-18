import unittest

from flexmock import flexmock, flexmock_teardown

from netman.adapters.switches.remote import RemoteSwitch
from netman.core.objects.switch_descriptor import SwitchDescriptor
from netman.core.objects.unicast_rpf_modes import STRICT
from tests.adapters.switches.remote_test import Reply


class RemoteSwitchUnicastRpfTest(unittest.TestCase):
    netman_url = 'http://netman.example.org:1234'

    def setUp(self):
        self.switch = RemoteSwitch(SwitchDescriptor(
            model="juniper", hostname="toto", username="tutu",
            password="titi", port=1234, netman_server=self.netman_url))

        self.requests_mock = flexmock()
        self.switch.requests = self.requests_mock
        self.headers = {
            'Netman-Port': "1234",
            'Netman-Model': 'juniper',
            'Netman-Password': 'titi',
            'Netman-Username': 'tutu',
            'Netman-Max-Version': "2",
            'Netman-Verbose-Errors': 'yes',
        }

    def tearDown(self):
        flexmock_teardown()

    def test_set_vlan_unicast_rpf_mode_strict_should_send_true(self):
        self.requests_mock.should_receive("put").once().with_args(
            url=self.netman_url+'/switches/toto/vlans/2000/unicast-rpf-mode',
            headers=self.headers,
            data=str(STRICT)
        ).and_return(
            Reply(
                content='',
                status_code=204))

        self.switch.set_vlan_unicast_rpf_mode(2000, STRICT)

    def test_unset_vlan_unicast_rpf_mode_should_send_true(self):
        self.requests_mock.should_receive("delete").once().with_args(
            url=self.netman_url+'/switches/toto/vlans/2000/unicast-rpf-mode',
            headers=self.headers,
        ).and_return(
            Reply(
                content='',
                status_code=204))

        self.switch.unset_vlan_unicast_rpf_mode(2000)
