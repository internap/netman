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

import argparse
from logging import DEBUG, getLogger

from flask import request
from flask.app import Flask

from adapters.threading_lock_factory import ThreadingLockFactory
from netman.adapters.memory_storage import MemoryStorage
from netman.api.api_utils import RegexConverter
from netman.api.netman_api import NetmanApi
from netman.api.switch_api import SwitchApi
from netman.api.switch_session_api import SwitchSessionApi
from netman.core.switch_factory import FlowControlSwitchFactory, RealSwitchFactory
from netman.core.switch_sessions import SwitchSessionManager

app = Flask('netman')
app.url_map.converters['regex'] = RegexConverter


@app.before_request
def log_request():
    logger = getLogger("netman.api")
    logger.info("{} : {}".format(request.method, request.url))
    if logger.isEnabledFor(DEBUG):
        logger.debug("body : {}".format(repr(request.data) if request.data else "<<empty>>"))
        logger.debug("Headers : " + ", ".join(["{0}={1}".format(h[0], h[1]) for h in request.headers]))


lock_factory = ThreadingLockFactory()
switch_factory = FlowControlSwitchFactory(MemoryStorage(), lock_factory)
real_switch_factory = RealSwitchFactory()
switch_session_manager = SwitchSessionManager()

NetmanApi(switch_factory).hook_to(app)
SwitchApi(switch_factory, switch_session_manager).hook_to(app)
SwitchSessionApi(real_switch_factory, switch_session_manager).hook_to(app)


def load_app(session_inactivity_timeout=None):
    if session_inactivity_timeout:
        switch_session_manager.session_inactivity_timeout = session_inactivity_timeout
    return app


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Netman Server')
    parser.add_argument('--host', nargs='?', default="127.0.0.1")
    parser.add_argument('--port', type=int, nargs='?', default=5000)
    parser.add_argument('--session-inactivity-timeout', type=int, nargs='?')

    args = parser.parse_args()

    params = {}
    if args.session_inactivity_timeout:
        params["session_inactivity_timeout"] = args.session_inactivity_timeout

    load_app(**params).run(host=args.host, port=args.port, threaded=True)
