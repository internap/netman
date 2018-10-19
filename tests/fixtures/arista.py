from jabstract import jabstract

result_payload = jabstract({
    'command': '',
    'encoding': 'json',
    'result': {}
})

vlan_data = jabstract({
    'dynamic': False,
    'interfaces': {'Cpu': {'privatePromoted': False}},
    'name': 'VLAN0123',
    'status': 'active'
})

interface_address = jabstract({
    'broadcastAddress': '255.255.255.255',
    'dhcp': False,
    'primaryIp': {'address': '192.168.11.1', 'maskLen': 29},
    'secondaryIps': {
        '192.168.12.1': {'address': '192.168.12.1', 'maskLen': 29},
        '192.168.13.1': {'address': '192.168.13.1', 'maskLen': 29}
    },
    'secondaryIpsOrderedList': [
        {'address': '192.168.12.1', 'maskLen': 29},
        {'address': '192.168.13.1', 'maskLen': 29}
    ],
    'virtualIp': {'address': '0.0.0.0', 'maskLen': 0},
    'virtualSecondaryIps': {},
    'virtualSecondaryIpsOrderedList': []
})

interface_vlan_data = jabstract({
    'bandwidth': 0,
    'burnedInAddress': 'fa:16:3e:02:b9:e2',
    'description': '',
    'forwardingModel': 'routed',
    'hardware': 'vlan',
    'interfaceAddress': [interface_address()],
    'interfaceStatus': 'notconnect',
    'lastStatusChangeTimestamp': 1539974209.994736,
    'lineProtocolStatus': 'lowerLayerDown',
    'mtu': 1500,
    'name': 'Vlan123',
    'physicalAddress': 'fa:16:3e:02:b9:e2'
})


def show_interfaces(*interface_data):
    return {'interfaces': {i["name"]: i for i in interface_data}}
