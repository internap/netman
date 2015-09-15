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


class MemoryStorage(object):
    def __init__(self):
        self.data = {}

    def set(self, name, data):
        self.data[name] = data

    def get(self, name):
        return self.data[name]

    def add_switch_descriptor(self, switch_descriptor):
        self.set("SWITCH:" + switch_descriptor.hostname, switch_descriptor)

    def get_switch_descriptor(self, hostname):
        return self.get("SWITCH:" + hostname)

    def get_switches(self):
        return [v for k, v in self.data.items() if k.startswith("SWITCH:")]
