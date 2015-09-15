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

#!/usr/bin/env python
from logging import DEBUG, getLogger
import logging.config

from flask import request
from flask.app import Flask

from adapters.threading_lock_factory import ThreadingLockFactory
from netman.api.netman_api import NetmanApi
from netman.core.switch_sessions import SwitchSessionManager
from netman.adapters.memory_storage import MemoryStorage
from netman.api.api_utils import RegexConverter
from netman.api.switch_api import SwitchApi
from netman.api.switch_session_api import SwitchSessionApi
from netman.core.switch_factory import SwitchFactory

app = Flask('netman')
app.url_map.converters['regex'] = RegexConverter


@app.before_request
def log_request():
    logger = getLogger("netman.api")
    logger.info("%s : %s" % (request.method, request.url))
    if logger.isEnabledFor(DEBUG):
        logging.getLogger("netman.api").debug("body : %s" % (repr(request.data) if request.data else "<<empty>>"))
        logging.getLogger("netman.api").debug("Headers : " + ", ".join(["{0}={1}".format(h[0], h[1]) for h in request.headers]))

switch_factory = SwitchFactory(MemoryStorage(), ThreadingLockFactory())
switch_session_manager = SwitchSessionManager()

NetmanApi().hook_to(app)
SwitchApi(switch_factory, switch_session_manager).hook_to(app)
SwitchSessionApi(switch_factory, switch_session_manager).hook_to(app)


if __name__ == '__main__':
    app.run()
