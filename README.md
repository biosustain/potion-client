
# Potion client

A client for REST APIs documented using JSON-schema in general, and `Flask-Presst` as well as the upcoming `Flask-Potion` in particular.

## Usage (preliminary)

	from potion_client import Client
	
	client = Client('http://localhost/schema')
	
	Address = client.Address
	
	# GET /address?where={"city": "Copenhagen"}
	addresses = Address.instances(where={"city": "Copenhagen"})
	# or Address.instances.where(Address.city == 'Copenhagen')
	
	addresses[1:10]  # -
	addresses[20:30] # GET /address?where={...}&page=2&per_page=20
	
	some_address = Address(123)
	# or possibly Address.get(123)
	
	# GET /address/123/same_city_as?other={"$ref": "/address/345"}
	some_address.same_city_as(other=Address(345))  # note: /address/345 is not loaded	
	# GET /address/recently-added?last="year"
	Address.recently_added(last="year")
	
	new_user = client.User(first_name="John", last_name="Doe")
	new_user.first_name = "Jane"
	new_user.address = some_address
	# POST /user {"first_name": "Jane", "last_name": "Doe", "address": {"$ref": "/address/123"}}
	new_user.save() # or client.User.create(first_name="", ...)
	new_user.update(address=None) # PATCH /user/1 {"address": null}
	new_user.destroy() # DELETE /user/1
	

	