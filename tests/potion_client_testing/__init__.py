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
import json
import requests
import sqlalchemy as sqla

from flask import Flask

from flask.testing import FlaskClient
from flask_testing import TestCase

from flask_potion import fields, Api
from flask_potion.resource import ModelResource
from flask_potion.routes import ItemAttributeRoute

from flask_sqlalchemy import SQLAlchemy

from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.orm import backref
from sqlalchemy.orm.collections import attribute_mapped_collection


from httmock import urlmatch

from potion_client import utils

import logging

logging.basicConfig(level=10)


class JSONType(sqla.TypeDecorator):
    """Enables JSON storage by encoding and decoding on the fly."""
    impl = sqla.String

    def process_bind_param(self, value, dialect):
        return json.dumps(value)

    def process_result_value(self, value, dialect):
        return json.loads(value)


class ApiClient(FlaskClient):
    def open(self, *args, **kw):
        """
        Sends HTTP Authorization header with  the ``HTTP_AUTHORIZATION`` config value
        unless :param:`authorize` is ``False``.
        """
        headers = kw.pop('headers', [])

        if 'data' in kw:
            kw['data'] = json.dumps(kw['data'])
            kw['content_type'] = 'application/json'

        return super(ApiClient, self).open(*args, headers=headers, **kw)


class MockResponseTool(object):

    encoding = "utf-8"

    @urlmatch(netloc='.*', method="GET", path=".*")
    def get_mock(self, url, request):
        path = utils.path_for_url(url)
        return self.reply(self.client.get(path))

    @urlmatch(netloc='.*', method="POST", path=".*")
    def post_mock(self, url, request):
        path = utils.path_for_url(url)
        body = json.loads(request.body)
        return self.reply(self.client.post(path, data=body))

    @urlmatch(netloc='.*', method="PATCH", path=".*")
    def patch_mock(self, url, request):
        path = utils.path_for_url(url)
        body = json.loads(request.body)
        return self.reply(self.client.patch(path, data=body))

    @urlmatch(netloc='.*', method="DELETE", path=".*")
    def delete_mock(self, url, request):
        path = utils.path_for_url(url)
        return self.reply(self.client.delete(path))

    def reply(self, response):
        content = self.decode(response)
        res = requests.Response()
        res._content = content.encode(self.encoding)
        res._content_consumed = content
        res.status_code = response.status_code
        res.encoding = self.encoding
        res.headers = response.headers
        return res

    def decode(self, response):
        return "".join([b.decode(self.encoding) for b in response.response])


class MockAPITestCase(MockResponseTool, TestCase):

    def create_app(self):
        app = Flask(__name__)
        app.config['SQLALCHEMY_ENGINE'] = 'sqlite://'
        app.test_client_class = ApiClient
        app.debug = True
        return app

    def setUp(self):
        super(MockAPITestCase, self).setUp()
        self.api = Api(self.app)
        self.sa = sa = SQLAlchemy(self.app)

        class Foo(sa.Model):
            id = sa.Column(sa.Integer, primary_key=True)
            attr1 = sa.Column(sa.String, nullable=False)
            attr2 = sa.Column(sa.String)
            attr3 = sa.Column(sa.String)
            baz = sa.relationship("Baz", uselist=False, backref="foo")
            date = sa.Column(sa.DateTime)

        class Bar(sa.Model):
            id = sa.Column(sa.Integer, primary_key=True)
            attr1 = sa.Column(sa.Integer, nullable=False)
            foo_id = sa.Column(sa.Integer, sa.ForeignKey(Foo.id), nullable=False)
            foo = sa.relationship(Foo, backref=backref('bars', lazy='dynamic'))

        class Baz(sa.Model):
            id = sa.Column(sa.Integer, primary_key=True)
            attr1 = sa.Column(sa.Float, nullable=False)
            attr2 = sa.Column(JSONType, nullable=True)
            foo_id = sa.Column(sa.Integer, sa.ForeignKey(Foo.id), nullable=False)

        class FooWithMappedBiz(sa.Model):
            id = sa.Column(sa.Integer, primary_key=True)
            attr1 = sa.Column(sa.String, nullable=False)
            bizes = association_proxy('foo_has_bizes', 'foo_with_mapped_biz',
                                      creator=lambda k, v: BizMapper(key=k, biz=v))

        class Biz(sa.Model):
            id = sa.Column(sa.Integer, primary_key=True)
            attr1 = sa.Column(sa.String, nullable=False)
            attr2 = sa.Column(sa.Float, nullable=False)

        class BizMapper(sa.Model):
            id = sa.Column(sa.Integer, primary_key=True)
            key = sa.Column(sa.String, index=True, nullable=False)
            foo_with_mapped_bar_id = sa.Column(sa.Integer, sa.ForeignKey(FooWithMappedBiz.id), nullable=False)
            biz_id = sa.Column(sa.Integer, sa.ForeignKey(Biz.id), nullable=False)
            biz = sa.relationship(Biz)

            foo_with_mapped_biz = sa.relationship(FooWithMappedBiz,
                                                  backref=backref('foo_has_bizes',
                                                                  collection_class=attribute_mapped_collection('key'),
                                                                  cascade='all, delete-orphan'))
        sa.create_all()

        class ResourceFoo(ModelResource):
            class Schema:
                bars = fields.ToMany("bar")
                baz = fields.ToOne("baz", nullable=True)
                date = fields.Date()

            class Meta:
                model = Foo
                exclude_fields = ['attr3']

            attr3 = ItemAttributeRoute(fields.String)

        class ResourceBar(ModelResource):
            class Schema:
                foo = fields.ToOne(ResourceFoo)

            class Meta:
                model = Bar

        class ResourceBaz(ModelResource):
            class Schema:
                attr2 = fields.Any(nullable=True)
                foo = fields.ToOne(ResourceFoo)

            class Meta:
                model = Baz

        class ResourceBiz(ModelResource):
            class Meta:
                model = Biz

        class ResourceFooWithMappedBiz(ModelResource):
            class Schema:
                bizes = fields.Object(fields.ToOne('biz'))

            class Meta:
                model = FooWithMappedBiz

        self.api.add_resource(ResourceFoo)
        self.api.add_resource(ResourceBar)
        self.api.add_resource(ResourceBaz)
        self.api.add_resource(ResourceBiz)
        self.api.add_resource(ResourceFooWithMappedBiz)

    def tearDown(self):
        self.sa.drop_all()