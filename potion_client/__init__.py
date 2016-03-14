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
import requests
from .constants import *
from .exceptions import NotFoundException
from .routes import Resource
from . import utils


class Client(object):
    def __init__(self, base_url="http://localhost", schema_path="/schema", api_prefix = "", **requests_kwargs):
        self._resources = {}
        self.base_url = base_url
        self.api_prefix = api_prefix
        self._schema_cache = {}

        response = requests.get(base_url + api_prefix + schema_path, **requests_kwargs)
        utils.validate_response_status(response)
        self._schema = response.json()
        self._schema_cache[schema_path + "#"] = self._schema

        for name, desc in self._schema[PROPERTIES].items():
            response = requests.get(self.base_url + desc[REF], **requests_kwargs)
            utils.validate_response_status(response)
            class_schema = response.json()
            resource = Resource.factory(desc.get(DOC, ""), name, class_schema, requests_kwargs, self)
            setattr(self, resource.__name__, resource)
            self._resources[name] = resource
            self._schema_cache[desc[REF]] = class_schema
            self._schema[PROPERTIES][name] = class_schema

    def resource(self, name):
        return self._resources[name]

    def resolve(self, ref, target_schema=None):
        if ref in self._schema_cache:
            return self._schema_cache[ref]
        if ref == "#":
            return target_schema or self._schema

        document, path = ref.split("#")
        if len(document) == 0:
            if target_schema:
                schema = target_schema
            else:
                schema = self._schema
        else:
            schema = self._schema_cache[document + "#"]

        null, key, fragment = path.split("/")
        if fragment in schema[key]:
            return schema[key][fragment]
        else:
            return None
