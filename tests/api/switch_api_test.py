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

from flexmock import flexmock, flexmock_teardown
from hamcrest import assert_that, equal_to, is_
from netaddr import IPNetwork
from netaddr.ip import IPAddress

from netman.core.objects.vrrp_group import VrrpGroup
from tests import ExactIpNetwork
from tests.api import matches_fixture
from tests.api.base_api_test import BaseApiTest
from netman.api.api_utils import RegexConverter
from netman.api.switch_api import SwitchApi
from netman.api.switch_session_api import SwitchSessionApi
from netman.core.objects.access_groups import IN, OUT
from netman.core.objects.exceptions import IPNotAvailable, UnknownIP, UnknownVlan, UnknownAccessGroup, UnknownInterface, \
    UnknownSwitch, OperationNotCompleted, UnknownSession, SessionAlreadyExists
from netman.core.objects.interface import Interface
from netman.core.objects.port_modes import ACCESS, TRUNK, DYNAMIC, BOND_MEMBER
from netman.core.objects.vlan import Vlan
from netman.core.objects.bond import Bond


class SwitchApiTest(BaseApiTest):
    def setUp(self):
        super(SwitchApiTest, self).setUp()
        self.app.url_map.converters['regex'] = RegexConverter

        self.switch_factory = flexmock()
        self.switch_mock = flexmock()
        self.session_manager = flexmock()

        self.session_manager.should_receive("get_switch_for_session").and_raise(UnknownSession("patate"))

        SwitchApi(self.switch_factory, self.session_manager).hook_to(self.app)
        SwitchSessionApi(self.switch_factory, self.session_manager).hook_to(self.app)

    def tearDown(self):
        flexmock_teardown()

    def test_vlans_serialization(self):
        self.switch_factory.should_receive('get_switch').with_args('my.switch').and_return(self.switch_mock).once().ordered()
        self.switch_mock.should_receive('connect').once().ordered()
        self.switch_mock.should_receive('get_vlans').and_return([
            Vlan(2, "", [IPNetwork('3.3.3.3/24'), IPNetwork('2.2.2.2/24')],
                 vrrp_groups=[
                     VrrpGroup(id=1, ips=[IPAddress('2.2.2.2')], priority=100),
                     VrrpGroup(id=2, ips=[IPAddress('3.3.3.1')], priority=100)
                 ],
                 dhcp_relay_servers=[IPAddress("10.10.10.1")]),
            Vlan(1, "One", [IPNetwork('1.1.1.1/24')], vrf_forwarding="MY_VRF", access_group_in="Blah_blah",
                 vrrp_groups=[
                     VrrpGroup(id=1, ips=[IPAddress('1.1.1.2')], priority=90, hello_interval=5, dead_interval=15,
                               track_id='101', track_decrement=50)
                 ]),
        ]).once().ordered()
        self.switch_mock.should_receive('disconnect').once().ordered()

        result, code = self.get("/switches/my.switch/vlans")

        assert_that(code, equal_to(200))
        assert_that(result, matches_fixture("get_switch_hostname_vlans.json"))

    def test_gat_vlans_can_be_empty(self):
        self.switch_factory.should_receive('get_switch').with_args('my.switch').and_return(self.switch_mock).once().ordered()
        self.switch_mock.should_receive('connect').once().ordered()
        self.switch_mock.should_receive('get_vlans').and_return([]).once().ordered()
        self.switch_mock.should_receive('disconnect').once().ordered()

        result, code = self.get("/switches/my.switch/vlans")

        assert_that(code, equal_to(200))
        assert_that(result, equal_to([]))

    def test_interfaces_serialization(self):
        self.switch_factory.should_receive('get_switch').with_args('my.switch').and_return(self.switch_mock).once().ordered()
        self.switch_mock.should_receive('connect').once().ordered()
        self.switch_mock.should_receive('get_interfaces').and_return([
            Interface(name="FastEthernet0/3", shutdown=True, port_mode=ACCESS, access_vlan=1999),
            Interface(name="GigabitEthernet0/6", shutdown=False, port_mode=DYNAMIC, access_vlan=1999, trunk_native_vlan=2999, trunk_vlans=[3001, 3000, 3002]),
            Interface(name="ethernet 1/4", shutdown=False, port_mode=TRUNK, trunk_native_vlan=2999, trunk_vlans=[3001, 3000, 3002]),
            Interface(name="GigabitEthernet0/8", shutdown=False, bond_master=12, port_mode=BOND_MEMBER, trunk_native_vlan=None, trunk_vlans=[]),
        ]).once().ordered()
        self.switch_mock.should_receive('disconnect').once().ordered()

        result, code = self.get("/switches/my.switch/interfaces")

        assert_that(code, equal_to(200))
        assert_that(result, matches_fixture("get_switch_hostname_interfaces.json"))

    def test_add_vlan(self):
        self.switch_factory.should_receive('get_switch').with_args('my.switch').and_return(self.switch_mock).once().ordered()
        self.switch_mock.should_receive('connect').once().ordered()
        self.switch_mock.should_receive('add_vlan').with_args(2000, "two_thousands").once().ordered()
        self.switch_mock.should_receive('disconnect').once().ordered()

        result, code = self.post("/switches/my.switch/vlans", fixture="post_switch_hostname_vlans.json")

        assert_that(code, equal_to(201))

    def test_add_vlan_name_is_optionnal(self):
        self.switch_factory.should_receive('get_switch').with_args('my.switch').and_return(self.switch_mock).once().ordered()
        self.switch_mock.should_receive('connect').once().ordered()
        self.switch_mock.should_receive('add_vlan').with_args(2000, None).once().ordered()
        self.switch_mock.should_receive('disconnect').once().ordered()

        result, code = self.post("/switches/my.switch/vlans", data={"number": 2000})

        assert_that(code, equal_to(201))

    def test_add_vlan_name_is_optionnal_and_can_be_specified_empty(self):
        self.switch_factory.should_receive('get_switch').with_args('my.switch').and_return(self.switch_mock).once().ordered()
        self.switch_mock.should_receive('connect').once().ordered()
        self.switch_mock.should_receive('add_vlan').with_args(2000, None).once().ordered()
        self.switch_mock.should_receive('disconnect').once().ordered()

        result, code = self.post("/switches/my.switch/vlans", data={"number": "2000", "name": ""})

        assert_that(code, equal_to(201))

    def test_add_vlan_validates_the_name_if_present(self):
        self.switch_factory.should_receive('get_switch').with_args('my.switch').never()

        result, code = self.post("/switches/my.switch/vlans", data={"number": 2000, "name": "deux milles"})
        assert_that(code, equal_to(400))
        assert_that(result, equal_to({'error': 'Vlan name is invalid'}))

        result, code = self.post("/switches/my.switch/vlans", data={"number": 4097})
        assert_that(code, equal_to(400))
        assert_that(result, equal_to({'error': 'Vlan number is invalid'}))

        result, code = self.post("/switches/my.switch/vlans", data={"number": 0})
        assert_that(code, equal_to(400))
        assert_that(result, equal_to({'error': 'Vlan number is invalid'}))

        result, code = self.post("/switches/my.switch/vlans", data={"number": "patate"})
        assert_that(code, equal_to(400))
        assert_that(result, equal_to({'error': 'Vlan number is invalid'}))

        result, code = self.post("/switches/my.switch/vlans", data={})
        assert_that(code, equal_to(400))
        assert_that(result, equal_to({'error': 'Vlan number is invalid'}))

        result, code = self.post("/switches/my.switch/vlans", raw_data="not even json")
        assert_that(code, equal_to(400))
        assert_that(result, equal_to({'error': 'Malformed content, should be a JSON object'}))

    def test_add_vlan_nameless(self):
        self.switch_factory.should_receive('get_switch').with_args('my.switch').and_return(self.switch_mock).once().ordered()
        self.switch_mock.should_receive('connect').once().ordered()
        self.switch_mock.should_receive('add_vlan').with_args(2000, None).once().ordered()
        self.switch_mock.should_receive('disconnect').once().ordered()

        result, code = self.post("/switches/my.switch/vlans", data={"number": 2000})

        assert_that(code, equal_to(201))

    def test_remove_vlan(self):
        self.switch_factory.should_receive('get_switch').with_args('my.switch').and_return(self.switch_mock).once().ordered()
        self.switch_mock.should_receive('connect').once().ordered()
        self.switch_mock.should_receive('remove_vlan').with_args(2000).once().ordered()
        self.switch_mock.should_receive('disconnect').once().ordered()

        result, code = self.delete("/switches/my.switch/vlans/2000")

        assert_that(code, equal_to(204))

    def test_configure_switch_port_access(self):
        self.switch_factory.should_receive('get_switch').with_args('my.switch').and_return(self.switch_mock).once().ordered()
        self.switch_mock.should_receive('connect').once().ordered()
        self.switch_mock.should_receive('set_access_mode').with_args("FastEthernet0/4").once().ordered()
        self.switch_mock.should_receive('disconnect').once().ordered()

        result, code = self.put("/switches/my.switch/interfaces/FastEthernet0/4/port-mode", raw_data="access")

        assert_that(code, equal_to(204))

    def test_configure_switch_port_trunk(self):
        self.switch_factory.should_receive('get_switch').with_args('my.switch').and_return(self.switch_mock).once().ordered()
        self.switch_mock.should_receive('connect').once().ordered()
        self.switch_mock.should_receive('set_trunk_mode').with_args("FastEthernet0/4").once().ordered()
        self.switch_mock.should_receive('disconnect').once().ordered()

        result, code = self.put("/switches/my.switch/interfaces/FastEthernet0/4/port-mode", raw_data="trunk")

        assert_that(code, equal_to(204))

    def test_configure_switch_port_unknown(self):
        self.switch_factory.should_receive('get_switch').with_args('my.switch').and_return(self.switch_mock).once().ordered()
        self.switch_mock.should_receive('connect').once().ordered()
        self.switch_mock.should_receive('set_switchport_mode').never()
        self.switch_mock.should_receive('disconnect').once().ordered()

        result, code = self.put("/switches/my.switch/interfaces/FastEthernet0/4/port-mode", raw_data="sirpatate")

        assert_that(code, equal_to(400))
        assert_that(result, equal_to({'error': 'Unknown port mode detected sirpatate'}))

    def test_configure_switch_bond_port_access(self):
        self.switch_factory.should_receive('get_switch').with_args('my.switch').and_return(self.switch_mock).once().ordered()
        self.switch_mock.should_receive('connect').once().ordered()
        self.switch_mock.should_receive('set_bond_access_mode').with_args(123).once().ordered()
        self.switch_mock.should_receive('disconnect').once().ordered()

        result, code = self.put("/switches/my.switch/bonds/123/port-mode", raw_data="access")

        assert_that(code, equal_to(204))

    def test_configure_switch_bond_port_trunk(self):
        self.switch_factory.should_receive('get_switch').with_args('my.switch').and_return(self.switch_mock).once().ordered()
        self.switch_mock.should_receive('connect').once().ordered()
        self.switch_mock.should_receive('set_bond_trunk_mode').with_args(123).once().ordered()
        self.switch_mock.should_receive('disconnect').once().ordered()

        result, code = self.put("/switches/my.switch/bonds/123/port-mode", raw_data="trunk")

        assert_that(code, equal_to(204))

    def test_edit_bond_spanning_tree(self):
        self.switch_factory.should_receive('get_switch').with_args('my.switch').and_return(self.switch_mock).once().ordered()
        self.switch_mock.should_receive('connect').once().ordered()
        self.switch_mock.should_receive('edit_bond_spanning_tree').with_args(5, edge=True).once().ordered()
        self.switch_mock.should_receive('disconnect').once().ordered()

        result, code = self.put("/switches/my.switch/bonds/5/spanning-tree",
                                fixture="put_switch_hostname_interfaces_intname_spanningtree.json")

        assert_that(code, equal_to(204))

    def test_edit_bond_spanning_tree_optional_params(self):
        self.switch_factory.should_receive('get_switch').with_args('my.switch').and_return(self.switch_mock).once().ordered()
        self.switch_mock.should_receive('connect').once().ordered()
        self.switch_mock.should_receive('edit_bond_spanning_tree').with_args(5).once().ordered()
        self.switch_mock.should_receive('disconnect').once().ordered()

        result, code = self.put("/switches/my.switch/bonds/5/spanning-tree", raw_data="{}")

        assert_that(code, equal_to(204))

    def test_edit_bond_spanning_tree_with_wrong_params(self):
        result, code = self.put("/switches/my.switch/bonds/5/spanning-tree",
                                raw_data="whizzle")

        assert_that(code, equal_to(400))
        assert_that(result['error'], is_('Malformed JSON request'))

        result, code = self.put("/switches/my.switch/bonds/5/spanning-tree",
                                raw_data='{"unknown_key": "value"}')

        assert_that(code, equal_to(400))
        assert_that(result['error'], is_('Unknown key: unknown_key'))

    def test_anonymous_switch(self):
        self.switch_factory.should_receive('get_anonymous_switch').with_args(
            hostname='my.switch',
            model='cisco',
            username='root',
            password='password',
            port=None,
            netman_server=None).once().ordered().and_return(self.switch_mock)

        self.switch_mock.should_receive('connect').once().ordered()
        self.switch_mock.should_receive('get_vlans').once().ordered().and_return([Vlan(1, "One"), Vlan(2, "Two")])
        self.switch_mock.should_receive('disconnect').once().ordered()

        result, code = self.get("/switches/my.switch/vlans", headers={'Netman-Model':'cisco', 'Netman-Username':'root',
                                                                      'Netman-Password':'password'})
        assert_that(code, equal_to(200))

    def test_anonymous_switch_all_headers_set(self):
        result, code = self.get("/switches/my.switch/vlans", headers={'Netman-Model':'cisco'})
        assert_that(code, equal_to(400))
        assert_that(result, equal_to({'error': 'For anonymous switch usage, please specify headers: Netman-Model, Netman-Username and Netman-Password.'}))

        result, code = self.get("/switches/my.switch/vlans", headers={'Netman-Username':'root'})
        assert_that(code, equal_to(400))
        assert_that(result, equal_to({'error': 'For anonymous switch usage, please specify headers: Netman-Model, Netman-Username and Netman-Password.'}))

        result, code = self.get("/switches/my.switch/vlans", headers={'Netman-Password':'password'})
        assert_that(code, equal_to(400))
        assert_that(result, equal_to({'error': 'For anonymous switch usage, please specify headers: Netman-Model, Netman-Username and Netman-Password.'}))

    def test_anonymous_switch_can_have_a_port_specified(self):
        self.switch_factory.should_receive('get_anonymous_switch').with_args(
            hostname='my.switch',
            model='cisco',
            username='root',
            password='password',
            port=830,
            netman_server=None).once().ordered().and_return(self.switch_mock)
        self.switch_mock.should_receive('connect').once().ordered()
        self.switch_mock.should_receive('get_vlans').and_return([Vlan(1, "One"), Vlan(2, "Two")]).once().ordered()
        self.switch_mock.should_receive('disconnect').once().ordered()

        result, code = self.get("/switches/my.switch/vlans", headers={'Netman-Model':'cisco', 'Netman-Username':'root',
                                                                      'Netman-Password':'password', 'Netman-Port':'830'})
        assert_that(code, equal_to(200))

    def test_anonymous_switch_port_has_to_be_integer(self):
        result, code = self.get("/switches/my.switch/vlans", headers={'Netman-Model':'cisco', 'Netman-Username':'root',
                                                                      'Netman-Password':'password', 'Netman-Port':'bleh'})
        assert_that(code, equal_to(400))

    def test_anonymous_switch_can_be_netman_proxied(self):
        self.switch_factory.should_receive('get_anonymous_switch').with_args(
            hostname='my.switch',
            model='cisco',
            username='root',
            password='password',
            port=None,
            netman_server='1.2.3.4').once().ordered().and_return(self.switch_mock)
        self.switch_mock.should_receive('connect').once().ordered()
        self.switch_mock.should_receive('get_vlans').and_return([Vlan(1, "One"), Vlan(2, "Two")]).once().ordered()
        self.switch_mock.should_receive('disconnect').once().ordered()

        result, code = self.get("/switches/my.switch/vlans", headers={
            'Netman-Model':'cisco',
            'Netman-Username':'root',
            'Netman-Password':'password',
            'Netman-Proxy-Server':'1.2.3.4'
        })
        assert_that(code, equal_to(200))

    def test_shutdown_interface(self):
        self.switch_factory.should_receive('get_switch').with_args('my.switch').and_return(self.switch_mock).once().ordered()
        self.switch_mock.should_receive('connect').once().ordered()
        self.switch_mock.should_receive('shutdown_interface').with_args('FastEthernet0/4').once().ordered()
        self.switch_mock.should_receive('disconnect').once().ordered()

        result, code = self.put("/switches/my.switch/interfaces/FastEthernet0/4/shutdown", raw_data='true')

        assert_that(code, equal_to(204))

    def test_openup_interface(self):
        self.switch_factory.should_receive('get_switch').with_args('my.switch').and_return(self.switch_mock).once().ordered()
        self.switch_mock.should_receive('connect').once().ordered()
        self.switch_mock.should_receive('openup_interface').with_args('FastEthernet0/4').once().ordered()
        self.switch_mock.should_receive('disconnect').once().ordered()

        result, code = self.put("/switches/my.switch/interfaces/FastEthernet0/4/shutdown", raw_data='false')

        assert_that(code, equal_to(204))

    def test_shutdown_interface_invalid_argument(self):
        self.switch_factory.should_receive('get_switch').with_args('my.switch').and_return(self.switch_mock).never()
        self.switch_mock.should_receive('connect').never()
        self.switch_mock.should_receive('shutdown_interface').with_args('FastEthernet0/4').never()
        self.switch_mock.should_receive('disconnect').never()

        result, code = self.put("/switches/my.switch/interfaces/FastEthernet0/4/shutdown", raw_data='Patate')

        assert_that(code, equal_to(400))
        assert_that(result, equal_to({'error': 'Unreadable content "patate". Should be either "true" or "false"'}))

    def test_shutdown_interface_no_argument(self):
        self.switch_factory.should_receive('get_switch').with_args('my.switch').and_return(self.switch_mock).never()
        self.switch_mock.should_receive('connect').never()
        self.switch_mock.should_receive('shutdown_interface').with_args('FastEthernet0/4').never()
        self.switch_mock.should_receive('disconnect').never()

        result, code = self.put("/switches/my.switch/interfaces/FastEthernet0/4/shutdown")
        assert_that(code, equal_to(400))
        assert_that(result, equal_to({'error': 'Unreadable content "". Should be either "true" or "false"'}))

    def test_set_access_vlan(self):
        self.switch_factory.should_receive('get_switch').with_args('my.switch').and_return(self.switch_mock).once().ordered()
        self.switch_mock.should_receive('connect').once().ordered()
        self.switch_mock.should_receive('set_access_vlan').with_args('FastEthernet0/4', 1000).once().ordered()
        self.switch_mock.should_receive('disconnect').once().ordered()

        result, code = self.put("/switches/my.switch/interfaces/FastEthernet0/4/access-vlan",
                                fixture="put_switch_hostname_interfaces_intname_accessvlan.txt")

        assert_that(code, equal_to(204))

    def test_remove_access_vlan(self):
        self.switch_factory.should_receive('get_switch').with_args('my.switch').and_return(self.switch_mock).once().ordered()
        self.switch_mock.should_receive('connect').once().ordered()
        self.switch_mock.should_receive('remove_access_vlan').with_args('FastEthernet0/4').once().ordered()
        self.switch_mock.should_receive('disconnect').once().ordered()

        result, code = self.delete("/switches/my.switch/interfaces/FastEthernet0/4/access-vlan")

        assert_that(code, equal_to(204))

    def test_set_bond_access_vlan(self):
        self.switch_factory.should_receive('get_switch').with_args('my.switch').and_return(self.switch_mock).once().ordered()
        self.switch_mock.should_receive('connect').once().ordered()
        self.switch_mock.should_receive('set_bond_access_vlan').with_args(4, 1000).once().ordered()
        self.switch_mock.should_receive('disconnect').once().ordered()

        result, code = self.put("/switches/my.switch/bonds/4/access-vlan",
                                fixture="put_switch_hostname_interfaces_intname_accessvlan.txt")

        assert_that(code, equal_to(204))

    def test_remove_bond_access_vlan(self):
        self.switch_factory.should_receive('get_switch').with_args('my.switch').and_return(self.switch_mock).once().ordered()
        self.switch_mock.should_receive('connect').once().ordered()
        self.switch_mock.should_receive('remove_bond_access_vlan').with_args(4).once().ordered()
        self.switch_mock.should_receive('disconnect').once().ordered()

        result, code = self.delete("/switches/my.switch/bonds/4/access-vlan")

        assert_that(code, equal_to(204))


    def test_invalid_set_access_vlan(self):
        self.switch_factory.should_receive('get_switch').with_args('my.switch').and_return(self.switch_mock).never()
        self.switch_mock.should_receive('set_access_vlan').never()
        self.switch_mock.should_receive('connect').never()
        self.switch_mock.should_receive('disconnect').never()

        result, code = self.put("/switches/my.switch/interfaces/FastEthernet0/4/access-vlan", raw_data='patate')

        assert_that(code, equal_to(400))
        assert_that(result, equal_to({'error': 'Vlan number is invalid'}))

    def test_add_trunk_vlan(self):
        self.switch_factory.should_receive('get_switch').with_args('my.switch').and_return(self.switch_mock).once().ordered()
        self.switch_mock.should_receive('connect').once().ordered()
        self.switch_mock.should_receive('add_trunk_vlan').with_args('FastEthernet0/4', 1000).once().ordered()
        self.switch_mock.should_receive('disconnect').once().ordered()

        result, code = self.post("/switches/my.switch/interfaces/FastEthernet0/4/trunk-vlans",
                                 fixture="post_switch_hostname_interfaces_intname_trunkvlans.txt")

        assert_that(code, equal_to(204))

    def test_remove_trunk_vlans(self):
        self.switch_factory.should_receive('get_switch').with_args('my.switch').and_return(self.switch_mock).once().ordered()
        self.switch_mock.should_receive('connect').once().ordered()
        self.switch_mock.should_receive('remove_trunk_vlan').with_args('FastEthernet0/4', 2999).once().ordered()
        self.switch_mock.should_receive('disconnect').once().ordered()

        result, code = self.delete("/switches/my.switch/interfaces/FastEthernet0/4/trunk-vlans/2999")

        assert_that(code, equal_to(204))

    def test_add_bond_trunk_vlan(self):
        self.switch_factory.should_receive('get_switch').with_args('my.switch').and_return(self.switch_mock).once().ordered()
        self.switch_mock.should_receive('connect').once().ordered()
        self.switch_mock.should_receive('add_bond_trunk_vlan').with_args(123, 1000).once().ordered()
        self.switch_mock.should_receive('disconnect').once().ordered()

        result, code = self.post("/switches/my.switch/bonds/123/trunk-vlans",
                                 fixture="post_switch_hostname_interfaces_intname_trunkvlans.txt")

        assert_that(code, equal_to(204))

    def test_remove_bond_trunk_vlans(self):
        self.switch_factory.should_receive('get_switch').with_args('my.switch').and_return(self.switch_mock).once().ordered()
        self.switch_mock.should_receive('connect').once().ordered()
        self.switch_mock.should_receive('remove_bond_trunk_vlan').with_args(123, 2999).once().ordered()
        self.switch_mock.should_receive('disconnect').once().ordered()

        result, code = self.delete("/switches/my.switch/bonds/123/trunk-vlans/2999")

        assert_that(code, equal_to(204))

    def test_invalid_add_trunk_vlan(self):
        self.switch_factory.should_receive('get_switch').with_args('my.switch').and_return(self.switch_mock).never()
        self.switch_mock.should_receive('connect').once().never()
        self.switch_mock.should_receive('add_trunk_vlan').never()
        self.switch_mock.should_receive('disconnect').never()

        result, code = self.post("/switches/my.switch/interfaces/FastEthernet0/4/trunk-vlans", raw_data='patate')

        assert_that(code, equal_to(400))
        assert_that(result, equal_to({'error': 'Vlan number is invalid'}))

    def test_invalid_remove_trunk_vlan(self):
        self.switch_factory.should_receive('get_switch').with_args('my.switch').and_return(self.switch_mock)
        self.switch_mock.should_receive('connect').never()
        self.switch_mock.should_receive('remove_trunk_vlan').never()
        self.switch_mock.should_receive('disconnect').never()

        result, code = self.delete("/switches/my.switch/interfaces/FastEthernet0/4/trunk-vlans/patate")

        assert_that(code, equal_to(400))
        assert_that(result, equal_to({'error': 'Vlan number is invalid'}))

    def test_configure_native_vlan_on_trunk(self):
        self.switch_factory.should_receive('get_switch').with_args('my.switch').and_return(self.switch_mock).once().ordered()
        self.switch_mock.should_receive('connect').once().ordered()
        self.switch_mock.should_receive('configure_native_vlan').with_args('FastEthernet0/4', 2999).once().ordered()
        self.switch_mock.should_receive('disconnect').once().ordered()

        result, code = self.put("/switches/my.switch/interfaces/FastEthernet0/4/trunk-native-vlan",
                                fixture="put_switch_hostname_interfaces_intname_nativevlan.txt")

        assert_that(code, equal_to(204))

    def test_configure_bond_native_vlan_on_trunk(self):
        self.switch_factory.should_receive('get_switch').with_args('my.switch').and_return(self.switch_mock).once().ordered()
        self.switch_mock.should_receive('connect').once().ordered()
        self.switch_mock.should_receive('configure_bond_native_vlan').with_args(123, 2999).once().ordered()
        self.switch_mock.should_receive('disconnect').once().ordered()

        result, code = self.put("/switches/my.switch/bonds/123/trunk-native-vlan",
                                fixture="put_switch_hostname_interfaces_intname_nativevlan.txt")

        assert_that(code, equal_to(204))

    def test_remove_bond_native_vlan_on_trunk(self):
        self.switch_factory.should_receive('get_switch').with_args('my.switch').and_return(self.switch_mock).once().ordered()
        self.switch_mock.should_receive('connect').once().ordered()
        self.switch_mock.should_receive('remove_bond_native_vlan').with_args(123).once().ordered()
        self.switch_mock.should_receive('disconnect').once().ordered()

        result, code = self.delete("/switches/my.switch/bonds/123/trunk-native-vlan")

        assert_that(code, equal_to(204))

    def test_add_ip_json(self):
        self.switch_factory.should_receive('get_switch').with_args('my.switch').and_return(self.switch_mock).once().ordered()
        self.switch_mock.should_receive('connect').once().ordered()
        self.switch_mock.should_receive('add_ip_to_vlan').with_args(2500, ExactIpNetwork("1.2.3.4", 25)).once().ordered()
        self.switch_mock.should_receive('disconnect').once().ordered()

        result, code = self.post("/switches/my.switch/vlans/2500/ips", fixture="post_switch_hostname_vlans_vlanid_ips.json")

        assert_that(code, equal_to(201))

    def test_add_ip_ipnetwork(self):
        self.switch_factory.should_receive('get_switch').with_args('my.switch').and_return(self.switch_mock).once().ordered()
        self.switch_mock.should_receive('connect').once().ordered()
        self.switch_mock.should_receive('add_ip_to_vlan').with_args(2500, ExactIpNetwork("1.2.3.4", 25)).once().ordered()
        self.switch_mock.should_receive('disconnect').once().ordered()

        result, code = self.post("/switches/my.switch/vlans/2500/ips", fixture="post_switch_hostname_vlans_vlanid_ips.txt")

        assert_that(code, equal_to(201))

    def test_add_ip_malformed_request(self):
        self.switch_factory.should_receive('get_switch').never()

        result, code = self.post("/switches/my.switch/vlans/2500/ips", raw_data="not json and not ip network")
        assert_that(code, equal_to(400))
        assert_that(result, equal_to({'error': 'Malformed content, should be : x.x.x.x/xx or {"address": "x.x.x.x", "mask": "xx"}'}))

        result, code = self.post("/switches/my.switch/vlans/2500/ips", data={})
        assert_that(code, equal_to(400))
        assert_that(result, equal_to({'error': 'Malformed content, should be : x.x.x.x/xx or {"address": "x.x.x.x", "mask": "xx"}'}))

        result, code = self.post("/switches/my.switch/vlans/2500/ips", data={"address": "1.1.1.1"})
        assert_that(code, equal_to(400))
        assert_that(result, equal_to({'error': 'Malformed content, should be : x.x.x.x/xx or {"address": "x.x.x.x", "mask": "xx"}'}))

        result, code = self.post("/switches/my.switch/vlans/2500/ips", data={"mask": "25"})
        assert_that(code, equal_to(400))
        assert_that(result, equal_to({'error': 'Malformed content, should be : x.x.x.x/xx or {"address": "x.x.x.x", "mask": "xx"}'}))

        result, code = self.post("/switches/my.switch/vlans/2500/ips", data={"address": "not an ip", "mask": 25})
        assert_that(code, equal_to(400))
        assert_that(result, equal_to({'error': 'Malformed content, should be : x.x.x.x/xx or {"address": "x.x.x.x", "mask": "xx"}'}))

        result, code = self.post("/switches/my.switch/vlans/2500/ips", data={"address": "1.1.1.1", "mask": "not a mask"})
        assert_that(code, equal_to(400))
        assert_that(result, equal_to({'error': 'Malformed content, should be : x.x.x.x/xx or {"address": "x.x.x.x", "mask": "xx"}'}))

    def test_add_ip_not_available(self):
        self.switch_factory.should_receive('get_switch').with_args('my.switch').and_return(self.switch_mock).once().ordered()
        self.switch_mock.should_receive('connect').once().ordered()
        self.switch_mock.should_receive('add_ip_to_vlan').with_args(2500, ExactIpNetwork("1.2.3.4", 25)).once().ordered()\
            .and_raise(IPNotAvailable(IPNetwork("1.2.3.4/25")))
        self.switch_mock.should_receive('disconnect').once().ordered()

        result, code = self.post("/switches/my.switch/vlans/2500/ips", data={"address": "1.2.3.4", "mask": 25})

        assert_that(code, equal_to(409))
        assert_that(result, equal_to({'error': 'IP 1.2.3.4/25 is not available in this vlan'}))

    def test_add_ip_unknown_vlan(self):
        self.switch_factory.should_receive('get_switch').with_args('my.switch').and_return(self.switch_mock).once().ordered()
        self.switch_mock.should_receive('connect').once().ordered()
        self.switch_mock.should_receive('add_ip_to_vlan').with_args(2500, ExactIpNetwork("1.2.3.4", 25)).once().ordered()\
            .and_raise(UnknownVlan('2500'))
        self.switch_mock.should_receive('disconnect').once().ordered()

        result, code = self.post("/switches/my.switch/vlans/2500/ips", data={"address": "1.2.3.4", "mask": 25})

        assert_that(code, equal_to(404))
        assert_that(result, equal_to({'error': 'Vlan 2500 not found'}))

    def test_remove_ip(self):
        self.switch_factory.should_receive('get_switch').with_args('my.switch').and_return(self.switch_mock).once().ordered()
        self.switch_mock.should_receive('connect').once().ordered()
        self.switch_mock.should_receive('remove_ip_from_vlan').with_args(2500, ExactIpNetwork("1.2.3.4", 25)).once().ordered()
        self.switch_mock.should_receive('disconnect').once().ordered()

        result, code = self.delete("/switches/my.switch/vlans/2500/ips/1.2.3.4/25")

        assert_that(code, equal_to(204))

    def test_remove_ip_unknown_vlan(self):
        self.switch_factory.should_receive('get_switch').with_args('my.switch').and_return(self.switch_mock).once().ordered()
        self.switch_mock.should_receive('connect').once().ordered()
        self.switch_mock.should_receive('remove_ip_from_vlan').with_args(2500, ExactIpNetwork("1.2.3.4", 25)).once().ordered()\
            .and_raise(UnknownVlan('2500'))
        self.switch_mock.should_receive('disconnect').once().ordered()

        result, code = self.delete("/switches/my.switch/vlans/2500/ips/1.2.3.4/25")

        assert_that(code, equal_to(404))
        assert_that(result, equal_to({'error': 'Vlan 2500 not found'}))

    def test_remove_unknown_ip(self):
        self.switch_factory.should_receive('get_switch').with_args('my.switch').and_return(self.switch_mock).once().ordered()
        self.switch_mock.should_receive('connect').once().ordered()
        self.switch_mock.should_receive('remove_ip_from_vlan').with_args(2500, ExactIpNetwork("1.2.3.4", 25)).once().ordered()\
            .and_raise(UnknownIP(IPNetwork("1.2.3.4/25")))
        self.switch_mock.should_receive('disconnect').once().ordered()

        result, code = self.delete("/switches/my.switch/vlans/2500/ips/1.2.3.4/25")

        assert_that(code, equal_to(404))
        assert_that(result, equal_to({'error': 'IP 1.2.3.4/25 not found'}))

    def test_remove_ip_malformed_url(self):
        self.switch_factory.should_receive('get_switch').with_args('my.switch').and_return(self.switch_mock)
        self.switch_mock.should_receive('connect').never()

        result, code = self.delete("/switches/my.switch/vlans/2500/ips/wat")
        assert_that(code, equal_to(400))
        assert_that(result, equal_to({'error': 'Malformed IP, should be : x.x.x.x/xx'}))

        result, code = self.delete("/switches/my.switch/vlans/2500/ips/1.1.1.")
        assert_that(code, equal_to(400))
        assert_that(result, equal_to({'error': 'Malformed IP, should be : x.x.x.x/xx'}))

        result, code = self.delete("/switches/my.switch/vlans/2500/ips/1.1.1/")
        assert_that(code, equal_to(400))
        assert_that(result, equal_to({'error': 'Malformed IP, should be : x.x.x.x/xx'}))

    def test_add_vrrp_group_json(self):
        self.switch_factory.should_receive('get_switch').with_args('my.switch').and_return(self.switch_mock).once().ordered()
        self.switch_mock.should_receive('connect').once().ordered()
        self.switch_mock.should_receive('add_vrrp_group').with_args(
            vlan_number=2500, group_id=2,
            ips=[IPAddress("10.10.0.1"), IPAddress("10.10.0.2"), IPAddress("10.10.0.3")],
            priority=100,
            hello_interval=5,
            dead_interval=15,
            track_decrement=50,
            track_id="101",
        ).once().ordered()

        self.switch_mock.should_receive('disconnect').once().ordered()

        result, code = self.post("/switches/my.switch/vlans/2500/vrrp-groups",
                                 fixture="post_switch_hostname_vlans_vlanid_vrrp_groups.json")

        assert_that(code, equal_to(201))

    def test_add_partial_vrrp_group_json(self):
        self.switch_factory.should_receive('get_switch').with_args('my.switch').and_return(self.switch_mock).once().ordered()
        self.switch_mock.should_receive('connect').once().ordered()
        self.switch_mock.should_receive('add_vrrp_group').with_args(
            vlan_number=2500, group_id=2,
            ips=[IPAddress("10.10.0.1"), IPAddress("10.10.0.2"), IPAddress("10.10.0.3")],
            priority=100,
            hello_interval=None,
            dead_interval=None,
            track_decrement=None,
            track_id=None,
        ).once().ordered()

        self.switch_mock.should_receive('disconnect').once().ordered()

        result, code = self.post("/switches/my.switch/vlans/2500/vrrp-groups",
                                 data={
                                     "id": 2,
                                     "ips": ["10.10.0.1", "10.10.0.2", "10.10.0.3"],
                                     "priority": 100,
                                 })

        assert_that(code, equal_to(201))

    def test_add_vrrp_group_malformed_request(self):
        self.switch_factory.should_receive('get_switch').never()

        result, code = self.post("/switches/my.switch/vlans/2500/vrrp-groups", raw_data="not json")
        assert_that(code, equal_to(400))
        assert_that(result, equal_to({'error': 'Malformed content, should be a JSON object'}))

        result, code = self.post("/switches/my.switch/vlans/2500/vrrp-groups", data={})
        assert_that(code, equal_to(400))
        assert_that(result, equal_to({'error': 'VRRP group id is mandatory'}))

        result, code = self.post("/switches/my.switch/vlans/2500/vrrp-groups",
                                 data={"id": 2, "ips": ["dwwdqdw"], "priority": 100})
        assert_that(code, equal_to(400))
        assert_that(result, equal_to({'error': 'Incorrect IP Address: "dwwdqdw", should be x.x.x.x'}))

        result, code = self.post("/switches/my.switch/vlans/2500/vrrp-groups",
                                 data={"id": 2, "ips": ["10.10.0.1/32"], "priority": 100})
        assert_that(code, equal_to(400))
        assert_that(result, equal_to({'error': 'Incorrect IP Address: "10.10.0.1/32", should be x.x.x.x'}))

    def test_remove_vrrp_group(self):
        self.switch_factory.should_receive('get_switch').with_args('my.switch').and_return(self.switch_mock).once().ordered()
        self.switch_mock.should_receive('connect').once().ordered()
        self.switch_mock.should_receive('remove_vrrp_group').with_args(2500, 4).once().ordered()
        self.switch_mock.should_receive('disconnect').once().ordered()

        result, code = self.delete("/switches/my.switch/vlans/2500/vrrp-groups/4")

        assert_that(code, equal_to(204))

    def test_add_dhcp_relay_server(self):
        self.switch_factory.should_receive('get_switch').with_args('my.switch').and_return(self.switch_mock).once().ordered()
        self.switch_mock.should_receive('connect').once().ordered()
        self.switch_mock.should_receive('add_dhcp_relay_server').with_args(
            vlan_number=2500,
            ip_address=IPAddress("10.10.10.1"),
        ).once().ordered()

        self.switch_mock.should_receive('disconnect').once().ordered()

        result, code = self.post("/switches/my.switch/vlans/2500/dhcp-relay-server",
                                 fixture="put_switch_hostname_vlans_vlanid_dhcp_relay_server.txt")

        assert_that(code, equal_to(204))

    def test_remove_dhcp_relay_server(self):
        self.switch_factory.should_receive('get_switch').with_args('my.switch').and_return(self.switch_mock).once().ordered()
        self.switch_mock.should_receive('connect').once().ordered()
        self.switch_mock.should_receive('remove_dhcp_relay_server').with_args(
            vlan_number=2500,
            ip_address=IPAddress('10.10.10.1')
        ).once().ordered()

        self.switch_mock.should_receive('disconnect').once().ordered()

        result, code = self.delete("/switches/my.switch/vlans/2500/dhcp-relay-server/10.10.10.1")

        assert_that(code, equal_to(204))

    def test_add_dhcp_relay_server_malformed_data(self):
        result, code = self.post("/switches/my.switch/vlans/2500/dhcp-relay-server", raw_data="NOT AN IP")

        assert_that(code, equal_to(400))

    def test_remove_dhcp_relay_server_malformed_data(self):
        self.switch_factory.should_receive('get_switch').with_args('my.switch').and_return(self.switch_mock).once().ordered()
        result, code = self.delete("/switches/my.switch/vlans/2500/dhcp-relay-server/NOT_AN_IP")

        assert_that(code, equal_to(400))

    def test_enable_lldp(self):
        self.switch_factory.should_receive('get_switch').with_args('my.switch').and_return(self.switch_mock).once().ordered()
        self.switch_mock.should_receive('connect').once().ordered()
        self.switch_mock.should_receive('enable_lldp').with_args("FastEthernet0/4", True).once().ordered()

        self.switch_mock.should_receive('disconnect').once().ordered()

        result, code = self.put("/switches/my.switch/interfaces/FastEthernet0/4/lldp", raw_data="true")

        assert_that(code, equal_to(204))

    def test_disable_lldp(self):
        self.switch_factory.should_receive('get_switch').with_args('my.switch').and_return(self.switch_mock).once().ordered()
        self.switch_mock.should_receive('connect').once().ordered()
        self.switch_mock.should_receive('enable_lldp').with_args("FastEthernet0/4", False).once().ordered()

        self.switch_mock.should_receive('disconnect').once().ordered()

        result, code = self.put("/switches/my.switch/interfaces/FastEthernet0/4/lldp", raw_data="false")

        assert_that(code, equal_to(204))

    def test_put_access_groups_in(self):
        self.switch_factory.should_receive('get_switch').with_args('my.switch').and_return(self.switch_mock).once().ordered()
        self.switch_mock.should_receive('connect').once().ordered()
        self.switch_mock.should_receive('set_vlan_access_group').with_args(2500, IN, "spaceless_string").once().ordered()
        self.switch_mock.should_receive('disconnect').once().ordered()

        result, code = self.put("/switches/my.switch/vlans/2500/access-groups/in",
                                fixture="put_switch_hostname_vlans_vlanid_accessgroups_in.txt")

        assert_that(code, equal_to(204))

    def test_put_access_groups_out(self):
        self.switch_factory.should_receive('get_switch').with_args('my.switch').and_return(self.switch_mock).once().ordered()
        self.switch_mock.should_receive('connect').once().ordered()
        self.switch_mock.should_receive('set_vlan_access_group').with_args(2500, OUT, "spaceless_string").once().ordered()
        self.switch_mock.should_receive('disconnect').once().ordered()

        result, code = self.put("/switches/my.switch/vlans/2500/access-groups/out",
                                fixture="put_switch_hostname_vlans_vlanid_accessgroups_in.txt")

        assert_that(code, equal_to(204))

    def test_put_access_groups_malformed_body(self):
        self.switch_factory.should_receive('get_switch').with_args('my.switch').and_return(self.switch_mock).once().ordered()

        result, code = self.put("/switches/my.switch/vlans/2500/access-groups/out", raw_data="Hey hey")
        assert_that(code, equal_to(400))

        result, code = self.put("/switches/my.switch/vlans/2500/access-groups/out", raw_data="")
        assert_that(code, equal_to(400))

        result, code = self.put("/switches/my.switch/vlans/2500/access-groups/notin", raw_data="good")
        assert_that(code, equal_to(404))

    def test_put_access_groups_vlan_not_found(self):
        self.switch_factory.should_receive('get_switch').with_args('my.switch').and_return(self.switch_mock).once().ordered()
        self.switch_mock.should_receive('connect').once().ordered()
        self.switch_mock.should_receive('set_vlan_access_group').with_args(2500, OUT, "spaceless_string").once().ordered().and_raise(UnknownVlan('2500'))
        self.switch_mock.should_receive('disconnect').once().ordered()

        result, code = self.put("/switches/my.switch/vlans/2500/access-groups/out",
                                fixture="put_switch_hostname_vlans_vlanid_accessgroups_in.txt")

        assert_that(code, equal_to(404))
        assert_that(result, equal_to({'error': 'Vlan 2500 not found'}))

    def test_put_access_groups_vlan_wrong_name(self):
        self.switch_factory.should_receive('get_switch').with_args('my.switch').and_return(self.switch_mock).once().ordered()
        self.switch_mock.should_receive('connect').once().ordered()
        self.switch_mock.should_receive('set_vlan_access_group').with_args(2500, OUT, "blablabla").once().ordered()\
            .and_raise(ValueError('Access group name \"blablabla\" is invalid'))
        self.switch_mock.should_receive('disconnect').once().ordered()

        result, code = self.put("/switches/my.switch/vlans/2500/access-groups/out", raw_data="blablabla")

        assert_that(code, equal_to(400))
        assert_that(result, equal_to({'error': 'Access group name \"blablabla\" is invalid'}))

    def delete_put_access_groups_in(self):
        self.switch_factory.should_receive('get_switch').with_args('my.switch').and_return(self.switch_mock).once().ordered()
        self.switch_mock.should_receive('connect').once().ordered()
        self.switch_mock.should_receive('remove_vlan_access_group').with_args(2500, IN).once().ordered()
        self.switch_mock.should_receive('disconnect').once().ordered()

        result, code = self.delete("/switches/my.switch/vlans/2500/access-groups/in")

        assert_that(code, equal_to(204))

    def delete_put_access_groups_out(self):
        self.switch_factory.should_receive('get_switch').with_args('my.switch').and_return(self.switch_mock).once().ordered()
        self.switch_mock.should_receive('connect').once().ordered()
        self.switch_mock.should_receive('remove_vlan_access_group').with_args(2500, OUT).once().ordered()
        self.switch_mock.should_receive('disconnect').once().ordered()

        result, code = self.delete("/switches/my.switch/vlans/2500/access-groups/out")

        assert_that(code, equal_to(204))


    def test_delete_access_groups_vlan_not_found(self):
        self.switch_factory.should_receive('get_switch').with_args('my.switch').and_return(self.switch_mock).once().ordered()
        self.switch_mock.should_receive('connect').once().ordered()
        self.switch_mock.should_receive('remove_vlan_access_group').with_args(2500, OUT).once().ordered()\
            .and_raise(UnknownVlan('2500'))
        self.switch_mock.should_receive('disconnect').once().ordered()

        result, code = self.delete("/switches/my.switch/vlans/2500/access-groups/out")

        assert_that(code, equal_to(404))
        assert_that(result, equal_to({'error': 'Vlan 2500 not found'}))


    def test_delete_access_groups_not_found(self):
        self.switch_factory.should_receive('get_switch').with_args('my.switch').and_return(self.switch_mock).once().ordered()
        self.switch_mock.should_receive('connect').once().ordered()
        self.switch_mock.should_receive('remove_vlan_access_group').with_args(2500, OUT).once().ordered()\
            .and_raise(UnknownAccessGroup(IN))
        self.switch_mock.should_receive('disconnect').once().ordered()

        result, code = self.delete("/switches/my.switch/vlans/2500/access-groups/out")

        assert_that(code, equal_to(404))
        assert_that(result, equal_to({'error': 'Inbound IP access group not found'}))

    def test_delete_access_groups_malformed_request(self):
        self.switch_factory.should_receive('get_switch').with_args('my.switch').and_return(self.switch_mock).once().ordered()

        result, code = self.delete("/switches/my.switch/vlans/2500/access-groups/notout")
        assert_that(code, equal_to(404))

    def test_set_vlan_vrf(self):
        self.switch_factory.should_receive('get_switch').with_args('my.switch').and_return(self.switch_mock).once().ordered()
        self.switch_mock.should_receive('connect').once().ordered()
        self.switch_mock.should_receive('set_vlan_vrf').with_args(2500, "DEFAULT_LAN").once().ordered()
        self.switch_mock.should_receive('disconnect').once().ordered()

        result, code = self.put("/switches/my.switch/vlans/2500/vrf-forwarding", raw_data="DEFAULT_LAN")

        assert_that(code, equal_to(204))

    def test_remove_vlan_vrf(self):
        self.switch_factory.should_receive('get_switch').with_args('my.switch').and_return(self.switch_mock).once().ordered()
        self.switch_mock.should_receive('connect').once().ordered()
        self.switch_mock.should_receive('remove_vlan_vrf').with_args(2500).once().ordered()
        self.switch_mock.should_receive('disconnect').once().ordered()

        result, code = self.delete("/switches/my.switch/vlans/2500/vrf-forwarding")

        assert_that(code, equal_to(204))

    def test_bonds_serialization(self):
        self.switch_factory.should_receive('get_switch').with_args('my.switch').and_return(self.switch_mock).once().ordered()
        self.switch_mock.should_receive('connect').once().ordered()
        self.switch_mock.should_receive('get_bonds').once().ordered().and_return([
            Bond(
                number=3,
                link_speed='1g',
                interface=Interface(
                    name="ae3",
                    shutdown=True,
                    port_mode=ACCESS,
                    access_vlan=1999)),
            Bond(
                number=6,
                link_speed='10g',
                interface=Interface(
                    name="ae6",
                    shutdown=False,
                    port_mode=DYNAMIC,
                    access_vlan=1999,
                    trunk_native_vlan=2999,
                    trunk_vlans=[3001, 3000, 3002])),
            Bond(
                number=4,
                members=["ge-0/0/1", "ge-1/0/1"],
                interface=Interface(
                    name="ae4",
                    shutdown=False,
                    port_mode=TRUNK,
                    trunk_native_vlan=2999,
                    trunk_vlans=[3001, 3000, 3002])),
            ])
        self.switch_mock.should_receive('disconnect').once().ordered()

        result, code = self.get("/switches/my.switch/bonds")

        assert_that(code, equal_to(200))
        assert_that(result, matches_fixture("get_switch_hostname_bonds.json"))

    def test_get_bond_is_correctly_serialized(self):
        self.switch_factory.should_receive('get_switch').with_args('my.switch').and_return(self.switch_mock).once().ordered()
        self.switch_mock.should_receive('connect').once().ordered()
        self.switch_mock.should_receive('get_bond').with_args(3).once().ordered().and_return(
            Bond(
                number=3,
                link_speed='1g',
                interface=Interface(
                    name="ae3",
                    shutdown=True,
                    port_mode=ACCESS,
                    access_vlan=1999))
            )
        self.switch_mock.should_receive('disconnect').once().ordered()

        result, code = self.get("/switches/my.switch/bonds/3")

        assert_that(code, equal_to(200))
        assert_that(result, matches_fixture("get_switch_hostname_bond.json"))


    def test_add_bond(self):
        self.switch_factory.should_receive('get_switch').with_args('my.switch').and_return(self.switch_mock).once().ordered()
        self.switch_mock.should_receive('connect').once().ordered()
        self.switch_mock.should_receive('add_bond').with_args(55).once().ordered()
        self.switch_mock.should_receive('disconnect').once().ordered()

        result, code = self.post("/switches/my.switch/bonds", fixture="post_switch_hostname_bonds.json")

        assert_that(code, equal_to(201))

    def test_remove_bond(self):
        self.switch_factory.should_receive('get_switch').with_args('my.switch').and_return(self.switch_mock).once().ordered()
        self.switch_mock.should_receive('connect').once().ordered()
        self.switch_mock.should_receive('remove_bond').with_args(55).once().ordered()
        self.switch_mock.should_receive('disconnect').once().ordered()

        result, code = self.delete("/switches/my.switch/bonds/55")

        assert_that(code, equal_to(204))

    def test_remove_bond_bad_number(self):
        self.switch_factory.should_receive('get_switch').with_args('my.switch').and_return(self.switch_mock).once().ordered()

        result, code = self.delete("/switches/my.switch/bonds/allo")

        assert_that(code, equal_to(400))

    def test_set_bond_link_speed(self):
        self.switch_factory.should_receive('get_switch').with_args('my.switch').and_return(self.switch_mock).once().ordered()
        self.switch_mock.should_receive('connect').once().ordered()
        self.switch_mock.should_receive('set_bond_link_speed').with_args(4, '1g').once().ordered()
        self.switch_mock.should_receive('disconnect').once().ordered()

        result, code = self.put("/switches/my.switch/bonds/4/link-speed", fixture="put_switch_hostname_bonds_link_speed.txt")

        assert_that(code, equal_to(204))

    def test_set_bond_link_speed_bad_speed(self):
        result, code = self.put("/switches/my.switch/bonds/4/link-speed", raw_data="9001pb")

        assert_that(code, equal_to(400))
        assert_that(result, equal_to({'error': 'Malformed bond link speed'}))

    def test_add_interface_to_bond(self):
        self.switch_factory.should_receive('get_switch').with_args('my.switch').and_return(self.switch_mock).once().ordered()
        self.switch_mock.should_receive('connect').once().ordered()
        self.switch_mock.should_receive('add_interface_to_bond').with_args('FastEthernet0/4', 10).once().ordered()
        self.switch_mock.should_receive('disconnect').once().ordered()

        result, code = self.put("/switches/my.switch/interfaces/FastEthernet0/4/bond-master",
                                fixture="put_switch_hostname_interfaces_bond_master.txt")

        assert_that(code, equal_to(204))

    def test_remove_interface_from_bond(self):
        self.switch_factory.should_receive('get_switch').with_args('my.switch').and_return(self.switch_mock).once().ordered()
        self.switch_mock.should_receive('connect').once().ordered()
        self.switch_mock.should_receive('remove_interface_from_bond').with_args('FastEthernet0/4').once().ordered()
        self.switch_mock.should_receive('disconnect').once().ordered()

        result, code = self.delete("/switches/my.switch/interfaces/FastEthernet0/4/bond-master")

        assert_that(code, equal_to(204))

    def test_set_interface_description(self):
        self.switch_factory.should_receive('get_switch').with_args('my.switch').and_return(self.switch_mock).once().ordered()
        self.switch_mock.should_receive('connect').once().ordered()
        self.switch_mock.should_receive('set_interface_description').with_args("FastEthernet0/4", "Resistance is futile").once().ordered()
        self.switch_mock.should_receive('disconnect').once().ordered()

        result, code = self.put("/switches/my.switch/interfaces/FastEthernet0/4/description", raw_data="Resistance is futile")

        assert_that(code, equal_to(204))

    def test_remove_interface_description(self):
        self.switch_factory.should_receive('get_switch').with_args('my.switch').and_return(self.switch_mock).once().ordered()
        self.switch_mock.should_receive('connect').once().ordered()
        self.switch_mock.should_receive('remove_interface_description').with_args("FastEthernet0/4").once().ordered()
        self.switch_mock.should_receive('disconnect').once().ordered()

        result, code = self.delete("/switches/my.switch/interfaces/FastEthernet0/4/description")

        assert_that(code, equal_to(204))

    def test_set_bond_description(self):
        self.switch_factory.should_receive('get_switch').with_args('my.switch').and_return(self.switch_mock).once().ordered()
        self.switch_mock.should_receive('connect').once().ordered()
        self.switch_mock.should_receive('set_bond_description').with_args(123, "Resistance is futile").once().ordered()
        self.switch_mock.should_receive('disconnect').once().ordered()

        result, code = self.put("/switches/my.switch/bonds/123/description", raw_data="Resistance is futile")

        assert_that(code, equal_to(204))

    def test_remove_bond_description(self):
        self.switch_factory.should_receive('get_switch').with_args('my.switch').and_return(self.switch_mock).once().ordered()
        self.switch_mock.should_receive('connect').once().ordered()
        self.switch_mock.should_receive('remove_bond_description').with_args(123).once().ordered()
        self.switch_mock.should_receive('disconnect').once().ordered()

        result, code = self.delete("/switches/my.switch/bonds/123/description")

        assert_that(code, equal_to(204))

    def test_edit_interface_spanning_tree(self):
        self.switch_factory.should_receive('get_switch').with_args('my.switch').and_return(self.switch_mock).once().ordered()
        self.switch_mock.should_receive('connect').once().ordered()
        self.switch_mock.should_receive('edit_interface_spanning_tree').with_args("FastEthernet0/4", edge=True).once().ordered()
        self.switch_mock.should_receive('disconnect').once().ordered()

        result, code = self.put("/switches/my.switch/interfaces/FastEthernet0/4/spanning-tree",
                                fixture="put_switch_hostname_interfaces_intname_spanningtree.json")

        assert_that(code, equal_to(204))

    def test_edit_interface_spanning_tree_optional_params(self):
        self.switch_factory.should_receive('get_switch').with_args('my.switch').and_return(self.switch_mock).once().ordered()
        self.switch_mock.should_receive('connect').once().ordered()
        self.switch_mock.should_receive('edit_interface_spanning_tree').with_args("FastEthernet0/4").once().ordered()
        self.switch_mock.should_receive('disconnect').once().ordered()

        result, code = self.put("/switches/my.switch/interfaces/FastEthernet0/4/spanning-tree", raw_data="{}")

        assert_that(code, equal_to(204))

    def test_edit_interface_spanning_tree_with_wrong_params(self):
        result, code = self.put("/switches/my.switch/interfaces/FastEthernet0/4/spanning-tree",
                                raw_data="whizzle")

        assert_that(code, equal_to(400))
        assert_that(result['error'], is_('Malformed JSON request'))

        result, code = self.put("/switches/my.switch/interfaces/FastEthernet0/4/spanning-tree",
                                raw_data='{"unknown_key": "value"}')

        assert_that(code, equal_to(400))
        assert_that(result['error'], is_('Unknown key: unknown_key'))

    def test_uncaught_exceptions_are_formatted_correctly(self):
        self.switch_factory.should_receive('get_switch').with_args('my.switch').and_return(self.switch_mock).once().ordered()
        self.switch_mock.should_receive('connect').once().ordered()
        self.switch_mock.should_receive('set_access_vlan').with_args('FastEthernet0/4', 1000).once().ordered()\
            .and_raise(Exception("SHIZZLE"))
        self.switch_mock.should_receive('disconnect').once().ordered()

        result, code = self.put("/switches/my.switch/interfaces/FastEthernet0/4/access-vlan",
                                fixture="put_switch_hostname_interfaces_intname_accessvlan.txt")

        assert_that(code, is_(500))
        assert_that(result, is_({"error": "SHIZZLE"}))

    def test_raised_exceptions_are_kept_in_the_error_message_for_remote_usage(self):
        self.switch_factory.should_receive('get_switch').with_args('my.switch').and_return(self.switch_mock).once().ordered()
        self.switch_mock.should_receive('connect').once().ordered()
        self.switch_mock.should_receive('set_access_vlan').with_args('FastEthernet0/4', 1000).once().ordered()\
            .and_raise(UnknownInterface("SHIZZLE"))
        self.switch_mock.should_receive('disconnect').once().ordered()

        result, code = self.put("/switches/my.switch/interfaces/FastEthernet0/4/access-vlan",
                                fixture="put_switch_hostname_interfaces_intname_accessvlan.txt",
                                headers={"Netman-Verbose-Errors": "yes"})

        assert_that(code, is_(404))
        assert_that(result, is_({
            "error": "Unknown interface SHIZZLE",
            "error-module": UnknownInterface.__module__,
            "error-class": UnknownInterface.__name__,
        }))

    def test_raised_exceptions_are_kept_in_the_error_message_for_remote_usage_even_plain_exceptions(self):
        self.switch_factory.should_receive('get_switch').with_args('my.switch').and_return(self.switch_mock).once().ordered()
        self.switch_mock.should_receive('connect').once().ordered()
        self.switch_mock.should_receive('set_access_vlan').with_args('FastEthernet0/4', 1000).once().ordered() \
            .and_raise(Exception("ERMAHGERD"))
        self.switch_mock.should_receive('disconnect').once().ordered()

        result, code = self.put("/switches/my.switch/interfaces/FastEthernet0/4/access-vlan",
                                fixture="put_switch_hostname_interfaces_intname_accessvlan.txt",
                                headers={"Netman-Verbose-Errors": "yes"})

        assert_that(code, is_(500))
        assert_that(result, is_({
            "error": "ERMAHGERD",
            "error-class": "Exception",
        }))

    def test_open_session(self):
        session_id = 'patate'

        self.switch_factory.should_receive('get_switch').with_args('my.switch').and_return(self.switch_mock).once().ordered()
        self.session_manager.should_receive('open_session').with_args(self.switch_mock, session_id).and_return(session_id).once().ordered()

        result, code = self.post("/switches-sessions/patate", fixture="post_switch_session.json")

        assert_that(result, matches_fixture("post_switch_session_result.json"))

        assert_that(code, equal_to(201))

    def test_duplicate_session(self):
        self.switch_factory.should_receive('get_switch').with_args('my.switch').and_return(self.switch_mock).once().ordered()
        self.session_manager.should_receive('open_session').with_args(self.switch_mock, 'patate')\
            .and_raise(SessionAlreadyExists('patate'))

        result, code = self.post("/switches-sessions/patate", fixture="post_switch_session.json")

        assert_that(code, equal_to(409))
        assert_that(result['error'], is_('Session ID already exists: patate'))

    def test_close_session(self):

        session_uuid = 'patate'

        self.session_manager.should_receive("get_switch_for_session").with_args(session_uuid).and_return(self.switch_mock)
        self.session_manager.should_receive('close_session').with_args(session_uuid).once().ordered()

        result, code = self.delete("/switches-sessions/" + session_uuid)

        assert_that(code, equal_to(204))

    def test_session_commit(self):
        session_uuid = 'poisson'

        self.session_manager.should_receive("get_switch_for_session").with_args(session_uuid).and_return(self.switch_mock)
        self.session_manager.should_receive('commit_session').with_args(session_uuid).once().ordered()
        result, code = self.post("/switches-sessions/{}/actions".format(session_uuid), raw_data="commit")
        assert_that(code, equal_to(204), str(result))

    def test_session_rollback(self):
        session_uuid = 'poisson'

        self.session_manager.should_receive("get_switch_for_session").with_args(session_uuid).and_return(self.switch_mock)
        self.session_manager.should_receive('rollback_session').with_args(session_uuid).once().ordered()
        result, code = self.post("/switches-sessions/{}/actions".format(session_uuid), raw_data="rollback")
        assert_that(code, equal_to(204), str(result))

    def test_unknown_session(self):
        session_uuid = 'patate'
        result, code = self.post("/switches-sessions/{}/vlans".format(session_uuid), data={"number": 2000})
        assert_that(code, equal_to(404))
        assert_that(result['error'], is_("Session \"%s\" not found." % session_uuid))

    def test_open_session_with_malformed_post_data(self):
        result, code = self.post("/switches-sessions/session_me_timbers", data={"bad_data": 666})

        assert_that(code, is_(400))
        assert_that(result['error'], is_('Malformed switch session request'))

    def test_open_session_unknown_switch(self):
        self.switch_factory.should_receive('get_switch').with_args('bad_hostname').and_raise(UnknownSwitch(name='bad_hostname'))

        result, code = self.post("/switches-sessions/session-me-timbers", data={"hostname": 'bad_hostname'})

        assert_that(code, is_(404))
        assert_that(result['error'], is_("Switch \"{0}\" is not configured".format('bad_hostname')))

    def test_close_session_with_error(self):
        session_uuid = 'patate'

        self.session_manager.should_receive("get_switch_for_session").with_args(session_uuid).and_return(self.switch_mock)
        self.session_manager.should_receive('close_session').with_args(session_uuid).once().ordered()\
            .and_raise(OperationNotCompleted())

        result, code = self.delete("/switches-sessions/" + session_uuid)
        assert_that(code, equal_to(500))

    def test_an_error_inside_a_session_call_is_properly_relayed(self):
        session_uuid = 'patate'

        self.switch_factory.should_receive('get_switch').with_args('my.switch').and_return(self.switch_mock).once().ordered()
        self.session_manager.should_receive("open_session").with_args(self.switch_mock, 'patate').once()\
            .and_return(session_uuid)

        result, code = self.post("/switches-sessions/patate", fixture="post_switch_session.json")

        assert_that(code, equal_to(201))
        assert_that(result['session_id'], session_uuid)

        self.session_manager.should_receive("get_switch_for_session").with_args(session_uuid).and_return(self.switch_mock)

        self.session_manager.should_receive("keep_alive").with_args(session_uuid).once()
        self.switch_mock.should_receive('set_vlan_access_group').with_args(2500, OUT, "spaceless_string").once()\
            .and_raise(UnknownVlan('2500')).ordered()

        result, code = self.put("/switches-sessions/{}/vlans/2500/access-groups/out".format(session_uuid),
                                fixture="put_switch_hostname_vlans_vlanid_accessgroups_in.txt")

        assert_that(code, equal_to(404))
        assert_that(result, equal_to({'error': 'Vlan 2500 not found',}))

    def test_an_error_inside_a_session_call_is_properly_relayed_with_exception_marshalling_when_requested(self):
        session_uuid = 'patate'

        self.switch_factory.should_receive('get_switch').with_args('my.switch').and_return(self.switch_mock).once().ordered()
        self.session_manager.should_receive("open_session").with_args(self.switch_mock, session_uuid).once()\
            .and_return(session_uuid)

        result, code = self.post("/switches-sessions/patate", fixture="post_switch_session.json")

        assert_that(code, equal_to(201))
        assert_that(result['session_id'], session_uuid)

        self.session_manager.should_receive("get_switch_for_session").with_args(session_uuid).and_return(self.switch_mock)

        self.session_manager.should_receive("keep_alive").with_args(session_uuid).once().ordered()
        self.switch_mock.should_receive('set_vlan_access_group').with_args(2500, OUT, "spaceless_string").once().ordered()\
            .and_raise(UnknownVlan('2500'))
        result, code = self.put("/switches-sessions/{}/vlans/2500/access-groups/out".format(session_uuid),
                                fixture="put_switch_hostname_vlans_vlanid_accessgroups_in.txt",
                                headers={"Netman-Verbose-Errors": "yes"})

        assert_that(code, equal_to(404))
        assert_that(result, equal_to({
            'error': 'Vlan 2500 not found',
            "error-module": UnknownVlan.__module__,
            "error-class": UnknownVlan.__name__,
        }))

    def test_an_error_without_a_message_is_given_one_containing_the_error_name_and_module(self):
        self.switch_factory.should_receive('get_switch').with_args('my.switch').and_return(self.switch_mock).once().ordered()
        self.switch_mock.should_receive('connect').once().ordered()
        self.switch_mock.should_receive('remove_vlan_access_group').with_args(2500, OUT).once().ordered()\
            .and_raise(EmptyException())
        self.switch_mock.should_receive('disconnect').once().ordered()

        result, code = self.delete("/switches/my.switch/vlans/2500/access-groups/out")

        assert_that(code, equal_to(500))
        assert_that(result, equal_to({'error': 'Unexpected error: tests.api.switch_api_test.EmptyException'}))


class EmptyException(Exception):
    pass
