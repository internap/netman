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

import re
import threading


class RegexFacilitator(object):
    def __init__(self):
        self._m = {}

    @property
    def m(self):
        return self._m[threading.current_thread().ident]

    @m.setter
    def m(self, match):
        self._m[threading.current_thread().ident] = match

    def match(self, pattern, string, flags=0):
        self.m = re.match(pattern, string, flags)
        return self.m

    def __getitem__(self, key):
        return self.m.groups()[key]


regex = RegexFacilitator()


def raw_or_json(raw_data, data):
    posting_data = raw_data
    if data is not None:
        posting_data = json.dumps(data)
    return posting_data
