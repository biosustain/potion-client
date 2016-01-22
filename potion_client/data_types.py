# Copyright 2015 Novo Nordisk Foundation Center for Biosustainability, DTU.

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

# http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import calendar
from datetime import datetime
from potion_client import utils

_handlers = {}


def for_key(key):
    return _handlers.get(key, DataType)


class DataType(object):
    @classmethod
    def serialize(cls, obj):
        return obj

    @classmethod
    def resolve(cls, obj, client):
        return obj


class Reference(DataType):
    @classmethod
    def serialize(cls, obj):
        return obj.uri

    @classmethod
    def resolve(cls, obj, client):
        return utils.evaluate_ref(obj["$ref"], client)


_handlers["$ref"] = Reference


class Date(DataType):
    @classmethod
    def serialize(cls, obj):
        return int(calendar.timegm(obj.utctimetuple()) * 1000)

    @classmethod
    def resolve(cls, obj, client):
        return datetime.fromtimestamp(obj["$date"] / 1000, utils.timezone.utc)


_handlers["$date"] = Date
