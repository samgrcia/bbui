import configparser
import yaml
from ClusterShell.NodeSet import NodeSet

def parse_ini(filename : str) -> dict:
    out = {}
    config = configparser.ConfigParser(allow_no_value=True,
                                                delimiters='=')
    config.read(filename)

    for section in config.sections():
        
        if ":children" in section:
            if section.split(':')[0] not in out.keys():
                out[section.split(':')[0]] = {
                                    'children': [],
                                    'groupvars': {},
                                    'hosts': []
                                }
            out[section.split(':')[0]]['children'] =  [g for g in config[section]]
        elif ":vars" in section:
            if section.split(':')[0] not in out.keys():
                out[section.split(':')[0]] = {
                                    'children': [],
                                    'groupvars': {},
                                    'hosts': []
                                }
            for k, v in config[section].items():
                out[section.split(':')[0]]['groupvars'] = {k : v}
        
        else:
            if section not in out.keys():
                out[section] = {
                                    'children': [],
                                    'groupvars': {},
                                    'hosts': []
                                }
            for h in config[section]:
                h = h.replace(':','-')
                ns = NodeSet(h)
                out[section]['hosts'] = [h for h in ns]

    return out

def parse_yaml():
    pass