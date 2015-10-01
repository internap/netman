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

import logging

from flask import request

from netman.api.api_utils import BadRequest


class SwitchApiBase(object):
    def __init__(self, switch_factory, sessions_manager):
        self.switch_factory = switch_factory
        self.sessions_manager = sessions_manager

    def hook_to(self, server):
        raise NotImplemented()

    @property
    def logger(self):
        return logging.getLogger(__name__)

    def resolve_switch(self, hostname):
        headers_present = [h in request.headers for h in ['Netman-Model', 'Netman-Username', 'Netman-Password']]

        if any(headers_present):
            if not all(headers_present):
                raise BadRequest('For anonymous switch usage, please specify headers: Netman-Model, Netman-Username and Netman-Password.')

            port = None
            if "Netman-Port" in request.headers:
                try:
                    port = int(request.headers["Netman-Port"])
                except ValueError:
                    raise BadRequest('Netman-Port optional header should be an integer')

            netman_server = request.headers.get("Netman-Proxy-Server", None)
            if netman_server is not None and "," in netman_server:
                netman_server = [e.strip() for e in netman_server.split(",")]

            self.logger.info("Anonymous Switch Access (%s) %s@%s" % (request.headers['Netman-Model'], request.headers['Netman-Username'], hostname))
            return self.switch_factory.get_anonymous_switch(
                hostname=hostname,
                model=request.headers['Netman-Model'],
                username=request.headers['Netman-Username'],
                password=request.headers['Netman-Password'],
                port=port,
                netman_server=netman_server
            )
        else:
            return self.switch_factory.get_switch(hostname)

    def resolve_session(self, session_id):
        return self.sessions_manager.get_switch_for_session(session_id)
