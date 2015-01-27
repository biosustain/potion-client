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

from setuptools import setup, find_packages
requirements = ['requests', 'jsonschema']
test_requirements = ["Flask-Testing=>0.4.1", "flask-potion>=0.2.0", "httmock", "nose"]

setup(
    name='gvc',
    version='0.0',
    packages=find_packages(),
    install_requires=requirements,
    tests_requires=test_requirements,
    author='João Cardoso and Lars Schöning',
    author_email='joaca@biosustain.dtu.dk',
    description='',
    license='Apache License Version 2.0',
    keywords='potion client',
    url='TBD',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Topic :: Internet',
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: Apache Software License'
    ],
)
