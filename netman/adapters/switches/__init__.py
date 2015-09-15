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

import re

from netman import regex


class SubShell(object):
    def __init__(self, ssh, enter, exit_cmd, validate=None):
        self.ssh = ssh
        self.enter = enter
        self.exit = exit_cmd
        self.validate = validate or (lambda x: None)

    def __enter__(self):
        if isinstance(self.enter, list):
            [self.validate(self.ssh.do(cmd)) for cmd in self.enter]
        else:
            self.validate(self.ssh.do(self.enter))
        return self.ssh

    def __exit__(self, *_):
        self.ssh.do(self.exit)


def no_output(exc, *args):
    def m(welcome_msg):
        if len(welcome_msg) > 0:
            raise exc(*args)
    return m


def split_on_bang(data):
    current_chunk = []
    for line in data:
        if re.match("^!.*", line):
            if len(current_chunk) > 0:
                yield current_chunk
                current_chunk = []
        else:
            current_chunk.append(line)


def split_on_dedent(data):
    current_chunk = []
    for line in data:
        if re.match("^[^\s].*", line) and len(current_chunk) > 0:
            yield current_chunk
            current_chunk = [line]
        else:
            current_chunk.append(line)

    yield current_chunk


class ResultChecker(object):
    def __init__(self, result=None):
        self.result = result

    def on_any_result(self, exception, *args, **kwargs):
        if self.result and len(self.result) > 0:
            raise exception(*args, **kwargs)
        return self

    def on_result_matching(self, matcher, exception, *args, **kwargs):
        if regex.match(matcher, "\n".join(self.result), flags=re.DOTALL):
            raise exception(*args, **kwargs)
        return self
