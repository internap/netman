import json
import time
import unittest

from hamcrest import assert_that
from hamcrest import is_

from netman.adapters.switches.remote import RemoteSwitch
from netman.adapters.threading_lock_factory import ThreadingLockFactory
from netman.core.objects.flow_control_switch import FlowControlSwitch
from tests.system_tests import NetmanTestApp, get_available_switch, create_session


class SessionTest(unittest.TestCase):

    def test_creating_commit_deleting_session_works(self):
        with NetmanTestApp() as partial_client:
            client = partial_client(get_available_switch("cisco"))

            result = create_session(client, "i_love_sessions")
            session_id = result.json()['session_id']
            client.post("/switches-sessions/" + session_id + "/actions", data='start_transaction')

            result = client.post("/switches-sessions/" + session_id + "/actions", data='commit')
            assert_that(result.status_code, is_(204), result.text)

            client.post("/switches-sessions/" + session_id + "/actions", data='end_transaction')
            result = client.delete("/switches-sessions/" + session_id)
            assert_that(result.status_code, is_(204), result.text)

    def test_sessions_can_time_out(self):
        with NetmanTestApp() as partial_client:
            client = partial_client(get_available_switch("brocade"))

            result = create_session(client, "i_love_sessions")

            session_id = result.json()['session_id']

            time.sleep(2)

            result = client.post("/switches-sessions/" + session_id + "/actions", data='start_transaction')
            assert_that(result.json().get("error"), is_('Session "i_love_sessions" not found.'))
            assert_that(result.status_code, is_(404), 'Session should have timed out')

    def test_creating_two_duplicate_sessions_returns_409(self):
        with NetmanTestApp() as partial_client:
            client = partial_client(get_available_switch("dell"))

            result = create_session(client, "i_love_sessions")

            first_session_id = result.json()['session_id']

            result = client.post("/switches-sessions/{}".format(first_session_id),
                                 data=json.dumps({"hostname": client.switch.hostname}))
            assert_that(result.status_code, is_(409), result.text)

    def test_remote_sessions_can_continue_on_a_different_netman(self):
        with NetmanTestApp() as partial_client1, NetmanTestApp() as partial_client2:
            switch_descriptor = get_available_switch("juniper")

            client1 = partial_client1(switch_descriptor)
            first_netman_url = "{}:{}".format(client1.host, client1.port)

            client2 = partial_client2(switch_descriptor)
            second_netman_url = "{}:{}".format(client2.host, client2.port)

            remote_switch = RemoteSwitch(switch_descriptor)
            remote_switch._proxy = first_netman_url
            switch = FlowControlSwitch(remote_switch, ThreadingLockFactory().new_lock())

            with switch.transaction():
                switch.add_vlan(1498, "one")

                remote_switch._proxy = second_netman_url

                switch.add_vlan(1499, "two")

            assert_that(client1.get("/switches/{hostname}/vlans/1498").json()["name"], is_("one"))
            assert_that(client1.get("/switches/{hostname}/vlans/1499").json()["name"], is_("two"))
