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

from logging import getLogger
import threading

from netman.adapters.memory_session_storage import MemorySessionStorage
from netman.core.objects.exceptions import UnknownSession, SessionAlreadyExists, \
    NetmanException


class SwitchSessionManager(object):
    def __init__(self, session_inactivity_timeout=60, session_storage=None):
        self.session_storage = session_storage or MemorySessionStorage()
        self.sessions = {}
        self.session_inactivity_timeout = session_inactivity_timeout
        self.timers = {}

    @property
    def logger(self):
        return getLogger(__name__)

    def get_switch_for_session(self, session_id):
        try:
            return self.sessions[session_id]
        except KeyError:
            raise UnknownSession(session_id)

    def start_transaction(self, session_id):
        self.logger.info("Starting Transaction for session {}".format(session_id))
        self.keep_alive(session_id)
        switch = self.get_switch_for_session(session_id)
        try:
            switch.start_transaction()
        except:
            self.logger.exception("Session {} caught an exception while trying to start transaction".format(session_id))
            raise

    def end_transaction(self, session_id):
        self.logger.info("Ending Transaction for session {}".format(session_id))
        self.keep_alive(session_id)
        switch = self.get_switch_for_session(session_id)
        try:
            switch.end_transaction()
        except:
            self.logger.exception("Session {} caught an exception while trying to end transaction".format(session_id))
            raise

    def open_session(self, switch, session_id):
        self.logger.info("Creating session {}".format(session_id))

        if session_id in self.sessions:
            raise SessionAlreadyExists(session_id)

        self._add_session(session_id, switch)
        switch.connect()
        self.logger.info("Switch for session {} connected and session stored: ".format(session_id))
        self._start_timer(session_id)

        return session_id

    def _add_session(self, session_id, switch):
        self.sessions[session_id] = switch
        try:
            self.session_storage.add(session_id, switch.switch_descriptor)
        except NetmanException as e:
            self.logger.error('Switch for session {} could not be added in '
                              'SessionStorage: {}'.format(session_id, e))

    def _remove_session(self, session_id):
        del self.sessions[session_id]
        try:
            self.session_storage.remove(session_id)
        except NetmanException as e:
            self.logger.error('Switch for session {} could not be removed from '
                              'SessionStorage: {}'.format(session_id, e))

    def keep_alive(self, session_id):
        self.logger.info("Keeping-alive session {}".format(session_id))
        self._stop_timer(session_id)
        self._start_timer(session_id)

    def commit_session(self, session_id):
        self.logger.info("Committing session {}".format(session_id))
        self.keep_alive(session_id)
        switch = self.get_switch_for_session(session_id)
        switch.commit_transaction()

    def rollback_session(self, session_id):
        self.logger.info("Rolling back session {}".format(session_id))
        self.keep_alive(session_id)
        switch = self.get_switch_for_session(session_id)
        switch.rollback_transaction()

    def close_session(self, session_id):
        self.logger.info("Closing session {}".format(session_id))
        switch = self.get_switch_for_session(session_id)
        switch.disconnect()
        self._remove_session(session_id)
        self._stop_timer(session_id)

    def _cancel_session(self, session_id):
        self.logger.info("Inactivity timeout reached for session {}".format(session_id))
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
