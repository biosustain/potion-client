[![Build Status](https://travis-ci.org/biosustain/potion-client.svg?branch=master)](https://travis-ci.org/biosustain/potion-client)
[![Coverage Status](https://coveralls.io/repos/biosustain/potion-client/badge.svg?branch=master)](https://coveralls.io/r/biosustain/potion-client?branch=master)

# Potion client

A client for REST APIs documented using JSON-schema in general, and `Flask-Presst` as well as the upcoming `Flask-Potion` in particular.

## Example


    c = Client('http://localhost/api/schema')
    
    Project = c.Project
    Project.instances
    Project.instances.where(key=value)
    
    p = Project(1)
    p.name = "super project"
    p.save()
    
    User = c.User
    u = User()
    u.name = "Name"
    u.projects = [p]
    u.save()

    query = Project.instances.where(user=u)

    
## Dependencies

- [requests](http://docs.python-requests.org/en/latest/) for HTTP requests
- [jsonschema](python-jsonschema.readthedocs.org/en/latest/)
