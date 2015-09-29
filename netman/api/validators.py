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
import re

from netaddr import IPNetwork, AddrFormatError, IPAddress
from flask import request

from netman.api.api_utils import BadRequest, MultiContext
from netman.core.objects.access_groups import IN, OUT
from netman.core.objects.exceptions import UnknownResource, BadVlanNumber,\
    BadVlanName, BadBondNumber, BadBondLinkSpeed, MalformedSwitchSessionRequest, \
    BadVrrpGroupNumber


def resource(*validators):

    def resource_decorator(fn):
        @wraps(fn)
        def wrapper(self, **kwargs):
            with MultiContext(self, kwargs, *validators) as ctxs:
                return fn(self, *ctxs, **kwargs)

        return wrapper

    return resource_decorator


def content(validator_fn):

    def content_decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            kwargs.update(validator_fn(request.data))
            return fn(*args, **kwargs)

        return wrapper

    return content_decorator


class Vlan:
    def __init__(self, switch_api):
        self.switch_api = switch_api
        self.vlan = None

    def process(self, parameters):
        self.vlan = is_vlan_number(parameters.pop('vlan_number'))['vlan_number']

    def __enter__(self):
        return self.vlan

    def __exit__(self, *_):
        pass


class Bond:
    def __init__(self, switch_api):
        self.switch_api = switch_api
        self.bond = None

    def process(self, parameters):
        self.bond = is_bond_number(parameters.pop('bond_number'))['bond_number']

    def __enter__(self):
        return self.bond

    def __exit__(self, *_):
        pass


class IPNetworkResource:
    def __init__(self, switch_api):
        self.switch_api = switch_api
        self.ip_network = None

    def process(self, parameters):
        try:
            self.ip_network = is_ip_network(parameters.pop('ip_network'))['validated_ip_network']
        except BadRequest:
            raise BadRequest('Malformed IP, should be : x.x.x.x/xx')

    def __enter__(self):
        return self.ip_network

    def __exit__(self, *_):
        pass


class Switch:
    def __init__(self, switch_api):
        self.switch_api = switch_api
        self.is_session = False
        self.switch = None

    def process(self, parameters):
        hostname = parameters.pop('hostname')
        try:
            self.switch = self.switch_api.resolve_session(hostname)
            self.is_session = True
        except UnknownResource:
            self.switch = self.switch_api.resolve_switch(hostname)

    def __enter__(self):
        if not self.is_session:
            self.switch.connect()
        return self.switch

    def __exit__(self, *_):
        if not self.is_session:
            self.switch.disconnect()


class Session:
    def __init__(self, switch_api):
        self.switch_api = switch_api
        self.session = None

    def process(self, parameters):
        self.session = parameters.pop('session_id')
        self.switch_api.resolve_session(self.session)

    def __enter__(self):
        return self.session

    def __exit__(self, *_):
        pass


class Interface:
    def __init__(self, switch_api):
        self.switch_api = switch_api
        self.interface = None

    def process(self, parameters):
        self.interface = parameters.pop('interface_id')

    def __enter__(self):
        return self.interface

    def __exit__(self, *_):
        pass


class Resource:
    def __init__(self, switch_api):
        self.switch_api = switch_api
        self.resource = None

    def process(self, parameters):
        self.resource = parameters.pop('resource')

    def __enter__(self):
        return self.resource

    def __exit__(self, *_):
        pass


class Direction:
    def __init__(self, switch_api):
        self.switch_api = switch_api
        self.direction = None

    def process(self, parameters):
        direction = parameters.pop('direction')
        if direction.lower() == 'in':
            self.direction = IN
        elif direction.lower() == 'out':
            self.direction = OUT
        else:
            raise UnknownResource("Unknown direction : %s" % direction)

    def __enter__(self):
        return self.direction

    def __exit__(self, *_):
        pass


class VrrpGroup:
    def __init__(self, switch_api):
        self.switch_api = switch_api
        self.vrrp_group_id = None

    def process(self, parameters):
        try:
            self.vrrp_group_id = int(parameters.pop('vrrp_group_id'))
            if not 1 <= self.vrrp_group_id <= 255:
                raise BadVrrpGroupNumber()
        except (ValueError, KeyError):
            raise BadVrrpGroupNumber()

    def __enter__(self):
        return self.vrrp_group_id

    def __exit__(self, *_):
        pass


def is_session(data, **_):
    try:
        json_data = json.loads(data)
    except ValueError:
        raise BadRequest("Malformed content, should be a JSON object")

    if "hostname" not in json_data:
        raise MalformedSwitchSessionRequest()
    return {
        'hostname': json_data["hostname"]
    }


def is_vlan(data, **_):
    try:
        json_data = json.loads(data)
    except ValueError:
        raise BadRequest("Malformed content, should be a JSON object")

    if "number" not in json_data:
        raise BadVlanNumber()

    name = json_data["name"] if "name" in json_data and len(json_data["name"]) > 0 else None
    if name and " " in name:
        raise BadVlanName()

    return {
        'number': is_vlan_number(json_data["number"])['vlan_number'],
        'name': name
    }


def is_vlan_number(vlan_number, **_):
    try:
        vlan_int = int(vlan_number)
    except ValueError:
        logging.getLogger("netman.api").info("Rejected vlan content : %s" % repr(vlan_number))
        raise BadVlanNumber()

    if not 1 <= vlan_int <= 4094:
        logging.getLogger("netman.api").info("Rejected vlan number : %d" % vlan_number)
        raise BadVlanNumber()

    return {'vlan_number': vlan_int}


def is_ip_network(data, **_):
    try:
        try:
            json_addr = json.loads(data)
            ip = IPNetwork("%s/%s" % (json_addr["address"], json_addr["mask"]))
        except ValueError:
            ip = IPNetwork(data)
    except (KeyError, AddrFormatError):
        raise BadRequest('Malformed content, should be : x.x.x.x/xx or {"address": "x.x.x.x", "mask": "xx"}')

    return {'validated_ip_network': ip}


def is_vrrp_group(data, **_):
    try:
        data = json.loads(data)
    except ValueError:
        raise BadRequest("Malformed content, should be a JSON object")

    if data.get('id') is None:
        raise BadRequest("VRRP group id is mandatory")

    return dict(
        group_id=data.pop('id'),
        ips=[validate_ip_address(i) for i in data.pop('ips', [])],
        **data
    )


def is_boolean(option, **_):
    option = option.lower()
    if option not in ['true', 'false']:
        raise BadRequest('Unreadable content "%s". Should be either "true" or "false"' % option)

    return {'state': option == 'true'}


def is_access_group_name(data, **_):
    if data == "" or " " in data:
        raise BadRequest('Malformed access group name')

    return {'access_group_name': data}


def is_vrf_name(data, **_):
    if data == "" or " " in data:
        raise BadRequest('Malformed VRF name')

    return {'vrf_name': data}


def is_bond_number(bond_number, **_):
    try:
        bond_number_int = int(bond_number)
    except ValueError:
        logging.getLogger("netman.api").info("Rejected number content : %s" % repr(bond_number))
        raise BadBondNumber()

    return {'bond_number': bond_number_int}


def is_bond(data, **_):
    try:
        json_data = json.loads(data)
    except ValueError:
        raise BadRequest("Malformed content, should be a JSON object")

    if "number" not in json_data:
        raise BadBondNumber()

    return {
        'bond_number': is_bond_number(json_data["number"])['bond_number'],
    }


def is_bond_link_speed(data, **_):
    if re.match(r'^\d+[mg]$', data):
        return {'bond_link_speed': data}

    raise BadBondLinkSpeed()


def is_description(description, **_):
    return {'description': description}


def is_dict_with(**fields):
    def m(data, **_):
        try:
            result = json.loads(data)
        except ValueError:
            raise BadRequest("Malformed JSON request")
        for field, validator in fields.iteritems():
            validator(result, field)
        for field, validator in result.iteritems():
            if field not in fields:
                raise BadRequest("Unknown key: {}".format(field))
        return result

    return m


def validate_ip_address(data):
    try:
        return IPAddress(data)
    except:
        raise BadRequest("Incorrect IP Address: \"{}\", should be x.x.x.x".format(data))


def optional(sub_validator):
    def m(params, key):
        if key in params:
            sub_validator(params, key)
    return m


def is_type(obj_type):
    def m(params, key):
        if not isinstance(params[key], obj_type):
            raise BadRequest('Expected "{}" type for key {}, got "{}"'.format(obj_type.__name__, key, type(params[key]).__name__))
    return m
