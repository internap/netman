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
from datetime import datetime

from flask import current_app


class Serializer(object):
    def __init__(self, public_fields):
        super(Serializer, self).__init__()
        self.public_fields = public_fields

    def to_serializable_dict(self):
        data = {}
        for public_key in self.public_fields:
            data[public_key] = getattr(self, public_key)
        return data


class SWEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Serializer):
            return obj.to_serializable_dict()
        if isinstance(obj, datetime):
            return obj.strftime("%Y-%m-%dT%H:%M:%S%z")
        return json.JSONEncoder.default(self, obj)


def SWJsonify(*args, **kwargs):
    if kwargs:
        data = dict(*args, **kwargs)
    else:
        data = args[0]

    data_as_json = json.dumps(data, cls=SWEncoder, indent=None, separators=(',', ':'))
    response = current_app.response_class(
        data_as_json, mimetype='application/json; charset=UTF-8')

    return response
    # source https://github.com/mitsuhiko/flask/blob/master/flask/helpers.py
