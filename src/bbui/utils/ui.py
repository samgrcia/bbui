import bbui.utils.env as bbenv
from pathlib import Path
import yaml
import configparser

def create_tmp_inventory(i : dict) -> None :
    inventory_path = Path(bbenv.BB_TMP_PATH + "/" + bbenv.BB_INVENTORY_NAME)
    # create inventory_path
    inventory_path.mkdir(parents=True)

    # write inventory files
    

def exists_tmp_inventory() -> bool :
    exists = False

    return exists

def delete_tmp_inventory() -> None :
    pass

def init_inventory(p = bbenv.WORKDIR):
    cluster_path = Path(p +'/' + bbenv.BB_CLUSTER_DIR_NAME)
    nodes_path = cluster_path / bbenv.BB_NODES_DIR_NAME
    groups_path = cluster_path / bbenv.BB_GROUPS_DIR_NAME
    
    nodes_path.mkdir(parents=True)
    groups_path.mkdir()

def write_inventory(p : str, i : dict):
    
    cluster_path = Path(p +'/' + bbenv.BB_CLUSTER_DIR_NAME)
    nodes_path = cluster_path / bbenv.BB_NODES_DIR_NAME
    groups_path = cluster_path / bbenv.BB_GROUPS_DIR_NAME
    
    groups = {}
    hosts = { 'all' : { 'hosts' : {}}}

    for h, v in i['hosts'].items():
        hosts['all']['hosts'][h] = v

    nodes_path.mkdir(parents=True, exist_ok=True)
    with open(nodes_path / 'all.yml', 'w') as f:
        yaml.dump(hosts,f)

    for g, v in i['groups'].items():
        groups[g] = configparser.ConfigParser(allow_no_value=True,
                                                delimiters='=')
        for section, values in v.items():
            if section == "hosts":
                if g not in groups[g].keys():
                    groups[g][g] = {}
                for h in values:
                    groups[g][g][h] = None
            elif section == "children":
                if g + ":children" not in groups.keys():
                    groups[g][g + ":children"] = {}
                for subg in values:
                    groups[g][g + ":children"][subg] = None
                if len(groups[g][g + ":children"].keys()) == 0:
                    del groups[g][g + ":children"]
            elif section == "groupvars":
                if g + ":vars" not in groups.keys():
                    groups[g][g + ":vars"] = {}
                for k, v in values.items():
                    groups[g][g + ":vars"][k] = v
                if len(groups[g][g + ":vars"]) == 0:
                    del groups[g][g + ":vars"]
            else:
                continue

        groups_path.mkdir(parents=True, exist_ok=True)

        with open(groups_path / g, 'w') as f:
            groups[g].write(f)

    
    