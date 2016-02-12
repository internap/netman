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
from netman.core.objects.switch_descriptor import SwitchDescriptor


class SwitchApiBase(object):
    def __init__(self, switch_factory, sessions_manager):
        self.switch_factory = switch_factory
        self.sessions_manager = sessions_manager

    def hook_to(self, server):
        raise NotImplemented()

    @property
    def logger(self):
        return logging.getLogger(__name__)

    def _get_switch_descriptor_from_request_headers(self, hostname):
        headers_present = [h in request.headers for h in ['Netman-Model', 'Netman-Username', 'Netman-Password']]

        if not any(headers_present):
            return None

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

        self.logger.info("Anonymous Switch Access ({}) {}@{}".format(request.headers['Netman-Model'], request.headers['Netman-Username'], hostname))
        return SwitchDescriptor(
            hostname=hostname,
            model=request.headers['Netman-Model'],
            username=request.headers['Netman-Username'],
            password=request.headers['Netman-Password'],
            port=port,
            netman_server=netman_server
        )

    def resolve_switch(self, hostname):
        switch_descriptor = self._get_switch_descriptor_from_request_headers(hostname)

        if switch_descriptor:
            return self.switch_factory.get_switch_by_descriptor(switch_descriptor)
        return self.switch_factory.get_switch(hostname)

    def resolve_session(self, session_id):
        return self.sessions_manager.get_switch_for_session(session_id)
