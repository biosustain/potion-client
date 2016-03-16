import json
import re

from requests import Request

from potion_client import PotionJSONDecoder
from potion_client.collection import PaginatedList
from potion_client.converter import PotionJSONEncoder
from potion_client.schema import Schema


class Link(object):

    def __init__(self, client, method, href, rel, schema=None, target_schema=None):
        self.method = method
        self.href_placeholders = re.findall(r"{(\w+)}", href)
        self.href = href
        self.rel = rel
        self.schema = Schema(schema)
        self.target_schema = Schema(target_schema)

    @property
    def requires_instance(self):
        return '{id}' in self.href

    def returns_pagination(self):
        if self.method == 'GET' and self.schema is not None:
            schema_properties = self.schema.get('properties', {})
            return 'page' in schema_properties and 'per_page' in schema_properties
        return False

    def __get__(self, instance, owner):
        return LinkBinding(self, instance, owner)


class LinkBinding(object):
    def __init__(self, link, instance, owner):
        self.link = link
        self.instance = instance
        self.owner = owner

    def request_factory(self, data, params):
        if self.instance is None:
            request_url = self.owner._client._root_url + self.link.href.format(**params)
        else:
            request_url = self.owner._client._root_url + self.link.href.format(id=self.instance.id, **self.instance)

        request_data = data
        request_params = {name: value for name, value in params.items()
                          if name not in self.link.href_placeholders and self.link.schema.can_include_property(name)}

        if data is None:
            request_data = request_params
        elif isinstance(data, dict):
            request_params = data

        if self.link.method == 'GET':
            req = Request(self.link.method,
                          request_url,
                          params={k: json.dumps(v, cls=PotionJSONEncoder)
                                  for k, v in request_params.items()})
        else:
            req = Request(self.link.method,
                          request_url,
                          headers={'content-type': 'application/json'},
                          data=json.dumps(request_data, cls=PotionJSONEncoder))
        return req

    def make_request(self, data, params):
        req = self.request_factory(data, params)
        prepared_request = self.owner._client.session.prepare_request(req)

        response = self.owner._client.session.send(prepared_request)

        # return error for some error conditions
        response.raise_for_status()

        return response, response.json(cls=PotionJSONDecoder,
                                       client=self.owner._client,
                                       default_instance=self.instance)

    def __getattr__(self, item):
        return getattr(self.link, item)

    def __call__(self, *arg, **params):
        data = None

        # Need to pass positional argument as *arg so that properties of the same name are not overridden in **params.
        if len(arg) > 1:
            raise TypeError('Link must be called with no more than one positional argument')
        elif len(arg) == 1:
            data = arg[0]

        if self.link.returns_pagination():
            return PaginatedList(self, params)

        response, response_data = self.make_request(data, params)
        return response_data