# bbui

Ansible YAML inventory manager with a Python backend and a Typer CLI.

## Installation

```bash
poetry install
```

## Usage

```bash
# Add a host
bbcli host add web01 --group webservers

# List hosts
bbcli host list

# Show a host
bbcli host show web01

# Remove a host
bbcli host remove web01

# Add a group
bbcli group add databases

# List groups
bbcli group list

# Remove a group
bbcli group remove databases
```

The inventory file defaults to `inventory.yml` in the current directory.
Override with `--inventory <path>` or the `BBUI_INVENTORY` environment variable.

## Development

```bash
poetry run pytest --cov=bbui
poetry run ruff check bbui
poetry run mypy bbui
```
