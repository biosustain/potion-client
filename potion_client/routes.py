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
from urllib.parse import urlparse
from jsonschema import validate
import requests
from potion_client import utils
from .constants import *
import logging
from potion_client.exceptions import HTTP_EXCEPTIONS, HTTP_MESSAGES

logger = logging.getLogger(__name__)
logger.level = logging.DEBUG


_string_formatter = string.Formatter()


class AttributeMapper(object):
    def __init__(self, definition, required=False, read_only=False):
        self.definition = definition
        self.required = required
        self.read_only = read_only

    @property
    def type(self):
        if ITEMS in self.definition:
            return list
        return utils.type_for(self.definition[TYPE])[0]

    def serialize(self, obj, valid=True):
        value = utils.convert_value(obj, self.definition)
        if valid:
            validate(value, self.definition)
        return value

    def resolve(self, obj, client, override_definition=None):
        definition = override_definition or self.definition
        if obj is None:
            return obj
        if ITEMS in definition:
            return [self.resolve(item, client, self.definition[ITEMS]) for item in obj]
        elif PROPERTIES in definition:
            key = list(definition[PROPERTIES].keys())[0]
            resolver = client.resolvers[key]
            obj = resolver.resolve(obj[key], client)

        return obj

    @property
    def empty_value(self):
        if self.read_only:
            return None
        return self.serialize(None, valid=False)


class DynamicElement(object):

    def __init__(self, link):
        assert isinstance(link, (Link, type(None))), "Invalid link type (%s) for proxy" % type(link)
        self._link = link

    @property
    def return_type(self):
        raise NotImplementedError

    def _resolve(self):
        pass


class LinkProxy(DynamicElement):

    def __init__(self, link=None, binding=None, attributes={}, **kwargs):
        super(LinkProxy, self).__init__(link)
        self._kwargs = kwargs
        self._binding = binding
        self._attributes = attributes

    def serialize_attribute_value(self, key, value):
        if key in self._attributes:
            return self._attributes[key].serialize(value)
        return value

    def handler(self, res: requests.Response):
        raise NotImplementedError

    def bind(self, instance):
        return self.return_type(link=self._link, binding=instance)

    @property
    def return_type(self):
        if self._link.return_type is list:
            return ListLinkProxy
        elif self._link.return_type is object:
            return InstanceLinkProxy
        elif self._link.return_type is dict:
            return InstanceLinkProxy
        else:
            return VoidLinkProxy

    def __get__(self, instance, owner):
        return self.bind(instance or owner)

    def __repr__(self):
        return "[Proxy %s '%s'] %s" % (self._link.method, self._link.route.path, self._kwargs)

    def _parse_schema(self):
        if PROPERTIES in self._link.schema:
            properties = self._link.schema[PROPERTIES]
            for prop in properties.keys():
                self._attributes[prop] = AttributeMapper(properties[prop], False, False)
                setattr(self, prop, self._proxy(prop))

    def _proxy(self, prop):

        def new_proxy(*args, **kwargs):
            new_kwargs = self._kwargs
            if len(args) > 0:
                assert len(kwargs) == 0, "Setting args and kwargs is not supported"
                if len(args) == 1:
                    new_kwargs[prop] = args[0]
                else:
                    new_kwargs[prop] = args
            else:
                new_kwargs[prop] = kwargs
            proxy = self.return_type(link=self._link, binding=self._binding, attributes=self._attributes, **new_kwargs)
            return proxy

        return new_proxy

    def _resolve(self, *args, **kwargs):
        new_kwargs = self._kwargs
        new_kwargs.update(kwargs)
        self._link(*args, handler=self.handler, binding=self._binding, **new_kwargs)


class BoundedLinkProxy(LinkProxy):
    def __init__(self, **kwargs):
        super(BoundedLinkProxy, self).__init__(**kwargs)
        self._parse_schema()

    def __repr__(self):
        return "[BoundedProxy %s '%s' %s] %s" % (self._link.method, self._link.route.path, self._binding, self._kwargs)


class VoidLinkProxy(BoundedLinkProxy):
    def handler(self, res: requests.Response):
        return None

    def __call__(self, *args, **kwargs):
        self._resolve(*args, **kwargs)

    def __repr__(self):
        return "[BoundedProxy %s '%s' %s] %s => None" % (self._link.method,
                                                      self._link.route.path,
                                                      self._binding,
                                                      self._kwargs)


class ListLinkProxy(BoundedLinkProxy):
    def __init__(self, links={}, **kwargs):
        super(ListLinkProxy, self).__init__(**kwargs)
        self._collection = None
        self._total = 0
        self._links = links

    def handler(self, res: requests.Response):
        self._collection = res.json()
        res.links.pop("self")
        [self._create_link(name, link) for name, link in res.links.items()]
        self._total = int(res.headers["X-Total-Count"])

    def _create_link(self, name, link):
        if not isinstance(link, LinkProxy):
            url = urlparse(link[URL])
            new_kwargs = self._kwargs
            new_kwargs.update(utils.params_to_dictionary(url.query))

            for key, value in new_kwargs.items():
                new_kwargs[key] = self.serialize_attribute_value(key, value)
            link = ListLinkProxy(link=self._link, binding=self._binding, **new_kwargs)
        setattr(self, name, link)
        self._links[name] = link

    def __iter__(self):
        return ListLinkIterator(self)

    @property
    def slice_size(self):
        if self._collection is None:
            self._resolve()
        return len(self._collection)

    def __len__(self):
        if self._collection is None:
            self._resolve()
        return self._total

    def __getitem__(self, index: int):
        if self._collection is None:
            self._resolve()

        if index > self._total:
            per_page = self._kwargs['per_page']
            page = index/per_page
            kwargs = self._kwargs
            kwargs['page'] = page
            link = ListLinkIterator(link=self._link, binding=self._binding, **kwargs)
            return link[index-page*per_page]

        return utils.evaluate_ref(self._collection[index][URI], self._binding.client, self._collection[index])

    def __repr__(self):
        return "[BoundedProxy %s '%s' %s] %s => Collection" % (self._link.method,
                                                            self._link.route.path,
                                                            self._binding,
                                                            self._kwargs)


class ListLinkIterator(object):

    def __init__(self, list_link: ListLinkProxy):
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


class InstanceLinkProxy(BoundedLinkProxy):

    def get_handler(self, resolve):
        if resolve:
            return lambda res: self._binding.client.resolve_element(res.json())
        else:
            return lambda res: res.json()

    def __init__(self, **kwargs):
        binding = kwargs["binding"]
        assert isinstance(binding, (Resource, type(Resource))), "Invalid link type (%s) for object" % type(binding)
        super(InstanceLinkProxy, self).__init__(**kwargs)

    def __repr__(self):
        return "[BoundedProxy %s '%s' %s] %s => object" % (self._link.method,
                                                           self._link.route.path,
                                                           self._binding,
                                                           self._kwargs)

    def __call__(self, *args, **kwargs):
        return self._resolve(*args, **kwargs)

    def _resolve(self, *args, **kwargs):
        resolve = kwargs.pop("resolve", True)
        new_kwargs = self._kwargs
        new_kwargs.update(kwargs)
        return self._link(*args, handler=self.get_handler(resolve), binding=self._binding, **new_kwargs)


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
    def __init__(self, route, method=GET, schema=None, target_schema=None, requests_kwargs=None):
        self.route = route
        self.method = method
        self.schema = schema
        self.target_schema = target_schema
        self.request_kwargs = requests_kwargs

    @property
    def return_type(self) -> type:
        if TYPE in self.target_schema:
            return utils.type_for(self.target_schema[TYPE])[0]
        elif REF in self.target_schema:
            if self.target_schema[REF] == "#":
                return object
            else:
                self.target_schema = self.client.resolve(self.target_schema[REF])
                return self.return_type
        else:
            return None

    def __call__(self, *args, binding=None, handler=None, **kwargs):
        # TODO: set the proper schema for input
        url = self.generate_url(binding, self.route)
        json, params = self._process_args(binding, *args, **kwargs)
        params = utils.dictionary_to_params(params)
        res = requests.request(self.method, url=url, json=json, params=params, **self.request_kwargs)
        if res.status_code >= 400:
            code = res.status_code
            default_error = RuntimeError
            default_message = "Error: %s" % res.status_code
            raise HTTP_EXCEPTIONS.get(code, default_error)(HTTP_MESSAGES.get(code, default_message), res.text)
        return handler(res)

    def generate_url(self, binding, route):
        base_url = binding.client.base_url
        url = "{base}{path}".format(base=base_url, path=route.path)
        if isinstance(binding, Resource):
            url = url.format(**{k: getattr(binding, str(k)) for k in self.route.keys})
        if url.endswith("/"):
            return url[0:-1]
        logger.debug("Generated url: %s" % url)
        return url

    def _process_args(self, binding, *args, **kwargs):
        json, params = None, {}
        if len(args) == 1:
            args = args[0]
        if self.method in [POST, PATCH]:
            args = self._check_input(args)
            json = self._validate_in(args, binding)
        else:
            params = self._validate_in(kwargs, binding)

        return json, params

    def _check_input(self, obj):
        if isinstance(obj, Resource):
            return self._check_input(obj.instance)
        elif isinstance(obj, (list, tuple)):
            return [self._check_input(el) for el in obj]
        elif isinstance(obj, dict):
            for key, value in obj.items():
                obj[key] = self._check_input(value)
            return obj
        else:
            return obj

    def _validate_params(self, params):
        utils.validate_schema(self.schema, params)
        for param in self.schema[PROPERTIES]:
            if 'default ' in self.schema[PROPERTIES][param]:
                if param not in params:
                    params[param] = self.schema[PROPERTIES][param]['default']
        return params

    def _validate_in(self, params, binding):
        if REF in self.schema and self.schema[REF] == "#":
            self.schema = getattr(binding, "_schema")
        return utils.validate_schema(self.schema, params)

    def _validate_out(self, out, binding):
        if REF in self.schema and self.schema[REF] == "#":
            self.target_schema = getattr(binding, "_schema")
        return utils.validate_schema(self.target_schema, out)

    def __repr__(self):
        return "[Link %s '%s']" % (self.method, self.route.path)


class Resource(object):
    client = None
    _schema = None
    _instance_links = None
    _self_route = None
    _attributes = None

    def __init__(self, oid=None, instance=None):
        self._create_proxies()
        self._id = oid
        self._instance = instance
        if oid is None:  # make a new object
            self._instance = {}

    def _create_proxies(self):
        for name, link in self._instance_links.items():
            setattr(self, name, LinkProxy(link=link).bind(self))

    @property
    def instance(self):
        instance = {}

        for key in self._attributes.keys():
            attr = self._attributes[key]
            value = self._instance.get(key, attr.empty_value)
            if not attr.read_only and value is not None:
                instance[key] = value

        return instance

    @property
    def properties(self):
        return self._schema.get(PROPERTIES, {})

    def __getattr__(self, key):
        if key in self._attributes:
            self._ensure_instance()
            attr = self._attributes[key]
            item = self._instance.get(key, None)
            return attr.resolve(item, self.client)
        else:
            getattr(super(Resource, self), key, self)

    def __setattr__(self, key, value):
        assert not key.startswith("$"), "Invalid property %s" % key

        if key in self._attributes:
            attr = self._attributes[key]
            self._ensure_instance()
            self._instance[key] = attr.serialize(value)
        else:
            super(Resource, self).__setattr__(key, value)

    def _ensure_instance(self):
        if self._instance is None:
            self._instance = self.self(resolve=False)

    def save(self):
        if self.id is None:
            assert isinstance(self.create, InstanceLinkProxy), "Invalid proxy type %s" % type(self.create)
            self._instance = self.create(self, resolve=False)
        else:
            assert isinstance(self.update, InstanceLinkProxy), "Invalid proxy type %s" % type(self.create)
            self._instance = self.update(self, resolve=False)

    def refresh(self):
        self._instance = self.self(resolve=False)

    @property
    def id(self):
        if self._id is None:
            if self._instance and (URI in self._instance):
                self._id = utils.parse_uri(self._instance[URI])[-1]
        return self._id

    def __dir__(self):
        return super(Resource, self).__dir__() + list(self._schema[PROPERTIES].keys())

    @property
    def uri(self):
        self._ensure_instance()
        if URI in self._instance:
            return self._instance[URI]

    @classmethod
    def factory(cls, docstring, name, schema, requests_kwargs, client):
        class_name = utils.camelize(name)

        resource = type(class_name, (cls, ), {})
        resource.__doc__ = docstring
        resource._schema = schema
        resource.client = client
        resource._instance_links = {}
        resource._attributes = {}

        routes = {}

        for link_desc in schema[LINKS]:
            if link_desc[HREF] in routes:
                route = routes[link_desc[HREF]]
            else:
                route = Route(link_desc[HREF])
                routes[link_desc[HREF]] = route

            link = Link(route,
                        method=link_desc[METHOD],
                        schema=link_desc.get(SCHEMA, {}),
                        target_schema=link_desc.get(TARGET_SCHEMA, {}),
                        requests_kwargs=requests_kwargs)

            if route.is_instance:
                resource._instance_links[link_desc[REL]] = link
            else:
                setattr(resource, link_desc[REL], LinkProxy(link))

        for name, prop in schema[PROPERTIES].items():
            read_only = READ_ONLY in prop
            required = type(None) in utils.type_for(prop.get(TYPE, object))
            resource._attributes[name] = AttributeMapper(prop, required, read_only)

        return resource

    def __str__(self):
        return "<%s %s: %s>" % (self.__class__, getattr(self, "id"), str(self._instance))

    def __eq__(self, other):
        if self.uri and other.uri:
            return self.uri == other.uri
        else:
            super(Resource, self).__eq__(other)