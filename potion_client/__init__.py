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
from potion_client.exceptions import NotFoundException
from potion_client.routes import Resource


class Client(object):
    def __init__(self, base_url="http://localhost", schema_path="/schema", **requests_kwargs):
        self._resources = {}
        self.base_url = base_url
        self._schema_cache = {}

        response = requests.get(base_url+schema_path, **requests_kwargs)
        if response.status_code == 404:
            raise NotFoundException()
        self._schema = response.json()
        self._schema_cache[schema_path+"#"] = self._schema

        for name, desc in self._schema[PROPERTIES].items():
            class_schema_url = self.base_url + desc[REF]
            response = requests.get(class_schema_url, **requests_kwargs)
            class_schema = response.json()
            resource = Resource.factory(desc.get(DOC, ""), name, class_schema, requests_kwargs, self)
            setattr(self, resource.__name__, resource)
            self._resources[name] = resource
            self._schema_cache[desc[REF]] = class_schema
            self._schema[PROPERTIES][name] = class_schema
            for prop in class_schema[PROPERTIES].keys():
                p = class_schema[PROPERTIES][prop]
                if REF in p:
                    class_schema[PROPERTIES][prop] = self.resolve(p[REF], class_schema)

    def resource(self, name):
        return self._resources[name]

    def resolve_element(self, obj):
        if isinstance(obj, dict):
            if URI in obj:
                path = obj[URI].split("/")
                id, klass = path[-1], path[-2]
                return self._resources[klass](id, instance=obj)
        elif isinstance(obj, str):
            if obj.startswith("/"):
                path = obj[URI].split("/")
                id, klass = path[-1], path[-2]
                return self._resources[klass](id)

        return obj

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
            schema = self._schema_cache[document+"#"]

        null, key, fragment = path.split("/")
        if fragment in schema[key]:
            return schema[key][fragment]
        else:
            return None
