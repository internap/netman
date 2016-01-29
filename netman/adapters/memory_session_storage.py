# Copyright 2016 Internap.
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

from netman.core.objects.exceptions import SessionAlreadyExists, UnknownSession
from netman.core.session_storage import SessionStorage


class MemorySessionStorage(SessionStorage):
    def __init__(self):
        super(MemorySessionStorage, self).__init__()
        self._sessions = {}

    def add(self, session_id, switch_descriptor):
        if session_id not in self._sessions:
            self._sessions[session_id] = switch_descriptor
        else:
            raise SessionAlreadyExists(session_id)

    def get(self, session_id):
        if session_id in self._sessions:
            return self._sessions[session_id]

    def remove(self, session_id):
        if session_id not in self._sessions:
            raise UnknownSession(session_id)
        del self._sessions[session_id]
