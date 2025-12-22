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
def writetmp (writedir):
    i = Inventory()
    ui.write_inventory(writedir, i.to_dict())

if __name__ == "__main__":
    app()