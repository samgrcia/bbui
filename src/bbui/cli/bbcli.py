import typer
import bbui.cli.inventory as inventory
import bbui.cli.host as host
import bbui.cli.test as test

app = typer.Typer()
app.add_typer(inventory.app, name="inventory")
app.add_typer(host.app, name="host")
app.add_typer(test.app, name="test")


if __name__ == "__main__":
    app()