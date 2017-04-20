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

from functools import wraps
import json
import logging

from flask import make_response, request, Response, current_app
from werkzeug.routing import BaseConverter
from netman.api import NETMAN_API_VERSION

from netman.core.objects.exceptions import UnknownResource, Conflict, InvalidValue


def to_response(fn):
    @wraps(fn)
    def wrapper(self, *args, **kwargs):
        try:
            result = fn(self, *args, **kwargs)
            if isinstance(result, Response):
                return result
            else:
                code, data = result
                if data is not None:
                    response = json_response(data, code)
                else:
                    response = make_response("", code)
        except InvalidValue as e:
            response = exception_to_response(e, 400)
        except UnknownResource as e:
            response = exception_to_response(e, 404)
        except Conflict as e:
            response = exception_to_response(e, 409)
        except NotImplementedError as e:
            response = exception_to_response(e, 501)
        except Exception as e:
            logging.exception(e)
            response = exception_to_response(e, 500)

        self.logger.info("Responding {} : {}".format(response.status_code, response.data))
        if 'Netman-Max-Version' in request.headers:
            response.headers['Netman-Version'] = min(
                float(request.headers['Netman-Max-Version']),
                NETMAN_API_VERSION)
        return response

    return wrapper


def exception_to_response(exception, code):
    data = {'error': str(exception)}

    if "Netman-Verbose-Errors" in request.headers:
        if hasattr(exception, "__module__"):
            data["error-module"] = exception.__module__
        data["error-class"] = exception.__class__.__name__
    else:
        if data['error'] == "":
            if hasattr(exception, "__module__"):
                data['error'] = "Unexpected error: {}.{}".format(exception.__module__, exception.__class__.__name__)
            else:
                data['error'] = "Unexpected error: {}".format(exception.__class__.__name__)

    response = json_response(data, code)
    response.status_code = code

    return response


def json_response(data, code):

    json_data = json.dumps(data, indent=None)
    response = current_app.response_class(json_data, mimetype='application/json; charset=UTF-8')
    response.status_code = code

    return response


class RegexConverter(BaseConverter):
    def __init__(self, url_map, *items):
        super(RegexConverter, self).__init__(url_map)
        self.regex = items[0]


class BadRequest(InvalidValue):
    pass


class MultiContext(object):
    def __init__(self, switch_api, parameters,  *contexts):
        self.context_instances = []
        for context in contexts:
            obj = context(switch_api)
            obj.process(parameters)
            self.context_instances.append(obj)

        self.parameters = parameters

    def __enter__(self):
        return [(obj.__enter__()) for obj in self.context_instances]

    def __exit__(self, type_, value, traceback):
        for context in self.context_instances:
            context.__exit__(type_, value, traceback)
