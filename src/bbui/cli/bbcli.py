import typer
import inventory 
import host

app = typer.Typer()
app.add_typer(inventory.app, name="inventory")
app.add_typer(host.app, name="host")


if __name__ == "__main__":
    app()