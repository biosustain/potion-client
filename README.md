
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


## Dependencies

- [requests](http://docs.python-requests.org/en/latest/) for HTTP requests
- [jsonschema](python-jsonschema.readthedocs.org/en/latest/)