# Imports
from pathlib import Path
from bbui.inventory.host import Host
from bbui.inventory.group import Group
from bbui.utils.parser import parse_ini

from yaml import safe_load as yload , dump

# Globals
class Inventory() : 
    
    def __init__(self, p = "/etc/bluebanquise", crawl : bool = True) :
        self.hosts = {}
        self.groups = {}
        self.p = Path(p)
    
        if crawl:
            self.crawl_inventory()

    def crawl_inventory(self):
        p_inventory = self.p / 'cluster' / 'nodes'
        for p in p_inventory.glob('*.y*ml'):
            with open(p) as f:
                inv = yload(f)
                for k, v in inv['all']['hosts'].items():
                    self.hosts[k] = Host(k, v)
        p_inventory = self.p / 'cluster' / 'groups'
        for p in p_inventory.glob('**/*'):
            groups = parse_ini(str(p))
            for k, v in groups.items():
                for h in v['hosts']:
                    if h not in self.hosts.keys():
                        self.hosts[h] = Host(h)
                self.groups[k] = Group(k, v['hosts'],v['groupvars'],v['children'])
        
    def __str__(self) -> str:
        return dump(self.to_dict())
    
    def to_dict(self) -> dict: 
        out = {}
        out['hosts'] = {}
        out['groups'] = {}

        for k, v in self.hosts.items():
            out['hosts'][k] = v.to_dict()
        
        for k, v in self.groups.items():
            out['groups'][k] = v.to_dict()

        return out

if __name__ == "__main__":
    i = Inventory(p='/workspaces/bb-tui/etc/bluebanquise/inventory/')

    print(i)