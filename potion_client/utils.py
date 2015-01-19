# Copyright 2014 Novo Nordisk Foundation Center for Biosustainability, DTU.

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

# http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import string
from jsonschema import validate
from potion_client.constants import *

def camelize(a_string):
    assert isinstance(a_string, str)
    return "".join([part.capitalize() for part in a_string.replace("-", "_").split("_")])


def params_to_dict(params_string):
    d = {}
    for part in params_string.split("&"):
        key, value = part.split("=")
        if not key not in d:
            d[key] = []
        d[key].append(value)

    for key in d.keys():
        if len(d[key]) == 1:
            d[key] = d[key][0]

    return d


def dictionary_to_params(d):
    s = []
    for key, value in d.items():
        s.append("%s=%s" % (key, value))

    return "&".join(s)


def extract_keys(a_string, formatter=string.Formatter()):
    format_iterator = formatter.parse(a_string)
    return [t[1] for t in format_iterator if not t[1] is None]


def validate_schema(schema, obj):
    if schema is not None:
        validate(obj, schema)
    return obj


def make_valid_value_list(values, definition):
    return values
    for value in values:
        pass


def make_valid_value_dict(dictionary, definition):
    return dictionary
    pass


def make_valid_value_object(obj, definition):
    if PROPERTIES in definition:
        return_obj = {}
        for key in definition[PROPERTIES].keys():
            return_obj[key] = getattr(obj, definition[PROPERTIES][key][FORMAT])
        return return_obj
    else:
        return obj


def make_valid_value(value, definition):
    if isinstance(value, list):
        return make_valid_value_list(value, definition)
    elif isinstance(value, dict):
        return make_valid_value_dict(value, definition)
    elif isinstance(value, object):
        return make_valid_value_object(value, definition)
    else:
        return value


def type_for(json_type):
    return TYPES[json_type]
