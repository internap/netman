# Copyright 2015 Internap.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import unittest

from hamcrest import assert_that, equal_to, is_, instance_of
import mock
from ncclient.operations import RPCError
from netaddr import IPAddress
from flexmock import flexmock, flexmock_teardown

from netman.core.objects.interface_states import OFF, ON
from tests import ExactIpNetwork, ignore_deprecation_warnings
from tests.api import open_fixture
from netman.adapters.switches.remote import RemoteSwitch, factory
from netman.core.objects.access_groups import IN, OUT
from netman.core.objects.exceptions import UnknownBond, VlanAlreadyExist, BadBondLinkSpeed, LockedSwitch, \
    NetmanException, UnknownInterface, UnknownSession, UnknownVlan
from netman.core.objects.port_modes import ACCESS, TRUNK, DYNAMIC
from netman.core.objects.switch_descriptor import SwitchDescriptor


class AnException(Exception):
    pass


@ignore_deprecation_warnings
def test_factory():
    switch = factory(SwitchDescriptor(hostname='hostname', model='juniper', username='username', password='password', port=22))

    assert_that(switch, instance_of(RemoteSwitch))
    assert_that(switch.switch_descriptor.hostname, equal_to("hostname"))
    assert_that(switch.switch_descriptor.model, equal_to("juniper"))
    assert_that(switch.switch_descriptor.username, equal_to("username"))
    assert_that(switch.switch_descriptor.password, equal_to("password"))
    assert_that(switch.switch_descriptor.port, equal_to(22))


class RemoteSwitchTest(unittest.TestCase):
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

    def test_switch_has_a_logger_configured_with_the_switch_name(self):
        assert_that(self.switch.logger.name, is_(RemoteSwitch.__module__ + ".toto"))

    @mock.patch('uuid.uuid4')
    def test_start_then_commit_returns_to_normal_behavior(self, m_uuid):
        m_uuid.return_value = '0123456789'
        self.headers['Netman-Session-Id'] = '0123456789'
        self.requests_mock.should_receive("post").once().with_args(
            url=self.netman_url+'/switches-sessions/0123456789',
            headers=self.headers,
            data=JsonData(hostname="toto")
        ).and_return(
            Reply(
                content=json.dumps({'session_id': '0123456789'}),
                status_code=201))
        self.requests_mock.should_receive("post").once().with_args(
            url=self.netman_url+'/switches-sessions/0123456789/actions',
            data='start_transaction',
            headers={'Netman-Verbose-Errors': "yes",
                     'Netman-Max-Version': "2",
                     'Netman-Session-Id': '0123456789'}
        ).and_return(
            Reply(
                content="",
                status_code=204))
        self.requests_mock.should_receive("post").once().with_args(
            url=self.netman_url+'/switches-sessions/0123456789/actions',
            data='commit',
            headers={'Netman-Verbose-Errors': "yes",
                     'Netman-Max-Version': "2",
                     'Netman-Session-Id': '0123456789'}
        ).and_return(
            Reply(
                content="",
                status_code=204))
        self.requests_mock.should_receive("post").once().with_args(
            url=self.netman_url+'/switches-sessions/0123456789/actions',
            data='end_transaction',
            headers={'Netman-Verbose-Errors': "yes",
                     'Netman-Max-Version': "2",
                     'Netman-Session-Id': '0123456789'}
        ).and_return(
            Reply(
                content="",
                status_code=204))
        self.requests_mock.should_receive("delete").once().with_args(
            url=self.netman_url+'/switches-sessions/0123456789',
            headers={'Netman-Verbose-Errors': "yes",
                     'Netman-Max-Version': "2",
                     'Netman-Session-Id': '0123456789'}
        ).and_return(
            Reply(
                content="",
                status_code=204))

        self.switch.connect()
        self.switch.start_transaction()
        self.switch.commit_transaction()
        self.switch.end_transaction()
        self.switch.disconnect()
        self.setUp()
        self.test_add_bond()

    @mock.patch('uuid.uuid4')
    def test_connect_fails_to_obtain_a_session(self, m_uuid):
        m_uuid.return_value = '0123456789'
        self.headers['Netman-Session-Id'] = '0123456789'
        self.requests_mock.should_receive("post").once().with_args(
            url=self.netman_url+'/switches-sessions/0123456789',
            headers=self.headers,
            data=JsonData(hostname="toto")
        ).and_return(
            Reply(
                content=json.dumps({
                    "error": "",
                    "error-module": AnException.__module__,
                    "error-class": AnException.__name__
                }),
                status_code=500))

        with self.assertRaises(AnException):
            self.switch.connect()

    @mock.patch('uuid.uuid4')
    def test_disconnect_fails_and_return_to_normal_behavior(self, m_uuid):
        m_uuid.return_value = '0123456789'
        self.headers['Netman-Session-Id'] = '0123456789'
        self.requests_mock.should_receive("post").once().with_args(
            url=self.netman_url+'/switches-sessions/0123456789',
            headers=self.headers,
            data=JsonData(hostname="toto")
        ).and_return(
            Reply(
                content=json.dumps({'session_id': '0123456789'}),
                status_code=201))

        self.requests_mock.should_receive("delete").once().with_args(
            url=self.netman_url+'/switches-sessions/0123456789',
            headers={'Netman-Verbose-Errors': "yes",
                     'Netman-Max-Version': "2",
                     'Netman-Session-Id': '0123456789'}
        ).and_return(
            Reply(
                content=json.dumps({
                    "error": "",
                    "error-module": AnException.__module__,
                    "error-class": AnException.__name__
                }),
                status_code=500))

        self.switch.connect()
        with self.assertRaises(AnException):
            self.switch.disconnect()
        self.setUp()
        self.test_add_bond()

    @mock.patch('uuid.uuid4')
    def test_session_is_used_when_we_are_in_a_session(self, m_uuid):
        m_uuid.return_value = '0123456789'
        self.headers['Netman-Session-Id'] = '0123456789'
        self.requests_mock.should_receive("post").once().with_args(
            url=self.netman_url+'/switches-sessions/0123456789',
            headers=self.headers,
            data=JsonData(hostname="toto")
        ).and_return(
            Reply(
                content=json.dumps({'session_id': '0123456789'}),
                status_code=201))

        self.requests_mock.should_receive("post").once().with_args(
            url=self.netman_url+'/switches-sessions/0123456789/bonds',
            headers=self.headers,
            data=JsonData(number=6)
        ).and_return(
            Reply(
                content='',
                status_code=201))

        self.switch.connect()
        self.switch.add_bond(6)

    @mock.patch('uuid.uuid4')
    def test_commit_transaction_fails_to_commit(self, m_uuid):
        m_uuid.return_value = '0123456789'

        self.headers['Netman-Session-Id'] = '0123456789'
        self.requests_mock.should_receive("post").once().with_args(
            url=self.netman_url+'/switches-sessions/0123456789',
            headers=self.headers,
            data=JsonData(hostname="toto")
        ).and_return(
            Reply(
                content=json.dumps({'session_id': '0123456789'}),
                status_code=201))

        self.requests_mock.should_receive("post").once().with_args(
            url=self.netman_url+'/switches-sessions/0123456789/actions',
            data='commit',
            headers={'Netman-Verbose-Errors': "yes",
                     'Netman-Max-Version': "2",
                     'Netman-Session-Id': '0123456789'}
        ).and_return(
            Reply(
                content=json.dumps({
                    "error": "",
                    "error-module": AnException.__module__,
                    "error-class": AnException.__name__
                }),
                status_code=500))

        self.switch.connect()
        with self.assertRaises(AnException):
            self.switch.commit_transaction()

    @mock.patch('uuid.uuid4')
    def test_rollback_transaction_fails_to_rollback(self, m_uuid):
        m_uuid.return_value = '0123456789'
        self.headers['Netman-Session-Id'] = '0123456789'
        self.requests_mock.should_receive("post").once().ordered().with_args(
            url=self.netman_url+'/switches-sessions/0123456789',
            headers=self.headers,
            data=JsonData(hostname="toto")
        ).and_return(
            Reply(
                content=json.dumps({'session_id': '0123456789'}),
                status_code=201))

        self.requests_mock.should_receive("post").once().ordered().with_args(
            url=self.netman_url+'/switches-sessions/0123456789/actions',
            data='rollback',
            headers={'Netman-Verbose-Errors': "yes",
                     'Netman-Max-Version': "2",
                     'Netman-Session-Id': '0123456789'}
        ).and_return(
            Reply(
                content=json.dumps({
                    "error": "",
                    "error-module": AnException.__module__,
                    "error-class": AnException.__name__
                }),
                status_code=500))

        self.switch.connect()
        with self.assertRaises(AnException):
            self.switch.rollback_transaction()

    @mock.patch('uuid.uuid4')
    def test_receiving_unknown_session_during_transaction_will_connect_again(self, m_uuid):
        m_uuid.return_value = '0123456789'
        first_connect_headers = self.headers.copy()
        first_connect_headers['Netman-Session-Id'] = '0123456789'

        self.requests_mock.should_receive("post").once().with_args(
            url=self.netman_url+'/switches-sessions/0123456789',
            headers=first_connect_headers,
            data=JsonData(hostname="toto")
        ).and_return(
            Reply(
                content=json.dumps({'session_id': '0123456789'}),
                status_code=201))

        self.switch.connect()

        self.requests_mock.should_receive("post").once().with_args(
            url=self.netman_url+'/switches-sessions/0123456789/bonds',
            headers=first_connect_headers,
            data=JsonData(number=6)
        ).and_return(
            Reply(
                content=json.dumps({
                    "error": "",
                    "error-module": UnknownSession.__module__,
                    "error-class": UnknownSession.__name__
                }),
                status_code=500))

        m_uuid.return_value = 'new-session-id'
        second_connect_headers = self.headers.copy()
        second_connect_headers['Netman-Session-Id'] = 'new-session-id'

        self.requests_mock.should_receive("post").once().with_args(
            url=self.netman_url+'/switches-sessions/new-session-id',
            headers=second_connect_headers,
            data=JsonData(hostname="toto")
        ).and_return(
            Reply(
                content=json.dumps({'session_id': 'new-session-id'}),
                status_code=201))

        self.requests_mock.should_receive("post").once().with_args(
            url=self.netman_url+'/switches-sessions/new-session-id/bonds',
            headers=second_connect_headers,
            data=JsonData(number=6)
        ).and_return(
            Reply(
                content='',
                status_code=201))

        self.switch.add_bond(6)

    @mock.patch('uuid.uuid4')
    def test_receiving_unknown_session_twice_during_transaction_will_raise_an_exception(self, m_uuid):
        m_uuid.return_value = '0123456789'
        first_connect_headers = self.headers.copy()
        first_connect_headers['Netman-Session-Id'] = '0123456789'

        self.requests_mock.should_receive("post").once().with_args(
            url=self.netman_url+'/switches-sessions/0123456789',
            headers=first_connect_headers,
            data=JsonData(hostname="toto")
        ).and_return(
            Reply(
                content=json.dumps({'session_id': '0123456789'}),
                status_code=201))

        self.switch.connect()

        self.requests_mock.should_receive("post").once().with_args(
            url=self.netman_url+'/switches-sessions/0123456789/bonds',
            headers=first_connect_headers,
            data=JsonData(number=6)
        ).and_return(
            Reply(
                content=json.dumps({
                    "error": "",
                    "error-module": UnknownSession.__module__,
                    "error-class": UnknownSession.__name__
                }),
                status_code=500))

        m_uuid.return_value = 'new-session-id'
        second_connect_headers = self.headers.copy()
        second_connect_headers['Netman-Session-Id'] = 'new-session-id'

        self.requests_mock.should_receive("post").once().with_args(
            url=self.netman_url+'/switches-sessions/new-session-id',
            headers=second_connect_headers,
            data=JsonData(hostname="toto")
        ).and_return(
            Reply(
                content=json.dumps({'session_id': 'new-session-id'}),
                status_code=201))

        self.requests_mock.should_receive("post").once().with_args(
            url=self.netman_url+'/switches-sessions/new-session-id/bonds',
            headers=second_connect_headers,
            data=JsonData(number=6)
        ).and_return(
            Reply(
                content=json.dumps({
                    "error": "",
                    "error-module": UnknownSession.__module__,
                    "error-class": UnknownSession.__name__
                }),
                status_code=500))

        with self.assertRaises(UnknownSession):
            self.switch.add_bond(6)

    @mock.patch('uuid.uuid4')
    def test_multi_proxy_1(self, m_uuid):
        self.switch = RemoteSwitch(SwitchDescriptor(
            model="juniper", hostname="toto", username="tutu",
            password="titi", port=1234, netman_server=[self.netman_url, "1.2.3.4"]))

        self.requests_mock = flexmock()
        self.switch.requests = self.requests_mock

        m_uuid.return_value = '0123456789'
        self.requests_mock.should_receive("post").once().ordered().with_args(
            url=self.netman_url+'/switches-sessions/0123456789',
            headers={
                'Netman-Port': "1234",
                'Netman-Model': 'juniper',
                'Netman-Password': 'titi',
                'Netman-Username': 'tutu',
                'Netman-Verbose-Errors': 'yes',
                'Netman-Proxy-Server': '1.2.3.4',
                'Netman-Max-Version': "2",
                'Netman-Session-Id': '0123456789'
            },
            data=JsonData(hostname="toto")
        ).and_return(
            Reply(
                content=json.dumps({'session_id': '0123456789'}),
                status_code=201))

        self.requests_mock.should_receive("delete").once().with_args(
            url=self.netman_url+'/switches-sessions/0123456789',
            headers={'Netman-Verbose-Errors': "yes",
                     'Netman-Max-Version': "2",
                     'Netman-Session-Id': '0123456789'}
        ).and_return(
            Reply(
                content="",
                status_code=204))

        self.switch.connect()
        self.switch.disconnect()
        self.setUp()
        self.test_add_bond()

    @mock.patch('uuid.uuid4')
    def test_multi_proxy_few(self, m_uuid):
        self.switch = RemoteSwitch(SwitchDescriptor(
            model="juniper", hostname="toto", username="tutu",
            password="titi", port=1234, netman_server=[self.netman_url, "1.2.3.4", "5.6.7.8"]))

        self.requests_mock = flexmock()
        self.switch.requests = self.requests_mock

        m_uuid.return_value = '0123456789'
        self.requests_mock.should_receive("post").once().ordered().with_args(
            url=self.netman_url+'/switches-sessions/0123456789',
            headers={
                'Netman-Port': "1234",
                'Netman-Model': 'juniper',
                'Netman-Password': 'titi',
                'Netman-Username': 'tutu',
                'Netman-Verbose-Errors': 'yes',
                'Netman-Proxy-Server': '1.2.3.4,5.6.7.8',
                'Netman-Max-Version': "2",
                'Netman-Session-Id': '0123456789'
            },
            data=JsonData(hostname="toto")
        ).and_return(
            Reply(
                content=json.dumps({'session_id': '0123456789'}),
                status_code=201))

        self.requests_mock.should_receive("delete").once().with_args(
            url=self.netman_url+'/switches-sessions/0123456789',
            headers={'Netman-Verbose-Errors': "yes",
                     'Netman-Max-Version': "2",
                     'Netman-Session-Id': '0123456789'}
        ).and_return(
            Reply(
                content="",
                status_code=204))

        self.switch.connect()
        self.switch.disconnect()
        self.setUp()
        self.test_add_bond()

    def test_get_vlan(self):
        self.requests_mock.should_receive("get").once().with_args(
            url=self.netman_url+'/switches/toto/vlans/1',
            headers=self.headers
        ).and_return(
            Reply(
                content=open_fixture('get_switch_hostname_vlans_vlan.json').read(),
                status_code=200))

        vlan1 = self.switch.get_vlan(1)

        assert_that(vlan1.number, is_(1))
        assert_that(vlan1.name, is_('One'))
        assert_that(vlan1.ips, is_([ExactIpNetwork('1.1.1.1', 24)]))
        assert_that(vlan1.vrf_forwarding, is_("MY_VRF"))
        assert_that(vlan1.access_groups[IN], is_("Blah_blah"))
        assert_that(vlan1.access_groups[OUT], is_(None))
        assert_that(vlan1.dhcp_relay_servers, is_([]))
        vrrp_group = vlan1.vrrp_groups[0]
        assert_that(vrrp_group.id, is_(1))
        assert_that(vrrp_group.ips, is_([IPAddress("1.1.1.2")]))
        assert_that(vrrp_group.priority, is_(90))
        assert_that(vrrp_group.hello_interval, is_(5))
        assert_that(vrrp_group.dead_interval, is_(15))
        assert_that(vrrp_group.track_id, is_("101"))
        assert_that(vrrp_group.track_decrement, is_(50))

    def test_get_vlans(self):
        self.requests_mock.should_receive("get").once().with_args(
            url=self.netman_url+'/switches/toto/vlans',
            headers=self.headers
        ).and_return(
            Reply(
                content=open_fixture('get_switch_hostname_vlans.json').read(),
                status_code=200))

        vlan1, vlan2 = self.switch.get_vlans()

        assert_that(vlan1.number, is_(1))
        assert_that(vlan1.name, is_('One'))
        assert_that(vlan1.ips, is_([ExactIpNetwork('1.1.1.1', 24)]))
        assert_that(vlan1.vrf_forwarding, is_("MY_VRF"))
        assert_that(vlan1.access_groups[IN], is_("Blah_blah"))
        assert_that(vlan1.access_groups[OUT], is_(None))
        assert_that(vlan1.dhcp_relay_servers, is_([]))
        vrrp_group = vlan1.vrrp_groups[0]        
        assert_that(vrrp_group.id, is_(1))
        assert_that(vrrp_group.ips, is_([IPAddress("1.1.1.2")]))
        assert_that(vrrp_group.priority, is_(90))
        assert_that(vrrp_group.hello_interval, is_(5))
        assert_that(vrrp_group.dead_interval, is_(15))
        assert_that(vrrp_group.track_id, is_("101"))
        assert_that(vrrp_group.track_decrement, is_(50))

        assert_that(vlan2.number, is_(2))
        assert_that(vlan2.name, is_(''))
        assert_that(vlan2.ips, is_([ExactIpNetwork('2.2.2.2', 24), ExactIpNetwork('3.3.3.3', 24)]))
        assert_that(vlan2.vrf_forwarding, is_(None))
        assert_that(vlan2.access_groups[IN], is_(None))
        assert_that(vlan2.access_groups[OUT], is_(None))
        assert_that(vlan2.dhcp_relay_servers, is_([IPAddress("10.10.10.1")]))
        vrrp_group1, vrrp_group2 = vlan2.vrrp_groups
        assert_that(vrrp_group1.id, is_(1))
        assert_that(vrrp_group1.ips, is_([IPAddress("2.2.2.2")]))
        assert_that(vrrp_group1.priority, is_(100))
        assert_that(vrrp_group1.hello_interval, is_(None))
        assert_that(vrrp_group1.dead_interval, is_(None))
        assert_that(vrrp_group1.track_id, is_(None))
        assert_that(vrrp_group1.track_decrement, is_(None))
        assert_that(vrrp_group2.id, is_(2))
        assert_that(vrrp_group2.ips, is_([IPAddress("3.3.3.1")]))
        assert_that(vrrp_group2.priority, is_(100))

    def test_get_vlan_interfaces(self):
        self.requests_mock.should_receive("get").once().with_args(
                url=self.netman_url+'/switches/toto/vlans/1/interfaces',
                headers=self.headers
        ).and_return(
            Reply(
                content=open_fixture('get_switch_hostname_vlans_vlan_interfaces.json').read(),
                status_code=200)
        )

        interfaces = self.switch.get_vlan_interfaces(1)

        assert_that(interfaces, is_(["ethernet 1/4", "FastEthernet0/3", "GigabitEthernet0/8"]))

    def test_get_vlan_interfaces_with_no_vlan_raises(self):
        self.requests_mock.should_receive("get").once().with_args(
                url=self.netman_url+'/switches/toto/vlans/4000/interfaces',
                headers=self.headers
        ).and_return(
                Reply(
                        content=json.dumps({
                            "error": "Vlan 4000 not found",
                            "error-module": UnknownVlan.__module__,
                            "error-class": UnknownVlan.__name__
                        }),
                        status_code=404))

        with self.assertRaises(UnknownVlan) as expect:
            self.switch.get_vlan_interfaces('4000')

        assert_that(str(expect.exception), equal_to("Vlan 4000 not found"))

    def test_get_interface(self):
        self.requests_mock.should_receive("get").once().with_args(
                url=self.netman_url+'/switches/toto/interfaces/ethernet 1/4',
                headers=self.headers
        ).and_return(
                Reply(
                        content=open_fixture('get_switch_hostname_interface.json').read(),
                        status_code=200))

        interface = self.switch.get_interface('ethernet 1/4')

        assert_that(interface.name, equal_to("ethernet 1/4"))
        assert_that(interface.shutdown, equal_to(False))
        assert_that(interface.port_mode, equal_to(TRUNK))
        assert_that(interface.access_vlan, equal_to(None))
        assert_that(interface.trunk_native_vlan, equal_to(2999))
        assert_that(interface.trunk_vlans, equal_to([3000, 3001, 3002]))

    def test_get_nonexistent_interface_raises(self):
        self.requests_mock.should_receive("get").once().with_args(
                url=self.netman_url+'/switches/toto/interfaces/ethernet 1/INEXISTENT',
                headers=self.headers
        ).and_return(
                Reply(
                        content=json.dumps({
                            "error": "Interface ethernet 1/INEXISTENT not found",
                            "error-module": UnknownInterface.__module__,
                            "error-class": UnknownInterface.__name__
                        }),
                        status_code=404))

        with self.assertRaises(UnknownInterface) as expect:
            self.switch.get_interface('ethernet 1/INEXISTENT')

        assert_that(str(expect.exception), equal_to("Interface ethernet 1/INEXISTENT not found"))

    def test_get_interfaces(self):
        self.requests_mock.should_receive("get").once().with_args(
            url=self.netman_url+'/switches/toto/interfaces',
            headers=self.headers
        ).and_return(
            Reply(
                content=open_fixture('get_switch_hostname_interfaces.json').read(),
                status_code=200))

        if1, if2, if3, if4 = self.switch.get_interfaces()

        assert_that(if1.name, equal_to("ethernet 1/4"))
        assert_that(if1.shutdown, equal_to(False))
        assert_that(if1.port_mode, equal_to(TRUNK))
        assert_that(if1.access_vlan, equal_to(None))
        assert_that(if1.trunk_native_vlan, equal_to(2999))
        assert_that(if1.trunk_vlans, equal_to([3000, 3001, 3002]))

        assert_that(if2.name, equal_to("FastEthernet0/3"))
        assert_that(if2.shutdown, equal_to(True))
        assert_that(if2.port_mode, equal_to(ACCESS))
        assert_that(if2.access_vlan, equal_to(1999))
        assert_that(if2.trunk_native_vlan, equal_to(None))
        assert_that(if2.trunk_vlans, equal_to([]))

        assert_that(if3.name, equal_to("GigabitEthernet0/6"))
        assert_that(if3.port_mode, equal_to(DYNAMIC))
        assert_that(if3.access_vlan, equal_to(1999))
        assert_that(if3.trunk_native_vlan, equal_to(2999))
        assert_that(if3.trunk_vlans, equal_to([3000, 3001, 3002]))

        assert_that(if4.name, equal_to("GigabitEthernet0/8"))
        assert_that(if4.shutdown, equal_to(False))
        assert_that(if4.bond_master, equal_to(12))

    @ignore_deprecation_warnings
    def test_get_bond_v1(self):
        self.requests_mock.should_receive("get").once().with_args(
            url=self.netman_url+'/switches/toto/bonds/3',
            headers=self.headers
        ).and_return(
            Reply(
                content=open_fixture('get_switch_hostname_bond_v1.json').read(),
                status_code=200))

        if1 = self.switch.get_bond(3)

        assert_that(if1.number, equal_to(3))
        assert_that(if1.link_speed, equal_to('1g'))
        assert_that(if1.interface.name, equal_to(None))
        assert_that(if1.interface.shutdown, equal_to(True))
        assert_that(if1.interface.port_mode, equal_to(ACCESS))
        assert_that(if1.interface.access_vlan, equal_to(1999))
        assert_that(if1.interface.trunk_native_vlan, equal_to(None))
        assert_that(if1.interface.trunk_vlans, equal_to([]))
        assert_that(if1.members, equal_to([]))

    def test_get_bond_v2(self):
        self.requests_mock.should_receive("get").once().with_args(
            url=self.netman_url+'/switches/toto/bonds/3',
            headers=self.headers
        ).and_return(
            Reply(
                headers={'Netman-Version': '2'},
                content=open_fixture('get_switch_hostname_bond_v2.json').read(),
                status_code=200))

        if1 = self.switch.get_bond(3)

        assert_that(if1.number, equal_to(3))
        assert_that(if1.link_speed, equal_to('1g'))
        assert_that(if1.shutdown, equal_to(True))
        assert_that(if1.port_mode, equal_to(ACCESS))
        assert_that(if1.access_vlan, equal_to(1999))
        assert_that(if1.trunk_native_vlan, equal_to(None))
        assert_that(if1.trunk_vlans, equal_to([]))
        assert_that(if1.members, equal_to([]))

    def test_get_bonds_v1(self):
        self.requests_mock.should_receive("get").once().with_args(
            url=self.netman_url+'/switches/toto/bonds',
            headers=self.headers
        ).and_return(
            Reply(
                content=open_fixture('get_switch_hostname_bonds_v1.json').read(),
                status_code=200))

        if1, if2, if3 = self.switch.get_bonds()

        assert_that(if1.number, equal_to(3))
        assert_that(if1.link_speed, equal_to('1g'))
        assert_that(if1.interface.name, equal_to(None))
        assert_that(if1.interface.shutdown, equal_to(True))
        assert_that(if1.interface.port_mode, equal_to(ACCESS))
        assert_that(if1.interface.access_vlan, equal_to(1999))
        assert_that(if1.interface.trunk_native_vlan, equal_to(None))
        assert_that(if1.interface.trunk_vlans, equal_to([]))
        assert_that(if1.members, equal_to([]))

        assert_that(if2.number, equal_to(4))
        assert_that(if2.members, equal_to(["ge-0/0/1", "ge-1/0/1"]))
        assert_that(if2.interface.name, equal_to(None))
        assert_that(if2.interface.shutdown, equal_to(False))
        assert_that(if2.interface.port_mode, equal_to(TRUNK))
        assert_that(if2.interface.access_vlan, equal_to(None))
        assert_that(if2.interface.trunk_native_vlan, equal_to(2999))
        assert_that(if2.interface.trunk_vlans, equal_to([3000, 3001, 3002]))

        assert_that(if3.number, equal_to(6))
        assert_that(if3.link_speed, equal_to('10g'))
        assert_that(if3.interface.name, equal_to(None))
        assert_that(if3.interface.shutdown, equal_to(False))
        assert_that(if3.interface.port_mode, equal_to(DYNAMIC))
        assert_that(if3.interface.access_vlan, equal_to(1999))
        assert_that(if3.interface.trunk_native_vlan, equal_to(2999))
        assert_that(if3.interface.trunk_vlans, equal_to([3000, 3001, 3002]))
        assert_that(if3.members, equal_to([]))

    def test_get_bonds_v2(self):
        self.requests_mock.should_receive("get").once().with_args(
            url=self.netman_url+'/switches/toto/bonds',
            headers=self.headers
        ).and_return(
            Reply(
                headers={'Netman-Version': '2'},
                content=open_fixture('get_switch_hostname_bonds_v2.json').read(),
                status_code=200))

        if1, if2, if3 = self.switch.get_bonds()

        assert_that(if1.number, equal_to(3))
        assert_that(if1.link_speed, equal_to('1g'))
        assert_that(if1.shutdown, equal_to(True))
        assert_that(if1.port_mode, equal_to(ACCESS))
        assert_that(if1.access_vlan, equal_to(1999))
        assert_that(if1.trunk_native_vlan, equal_to(None))
        assert_that(if1.trunk_vlans, equal_to([]))
        assert_that(if1.members, equal_to([]))

        assert_that(if2.number, equal_to(4))
        assert_that(if2.members, equal_to(["ge-0/0/1", "ge-1/0/1"]))
        assert_that(if2.shutdown, equal_to(False))
        assert_that(if2.port_mode, equal_to(TRUNK))
        assert_that(if2.access_vlan, equal_to(None))
        assert_that(if2.trunk_native_vlan, equal_to(2999))
        assert_that(if2.trunk_vlans, equal_to([3000, 3001, 3002]))
        assert_that(if2.members, equal_to(['ge-0/0/1', 'ge-1/0/1']))

        assert_that(if3.number, equal_to(6))
        assert_that(if3.link_speed, equal_to('10g'))
        assert_that(if3.shutdown, equal_to(False))
        assert_that(if3.port_mode, equal_to(DYNAMIC))
        assert_that(if3.access_vlan, equal_to(1999))
        assert_that(if3.trunk_native_vlan, equal_to(2999))
        assert_that(if3.trunk_vlans, equal_to([3000, 3001, 3002]))
        assert_that(if3.members, equal_to([]))

    def test_add_vlan(self):
        self.requests_mock.should_receive("post").once().with_args(
            url=self.netman_url+'/switches/toto/vlans',
            headers=self.headers,
            data=JsonData(number=2000, name="deux-milles")
        ).and_return(
            Reply(
                content='',
                status_code=201))

        self.switch.add_vlan(2000, name="deux-milles")

    def test_add_vlan_without_a_name(self):
        self.requests_mock.should_receive("post").once().with_args(
            url=self.netman_url+'/switches/toto/vlans',
            headers=self.headers,
            data=JsonData(number=2000)
        ).and_return(
            Reply(
                content='',
                status_code=201))

        self.switch.add_vlan(2000)

    def test_add_vlan_already_exist(self):
        self.requests_mock.should_receive("post").once().with_args(
            url=self.netman_url+'/switches/toto/vlans',
            headers=self.headers,
            data=JsonData(number=2000, name="deux-milles")
        ).and_return(
            Reply(
                content=json.dumps({
                    "error": "Vlan 2000 already exists",
                    "error-module": VlanAlreadyExist.__module__,
                    "error-class": VlanAlreadyExist.__name__
                }),
                status_code=409))

        with self.assertRaises(VlanAlreadyExist) as expect:
            self.switch.add_vlan(2000, name="deux-milles")

        assert_that(str(expect.exception), equal_to("Vlan 2000 already exists"))

    def test_remove_vlan(self):
        self.requests_mock.should_receive("delete").once().with_args(
            url=self.netman_url+'/switches/toto/vlans/2000',
            headers=self.headers,
        ).and_return(
            Reply(
                content='',
                status_code=204))

        self.switch.remove_vlan(2000)

    def test_put_access_groups_in(self):
        self.requests_mock.should_receive("put").once().with_args(
            url=self.netman_url+'/switches/toto/vlans/2500/access-groups/in',
            headers=self.headers,
            data='spaceless-string'
        ).and_return(
            Reply(
                content='',
                status_code=204))

        self.switch.set_vlan_access_group(2500, IN, "spaceless-string")

    def test_put_access_groups_out(self):
        self.requests_mock.should_receive("put").once().with_args(
            url=self.netman_url+'/switches/toto/vlans/2500/access-groups/out',
            headers=self.headers,
            data='spaceless-string'
        ).and_return(
            Reply(
                content='',
                status_code=204))

        self.switch.set_vlan_access_group(2500, OUT, "spaceless-string")

    def test_remove_access_groups_in(self):
        self.requests_mock.should_receive("delete").once().with_args(
            url=self.netman_url+'/switches/toto/vlans/2500/access-groups/in',
            headers=self.headers
        ).and_return(
            Reply(
                content='',
                status_code=204))

        self.switch.unset_vlan_access_group(2500, IN)

    def test_remove_access_groups_out(self):
        self.requests_mock.should_receive("delete").once().with_args(
            url=self.netman_url+'/switches/toto/vlans/2500/access-groups/out',
            headers=self.headers
        ).and_return(
            Reply(
                content='',
                status_code=204))

        self.switch.unset_vlan_access_group(2500, OUT)

    def test_add_ip_to_vlan(self):
        self.requests_mock.should_receive("post").once().with_args(
            url=self.netman_url+'/switches/toto/vlans/2500/ips',
            headers=self.headers,
            data="1.2.3.4/25"
        ).and_return(
            Reply(
                content='',
                status_code=201))

        self.switch.add_ip_to_vlan(2500, ExactIpNetwork("1.2.3.4", 25))

    def test_remove_ip(self):
        self.requests_mock.should_receive("delete").once().with_args(
            url=self.netman_url+'/switches/toto/vlans/2500/ips/1.2.3.4/25',
            headers=self.headers
        ).and_return(
            Reply(
                content='',
                status_code=204))

        self.switch.remove_ip_from_vlan(2500, ExactIpNetwork("1.2.3.4", 25))

    def test_set_vlan_vrf(self):
        self.requests_mock.should_receive("put").once().with_args(
            url=self.netman_url+'/switches/toto/vlans/2500/vrf-forwarding',
            headers=self.headers,
            data="DEFAULT_LAN"
        ).and_return(
            Reply(
                content='',
                status_code=204))

        self.switch.set_vlan_vrf(2500, "DEFAULT_LAN")

    def test_unset_vlan_vrf(self):
        self.requests_mock.should_receive("delete").once().with_args(
            url=self.netman_url+'/switches/toto/vlans/2500/vrf-forwarding',
            headers=self.headers
        ).and_return(
            Reply(
                content='',
                status_code=204))

        self.switch.unset_vlan_vrf(2500)

    def test_port_mode_access(self):
        self.requests_mock.should_receive("put").once().with_args(
            url=self.netman_url+'/switches/toto/interfaces/ge-0/0/6/port-mode',
            headers=self.headers,
            data='access'
        ).and_return(
            Reply(
                content='',
                status_code=204))

        self.switch.set_access_mode("ge-0/0/6")

    def test_port_mode_trunk(self):
        self.requests_mock.should_receive("put").once().with_args(
            url=self.netman_url+'/switches/toto/interfaces/ge-0/0/6/port-mode',
            headers=self.headers,
            data='trunk'
        ).and_return(
            Reply(
                content='',
                status_code=204))

        self.switch.set_trunk_mode("ge-0/0/6")

    def test_bond_port_mode_access(self):
        self.requests_mock.should_receive("put").once().with_args(
            url=self.netman_url+'/switches/toto/bonds/123/port-mode',
            headers=self.headers,
            data='access'
        ).and_return(
            Reply(
                content='',
                status_code=204))

        self.switch.set_bond_access_mode(123)

    def test_bond_port_mode_trunk(self):
        self.requests_mock.should_receive("put").once().with_args(
            url=self.netman_url+'/switches/toto/bonds/123/port-mode',
            headers=self.headers,
            data='trunk'
        ).and_return(
            Reply(
                content='',
                status_code=204))

        self.switch.set_bond_trunk_mode(123)

    def test_set_access_vlan(self):
        self.requests_mock.should_receive("put").once().with_args(
            url=self.netman_url+'/switches/toto/interfaces/ge-0/0/6/access-vlan',
            headers=self.headers,
            data='1000'
        ).and_return(
            Reply(
                content='',
                status_code=204))

        self.switch.set_access_vlan("ge-0/0/6", 1000)

    def test_reset_interface(self):
        self.requests_mock.should_receive("put").once().with_args(
                url=self.netman_url+'/switches/toto/interfaces/ge-0/0/6',
                headers=self.headers,
                data=None
        ).and_return(
                Reply(
                        content='',
                        status_code=204))

        self.switch.reset_interface("ge-0/0/6")

    def test_reset_interface_with_unknown_interface_raises(self):
        self.requests_mock.should_receive("put").once().with_args(
                url=self.netman_url+'/switches/toto/interfaces/ne-0/0/66',
                headers=self.headers,
                data=None
        ).and_return(
                Reply(
                        content=json.dumps({
                            "error": "Interface ethernet ne-0/0/66 not found",
                            "error-module": UnknownInterface.__module__,
                            "error-class": UnknownInterface.__name__
                        }),
                        status_code=404))

        with self.assertRaises(UnknownInterface):
            self.switch.reset_interface('ne-0/0/66')

    def test_unset_interface_access_vlan(self):
        self.requests_mock.should_receive("delete").once().with_args(
            url=self.netman_url+'/switches/toto/interfaces/ge-0/0/6/access-vlan',
            headers=self.headers
        ).and_return(
            Reply(
                content='',
                status_code=204))

        self.switch.unset_interface_access_vlan("ge-0/0/6")

    def test_set_interface_native_vlan(self):
        self.requests_mock.should_receive("put").once().with_args(
            url=self.netman_url+'/switches/toto/interfaces/ge-0/0/6/trunk-native-vlan',
            headers=self.headers,
            data='1000'
        ).and_return(
            Reply(
                content='',
                status_code=204))

        self.switch.set_interface_native_vlan("ge-0/0/6", 1000)

    def test_unset_interface_native_vlan(self):
        self.requests_mock.should_receive("delete").once().with_args(
            url=self.netman_url+'/switches/toto/interfaces/ge-0/0/6/trunk-native-vlan',
            headers=self.headers,
        ).and_return(
            Reply(
                content='',
                status_code=204))

        self.switch.unset_interface_native_vlan("ge-0/0/6")

    def test_set_bond_native_vlan(self):
        self.requests_mock.should_receive("put").once().with_args(
            url=self.netman_url+'/switches/toto/bonds/123/trunk-native-vlan',
            headers=self.headers,
            data='1000'
        ).and_return(
            Reply(
                content='',
                status_code=204))

        self.switch.set_bond_native_vlan(123, 1000)

    def test_unset_bond_native_vlan(self):
        self.requests_mock.should_receive("delete").once().with_args(
            url=self.netman_url+'/switches/toto/bonds/123/trunk-native-vlan',
            headers=self.headers,
        ).and_return(
            Reply(
                content='',
                status_code=204))

        self.switch.unset_bond_native_vlan(123)

    def test_add_trunk_vlan(self):
        self.requests_mock.should_receive("post").once().with_args(
            url=self.netman_url+'/switches/toto/interfaces/ge-0/0/6/trunk-vlans',
            headers=self.headers,
            data='1000'
        ).and_return(
            Reply(
                content='',
                status_code=204))

        self.switch.add_trunk_vlan("ge-0/0/6", 1000)

    def test_remove_trunk_vlan(self):
        self.requests_mock.should_receive("delete").once().with_args(
            url=self.netman_url+'/switches/toto/interfaces/ge-0/0/6/trunk-vlans/1000',
            headers=self.headers
        ).and_return(
            Reply(
                content='',
                status_code=204))

        self.switch.remove_trunk_vlan("ge-0/0/6", 1000)

    def test_add_bond_trunk_vlan(self):
        self.requests_mock.should_receive("post").once().with_args(
            url=self.netman_url+'/switches/toto/bonds/123/trunk-vlans',
            headers=self.headers,
            data='1000'
        ).and_return(
            Reply(
                content='',
                status_code=204))

        self.switch.add_bond_trunk_vlan(123, 1000)

    def test_remove_bond_trunk_vlan(self):
        self.requests_mock.should_receive("delete").once().with_args(
            url=self.netman_url+'/switches/toto/bonds/123/trunk-vlans/1000',
            headers=self.headers
        ).and_return(
            Reply(
                content='',
                status_code=204))

        self.switch.remove_bond_trunk_vlan(123, 1000)

    def test_set_interface_description(self):
        self.requests_mock.should_receive("put").once().with_args(
            url=self.netman_url+'/switches/toto/interfaces/ge-0/0/6/description',
            headers=self.headers,
            data='Resistance is futile'
        ).and_return(
            Reply(
                content='',
                status_code=204))

        self.switch.set_interface_description("ge-0/0/6", "Resistance is futile")

    def test_unset_interface_description(self):
        self.requests_mock.should_receive("delete").once().with_args(
            url=self.netman_url+'/switches/toto/interfaces/ge-0/0/6/description',
            headers=self.headers
        ).and_return(
            Reply(
                content='',
                status_code=204))

        self.switch.unset_interface_description("ge-0/0/6")

    def test_set_bond_description(self):
        self.requests_mock.should_receive("put").once().with_args(
            url=self.netman_url+'/switches/toto/bonds/123/description',
            headers=self.headers,
            data='Resistance is futile'
        ).and_return(
            Reply(
                content='',
                status_code=204))

        self.switch.set_bond_description(123, "Resistance is futile")

    def test_unset_bond_description(self):
        self.requests_mock.should_receive("delete").once().with_args(
            url=self.netman_url+'/switches/toto/bonds/123/description',
            headers=self.headers
        ).and_return(
            Reply(
                content='',
                status_code=204))

        self.switch.unset_bond_description(123)

    def test_set_interface_mtu(self):
        self.requests_mock.should_receive("put").once().with_args(
            url=self.netman_url+'/switches/toto/interfaces/ge-0/0/6/mtu',
            headers=self.headers,
            data='5000'
        ).and_return(
            Reply(
                content='',
                status_code=204))

        self.switch.set_interface_mtu("ge-0/0/6", 5000)

    def test_unset_interface_mtu(self):
        self.requests_mock.should_receive("delete").once().with_args(
            url=self.netman_url+'/switches/toto/interfaces/ge-0/0/6/mtu',
            headers=self.headers
        ).and_return(
            Reply(
                content='',
                status_code=204))

        self.switch.unset_interface_mtu("ge-0/0/6")

    def test_set_bond_mtu(self):
        self.requests_mock.should_receive("put").once().with_args(
            url=self.netman_url+'/switches/toto/bonds/123/mtu',
            headers=self.headers,
            data='5000'
        ).and_return(
            Reply(
                content='',
                status_code=204))

        self.switch.set_bond_mtu(123, 5000)

    def test_unset_bond_mtu(self):
        self.requests_mock.should_receive("delete").once().with_args(
            url=self.netman_url+'/switches/toto/bonds/123/mtu',
            headers=self.headers
        ).and_return(
            Reply(
                content='',
                status_code=204))

        self.switch.unset_bond_mtu(123)

    def test_edit_interface_spanning_tree_succeeds(self):
        self.requests_mock.should_receive("put").once().with_args(
            url=self.netman_url+'/switches/toto/interfaces/ge-0/0/6/spanning-tree',
            headers=self.headers,
            data=json.dumps({"edge": True})
        ).and_return(
            Reply(
                content='',
                status_code=204))

        self.switch.edit_interface_spanning_tree("ge-0/0/6", edge=True)

    def test_edit_interface_spanning_tree_optional_params(self):
        self.requests_mock.should_receive("put").once().with_args(
            url=self.netman_url+'/switches/toto/interfaces/ge-0/0/6/spanning-tree',
            headers=self.headers,
            data=json.dumps({})
        ).and_return(
            Reply(
                content='',
                status_code=204))

        self.switch.edit_interface_spanning_tree("ge-0/0/6")

    def test_enable_interface(self):
        self.requests_mock.should_receive("put").once().with_args(
            url=self.netman_url+'/switches/toto/interfaces/ge-0/0/6/shutdown',
            headers=self.headers,
            data='false'
        ).and_return(
            Reply(
                content='',
                status_code=204))

        self.switch.set_interface_state("ge-0/0/6", ON)

    def test_disable_interface(self):
        self.requests_mock.should_receive("put").once().with_args(
            url=self.netman_url+'/switches/toto/interfaces/ge-0/0/6/shutdown',
            headers=self.headers,
            data='true'
        ).and_return(
            Reply(
                content='',
                status_code=204))

        self.switch.set_interface_state("ge-0/0/6", OFF)

    def test_unset_interface_state(self):
        self.requests_mock.should_receive("delete").once().with_args(
            url=self.netman_url+'/switches/toto/interfaces/ge-0/0/6/shutdown',
            headers=self.headers
        ).and_return(
            Reply(
                content='',
                status_code=204))

        self.switch.unset_interface_state("ge-0/0/6")

    def test_enable_interface_auto_negotiation(self):
        self.requests_mock.should_receive("put").once().with_args(
            url=self.netman_url+'/switches/toto/interfaces/ge-0/0/6/auto-negotiation',
            headers=self.headers,
            data='true'
        ).and_return(
            Reply(
                content='',
                status_code=204))

        self.switch.set_interface_auto_negotiation_state("ge-0/0/6", ON)

    def test_disable_interface_auto_negotiation(self):
        self.requests_mock.should_receive("put").once().with_args(
            url=self.netman_url+'/switches/toto/interfaces/ge-0/0/6/auto-negotiation',
            headers=self.headers,
            data='false'
        ).and_return(
            Reply(
                content='',
                status_code=204))

        self.switch.set_interface_auto_negotiation_state("ge-0/0/6", OFF)

    def test_unset_interface_auto_negotiation_state(self):
        self.requests_mock.should_receive("delete").once().with_args(
            url=self.netman_url+'/switches/toto/interfaces/ge-0/0/6/auto-negotiation',
            headers=self.headers
        ).and_return(
            Reply(
                content='',
                status_code=204))

        self.switch.unset_interface_auto_negotiation_state("ge-0/0/6")

    def test_add_bond(self):
        self.requests_mock.should_receive("post").once().with_args(
            url=self.netman_url+'/switches/toto/bonds',
            headers=self.headers,
            data=JsonData(number=6)
        ).and_return(
            Reply(
                content='',
                status_code=201))

        self.switch.add_bond(6)

    def test_remove(self):
        self.requests_mock.should_receive("delete").once().with_args(
            url=self.netman_url+'/switches/toto/bonds/6',
            headers=self.headers
        ).and_return(
            Reply(
                content='',
                status_code=204))

        self.switch.remove_bond(6)

    def test_add_interface_to_bond(self):
        self.requests_mock.should_receive("put").once().with_args(
            url=self.netman_url+'/switches/toto/interfaces/ge-0/0/6/bond-master',
            headers=self.headers,
            data='10'
        ).and_return(
            Reply(
                content='',
                status_code=204))

        self.switch.add_interface_to_bond('ge-0/0/6', 10)

    def test_remove_interface_from_bond(self):
        self.requests_mock.should_receive("delete").once().with_args(
            url=self.netman_url+'/switches/toto/interfaces/ge-0/0/6/bond-master',
            headers=self.headers
        ).and_return(
            Reply(
                content='',
                status_code=204))

        self.switch.remove_interface_from_bond('ge-0/0/6')

    def test_edit_bond_spanning_tree(self):
        self.requests_mock.should_receive("put").once().with_args(
            url=self.netman_url+'/switches/toto/bonds/5/spanning-tree',
            headers=self.headers,
            data=json.dumps({"edge": True})
        ).and_return(
            Reply(
                content='',
                status_code=204))

        self.switch.edit_bond_spanning_tree(5, edge=True)

    def edit_bond_spanning_tree_optional_params(self):
        self.requests_mock.should_receive("put").once().with_args(
            url=self.netman_url+'/switches/toto/bonds/5/spanning-tree',
            headers=self.headers,
            data=json.dumps({})
        ).and_return(
            Reply(
                content='',
                status_code=204))

        self.switch.edit_bond_spanning_tree(5)

    def test_change_bond_speed(self):
        self.requests_mock.should_receive("put").once().with_args(
            url=self.netman_url+'/switches/toto/bonds/10/link-speed',
            headers=self.headers,
            data='1g'
        ).and_return(
            Reply(
                content='',
                status_code=204))

        self.switch.set_bond_link_speed(10, '1g')

    def test_change_bond_speed_missing_bond(self):
        self.requests_mock.should_receive("put").once().with_args(
            url=self.netman_url+'/switches/toto/bonds/10/link-speed',
            headers=self.headers,
            data='1g'
        ).and_return(
            Reply(
                content=json.dumps({
                    "error": "Bond 10 not found",
                    "error-module": UnknownBond.__module__,
                    "error-class": UnknownBond.__name__
                }),
                status_code=404))

        with self.assertRaises(UnknownBond) as expect:
            self.switch.set_bond_link_speed(10, '1g')

        assert_that(str(expect.exception), equal_to("Bond 10 not found"))

    def test_change_bond_speed_wrong_value(self):
        self.requests_mock.should_receive("put").once().with_args(
            url=self.netman_url+'/switches/toto/bonds/10/link-speed',
            headers=self.headers,
            data='1z'
        ).and_return(
            Reply(
                content=json.dumps({
                    "error": "Malformed bond link speed",
                    "error-module": BadBondLinkSpeed.__module__,
                    "error-class": BadBondLinkSpeed.__name__
                }),
                status_code=400))

        with self.assertRaises(BadBondLinkSpeed) as expect:
            self.switch.set_bond_link_speed(10, '1z')

        assert_that(str(expect.exception), equal_to("Malformed bond link speed"))

    def test_change_bond_speed_switch_locked(self):
        self.requests_mock.should_receive("put").once().with_args(
            url=self.netman_url+'/switches/toto/bonds/10/link-speed',
            headers=self.headers,
            data='1z'
        ).and_return(
            Reply(
                content=json.dumps({
                    "error": "Switch is locked and can't be modified",
                    "error-module": LockedSwitch.__module__,
                    "error-class": LockedSwitch.__name__
                }),
                status_code=423))

        with self.assertRaises(LockedSwitch) as expect:
            self.switch.set_bond_link_speed(10, '1z')

        assert_that(str(expect.exception), equal_to("Switch is locked and can't be modified"))

    def test_add_vrrp_group(self):
        self.requests_mock.should_receive("post").once().with_args(
            url=self.netman_url+'/switches/toto/vlans/2000/vrrp-groups',
            headers=self.headers,
            data=JsonData(id=1,
                          priority=2,
                          ips=['1.2.3.4'],
                          hello_interval=5,
                          dead_interval=15,
                          track_id="101",
                          track_decrement=50)
        ).and_return(
            Reply(
                content='',
                status_code=201))

        self.switch.add_vrrp_group(2000, group_id=1, priority=2, ips=[IPAddress('1.2.3.4')], hello_interval=5,
                                   dead_interval=15, track_id='101', track_decrement=50)

    def test_remove_vrrp_group(self):
        self.requests_mock.should_receive("delete").once().with_args(
            url=self.netman_url+'/switches/toto/vlans/2000/vrrp-groups/123',
            headers=self.headers
        ).and_return(
            Reply(
                content='',
                status_code=201))

        self.switch.remove_vrrp_group(2000, group_id=123)

    def test_add_dhcp_relay_server(self):
        self.requests_mock.should_receive("post").once().with_args(
            url=self.netman_url+'/switches/toto/vlans/2000/dhcp-relay-server',
            headers=self.headers,
            data='1.2.3.4'
        ).and_return(
            Reply(
                content='',
                status_code=201))

        self.switch.add_dhcp_relay_server(2000, '1.2.3.4')

    def test_remove_dhcp_relay_server(self):
        self.requests_mock.should_receive("delete").once().with_args(
            url=self.netman_url+'/switches/toto/vlans/2000/dhcp-relay-server/1.2.3.4',
            headers=self.headers
        ).and_return(
            Reply(
                content='',
                status_code=201))

        self.switch.remove_dhcp_relay_server(2000, '1.2.3.4')

    def test_set_interface_lldp_state(self):
        self.requests_mock.should_receive("put").once().with_args(
            url=self.netman_url+'/switches/toto/interfaces/ge-0/0/6/lldp',
            headers=self.headers,
            data='true'
        ).and_return(
            Reply(
                content='',
                status_code=204))

        self.switch.set_interface_lldp_state("ge-0/0/6", True)

    def test_disable_lldp(self):
        self.requests_mock.should_receive("put").once().with_args(
            url=self.netman_url+'/switches/toto/interfaces/ge-0/0/6/lldp',
            headers=self.headers,
            data='false'
        ).and_return(
            Reply(
                content='',
                status_code=204))

        self.switch.set_interface_lldp_state("ge-0/0/6", False)

    def test_set_vlan_icmp_redirects_state_False_should_send_false(self):
        self.requests_mock.should_receive("put").once().with_args(
            url=self.netman_url+'/switches/toto/vlans/2000/icmp-redirects',
            headers=self.headers,
            data='false'
        ).and_return(
            Reply(
                content='',
                status_code=204))

        self.switch.set_vlan_icmp_redirects_state(2000, False)

    def test_set_vlan_icmp_redirects_state_True_should_send_true(self):
        self.requests_mock.should_receive("put").once().with_args(
            url=self.netman_url+'/switches/toto/vlans/2000/icmp-redirects',
            headers=self.headers,
            data='true'
        ).and_return(
            Reply(
                content='',
                status_code=204))

        self.switch.set_vlan_icmp_redirects_state(2000, True)

    def test_get_versions(self):
        data = {
            "v": "1.0",
            "units": {
                "1": {
                    "v": "1.0"
                }
            }
        }

        self.requests_mock.should_receive("get").once().with_args(
            url=self.netman_url+'/switches/toto/versions',
            headers=self.headers
        ).and_return(
            Reply(
                content=json.dumps(data),
                status_code=204))

        result = self.switch.get_versions()
        assert_that(result, is_(data))

    def test_unformatted_exceptions_are_handled(self):
        self.requests_mock.should_receive("put").once().and_return(Reply(
            content='Oops an unexpected excepton occured',
            status_code=500
        ))

        with self.assertRaises(Exception) as expect:
            self.switch.set_bond_link_speed(10, '1z')

        assert_that(str(expect.exception), equal_to("500: Oops an unexpected excepton occured"))

    def test_native_exceptions_are_handled(self):
        self.requests_mock.should_receive("put").once().and_return(Reply(
            content=json.dumps({
                "error": "Oops an unexpected excepton occured",
                "error-class": "Exception"
            }),
            status_code=500
        ))

        with self.assertRaises(Exception) as expect:
            self.switch.set_bond_link_speed(10, '1z')

        assert_that(str(expect.exception), equal_to("Oops an unexpected excepton occured"))

    def test_exceptions_missing_error_classes_work(self):
        self.requests_mock.should_receive("put").once().and_return(Reply(
            content=json.dumps({
                "error": "Oops an unexpected excepton occured"
            }),
            status_code=500
        ))

        with self.assertRaises(Exception) as expect:
            self.switch.set_bond_link_speed(10, '1z')

        assert_that(str(expect.exception), equal_to("Oops an unexpected excepton occured"))

    def test_exceptions_bad_init_works(self):
        self.requests_mock.should_receive("put").once().and_return(Reply(
            content=json.dumps({
                "error": "Switch is locked and can't be modified",
                "error-module": RPCError.__module__,
                "error-class": RPCError.__name__
            }),
            status_code=400
        ))

        with self.assertRaises(NetmanException) as expect:
            self.switch.set_bond_link_speed(10, '1z')

        assert_that(
            str(expect.exception),
            equal_to("ncclient.operations.rpc.RPCError: Switch is locked and can't be modified"))


class Reply:
    def __init__(self, status_code, content, headers=None):
        self.status_code = status_code
        self.content = content
        self.headers = headers or {}

    def json(self):
        return json.loads(self.content)


class JsonData:
    def __init__(self, **data):
        self.data = data

    def __eq__(self, other):
        try:
            return json.loads(other) == self.data
        except ValueError:
            return False
