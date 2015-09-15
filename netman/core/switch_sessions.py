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

from netman.core.objects.exceptions import UnknownSession, SessionAlreadyExists


class SwitchSessionManager(object):
    def __init__(self, session_inactivity_timeout=60):
        self.session_inactivity_timeout = session_inactivity_timeout
        self.sessions = {}
        self.timers = {}

    @property
    def logger(self):
        return logging.getLogger(__name__)

    def get_switch_for_session(self, session_id):
        try:
            return self.sessions[session_id]
        except KeyError:
            raise UnknownSession(session_id)

    def open_session(self, switch, session_id):
        self.logger.info("Creating session %s" % session_id)

        if session_id in self.sessions:
            raise SessionAlreadyExists(session_id)

        switch.connect()
        try:
            switch.start_transaction()
        except:
            self.logger.exception("Session %s caught an exception while trying to start transaction" % session_id)
            switch.disconnect()
            raise

        self.logger.info("Switch for session %s connected and in transaction mode, storing session" % session_id)
        self.sessions[session_id] = switch
        self._start_timer(session_id)

        return session_id

    def keep_alive(self, session_id):
        self.logger.info("Keep-aliving session %s" % session_id)
        self._stop_timer(session_id)
        self._start_timer(session_id)

    def commit_session(self, session_id):
        self.logger.info("Commiting session %s" % session_id)
        self.keep_alive(session_id)
        switch = self.get_switch_for_session(session_id)
        switch.commit_transaction()

    def rollback_session(self, session_id):
        self.logger.info("Rollbacking session %s" % session_id)
        self.keep_alive(session_id)
        switch = self.get_switch_for_session(session_id)
        switch.rollback_transaction()

    def close_session(self, session_id):
        self.logger.info("Closing session %s" % session_id)
        switch = self.get_switch_for_session(session_id)
        try:
            switch.end_transaction()
        finally:
            del self.sessions[session_id]
            self._stop_timer(session_id)
            switch.disconnect()

    def _cancel_session(self, session_id):
        self.logger.info("Inactivity timeout reached for session %s" % session_id)
        try:
            self.rollback_session(session_id)
        finally:
            self.close_session(session_id)

    def _start_timer(self, session_id):
        self.logger.info("Starting inactivity timer for session %s" % session_id)
        self.timers[session_id] = threading.Timer(
            self.session_inactivity_timeout, self._cancel_session,
            kwargs=dict(session_id=session_id))
        self.timers[session_id].start()

    def _stop_timer(self, session_id):
        self.logger.info("Stopping inactivity timer for session %s" % session_id)
        self.timers[session_id].cancel()
        del self.timers[session_id]
