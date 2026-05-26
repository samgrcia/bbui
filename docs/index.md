# bbui

**bbui** est un gestionnaire d'inventaires Ansible en ligne de commande.  
Il supporte les formats YAML et INI, le layout BlueBanquise, et un workflow de staging inspiré de git.

---

## Fonctionnalités

| Fonctionnalité | Description |
|---|---|
| Multi-format | Lecture et écriture YAML et INI |
| BlueBanquise | Layout et règles de groupes enforced automatiquement |
| Staging | Les modifications ne sont jamais écrites sans `commit` explicite |
| NodeSet | Manipulation de plages d'hôtes (`c[001:100]`) |
| Dot-notation | Inspection de variables imbriquées (`bmc.ip4`, `disks[0].name`) |

---

## Démarrage rapide

```bash
# Installation
poetry install

# Lister les hôtes d'un inventaire
bbcli host list -I ./my-inventory/

# Ajouter des hôtes (BlueBanquise)
bbcli host add 'c[001:010]' --groups fn_compute,hw_typeA,os_ubuntu -I ./my-inventory/

# Vérifier ce qui sera écrit
bbcli pending -I ./my-inventory/

# Écrire sur disque
bbcli commit -I ./my-inventory/
```

---

## Pages de documentation

- [Installation](installation.md)
- [Formats d'inventaire](inventory-layouts.md)
- [Syntaxe NodeSet](nodeset.md)
- [Workflow de staging](staging.md)
- [Référence CLI](cli-reference.md)
