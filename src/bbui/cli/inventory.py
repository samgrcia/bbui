from bbui.inventory.inventory import Inventory
import bbui.utils.env as bbenv
import bbui.utils.ui as ui
from pathlib import Path
import typer
from typing_extensions import Annotated

app = typer.Typer()

@app.command()
def dump():
    i = Inventory()
    print(i)

@app.command()
def init(workdir: Annotated[str, typer.Option(help="The working directory.")] = bbenv.WORKDIR):
    inventory_path = Path(workdir)
    if not inventory_path.exists():
        print(f"Initialising {inventory_path}.")
        
        ui.init_inventory(workdir)
    else:
        print(f"{inventory_path} already exists.")

if __name__ == "__main__":
    app()