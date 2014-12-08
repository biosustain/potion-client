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
import jsonschema
import requests
from .constants import *
from potion_client.exceptions import NotFoundException
from potion_client.routes import Resource


class Client(object):
    def __init__(self, base_url=None, schema_path="/schema", **requests_kwargs):
        self._url_identifiers = {}
        self.base_url = base_url
        self._schema_path = schema_path


        response = requests.get(base_url+schema_path, **requests_kwargs)
        if response.status_code == 404:
            raise NotFoundException()

        self._schema = json.loads(response.text)
        self._schema_cache = {}
        self._schema_resolver = jsonschema.RefResolver(base_uri=base_url,
                                                       referrer=self._schema,
                                                       cache_remote=True,
                                                       store=self._schema_cache)

        for name, desc in self._schema[PROPERTIES].items():
            class_schema_url = self.base_url + desc[REF]
            response = requests.get(class_schema_url, **requests_kwargs)
            class_schema = json.loads(response.text)
            resource = Resource.factory(desc.get(DOC, ""), name, class_schema, requests_kwargs)
            resource.client = self
            setattr(self, resource.__name__, resource)
            self._url_identifiers[desc[REF]] = resource

    @property
    def pagination_url(self):
        return self._schema_path + "#" + "/definitions/" + PAGINATION

    def resolve(self, path):
        if path in self._url_identifiers:
            return self._url_identifiers[path]._schema

        root, target = path.split("#")
        if len(root) == 0:
            schema = self._schema
        elif root == self._schema_path:
            schema = self._schema
        else:
            klass = self._url_identifiers[root+"#"]
            schema = klass._schema
        splt = target.split("/")
        section = splt[-2]
        fragment = splt[-1]

        return self._schema_resolver.resolve_fragment(schema[section], fragment)