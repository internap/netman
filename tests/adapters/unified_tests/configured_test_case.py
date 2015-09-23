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
import logging
import unittest
from functools import wraps
from unittest import SkipTest
from netman import raw_or_json

from netman.main import app


class ConfiguredTestCase(unittest.TestCase):
    switch_specs = None

    def setUp(self):
        tested_switch = type(self).switch_specs
        self.switch_hostname = tested_switch["hostname"]
        self.switch_port = tested_switch["port"]
        self.switch_type = tested_switch["model"]
        self.switch_username = tested_switch["username"]
        self.switch_password = tested_switch["password"]
        self.test_port = tested_switch["test_port_name"]

    def get(self, relative_url, fail_on_bad_code=True):
        with app.test_client() as http_client:
            r = http_client.get(**self.request(relative_url))

        if fail_on_bad_code and r.status_code >= 400:
            raise AssertionError("Call to %s returned %s : %s" % (relative_url, r.status_code, r.data))
        return json.loads(r.data)

    def post(self, relative_url, data=None, raw_data=None, fail_on_bad_code=True):
        with app.test_client() as http_client:
            r = http_client.post(data=raw_or_json(raw_data, data), **self.request(relative_url))
        if fail_on_bad_code and r.status_code >= 400:
            raise AssertionError("Call to %s returned %s : %s" % (relative_url, r.status_code, r.data))
        return r

    def put(self, relative_url, data=None, raw_data=None, fail_on_bad_code=True):
        with app.test_client() as http_client:
            r = http_client.put(data=raw_or_json(raw_data, data), **self.request(relative_url))
        if fail_on_bad_code and r.status_code >= 400:
            raise AssertionError("Call to %s returned %s : %s" % (relative_url, r.status_code, r.data))
        return r

    def delete(self, relative_url, fail_on_bad_code=True):
        with app.test_client() as http_client:
            r = http_client.delete(**self.request(relative_url))
        if fail_on_bad_code and r.status_code >= 400:
            raise AssertionError("Call to %s returned %s : %s" % (relative_url, r.status_code, r.data))
        return r

    def request(self, relative_url):
        logging.info("Querying " + ("http://netman.example.org%s" % relative_url.format(switch=self.switch_hostname, port=self.test_port)))
        headers = {
            'Netman-Model': self.switch_type,
            'Netman-Username': self.switch_username,
            'Netman-Password': self.switch_password,
            'Netman-Port': self.switch_port
        }

        return {
            "path": relative_url.format(switch=self.switch_hostname, port=self.test_port),
            "headers": headers
        }

    def get_vlan(self, number):
        data = self.get("/switches/{switch}/vlans")

        vlan = next((vlan for vlan in data if vlan["number"] == number), None)
        if not vlan:
            raise AssertionError("Vlan #{} not found".format(number))

        return vlan


def skip_on_switches(*to_skip):

    def resource_decorator(fn):
        @wraps(fn)
        def wrapper(self, *args, **kwargs):
            if not self.switch_type in to_skip:
                return fn(self, *args, **kwargs)

            else:
                raise SkipTest('Test not executed on Switch model %s' % self.switch_type)

        return wrapper

    return resource_decorator
