from bbui.utils.env import BB_TMP_PATH
from pathlib import Path
from yaml import dump
def create_tmp_inventory(i : dict) -> None :
    inventory_path = Path(BB_TMP_PATH + "/inventory")
    # create inventory_path

    # write inventory files
    

def exists_tmp_inventory() -> bool :
    exists = False

    return exists

def delete_tmp_inventory() -> None :
    pass