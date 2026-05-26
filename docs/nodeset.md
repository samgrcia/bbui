# Syntaxe NodeSet

bbui utilise [ClusterShell](https://clustershell.readthedocs.io/) pour manipuler les plages d'hôtes.  
Deux syntaxes coexistent : la syntaxe ClusterShell (pour les commandes CLI) et la syntaxe Ansible (dans les fichiers INI).

---

## Syntaxe ClusterShell (commandes CLI)

Toute commande acceptant un nom d'hôte accepte également une expression NodeSet.

| Expression | Expansion |
|---|---|
| `web01` | `web01` |
| `web[01:10]` | `web01` … `web10` |
| `web[01-10]` | `web01` … `web10` (tiret, synonyme de `:` en ClusterShell) |
| `web[01:10/2]` | `web01`, `web03`, `web05` … (pas de 2) |
| `web[01:10],db[1:5]` | union des deux plages |
| `web[01:10]!web05` | exclusion de `web05` |
| `c[001:100]` | `c001` … `c100` (zéro-padding préservé) |

```bash
# Ajouter 10 nœuds d'un coup
bbcli host add 'c[001:010]' --groups fn_compute,hw_typeA,os_ubuntu -I ./inventory/

# Afficher les vars d'une plage
bbcli host show 'c[001:004]' bmc.ip4 -I ./inventory/
```

---

## Syntaxe Ansible (fichiers INI)

Dans les fichiers INI générés par bbui, les plages utilisent le séparateur `:` (standard Ansible).  
Le séparateur `-` (ClusterShell) **n'est pas reconnu** par Ansible.

```ini
[fn_compute]
c[001:004]
g[001:002]

[fn_management]
mgt[1:2]
```

bbui convertit automatiquement lors de l'écriture : `node[01-03]` (ClusterShell) → `node[01:03]` (Ansible).

---

## Fold et expand

| Opération | Entrée | Sortie |
|---|---|---|
| Expand | `c[001:003]` | `['c001', 'c002', 'c003']` |
| Fold | `['c001', 'c002', 'c003']` | `c[001:003]` |

Les nœuds non-contigus sont séparés par une virgule :

```
['web01', 'web03']   →  web[01,03]
['web01', 'db01']    →  db01,web01   (groupes distincts → deux lignes en INI)
```

Dans les fichiers INI, chaque groupe de la liste repliée est écrit sur une ligne séparée :

```ini
[my_group]
db01
web[01,03]
```
