from jabstract import jabstract

vlans_payload = jabstract(
    {'jsonrpc': '2.0', 'id': '4418851472',
     'result': [{'sourceDetail': '', 'vlans': {}}]
     }
)

vlan_data = jabstract({'status': 'active', 'interfaces': {}, 'dynamic': False, 'name': 'Name'})
