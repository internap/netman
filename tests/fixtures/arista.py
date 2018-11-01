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

interface_data = jabstract({
    'autoNegotiate': 'off',
    'bandwidth': 0,
    'burnedInAddress': 'fa:16:3e:0e:ee:81',
    'description': '',
    'duplex': 'duplexFull',
    'forwardingModel': 'bridged',
    'hardware': 'ethernet',
    'interfaceAddress': [],
    'interfaceCounters': {
        'counterRefreshTime': 1541082601.226264,
        'inBroadcastPkts': 0,
        'inDiscards': 0,
        'inMulticastPkts': 30902,
        'inOctets': 2183607,
        'inTotalPkts': 30948,
        'inUcastPkts': 46,
        'inputErrorsDetail': {
            'alignmentErrors': 0,
            'fcsErrors': 0,
            'giantFrames': 0,
            'runtFrames': 0,
            'rxPause': 0,
            'symbolErrors': 0},
        'linkStatusChanges': 4,
        'outBroadcastPkts': 0,
        'outDiscards': 0,
        'outMulticastPkts': 447388,
        'outOctets': 32423850,
        'outUcastPkts': 0,
        'outputErrorsDetail': {
            'collisions': 0,
            'deferredTransmissions': 0,
            'lateCollisions': 0,
            'txPause': 0},
        'totalInErrors': 0,
        'totalOutErrors': 0},
    'interfaceStatistics': {
        'inBitsRate': 0.0,
        'inPktsRate': 0.0,
        'outBitsRate': 0.0,
        'outPktsRate': 0.0,
        'updateInterval': 300.0},
    'interfaceStatus': 'disabled',
    'lastStatusChangeTimestamp': 1541080271.3714354,
    'lineProtocolStatus': 'down',
    'loopbackMode': 'loopbackNone',
    'mtu': 9214,
    'name': 'Ethernet1',
    'physicalAddress': 'fa:16:3e:0e:ee:81'
})

switchport_data = jabstract({
    'accessVlanId': 1,
    'accessVlanName': 'default',
    'dot1qVlanTagRequired': False,
    'dot1qVlanTagRequiredStatus': False,
    'dynamicAllowedVlans': {},
    'dynamicTrunkGroups': [],
    'macLearning': True,
    'mode': 'access',
    'sourceportFilterMode': 'enabled',
    'staticTrunkGroups': [],
    'tpid': '0x8100',
    'tpidStatus': True,
    'trunkAllowedVlans': '800,805',
    'trunkingNativeVlanId': 1,
    'trunkingNativeVlanName': 'default'
})


def show_interfaces(*interface_data):
    return {'interfaces': {i["name"]: i for i in interface_data}}
