import json
import time
import unittest

from hamcrest import assert_that, less_than, greater_than
from hamcrest import is_

from tests.system_tests import NetmanTestApp, get_available_switch, create_session


class SessionTest(unittest.TestCase):

    def test_creating_commit_deleting_session_works(self):
        with NetmanTestApp() as partial_client:
            client = partial_client(get_available_switch("cisco"))

            result = create_session(client, "i_love_sessions")
            session_id = result.json()['session_id']

            result = client.post("/switches-sessions/" + session_id + "/actions", data='commit')
            assert_that(result.status_code, is_(204), result.text)

            result = client.delete("/switches-sessions/" + session_id)
            assert_that(result.status_code, is_(204), result.text)

    def test_sessions_timeout_let_the_next_session_takeover(self):
        with NetmanTestApp() as partial_client:
            client = partial_client(get_available_switch("brocade"))

            start_time = time.time()

            result = create_session(client, "i_love_sessions")
            assert_that(time.time() - start_time, is_(less_than(1)))

            first_session_id = result.json()['session_id']

            result = create_session(client, "i_really_love_sessions")
            assert_that(time.time() - start_time, is_(greater_than(1)))

            second_session_id = result.json()['session_id']

            result = client.post("/switches-sessions/" + first_session_id + "/actions", data='commit')
            assert_that(result.status_code, is_(404), 'Session should have timed out')

            result = client.post("/switches-sessions/" + second_session_id + "/actions", data='commit')
            assert_that(result.status_code, is_(204), result.text)

            result = client.delete("/switches-sessions/" + second_session_id)
            assert_that(result.status_code, is_(204), result.text)

    def test_creating_two_duplicate_sessions_returns_409(self):
        with NetmanTestApp() as partial_client:
            client = partial_client(get_available_switch("dell"))

            result = create_session(client, "i_love_sessions")

            first_session_id = result.json()['session_id']

            result = client.post("/switches-sessions/{}".format(first_session_id),
                                 data=json.dumps({"hostname": client.switch.hostname}))
            assert_that(result.status_code, is_(409), result.text)
