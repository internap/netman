[![Build Status](https://travis-ci.org/internap/netman.svg?branch=master)](https://travis-ci.org/internap/netman)
[![Documentation Status](https://readthedocs.org/projects/netman/badge/?version=latest)](http://netman.readthedocs.org/en/latest/?badge=latest)
[![PyPI version](https://badge.fury.io/py/netman.svg)](http://badge.fury.io/py/netman)

Netman
======

Netman is a unified REST API that provides vendor-agnostic network automation.
It abstracts the vendor-specific bits and leaves you with a clean and
simplified API.


Python code usage
-----------------

```python
switch_factory = SwitchFactory(MemoryStorage(), ThreadingLockFactory())
switch = switch_factory.get_anonymous_switch(
    model="cisco", 
    hostname="hostname_or_ip", 
    username="username", 
    password="password", 
)

switch.add_vlan(1000, name="myvlan")
```

REST API usage 
--------------

First, start the service

```bash
tox
.tox/py27/bin/python netman/main.py
 * Running on http://127.0.0.1:5000/ (Press CTRL+C to quit)
```

Then you can access it by http

```bash
curl -X POST http://127.0.0.1:5000/switches/hostname_or_ip/vlans -d '{"number": 1000, "name": "myvlan"}' 
    -H "Content-Type: application/json" 
    -H "Netman-model: cisco" 
    -H "Netman-username: username" 
    -H "Netman-password: password"
```

Disaggregated mode
------------------

Netman supports a disaggregated mode. This is a special mode of operation where netman will use a remote netman server to access the network equipment. This mode is particularly useful in the case where your network equipment is not available to your main netman server.  You can start a server somewhere, let's say at 192.168.1.1, running netman as described above. And use the proxy like this for direct code usage :

```python
switch_factory = SwitchFactory(MemoryStorage(), ThreadingLockFactory())
switch = switch_factory.get_anonymous_switch(
    model="cisco", 
    hostname="hostname_or_ip", 
    username="username", 
    password="password", 
    netman_server="http://192.168.1.1")

switch.add_vlan(1000, name="myvlan")
```

Or when invoked using the REST API, you can call the main server and provide the proxy netman server to be used.

```bash
curl -X POST http://127.0.0.1:5000/switches/hostname_or_ip/vlans -d '{"number": 1000, "name": "myvlan"}' 
    -H "Content-Type: application/json" 
    -H "Netman-model: cisco" 
    -H "Netman-username: username" 
    -H "Netman-password: password"
    -H "Netman-Proxy-Server: http://192.168.1.1"
```

Contributing
============

Feel free to raise issues and send some pull request, we'll be happy to look at them!
