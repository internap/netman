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

from netman.core.objects import Model


class SwitchDescriptor(Model):
    def __init__(self, model, hostname, username=None, password=None, port=None, netman_server=None):
        self.model = model
        self.hostname = hostname
        self.username = username
        self.password = password
        self.port = port
        self.netman_server = netman_server
