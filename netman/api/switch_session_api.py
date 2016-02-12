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

from flask import request

from netman.api.api_utils import BadRequest, to_response
from netman.api.switch_api_base import SwitchApiBase
from netman.api.validators import resource, content, Session, \
    Resource, is_session


class SwitchSessionApi(SwitchApiBase):
    def __init__(self, switch_factory, sessions_manager):
        super(SwitchSessionApi, self).__init__(switch_factory, sessions_manager)
        self.server = None

    def hook_to(self, server):
        server.add_url_rule('/switches-sessions/<session_id>', view_func=self.open_session, methods=['POST'])
        server.add_url_rule('/switches-sessions/<session_id>', view_func=self.close_session, methods=['DELETE'])
        server.add_url_rule('/switches-sessions/<session_id>/actions', view_func=self.act_on_session, methods=['POST'])
        server.add_url_rule('/switches-sessions/<session_id>/<path:resource>', view_func=self.on_session, methods=['GET', 'PUT', 'POST', 'DELETE'])

        self.server = server
        return self

    @to_response
    @content(is_session)
    def open_session(self, session_id, hostname):
        """
        Open a locked session on a switch

        :arg str hostname: Hostname or IP of the switch
        :body:

        .. literalinclude:: ../doc_config/api_samples/post_switch_session.json
            :language: json

        :code 201 CREATED:

        Example output:

        .. literalinclude:: ../doc_config/api_samples/post_switch_session_result.json
            :language: json

        """

        switch = self.resolve_switch(hostname)
        session_id = self.sessions_manager.open_session(switch, session_id)

        return 201, {'session_id': session_id}

    @to_response
    @resource(Session)
    def close_session(self, session_id):
        """
        Close a session on a switch

        :arg str session: ID of the session

        """

        self.sessions_manager.close_session(session_id)

        return 204, None

    @to_response
    @resource(Session, Resource)
    def on_session(self, session_id, resource_name):
        self.sessions_manager.keep_alive(session_id)
        with self.server.test_client() as http_client:
            response = http_client.open(
                '/switches/{}/{}'.format(session_id, resource_name),
                method=request.method,
                headers={k: v for k, v in request.headers.items()},
                data=request.data)
            return response

    @to_response
    @resource(Session)
    def act_on_session(self, session_id):
        """
        Commit or rollback a session on a switch

        :arg str session: ID of the session
        :body:
            ``commit`` or ``rollback``
        """

        action = request.data.lower()
        if action == 'start_transaction':
            self.sessions_manager.start_transaction(session_id)
        elif action == 'end_transaction':
            self.sessions_manager.end_transaction(session_id)
        elif action == 'commit':
            self.sessions_manager.commit_session(session_id)
        elif action == 'rollback':
            self.sessions_manager.rollback_session(session_id)
        else:
            raise BadRequest('Unknown action {}'.format(action))

        return 204, None
