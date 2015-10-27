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


class VrrpGroup(object):
    def __init__(self, id=None, ips=None, priority=None, hello_interval=None, dead_interval=None, track_id=None,
                 track_decrement=None):
        self.id = id
        self.ips = ips or []
        self.priority = priority
        self.hello_interval = hello_interval
        self.dead_interval = dead_interval
        self.track_id = track_id
        self.track_decrement = track_decrement

    def __eq__(self, other):
        if isinstance(other, type(self)):
            return self.__dict__ == other.__dict__
        return False

    def __str__(self):
        return ', '.join(['{} is {}'.format(elem[0], elem[1]) for elem in self.__dict__.items()])
