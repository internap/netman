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
from netman.api.objects import info


class NetmanApi(object):
    def __init__(self, switch_factory=None, get_distribution_callback=get_distribution):
        self.switch_factory = switch_factory
        self.app = None
        self.get_distribution = get_distribution_callback

    @property
    def logger(self):
        return logging.getLogger(__name__)

    def hook_to(self, server):
        self.app = server
        server.add_url_rule('/netman/info',endpoint="netman_info",view_func=self.get_info, methods=['GET'])
        server.add_url_rule('/netman/apidocs/', endpoint="netman_apidocs" ,view_func=self.api_docs, methods=['GET'])
        server.add_url_rule('/netman/apidocs/<path:filename>', endpoint="netman_apidocs" ,view_func=self.api_docs, methods=['GET'])

    @to_response
    def get_info(self):
        """
        Informations about the current deployment and state and generates a log entry on the netman.api logger \
        that says : ``/info requested this is a logging test``

        :code 200 OK:

        Example output:

        .. literalinclude:: ../doc_config/api_samples/get_info.json
            :language: json

        """
        logging.getLogger("netman.api").info("/info requested this is a logging test")

        return 200, info.to_api(
            status='running',
            version=self.get_distribution('netman').version,
            lock_provider=_class_fqdn(self.switch_factory.lock_factory)
        )

    def api_docs(self, filename=None):
        """
        Shows this documentation

        """
        return send_from_directory(os.path.dirname(__file__) + "/doc/html/", filename or "index.html")


def _class_fqdn(obj):
    return "{}.{}".format(obj.__module__, obj.__class__.__name__)
