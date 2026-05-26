# Référence CLI

## Options globales

Toutes les commandes acceptent ces deux options :

| Option | Abrégé | Env | Description |
|---|---|---|---|
| `--inventory PATH` | `-i` | `BBUI_INVENTORY` | Fichier d'inventaire unique (YAML ou INI). Écriture immédiate. |
| `--inventory-dir PATH` | `-I` | `BBUI_INVENTORY_DIR` | Répertoire d'inventaire. Active le workflow de staging. |

Quand `--inventory-dir` est utilisé, les modifications sont **stagées** et requièrent un `bbcli commit` pour être persistées.

---

## Hôtes

### `bbcli host add <nodeset>`

Stage l'ajout d'un ou plusieurs hôtes. Supporte la syntaxe NodeSet.

```bash
bbcli host add web01 -I ./inventory/
bbcli host add 'web[01:10]' --groups webservers,staging -I ./inventory/
bbcli host add 'c[001:100]' --groups fn_compute,hw_typeA,os_ubuntu -I ./inventory/
```

| Option | Abrégé | Description |
|---|---|---|
| `--groups LISTE` | `-g` | Groupes séparés par des virgules à assigner aux hôtes |

**Layout BlueBanquise** : les trois préfixes `fn_*`, `hw_*`, `os_*` sont obligatoires.  
Un hôte déjà existant est silencieusement ignoré (skip).

---

### `bbcli host remove <hostname>`

Stage la suppression d'un hôte.

```bash
bbcli host remove web05 -I ./inventory/
```

---

### `bbcli host list`

Affiche tous les hôtes, leurs groupes et leurs variables.  
Si des changements sont stagés, la vue stagée est affichée (avec avertissement).

```bash
bbcli host list -I ./inventory/
```

```
┌─ Hosts ──────────────────────────────────────────────────────┐
│ Name  │ Groups                          │ Vars               │
│ c001  │ fn_compute, hw_typeA, os_ubuntu │                    │
│ mgt1  │ fn_management, hw_typeC, os_rhel│ {'ip': '10.0.0.1'} │
└──────────────────────────────────────────────────────────────┘
```

---

### `bbcli host show <nodeset> [varname]`

Affiche les détails et les variables d'un ou plusieurs hôtes.

```bash
# Détails complets d'un hôte
bbcli host show web01 -I ./inventory/

# Détails de plusieurs hôtes via NodeSet
bbcli host show 'web[01:05]' -I ./inventory/

# Afficher une seule variable pour une plage d'hôtes
bbcli host show 'c[001:010]' bmc.ip4 -I ./inventory/
bbcli host show 'c[001:010]' disks[0].name -I ./inventory/
```

En mode variable unique, le résultat est un tableau compact `Hôte | Valeur`.  
En mode complet, chaque hôte est affiché dans un bloc avec ses variables en dot-notation.

---

## Groupes

### `bbcli group add <name>`

Stage l'ajout d'un groupe.

```bash
bbcli group add storage -I ./inventory/
```

---

### `bbcli group remove <name>`

Stage la suppression d'un groupe.

```bash
bbcli group remove storage -I ./inventory/
```

---

### `bbcli group list`

Liste tous les groupes avec leurs hôtes (NodeSet replié) et leurs sous-groupes.

```bash
bbcli group list -I ./inventory/
```

```
┌─ Groups ──────────────────────────────────────────┐
│ Name            │ Hosts        │ Children          │
│ fn_compute      │ c[001:004]   │                   │
│ fn_management   │ mgt[1:2]     │                   │
│ hw_cpu_type_A   │ c[001:004]   │                   │
└───────────────────────────────────────────────────┘
```

---

### `bbcli group show <name>`

Affiche les détails d'un groupe : hôtes, sous-groupes et variables.

```bash
bbcli group show webservers -I ./inventory/
```

---

## Variables

### `bbcli vars show <varname>`

Affiche chaque hôte et groupe qui définit `<varname>`, avec la valeur et le fichier source.  
Supporte la dot-notation pour les valeurs imbriquées.

```bash
# Variable simple
bbcli vars show ansible_user -I ./inventory/

# Variable imbriquée
bbcli vars show network.ip -I ./inventory/
bbcli vars show bmc.ip4 -I ./inventory/

# Élément de liste
bbcli vars show disks[0].name -I ./inventory/

# Filtres
bbcli vars show ansible_user -I ./inventory/ --hosts   # hôtes uniquement
bbcli vars show ntp_server   -I ./inventory/ --groups  # groupes uniquement
```

| Option | Abrégé | Description |
|---|---|---|
| `--hosts` | `-H` | N'affiche que les correspondances sur les hôtes |
| `--groups` | `-G` | N'affiche que les correspondances sur les groupes |

Exemple de sortie :

```
         Variable: ansible_user
┌───────┬────────────┬────────┬──────────────────────────────────────┐
│ Kind  │ Owner      │ Value  │ Source file                           │
│ host  │ web01      │ ubuntu │ inventory/cluster/nodes/web.yml       │
│ host  │ web02      │ ubuntu │ inventory/cluster/nodes/web.yml       │
│ group │ webservers │ deploy │ inventory/group_vars/webservers.yml   │
└───────┴────────────┴────────┴──────────────────────────────────────┘
```

### Syntaxe dot-notation

| Type de valeur | Format | Exemple |
|---|---|---|
| Scalaire | `key` | `ansible_user` |
| Dict imbriqué | `key.sub` | `network.ip` |
| Dict profond | `key.sub1.sub2` | `interfaces.eth0.speed` |
| Élément de liste | `key[i]` | `dns_servers[0]` |
| Clé dans liste | `key[i].sub` | `disks[0].name` |

---

## Staging

### `bbcli pending`

Affiche les changements stagés et les fichiers qui seront écrits au prochain `commit`.

```bash
bbcli pending -I ./inventory/
```

Nécessite `--inventory-dir`.

---

### `bbcli commit`

Écrit tous les changements stagés sur disque et vide le cache de staging.

```bash
bbcli commit -I ./inventory/
```

Nécessite `--inventory-dir`.

---

### `bbcli discard`

Abandonne tous les changements stagés sans écrire sur disque.

```bash
bbcli discard -I ./inventory/          # demande confirmation
bbcli discard -I ./inventory/ --force  # sans confirmation
```

| Option | Abrégé | Description |
|---|---|---|
| `--force` | `-f` | Ignore la demande de confirmation |

Nécessite `--inventory-dir`.
