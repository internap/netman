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


class FlaskResponse(object):
    def __init__(self, response):
        self.response = response
        self.status_code = response.status_code
        self.data = response.data
        self.headers = response.headers

    def json(self):
        return json.loads(self.response.data)


class FlaskRequest(object):
    def __init__(self, flask_client):
        self.flask_client = flask_client

    def get(self, url, **kwargs):
        return FlaskResponse(self.flask_client.get(path=url, **kwargs))

    def post(self, url, **kwargs):
        return FlaskResponse(self.flask_client.post(path=url, **kwargs))

    def put(self, url, **kwargs):
        return FlaskResponse(self.flask_client.put(path=url, **kwargs))

    def delete(self, url, **kwargs):
        return FlaskResponse(self.flask_client.delete(path=url, **kwargs))
