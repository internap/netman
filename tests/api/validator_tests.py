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
import json

import unittest

from flexmock import flexmock
from hamcrest import is_, equal_to
from hamcrest import assert_that

from netman.api.api_utils import MultiContext, BadRequest
from netman.api.validators import is_vlan_number, is_boolean, Vlan, Interface, is_dict_with, optional, is_type
from netman.core.objects.exceptions import BadVlanNumber


class DecoratorTests(unittest.TestCase):
    def test_resource_decorator(self):
        process1 = flexmock()
        process2 = flexmock()

        process1.should_receive('process').with_args('arg2').once()
        process1.should_receive('__enter__').once()

        process2.should_receive('process').with_args('arg2').once()
        process2.should_receive('__enter__').once()

        process1.should_receive('__exit__').once()
        process2.should_receive('__exit__').once()

        with MultiContext('arg1','arg2', process1, process2):
            pass

    def test_content_vlan(self):
        self.assertEquals(is_vlan_number('28'), {'vlan_number':28})

    def test_content_vlan_invalid(self):
        self.assertRaises(BadVlanNumber, is_vlan_number, 'patate')

    def test_content_vlan_invalid_number(self):
        self.assertRaises(BadVlanNumber, is_vlan_number, 2888888)

    def test_content_shutdown_options_true(self):
        self.assertEquals(is_boolean('true'), {'state':True})

    def test_content_shutdown_options_false(self):
        self.assertEquals(is_boolean('false'), {'state':False})

    def test_content_shutdown_options_invalid(self):
        self.assertRaises(BadRequest, is_boolean, 'patate')

    def test_resource_vlan(self):
        vlan = Vlan(None)
        vlan.process({'vlan_number': 2999})
        self.assertEquals(vlan.__enter__(), 2999)

    def test_resource_interface(self):
        interface = Interface(None)
        interface.process({'interface_id': 28})
        self.assertEquals(interface.__enter__(), 28)


class IsDictTests(unittest.TestCase):
    def test_empty(self):
        validate = is_dict_with()

        assert_that(validate("{}"), is_({}))

    def test_one_boolean(self):
        validate = is_dict_with(mybool=is_type(bool))
        data = {
            "mybool": True
        }

        assert_that(validate(json.dumps(data)), is_(data))

    def test_optional(self):
        validate = is_dict_with(mybool=optional(is_type(bool)))

        assert_that(validate("{}"), is_({}))

    def test_extra_field(self):
        validate = is_dict_with(mybool=is_type(bool))
        data = {
            "mybool": True,
            "yourbool": True
        }

        with self.assertRaises(BadRequest) as expect:
            validate(json.dumps(data))

        assert_that(str(expect.exception), equal_to("Unknown key: yourbool"))

    def test_incorrect_field(self):
        validate = is_dict_with(mybool=is_type(bool))
        data = {
            "mybool": "string",
        }

        with self.assertRaises(BadRequest) as expect:
            validate(json.dumps(data))

        assert_that(str(expect.exception), equal_to("Expected \"bool\" type for key mybool, got \"unicode\""))

    def test_not_json(self):
        validate = is_dict_with()

        with self.assertRaises(BadRequest) as expect:
            validate("what")

        assert_that(str(expect.exception), equal_to("Malformed JSON request"))
