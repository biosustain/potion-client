
## Example


    c = Client('http://localhost/api/schema')

    Project = c.Project

    Project.instances()

    Project.instances.where(key=value)





## Dependencies

- [requests](http://docs.python-requests.org/en/latest/) for HTTP requests
- [jsonschema](python-jsonschema.readthedocs.org/en/latest/)