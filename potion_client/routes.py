import string
from jsonschema import validate
import requests
from potion_client import utils
from .constants import *
import logging
from potion_client.exceptions import NotFoundException

logger = logging.getLogger(__name__)
logger.level = logging.DEBUG


_string_formatter = string.Formatter()


class Route(object):
    def __init__(self, path, resource_class, name):
        self.path = path
        self.name = name
        self.instance = None
        self.resource_class = resource_class

    def __get__(self, instance, owner):
        if instance is None:
            self.instance = owner
            return self._get
        else:
            self.instance = instance
            return self

    def __call__(self):
        return self._get()

    @property
    def client(self):
        if self.instance is None:
            return None
        else:
            return self.instance.client

    def generate_url(self):
        base_url = self.instance.client.base_url
        url = "{base}{path}".format(base=base_url, path=self.path)
        logger.debug("Generated url: %s" % url)
        return url.format(**self.extract_keys(self.instance, _string_formatter))

    def extract_keys(self, resource, formatter=_string_formatter):
        format_iterator = formatter.parse(self.path)
        object_values = dict([(t[1], getattr(resource, t[1])) for t in format_iterator if not t[1] is None])
        for key, val in object_values.items():
            if val is None:
                object_values[key] = ""
        return object_values


class LazyPaginatedCollection(object):
    def __init__(self, items, page, per_page, link, *args, **kwargs):
        self.page = page
        self.per_page = per_page
        self.link = link
        self.args = args
        self.kwargs = kwargs
        self.items = items

    def __getitem__(self, index):
        print(index)
        page = int(index/self.per_page)
        print(page)
        real_index = index - (page*index)
        print(real_index)
        if page != self.page:
            self.page = page + 1
            items = self.link(page=self.page, resolve=False, per_page=self.per_page, *self.args, **self.kwargs)
            self.items = list(map(lambda i: self.link.resolver._from_json(i), items))


        item = self.items[int(real_index)]
        item._ensure_instance()
        return item


class LazyCollection(object):
    def __init__(self, items, link,  *args, **kwargs):
        self.items = list(map(lambda i: self.link.resolver._from_json(i), items))

    def __getitem__(self, index):
        item = self.items[index]
        item._ensure_instance()
        return item


class Link(object):
    def __init__(self, route, method="GET", schema=None, target_schema=None, requests_kwargs=None):
        self.method = method
        self.schema = schema
        self.target_schema = target_schema
        self.requests_kwargs = requests_kwargs
        self.route = route
        self._resolved = False

    @property
    def resolver(self):
        if CLASS in self.target_schema:
            return self.target_schema[CLASS]
        else:
            return self.route.resource_class

    def _resolve_schema(self):
        if REF in self.schema:
            pagination_url = self.route.client.pagination_url
            if pagination_url == self.schema[REF]:
                resolved_schema_ref = self.route.instance.client.resolve(self.schema[REF])
                self.schema[PAGINATION] = Pagination(resolved_schema_ref)

        self._resolve_types(self.schema, type(None))

        if REF in self.target_schema:
            self.target_schema[REF] = self.route.client.resolve(self.target_schema[REF])
        else:
            self.target_schema[REF] = self.route.resource_class._schema

        self._resolve_types(self.target_schema, object)

        if ITEMS in self.target_schema:
            if REF in self.target_schema[ITEMS]:
                if self.target_schema[ITEMS][REF] in self.route.client._url_identifiers:
                    self.target_schema[CLASS] = self.route.client._url_identifiers[self.target_schema[ITEMS][REF]]
                self.target_schema[ITEMS][REF] = self.route.client.resolve(self.target_schema[ITEMS][REF])

        self._resolved = True

    def _resolve_types(self, schema, resolve):
        if TYPE in schema:
            types = schema[TYPE]
            if isinstance(types, list):
                types = map(lambda x: TYPES[x], types)
            else:
                types = [TYPES[types]]
            schema[TYPE] = types
        else:
            schema[TYPE] = [resolve]

    def _extract_pagination(self, params, **kwargs):
        if PAGINATION in self.schema:
            pagination = self.schema[PAGINATION]
            params.update(pagination.paginate(kwargs.pop("page", None), kwargs.pop("per_page", None)))
        return params, kwargs

    def _extract_objects(self, body, args):
        schema_type = self.schema[TYPE]
        if self.method == "GET":
            if self.route.name in self.route.instance._schema[PROPERTIES]:
                instance_property = self.route.instance._instance[self.route.name]
                args.append(instance_property)

        if len(args) == 1:
            args = args[0]
        elif len(args) == 0:
            args = None

        assert isinstance(args, *schema_type), "Expected %s and got %s" % (schema_type, type(args))

        body = args

        return body

    def __call__(self, resolve=True, *args, **kwargs):
        if not self._resolved:
            self._resolve_schema()

        params = {}
        body = []
        params, kwargs = self._extract_pagination(params, **kwargs)
        body = self._extract_objects(body, args)
        url = self.route.generate_url()

        kwargs.update(self.requests_kwargs)
        response = requests.request(self.method, url=url, params=params, json=body, **kwargs)
        if response.status_code == 404:
            raise NotFoundException(url)
        if resolve:
            return self._resolve_response(response.json(), params, args, kwargs)
        else:
            return response.json()

    def _resolve_response(self, obj, params, args, kwargs):
        assert isinstance(obj, *self.target_schema[TYPE])

        if isinstance(obj, list):
            if self.schema[PAGINATION]:
                return LazyPaginatedCollection(obj, params.get("page"), params.get("per_page"), self, *args, **kwargs)
            else:
                return LazyCollection(obj, self)
        return obj

    def __getitem__(self, pos):
        if not self._resolved:
            self._resolve_schema()

        if isinstance(pos, tuple):
            page = pos[0]
            limit = pos[1]
        else:
            page = pos
            if PAGINATION in self.schema:
                limit = self.schema[PAGINATION].per_page

        return self(per_page=limit, page=page)


class Resource:
    client = None
    _schema = None
    _routes = None

    @classmethod
    def get(cls, id):
        instance = cls.__new__(cls)
        instance.id = id
        instance._ensure_instance()
        return instance

    @classmethod
    def _from_json(cls, json):
        validate(json, cls.client._schema)
        id = json[URI].split("/")[-1]
        instance = cls.__new__(cls)
        instance.id = id
        instance._instance = json
        return instance

    def __init__(self, id=None, instance=None):
        self.id = id
        self._instance = instance
        if id is None:  # make a new object
            self._instance = {}

    def __getattr__(self, item):
        if item in self._schema[PROPERTIES]:
            self._ensure_instance()
            return self._instance.get(item, None)
        else:
            getattr(super(Resource, self), item, self)

    def __setattr__(self, key, value):
        if key in self._schema[PROPERTIES]:
            self._ensure_instance()
            self._instance[key] = value
        else:
            super(Resource, self).__setattr__(key, value)

    def _ensure_instance(self):
        if self._instance is None:
            self._instance = self.self()

    def save(self):
        validate(self._instance, self._schema)
        if self.id is None:
            self.self.create(self._instance)
        else:
            self.self.update(self._instance)

    def delete(self):
        if self.id is None:
            #raise some kind of error
            raise RuntimeError()
        else:
            self.self.destroy()

    def __dir__(self):
        return super(Resource, self).__dir__() + list(self._schema[PROPERTIES].keys())

    def resolve(self, path):
        if path in self.client._url_identifiers:
            return self.client._url_identifiers[path]._schema

        root, target = path.split("#")
        if len(root) == 0:
            schema = self._schema
        else:
            klass = self.client._url_identifiers[root+"#"]
            schema = klass._schema

        base, section, fragment = target.split("/")

        return self._schema_resolver.resolve_fragment(schema[section], fragment)

    @classmethod
    def factory(cls, docstring, name, schema, requests_kwargs):
        class_name = utils.camelize(name)
        resource = type(class_name, (cls, ), {})
        resource.__doc__ = docstring
        resource._schema = schema
        routes = []
        for link_desc in schema[LINKS]:
            rel = link_desc[REL].split(":")
            route_name = rel[0]

            if not route_name in routes:
                routes.append(route_name)
                route = Route(link_desc[HREF], resource, route_name)
                setattr(resource, route_name, route)

            link = Link(route,
                        method=link_desc[METHOD],
                        schema=link_desc.get(SCHEMA, {}),
                        target_schema=link_desc.get(TARGET_SCHEMA, {}),
                        requests_kwargs=requests_kwargs)

            if route_name == "self":
                link = Link(route,
                            method="PUT",
                            schema=link_desc.get(SCHEMA, {}),
                            target_schema=link_desc.get(TARGET_SCHEMA, {}),
                            requests_kwargs=requests_kwargs)
                setattr(route, "create", link)
                link = Link(route,
                            method="PATCH",
                            schema=link_desc.get(SCHEMA, {}),
                            target_schema=link_desc.get(TARGET_SCHEMA, {}),
                            requests_kwargs=requests_kwargs)
                setattr(route, "update", link)

            if len(rel) == 1:
                setattr(route, "_get", link)
            else:
                setattr(route, rel[1], link)
        return resource

    def __str__(self):
        return str(self._instance)


class Pagination(object):
    _DEFAULT = "default"

    def __init__(self, schema_definition):
        self._schema = schema_definition
        self._properties = self._schema[PROPERTIES]

    @property
    def per_page(self):
        return self._properties["per_page"][self._DEFAULT]

    def paginate(self, page=None, per_page=None):
        if page is None:
            page = self._properties["page"][self._DEFAULT]
        if per_page is None:
            per_page = self._properties["per_page"][self._DEFAULT]

        pagination = {
            "page": page,
            "per_page": per_page
        }

        validate(pagination, self._schema)
        return pagination