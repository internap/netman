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


def sub_dict(d, *keys):
    return {k: d[k] for k in keys}


class Serializer(object):
    since_version = 1

    def to_api(self, core_object):
        raise NotImplementedError()

    def to_core(self, api_dict):
        raise NotImplementedError()


class Serializers(object):
    def __init__(self, *serializers):
        self.serializers = sorted(serializers, key=lambda s: s.since_version, reverse=True)

    def at_most(self, version):
        if version is None:
            return self.serializers[-1]
        for s in self.serializers:
            if s.since_version <= float(version):
                return s

    def to_api(self, core_object, version=None):
        return self.at_most(version).to_api(core_object)

    def to_core(self, api_dict, version=None):
        return self.at_most(version).to_core(api_dict)