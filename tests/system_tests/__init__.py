import json
import logging
import random
import subprocess
from functools import partial

import pkg_resources
import requests
import time

import sys

from hamcrest import assert_that, is_

from tests import available_models


def create_session(client, id):
    result = client.post("/switches-sessions/{}".format(id),
                         data=json.dumps({"hostname": client.switch.hostname}))
    assert_that(result.status_code, is_(201), result.text)
    return result


def get_available_switch(model):
    return next((m["switch_descriptor"] for m in available_models if m["switch_descriptor"].model == model))


class NetmanTestApp(object):
    def __init__(self, ip=None, port=None, session_inactivity_timeout=2):
        self.ip = ip or "127.0.0.1"
        self.port = port or random.randrange(49152, 65535)
        self.session_inactivity_timeout = session_inactivity_timeout

    def __enter__(self):
        self._start(pkg_resources.resource_filename('netman', 'main.py'))
        return partial(NetmanClient, "http://{}".format(self.ip), self.port)

    def __exit__(self, *_):
        self._stop()

    def _start(self, path):
        params = self._popen_params(path)

        logging.info("starting netman : \"{}\"".format('" "'.join(params)))
        self.proc = subprocess.Popen(params, stderr=subprocess.STDOUT, stdout=subprocess.PIPE)
        self._wait_until_port_is_opened(self.port)

    def _stop(self):
        self.proc.terminate()
        stdout, stderr = self.proc.communicate()
        if stdout:
            logging.getLogger(__name__ + ".stdout").info(stdout)
        if stderr:
            logging.getLogger(__name__ + ".stderr").info(stderr)

    def _popen_params(self, path):
        params = [sys.executable, path,
                  "--host", self.ip,
                  "--port", str(self.port),
                  "--session-inactivity-timeout", str(self.session_inactivity_timeout)]
        return params

    def _wait_until_port_is_opened(self, port):
        for i in range(0, 20):
            try:
                requests.get("http://127.0.0.1:{}".format(port))
                return
            except:
                time.sleep(0.5)
        self._stop()
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
            "Netman-Port": str(self.switch.port),
        }

        def invocation(url, *args, **kwargs):
            return getattr(requests, name)(
                    ("{}:{}" + url).format(self.host, self.port, hostname=self.switch.hostname),
                    headers=headers,
                    *args, **kwargs
            )

        return invocation
