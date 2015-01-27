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
import json
import string
from jsonschema import validate
from potion_client.constants import *
from potion_client.exceptions import HTTP_EXCEPTIONS, HTTP_MESSAGES


def path_for_url(url):
    if url.query is not None and len(url.query) > 0:
        path = url.path + "?" + url.query
    else:
        path = url.path

    return path


def validate_response_status(response):
    if response.status_code >= 400:
        code = response.status_code
        default_error = RuntimeError
        default_message = "Error: %s" % response.status_code
        raise HTTP_EXCEPTIONS.get(code, default_error)(HTTP_MESSAGES.get(code, default_message), response.text)


def camelize(a_string):
    assert isinstance(a_string, str)
    return "".join([part.capitalize() for part in a_string.replace("-", "_").split("_")])


def params_to_dictionary(params_string):
    d = {}
    for part in params_string.split("&"):
        key, value = part.split("=")
        if key not in d:
            d[key] = []
        d[key].append(value)

    for key in d.keys():
        if len(d[key]) == 1:
            d[key] = d[key][0]

    return d


def dictionary_to_params(d):
    s = []
    for key, value in d.items():
        s.append("%s=%s" % (key, json.dumps(value)))

    return "&".join(s)


def extract_keys(a_string, formatter=string.Formatter()):
    format_iterator = formatter.parse(a_string)
    return [t[1] for t in format_iterator if not t[1] is None]


def validate_schema(schema, obj):
    if schema is not None:
        validate(obj, schema)
    return obj


def type_for(json_type):
    if isinstance(json_type, str):
        return [TYPES[json_type]]
    else:
        return [TYPES[t] for t in json_type]


def parse_uri(uri):
    split = uri.split("/")
    resource_name, resource_id = split[-2], split[-1]
    return resource_name, resource_id


def evaluate_ref(uri, client, instance=None):
    resource_name, resource_id = parse_uri(uri)
    resource_class = client.resource(resource_name)
    return resource_class(oid=resource_id, instance=instance)