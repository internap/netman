import json
import random
import unittest
import sys
import subprocess
import time

from hamcrest import assert_that, less_than, greater_than
from hamcrest import is_
import pkg_resources
import requests
from tests import available_models
from functools import partial


class SessionTest(unittest.TestCase):

    def test_creating_commit_deleting_session_works(self):
        with NetmanTestApp() as partial_client:
            client = partial_client(_switch_of_model("cisco"))

            result = _create_session(client, "i_love_sessions")
            session_id = result.json()['session_id']

            result = client.post("/switches-sessions/" + session_id + "/actions", data='commit')
            assert_that(result.status_code, is_(204), result.text)

            result = client.delete("/switches-sessions/" + session_id)
            assert_that(result.status_code, is_(204), result.text)

    def test_sessions_timeout_let_the_next_session_takeover(self):
        with NetmanTestApp() as partial_client:
            client = partial_client(_switch_of_model("brocade"))

            start_time = time.time()

            result = _create_session(client, "i_love_sessions")
            assert_that(time.time() - start_time, is_(less_than(1)))

            first_session_id = result.json()['session_id']

            result = _create_session(client, "i_really_love_sessions")
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
            client = partial_client(_switch_of_model("dell"))

            result = _create_session(client, "i_love_sessions")

            first_session_id = result.json()['session_id']

            result = client.post("/switches-sessions/{}".format(first_session_id),
                                 data=json.dumps({"hostname": client.switch.hostname}))
            assert_that(result.status_code, is_(409), result.text)


def _create_session(client, id):
    result = client.post("/switches-sessions/{}".format(id),
                         data=json.dumps({"hostname": client.switch.hostname}))
    assert_that(result.status_code, is_(201), result.text)
    return result


def _switch_of_model(model):
    return next((m["switch_descriptor"] for m in available_models if m["switch_descriptor"].model == model))


class NetmanTestApp(object):
    def __init__(self, port=None, ip=None):
        self.ip = ip or "127.0.0.1"
        self.port = port or random.randrange(30000, 40000)

    def start(self):
        self._start(pkg_resources.resource_filename('netman', 'main.py'))

    def stop(self):
        self.proc.terminate()

    def __enter__(self):
        self.start()
        return partial(NetmanClient, "http://{}".format(self.ip), self.port)

    def __exit__(self, *_):
        self.stop()

    def _start(self, path):
        python = sys.executable
        self.proc = subprocess.Popen([python, path,
                                      "--host", self.ip,
                                      "--port", str(self.port),
                                      "--session_inactivity_timeout", "2"],
                                     stderr=subprocess.STDOUT,
                                     stdout=subprocess.PIPE)
        self._wait_until_port_is_opened(self.port)

    def _wait_until_port_is_opened(self, port):
        for i in range(0, 10):
            try:
                requests.get("http://127.0.0.1:{}".format(port))
                return
            except:
                time.sleep(1)
        raise Exception("Service did not start")


class NetmanClient(object):
    def __init__(self, host, port, switch, session_id=None):
        self.host = host
        self.port = port
        self.switch = switch
        self.session_id = session_id

    def __getattr__(self, name):
        headers = {
            'Netman-Model': self.switch.model,
            'Netman-Username': self.switch.username,
            'Netman-Password': self.switch.password,
            "Netman-Port": self.switch.port,
        }

        def invocation(url, *args, **kwargs):
            return getattr(requests, name)(
                "{}:{}{}".format(self.host, self.port, url),
                headers=headers,
                *args, **kwargs
            )

        return invocation
