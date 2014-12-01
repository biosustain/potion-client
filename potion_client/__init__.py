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
import requests
from .constants import *

#schema
from potion_client.routes import Resource




class Client(object):
    def __init__(self, host=None, **requests_kwargs):
        schema_request = requests.get(host+SCHEMA_PATH, **requests_kwargs)
        #handle http errors

        schema = json.loads(schema_request.text)
        for name, desc in schema[PROPERTIES].items():
            resource = Resource.factory(host+desc[REF], desc.get(DOC, ""), name, **requests_kwargs)
            setattr(self, resource.__name__, resource)




