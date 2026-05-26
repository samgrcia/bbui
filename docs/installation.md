# Installation

## Prérequis

| Dépendance | Version |
|---|---|
| Python | 3.14+ |
| [ClusterShell](https://clustershell.readthedocs.io/) | ^1.9 |
| [Poetry](https://python-poetry.org/) | Pour le développement |

ClusterShell est installé automatiquement par Poetry.

---

## Depuis le dépôt

```bash
git clone https://github.com/samgrcia/bbui.git
cd bbui
poetry install
```

Vérification :

```bash
poetry run bbcli --help
```

---

## Variables d'environnement

Plutôt que de passer `--inventory` ou `--inventory-dir` à chaque commande, vous pouvez les exporter :

```bash
export BBUI_INVENTORY_DIR=/path/to/my-inventory
bbcli host list          # équivalent à bbcli host list -I /path/to/my-inventory
```

| Variable | Option équivalente | Description |
|---|---|---|
| `BBUI_INVENTORY` | `--inventory` / `-i` | Chemin vers un fichier d'inventaire unique |
| `BBUI_INVENTORY_DIR` | `--inventory-dir` / `-I` | Répertoire d'inventaire (active le staging) |

Quand les deux sont définis, `--inventory-dir` / `BBUI_INVENTORY_DIR` a priorité.
