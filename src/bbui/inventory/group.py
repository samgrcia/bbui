from yaml import dump

class Group():
    def __init__(self,
                    name : str, 
                    hosts : list = [], 
                    v : dict = {}, 
                    children : list = []) -> None:
        
        self.name = name
        self.hosts = hosts
        self.vars = v
        self.children = children

    def __str__(self) -> str:
        return dump(self.to_dict())

    def to_dict(self):
        return { 
                    'hosts' : self.hosts,
                    'groupvars' : self.vars,
                    'children' : self.children 
                }
    

if __name__ == "__main__":
    name = 'g1'
    hosts = [
        'node0',
        'node1',
        'node2',
        'node3'
    ]

    print(Group(name, hosts))