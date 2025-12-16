from bbui.inventory.inventory import Inventory
import typer

app = typer.Typer()

@app.command()
def yaml():
    i = Inventory("/workspaces/bb-tui/etc/bluebanquise")
    print(i)

@app.command()
def soon():
    i = Inventory("/workspaces/bb-tui/etc/bluebanquise")
    print(i)

if __name__ == "__main__":
    app()