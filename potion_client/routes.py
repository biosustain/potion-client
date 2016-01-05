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

from . import utils
from . import data_types
from .exceptions import OneOfException
from .constants import *

from json import dumps, loads
from functools import partial
from six.moves.urllib.parse import urlparse

import six
import string
import requests
import logging


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


_string_formatter = string.Formatter()

NoneType = type(None)


class DynamicElement(object):

    def __init__(self, link):
        assert isinstance(link, (Link, NoneType)), "Invalid link type (%s) for proxy" % type(link)
        self._link = link

    @property
    def return_type(self):
        raise NotImplementedError

    def _resolve(self, *args, **kwargs):
        pass

    @property
    def __doc__(self):
        return self._link.__doc__


class LinkProxy(DynamicElement):
    """
    A representation of a Link. It is used to manipulate the link context: binding and kwargs.
    """
    def __init__(self, link=None, binding=None, attributes=None, required=None, **kwargs):
        super(LinkProxy, self).__init__(link)
        self._kwargs = kwargs
        self._binding = binding
        self._attributes = attributes or {}
        self._required = required or []

    def serialize_attribute_value(self, key, value):
        if key in self._attributes:
            return self._attributes[key].serialize(value, required=key in self._required)
        return value

    def handler(self, res):
        return res.json()

    def bind(self, instance):
        return self.return_type(link=self._link, binding=instance)

    @property
    def return_type(self):
        if self._link.return_type is list:
            return CollectionLinkProxy
        elif self._link.return_type is NoneType:
            return VoidLinkProxy

        return ObjectLinkProxy

    def __get__(self, instance, owner):
        return self.bind(instance or owner)

    def __repr__(self):
        return "Proxy %s '%s' %s" % (self._link.method, self._link.route.path, self._kwargs)

    def _parse_schema(self):
        if PROPERTIES in self._link.schema:
            properties = self._link.schema[PROPERTIES]
            for prop in properties.keys():
                self._attributes[prop] = Attribute(properties[prop])
                setattr(self, utils.to_snake_case(prop), self._proxy(prop))
        self._required = self._link.schema.get(REQUIRED, [])

    def _parse_kwarg(self, key, value):
        if key in self._attributes:
            self._kwargs[key] = self._attributes[key].serialize(value, required=key in self._required)

    def _proxy(self, prop):

        def new_proxy(*args, **kwargs):
            new_kwargs = self._kwargs
            if len(args) > 0:
                assert len(kwargs) == 0, "Setting args and kwargs is not supported"
                if len(args) == 1:
                    val = args[0]
                else:
                    val = args
            else:
                val = kwargs
            attr = self._attributes.get(prop, None)
            if attr is not None:
                val = attr.serialize(val, required=prop in self._required)
            new_kwargs[prop] = val

            proxy = self.return_type(link=self._link, binding=self._binding, attributes=self._attributes, **new_kwargs)
            return proxy

        return new_proxy

    def _resolve(self, *args, **kwargs):
        new_kwargs = self._kwargs
        new_kwargs.update(kwargs)
        return self._link(*args, handler=self.handler, binding=self._binding, **new_kwargs)


class BoundedLinkProxy(LinkProxy):
    """
    A representation of a Link. It is used to manipulate the link context: binding and kwargs.
    The bounded link proxy requires a binding other then None.
    """
    def __init__(self, **kwargs):
        assert kwargs.get("binding", None) is not None
        super(BoundedLinkProxy, self).__init__(**kwargs)
        self._parse_schema()

    def __call__(self, *args, **kwargs):
        return self._resolve(*args, **kwargs)


class VoidLinkProxy(BoundedLinkProxy):
    """
    A representation of a Link. It requires a binding other then none. When resolved, it return always None.
    """
    def handler(self, res):
        return None

    @property
    def return_type(self):
        return NoneType


class CollectionLinkProxy(BoundedLinkProxy):
    """
    A representation of a Link. It requires a binding other then none.
    When resolved returns a collection. The collection as automatic pagination when supported.
    """

    def __init__(self, links=None, **kwargs):
        super(CollectionLinkProxy, self).__init__(**kwargs)
        self._collection = None
        self._total = 0
        self._links = links or {}

    def handler(self, res):
        try:
            self._total = int(res.headers["X-Total-Count"])
            res.links.pop("self", None)
            [self._create_link(name, link) for name, link in res.links.items()]
        except KeyError:
            self._total = len(res.json())

        return res.json()

    def _create_link(self, name, link):
        if not isinstance(link, LinkProxy):
            url = urlparse(link[URL])
            new_kwargs = self._kwargs

            for key, value in utils.params_to_dictionary(url.query).items():
                new_kwargs[key] = self.serialize_attribute_value(key, value)
            link = CollectionLinkProxy(link=self._link, binding=self._binding, **new_kwargs)
        setattr(self, name, link)
        self._links[name] = link

    def __iter__(self):
        return ListLinkIterator(self)

    @property
    def slice_size(self):
        if self._collection is None:
            self._collection = self._resolve()

        return len(self._collection)

    def __len__(self):
        if self._collection is None:
            self._collection = self._resolve()
        return self._total

    def __getitem__(self, index):
        if self._collection is None:
            self._collection = self._resolve()

        if index > self._total:
            per_page = self._kwargs['per_page']
            page = index/per_page
            kwargs = self._kwargs
            kwargs['page'] = page
            link = CollectionLinkProxy(link=self._link, binding=self._binding, **kwargs)
            return link[index-page*per_page]
        try:
            item = self._collection[index]
            if isinstance(item, dict):
                if URI in item:
                    return utils.evaluate_ref(self._collection[index][URI],
                                              self._binding.client,
                                              self._collection[index])
                elif REF in item:
                    return utils.evaluate_ref(self._collection[index][REF],
                                              self._binding.client)

            return item

        except IndexError:
            raise IndexError(index)

    def __call__(self, *args, **kwargs):
        new_kwargs = {}
        new_kwargs.update(self._kwargs)
        new_kwargs.update(kwargs)
        return CollectionLinkProxy(link=self._link, binding=self._binding, **new_kwargs)

    def __repr__(self):
        if self._collection is None:
            self._collection = self._resolve()
        if len(self) > 0:
            return "Collection [\n" + "\n,".join([repr(self[i]) for i, v in enumerate(self._collection)]) + "\n]"
        else:
            return "Collection [<Empty>]"

    def __eq__(self, other):
        equal = True
        if isinstance(other, list):
            for i, v in enumerate(other):
                equal = equal and self[i] == v

        elif isinstance(other, CollectionLinkProxy):
            equal = all([k in other._kwargs for k in self._kwargs]) and (k in self._kwargs for k in other._kwargs)
            if equal:
                for k, v in six.iteritems(self._kwargs):
                    equal = equal and v == other._kwargs[k]

        return equal


class ListLinkIterator(six.Iterator):

    def __init__(self, list_link):
        if hasattr(list_link, 'first'):
            self._slice_link = list_link.first
        else:
            self._slice_link = list_link

        self.pointer = 0
        self.total = len(self._slice_link)

    def __next__(self):
        if self.pointer >= self._slice_link.slice_size:
            if hasattr(self._slice_link, 'next'):
                self._slice_link = self._slice_link.next
                self.pointer = 0
            else:
                raise StopIteration

        ret = self._slice_link[self.pointer]
        self.pointer += 1
        return ret


class ObjectLinkProxy(BoundedLinkProxy):
    """
    A representation of a Link. It requires a binding other then none. When resolved, it returns an object as response.
    """

    def __init__(self, **kwargs):
        binding = kwargs["binding"]
        assert isinstance(binding, (Resource, type(Resource))), "Invalid link type (%s) for object" % type(binding)
        super(ObjectLinkProxy, self).__init__(**kwargs)

    def __call__(self, *args, **kwargs):
        return self._resolve(*args, **kwargs)


class Route(object):
    def __init__(self, path):
        self.default = None
        self.path = path
        self.keys = utils.extract_keys(path)

    @property
    def is_instance(self):
        return len(self.keys) > 0

    def extract_keys(self, resource):
        object_values = dict([(key, getattr(resource, key, None)) for key in self.keys])
        for key, val in object_values.items():
            if val is None:
                object_values[key] = ""
        return object_values


class Link(object):
    def __init__(self, route, method=GET, schema=None, target_schema=None, requests_kwargs=None, docstring=None):
        self.route = route
        self.method = method
        self.schema = schema
        self.target_schema = target_schema
        self.request_kwargs = requests_kwargs
        self.__doc__ = docstring
        self._serializer = {}

    @property
    def return_type(self):
        if TYPE in self.target_schema:
            return utils.type_for(self.target_schema[TYPE])[0]
        elif REF in self.target_schema:
            if self.target_schema[REF] == "#":
                return object
        else:
            return NoneType

    @property
    def input_types(self):
        if TYPE in self.schema:
            return utils.type_for(self.schema[TYPE])
        elif REF in self.schema:
            if self.schema[REF] == "#":
                return [object]
        else:
            return [NoneType]

    def __call__(self, *args, **kwargs):
        binding = kwargs.pop('binding', None)
        handler = kwargs.pop('handler', None)
        if REF in self.schema and self.schema[REF] == "#":
            self.schema = binding._schema
        if REF in self.target_schema and self.target_schema[REF] == "#":
            self.target_schema = binding._schema
        url = self.generate_url(binding, self.route)
        logger.debug("METHOD: %s" % self.method)
        logger.debug("URL: %s" % url)
        params = utils.dictionary_to_params(kwargs)
        logger.debug("PARAMS: %s" % params)
        args = self._process_args(args)
        data = loads(dumps(args, cls=utils.JSONEncoder))
        logger.debug("DATA: %s" % data)
        res = requests.request(self.method, url=url, json=data, params=params, **self.request_kwargs)
        utils.validate_response_status(res)
        return handler(res)

    def generate_url(self, binding, route):
        base_url = binding.client.base_url
        url = "{base}{path}".format(base=base_url, path=route.path)
        if isinstance(binding, Resource):
            url = url.format(**{k: getattr(binding, str(k)) for k in self.route.keys})
        if url.endswith("/"):
            return url[0:-1]
        return url

    def _process_args(self, args):
        if list not in self.input_types:
            if len(args) > 0:
                return args[0]
            elif len(args) == 0:
                return None
        else:
            return list(args)

    def __repr__(self):
        return "[Link %s '%s']" % (self.method, self.route.path)


class Attribute(object):
    def __init__(self, definition):
        self.read_only = definition.get(READ_ONLY, False)
        self.additional_properties = definition.get(ADDITIONAL_PROPERTIES, False)

        self.__doc__ = definition.get(DOC, None)
        self.definition = definition

        self._attributes = {}
        self._required = definition.get(REQUIRED, [])
        self._parse_definition()

    def _parse_definition(self):
        if PROPERTIES in self.definition:
            for name, prop in self.definition[PROPERTIES].items():
                if name in [REF, URI]:
                    self._required.append(name)
                self._attributes[name] = Attribute(prop)

        elif ITEMS in self.definition:
            self.definition = self.definition[ITEMS]
            self.__class__ = Items
            self._parse_definition()
        elif ONE_OF in self.definition:
            self.definition = self.definition[ONE_OF]
            self.__class__ = OneOf
            self._parse_definition()
        elif ANY_OF in self.definition:
            self.definition = self.definition[ANY_OF]
            self.__class__ = AnyOf
            self._parse_definition()
        elif TYPE in self.definition and utils.same_values_in(self.definition[TYPE], ALL_TYPES):
            self.__class__ = AnyObject
            self._parse_definition()
        elif isinstance(self.additional_properties, dict):
            self.__class__ = AttributeMapped
            self._parse_definition()

    @property
    def types(self):
        return utils.type_for(self.definition.get(TYPE, "object"))

    def valid_type(self, obj):
        if isinstance(obj, Resource) and dict in self.types:
            return True
        elif isinstance(obj, tuple(self.types)):
            return True
        else:
            return False

    def serialize(self, obj, valid=True, required=False):
        if obj is None:
            value = self.empty_value if required else None
        elif dict in self.types:
            value = {}
            if self.additional_properties:
                iterator = obj.keys()
            else:
                iterator = self._attributes.keys()
            for key in iterator:
                if key.startswith("$"):
                    try:
                        val = data_types.for_key(key).serialize(obj)
                    except NotImplementedError:
                        val = obj.get(key, None)
                else:
                    val = obj.get(key, None)
                    if key in self._attributes:
                        val = self._attributes[key].serialize(val, required=key in self._required)

                if val is not None:
                    value[key] = val

        else:
            value = self.types[0](obj)

        if value is not None and not required and valid:
            utils.validate(value, self.definition)
        return value

    def resolve(self, obj, client):
        if obj is None:
            return self.empty_value

        if PROPERTIES in self.definition:
            key = list(self.definition[PROPERTIES].keys())[0]
            obj = data_types.for_key(key).resolve(obj, client)

        return obj

    @property
    def empty_value(self):
        if self.read_only or NoneType in self.types:
            return None
        elif dict in self.types:
            return {}
        else:
            return self.definition.get(DEFAULT, None)

    def __repr__(self):
        return "Attribute\n" +\
               "\t%s\n" % self.types + \
               "\t" + "\n\t".join(["%s=%s" % (key, str(attr.__class__) + "[R]" if key in self._required else "")
                                   for key, attr in six.iteritems(self._attributes)])


class AnyOf(Attribute):
    def __init__(self, definitions):
        self.definition = definitions
        super(AnyOf, self).__init__({})

    def _parse_definition(self):
        self._attributes = [Attribute(definition) for definition in self.definition]

    def resolve(self, obj, client):
        errors = []
        for attr in self._attributes:
            try:
                return attr.resolve(obj, client)
            except Exception as e:
                errors.append(e)

    def serialize(self, obj, valid=True, required=True):
        if obj is None:
            return None

        errors = []
        for attr in self._attributes:
            try:
                if attr.valid_type(obj):
                    return attr.serialize(obj, valid, required)
                else:
                    raise AssertionError("Invalid type %s for %s" % (type(obj), self.types))
            except Exception as e:
                errors.append(e)

        return None

    @property
    def types(self):
        seen = set()
        all_types = [t for attr in self._attributes for t in attr.types]
        return [x for x in all_types if x not in seen and not seen.add(x)]

    def __repr__(self):
        return "AnyOf\n" + \
               "\t" + "\n\t".join(["%s %s" % (str(attr.__class__.__name__), attr.types) for attr in self._attributes])


class OneOf(AnyOf):
    def serialize(self, obj, valid=True, required=False):
        if obj is None:
            return None

        errors = []

        for attr in self._attributes:
            try:
                if attr.valid_type(obj):
                    return attr.serialize(obj, valid, required)
                else:
                    raise AssertionError("Invalid type %s for %s" % (type(obj), self.types))
            except Exception as e:
                errors.append(e)
        if required:
            raise OneOfException(errors)

    def __repr__(self):
        return "OneOf\n" + \
               "\t" + "\n\t".join(["%s %s" % (str(attr.__class__.__name__), attr.types) for attr in self._attributes])


class AnyObject(Attribute):

    def _parse_definition(self):
        pass

    def serialize(self, obj, valid=True, required=False):
        utils.validate_schema(self.definition, obj)

        return obj

    def resolve(self, obj, client):
        return obj


class AttributeMapped(Attribute):

    def _parse_definition(self):
            self._value_attribute = Attribute(self.additional_properties)

    def serialize(self, obj, valid=True, required=False):
        if obj is None:
            ret = self.empty_value
        else:
            ret = obj

        utils.validate_schema(self.definition, ret.to_json)

        return ret

    def resolve(self, obj, client):
        ret = self.empty_value
        if obj is not None:
            if isinstance(obj, dict):
                for key in obj.keys():
                    ret[key] = self._value_attribute.resolve(obj[key], client)
            elif isinstance(obj, MappedAttributeDict):
                ret = obj
        return ret

    @property
    def empty_value(self):
        return MappedAttributeDict(self._value_attribute)


class Items(Attribute):
    def __init__(self, *args, **kwargs):
        super(Items, self).__init__(*args, **kwargs)

    def serialize(self, iterable, valid=True, required=False):
        if iterable is None and required:
            return []

        assert isinstance(iterable, list), "Items expects list"
        return[super(Items, self).serialize(element, self.definition, required) for element in iterable]

    @property
    def empty_value(self):
        if NoneType in self.types:
            return None
        else:
            return []

    def resolve(self, iterable, client):
        if list is None:
            return self.empty_value

        return[super(Items, self).resolve(element, client) for element in iterable]


class MappedAttributeDict(object):
    def __init__(self, attribute):
        assert isinstance(attribute, Attribute)
        self._raw = dict()
        self._resolved = dict()
        self.attribute = attribute

    def __setitem__(self, key, value):
        self._raw[key] = self.attribute.serialize(value)
        self._resolved[key] = value

    def __getitem__(self, key):
        try:
            return self._resolved[key]
        except KeyError:
            raise KeyError(key)

    def keys(self):
        return self._raw.keys()

    @property
    def to_json(self):
        return self._raw

    def __repr__(self):
        return "AttributeMappedDict(%s)" % self._raw

    def __eq__(self, other):
        if isinstance(other, MappedAttributeDict):
            return self._raw == other._raw and self._resolved == other._resolved
        elif isinstance(other, dict):
            return self._resolved == other
        else:
            return False


class Resource(object):
    client = None
    _schema = None
    _instance_links = None
    _self_route = None
    _attributes = None
    _required = None

    def __init__(self, oid=None, instance=None, **kwargs):
        self._create_proxies()
        self._id = oid
        self._instance = instance
        if oid is None and instance is None:  # make a new object
            self._instance = {}

        for key, value in kwargs.items():
            try:
                setattr(self, key, value)
            except KeyError:
                pass

    def _create_proxies(self):
        for name, link in self._instance_links.items():
            setattr(self, name, LinkProxy(link=link).bind(self))

    @property
    def valid_instance(self):
        instance = {}

        for key in self._attributes.keys():

            attr = self._attributes[key]
            value = self._instance.get(key, attr.empty_value)
            if not attr.read_only:
                instance[key] = value
        return instance

    @property
    def instance(self):
        if self._instance is None:
            self._ensure_instance()
        return self._instance

    @property
    def properties(self):
        return self._schema.get(PROPERTIES, {})

    @classmethod
    def _get_property(cls, name, self):
        attr = cls._attributes[name]
        raw = self.instance.get(name, None)
        if raw is None:
            raw = attr.empty_value
            self._instance[name] = raw
        return attr.resolve(raw, self.client)

    @classmethod
    def _set_property(cls, key, self, value):
        serialized = cls._attributes[key].serialize(value, required=key in self._required)
        self.instance[key] = serialized

    @classmethod
    def _del_property(cls, name, self):
        self.instance.pop(name, None)

    def __getattr__(self, key):
        if key.startswith("$"):
            return self.instance[key]
        else:
            getattr(super(Resource, self), key, self)

    def __getitem__(self, key):
        return self.instance[key]

    def _ensure_instance(self):
        if self._instance is None:
            self._instance = self.self()

    def save(self):
        if self.id is None:
            assert isinstance(self.create, ObjectLinkProxy), "Invalid proxy type %s" % type(self.create)
            self._update(self.create(self))
        else:
            assert isinstance(self.update, ObjectLinkProxy), "Invalid proxy type %s" % type(self.update)
            self._update(self.update(self))

    def _update(self, raw_dict):
        for key, value in raw_dict.items():
            if key in self._attributes and isinstance(self._attributes[key], AttributeMapped):
                value = self._attributes[key].resolve(value, self.client)
            self._instance[key] = value

    def refresh(self):
        self._update(self.self())

    @property
    def id(self):
        if self._id is None:
            if self._instance and (URI in self._instance):
                self._id = utils.parse_uri(self._instance[URI])[-1]
        return self._id

    def __dir__(self):
        return super(Resource, self).__dir__() + list(self._schema[PROPERTIES].keys())

    def __repr__(self):
        self._ensure_instance()
        return "%s<id=%s\n\t" % (self.__class__.__name__, self.id) + \
            "\n\t".join(["%s=%s" % (k, getattr(self, k)) for k in self._instance]) + ">"

    def __eq__(self, other):
        if self.uri and other.uri:
            return self.uri == other.uri
        else:
            super(Resource, self).__eq__(other)

    to_json = valid_instance

    @classmethod
    def factory(cls, docstring, name, schema, requests_kwargs, client):
        class_name = utils.to_camel_case(name)

        resource = type(str(class_name), (cls, ), {'__doc__': docstring})
        resource._schema = schema
        resource.client = client
        resource._instance_links = {}
        resource._attributes = {}
        resource._required = []
        routes = {}

        for link_desc in schema[LINKS]:
            if link_desc[HREF] in routes:
                route = routes[link_desc[HREF]]
            else:
                route = Route(link_desc[HREF])
                routes[link_desc[HREF]] = route

            link = Link(route, method=link_desc[METHOD], schema=link_desc.get(SCHEMA, {}),
                        target_schema=link_desc.get(TARGET_SCHEMA, {}), requests_kwargs=requests_kwargs,
                        docstring=link_desc.get(DOC, None))

            rel = utils.to_snake_case(link_desc[REL])
            if route.is_instance:
                resource._instance_links[rel] = link
            else:
                setattr(resource, rel, LinkProxy(link))

        for name, prop in schema[PROPERTIES].items():
            attr = Attribute(prop)
            resource._attributes[name] = attr
            property_name = name
            if name.startswith("$"):
                property_name = name.replace("$", "")
            if attr.read_only:
                setattr(resource, property_name, property(fget=partial(resource._get_property, name), doc=attr.__doc__))
            else:
                setattr(resource, property_name, property(fget=partial(resource._get_property, name),
                                                          fset=partial(resource._set_property, name),
                                                          fdel=partial(resource._del_property, name),
                                                          doc=attr.__doc__))
        resource._required = schema.get(REQUIRED, [])

        return resource