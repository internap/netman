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

import logging
import threading

from netman.adapters.memory_session_storage import MemorySessionStorage
from netman.core.objects.exceptions import UnknownSession, SessionAlreadyExists


class SwitchSessionManager(object):
    def __init__(self, session_storage=None, session_inactivity_timeout=60):
        if not session_storage:
            session_storage = MemorySessionStorage()
        self.session_storage = session_storage
        self.session_inactivity_timeout = session_inactivity_timeout
        self.timers = {}

    @property
    def logger(self):
        return logging.getLogger(__name__)

    def get_switch_for_session(self, session_id):
        switch = self.session_storage.get(session_id)
        if not switch:
            raise UnknownSession(session_id)
        return switch

    def open_session(self, switch, session_id):
        self.logger.info("Creating session {}".format(session_id))

        if self.session_storage.get(session_id):
            raise SessionAlreadyExists(session_id)

        switch.connect()
        try:
            switch.start_transaction()
        except:
            self.logger.exception("Session {} caught an exception while trying to start transaction".format(session_id))
            switch.disconnect()
            raise

        self.logger.info("Switch for session {} connected and in transaction mode, storing session".format(session_id))
        self.session_storage.add(switch, session_id)
        self._start_timer(session_id)

        return session_id

    def keep_alive(self, session_id):
        self.logger.info("Keep-aliving session {}".format(session_id))
        self._stop_timer(session_id)
        self._start_timer(session_id)

    def commit_session(self, session_id):
        self.logger.info("Commiting session {}".format(session_id))
        self.keep_alive(session_id)
        switch = self.get_switch_for_session(session_id)
        switch.commit_transaction()

    def rollback_session(self, session_id):
        self.logger.info("Rollbacking session {}".format(session_id))
        self.keep_alive(session_id)
        switch = self.get_switch_for_session(session_id)
        switch.rollback_transaction()

    def close_session(self, session_id):
        self.logger.info("Closing session {}".format(session_id))
        switch = self.get_switch_for_session(session_id)
        try:
            switch.end_transaction()
        finally:
            self.session_storage.remove(session_id)
            self._stop_timer(session_id)
            switch.disconnect()

    def _cancel_session(self, session_id):
        self.logger.info("Inactivity timeout reached for session {}".format(session_id))
        try:
            self.rollback_session(session_id)
        finally:
            self.close_session(session_id)

    def _start_timer(self, session_id):
        self.logger.info("Starting inactivity timer for session {}".format(session_id))
        self.timers[session_id] = threading.Timer(
            self.session_inactivity_timeout, self._cancel_session,
            kwargs=dict(session_id=session_id))
        self.timers[session_id].start()

    def _stop_timer(self, session_id):
        self.logger.info("Stopping inactivity timer for session {}".format(session_id))
        self.timers[session_id].cancel()
        del self.timers[session_id]
