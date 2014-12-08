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

SCHEMA_PATH = "/schema"
DEFAULT_PER_PAGE = 20


#HTTP constants
GET = "GET"


#Schema Constants
PROPERTIES = "properties"
REF = "$ref"
DOC = "description"
LINKS = "links"
HREF = "href"
METHOD = "method"
REL = "rel"
SCHEMA = "schema"
DEFINITIONS = "definitions"
TARGET_SCHEMA = "targetSchema"
URI = "_uri"
TYPE = "type"
ITEMS = "items"
PAGINATION = "_pagination"
CLASS = "class"


#Expected types
TYPES = {
    "array": list,
    "object": dict
}