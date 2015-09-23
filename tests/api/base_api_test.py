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

import json
import unittest
import flask
from netman import raw_or_json

from tests.api import open_fixture


class BaseApiTest(unittest.TestCase):
    def setUp(self):
        super(BaseApiTest, self).setUp()

        self.app = flask.Flask(__name__)

    def get(self, url, **kwargs):
        with self.app.test_client() as http_client:
            request_result = http_client.get(url, **kwargs)

        return to_json(request_result.data), request_result.status_code

    def post(self, url, data=None, raw_data=None, fixture=None):
        if fixture is not None:
            posting_data = open_fixture(fixture).read()
        else:
            posting_data = raw_or_json(raw_data, data)

        with self.app.test_client() as http_client:
            request_result = http_client.post(url, data=posting_data)
        return to_json(request_result.data), request_result.status_code

    def delete(self, url, **kwargs):
        with self.app.test_client() as http_client:
            request_result = http_client.delete(url, **kwargs)

        return to_json(request_result.data), request_result.status_code

    def put(self, url, data=None, raw_data=None, fixture=None, **kwargs):
        if fixture is not None:
            posting_data = open_fixture(fixture).read()
        else:
            posting_data = raw_or_json(raw_data, data)

        with self.app.test_client() as http_client:
            request_result = http_client.put(url, data=posting_data, **kwargs)

        return to_json(request_result.data), request_result.status_code


def to_json(string):
    try:
        return json.loads(string)
    except ValueError:
        return None
