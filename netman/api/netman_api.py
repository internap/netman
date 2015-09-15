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
import os

from flask import send_from_directory
from pkg_resources import get_distribution

from netman.api.api_utils import to_response
from netman.api.objects.info import SerializableInfo


class NetmanApi(object):
    def __init__(self, get_distribution_callback=get_distribution):
        self.app = None
        self.get_distribution = get_distribution_callback

    @property
    def logger(self):
        return logging.getLogger(__name__)

    def hook_to(self, server):
        self.app = server
        server.add_url_rule('/netman/info', view_func=self.get_info, methods=['GET'])
        server.add_url_rule('/netman/apidocs/', view_func=self.api_docs, methods=['GET'])
        server.add_url_rule('/netman/apidocs/<path:filename>', view_func=self.api_docs, methods=['GET'])

    @to_response
    def get_info(self):
        """
        Informations about the current deployment and state and generates a log entry on the netman.api logger \
        that says : ``/info requested this is a logging test``

        :code 200 OK:

        Example output:

        .. literalinclude:: ../../../tests/api/fixtures/get_info.json
            :language: json

        """
        logging.getLogger("netman.api").info("/info requested this is a logging test")

        return 200, SerializableInfo(
            status='running',
            version=self.get_distribution('netman').version
        )

    def api_docs(self, filename=None):
        """
        Shows this documentation

        """
        return send_from_directory(os.path.dirname(__file__) + "/doc_generated/html/", filename or "index.html")
