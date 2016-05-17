# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import codecs

from setuptools import setup

setup(
    name='Potion-client',
    version='2.4.0',
    packages=[str('potion_client')],  # https://bugs.python.org/issue13943
    url='https://github.com/biosustain/potion-client',
    license='MIT',
    author='Lars Schöning',
    author_email='lays@biosustain.dtu.dk',
    description='A client for APIs written in Flask-Potion',
    long_description=codecs.open('README.rst', encoding='utf-8').read(),
    install_requires=[
        'jsonschema>=2.4',
        'requests>=2.5',
        'six'
    ],
    test_suite='nose.collector',
    tests_require=[
        'responses',
        'nose>=1.3'
    ],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Topic :: Internet',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'License :: OSI Approved :: MIT License'
    ]
)
