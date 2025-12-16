from bbui.inventory.inventory import Inventory
import typer

app = typer.Typer()

@app.command()
def yaml(hostname):
    i = Inventory("/workspaces/bb-tui/etc/bluebanquise")
    
    if hostname in i.i.keys():
        print(i.i[hostname])
    

        

@app.command()
def soon():
    i = Inventory("/workspaces/bb-tui/etc/bluebanquise")
    print(i)

if __name__ == "__main__":
    app()