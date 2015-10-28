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

class VrrpGroupDescriptor(object):
    def __init__(self, hello_interval=None, dead_interval=None, track_id=None, track_decrement=None,
                 priority_allocation_strategy=None):
        self.id = id
        self.hello_interval = hello_interval
        self.dead_interval = dead_interval
        self.track_id = track_id
        self.track_decrement = track_decrement
        self.priority_allocation_strategy = priority_allocation_strategy

    def __str__(self):
        return ', '.join(['{} is {}'.format(elem[0], elem[1]) for elem in self.__dict__.items()])
