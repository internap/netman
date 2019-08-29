import time
import unittest

import sys
from hamcrest import assert_that, less_than
from hamcrest import is_
from os.path import dirname, join

from tests.system_tests import NetmanTestApp, create_session, get_available_switch


class UwsgiCompatibilityTest(unittest.TestCase):
    def test_run_netman_with_a_uwsgi_wrapper(self):
        with UwsgiNetmanTestApp() as partial_client:
            client = partial_client(get_available_switch("cisco"))

            create_session(client, "my_session")

            result = client.delete("/switches-sessions/my_session")
            assert_that(result.status_code, is_(204), result.text)

    def test_parameters_can_be_passed_through_the_command_line(self):
        with UwsgiNetmanTestApp() as partial_client:
            client = partial_client(get_available_switch("brocade"))
            start_time = time.time()

            create_session(client, "session_timeouting")

            create_session(client, "session_taking_over")

            result = client.delete("/switches-sessions/session_taking_over")
            assert_that(result.status_code, is_(204), result.text)

            assert_that(time.time() - start_time, is_(less_than(3)))


class UwsgiNetmanTestApp(NetmanTestApp):
    def _popen_params(self, path):
        uwsgi_executable = join(dirname(sys.executable), 'uwsgi')
        params = [uwsgi_executable, "--module", "netman.main:app",
                  "--http", "{}:{}".format(self.ip, self.port),
                  "--threads", "2"]
        return params
