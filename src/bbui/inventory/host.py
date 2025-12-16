from bbui.inventory.interface import InterfaceEthernet, InterfaceInfiniband
from yaml import dump

class Host():
    def __init__(self, hostname : str, v : dict = {}):
        self.hostname = hostname
        self.vars = v     
    
    def __str__(self) -> str:
        return dump(self.to_dict())

    def to_dict(self) -> dict:       
        return self.vars 

class BbHost(Host):
    def __init__(self, hostname: str, v: dict = {}):
        super().__init__(hostname, v)
        
        self.bmc = {'name' : '','ip4' : '', 'network' : '', 'mac' : ''}
        self.interfaces = []

        # Parse v
        ## Parse BMC
        if 'bmc' in v.keys():
            if 'name' in v['bmc'].keys():
                self.bmc['name'] = v['bmc']['name']
            if 'ip4' in v['bmc'].keys():
                self.bmc['ip4'] = v['bmc']['ip4']
            if 'network' in v['bmc'].keys():
                self.bmc['network'] = v['bmc']['network']
            if 'mac' in v['bmc'].keys():
                self.bmc['mac'] = v['bmc']['mac']
        
        ## Parse network interfaces
        if 'network_interfaces' in v.keys():
            for k in v['network_interfaces']:
                if "interface" not in k.keys():
                    # Erreur
                    pass 
                else: 
                    if "type" == "infiniband":
                        i = InterfaceInfiniband(k['interface'], k['ip4'], k['network'], "")
                    else:
                        i = InterfaceEthernet(k['interface'], k['ip4'], k['network'])
                    self.interfaces.append(i)
        
    def to_dict(self) -> dict:
        return {
                    'bmc': self.bmc,
                    'network_interfaces' : [ iface.to_dict() for iface in self.interfaces]
                }


if __name__ == "__main__":
    hostname = "node01"
    v = {
                'bmc': {
                    'name': 'bmgt1',
                    'ip4': '10.10.100.1',
                    'network': 'net-admin',
                    'mac': '2a:2b:3c:4d:10:11'
                },
                'network_interfaces': [
                    {
                        'interface': 'enp2s0',
                        'ip4': '10.10.0.1',
                        'network': 'net-admin',
                        'mac': '1a:2b:3c:4d:10:9f',
                        'never_default4': 'true'  
                    },
                    {
                        'interface': 'enp1s0',
                        'ip4': '192.168.1.20',
                        'network': 'external-network',
                        'skip': 'true'
                    }
                ],
                'foo': 'bar'
            }
    h1 =  Host(hostname, v)
    h2 =  BbHost(hostname, v)

    print(h1)
    print('--------------------')
    print(h2)
