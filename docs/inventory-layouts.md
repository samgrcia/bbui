# Formats d'inventaire

bbui supporte deux layouts : un layout générique Ansible, et le layout structuré BlueBanquise.  
La détection est automatique au lancement de toute commande.

---

## Layout générique

Un répertoire contenant un mélange de fichiers YAML et INI.

```
inventory/
├── hosts.yml           # hôtes en YAML
├── staging.ini         # hôtes en INI
└── group_vars/
    ├── all.yml         # vars appliquées à tous les groupes
    ├── webservers.yml  # vars pour le groupe "webservers"
    └── databases/      # vars pour "databases" (layout répertoire)
        ├── main.yml
        └── secrets.yml
```

Les fichiers sont chargés par ordre alphabétique. En cas de conflit, le dernier fichier l'emporte.  
`group_vars/` est appliqué en dernier, comme dans Ansible.

### Format YAML

```yaml
all:
  children:
    webservers:
      hosts:
        web01:
          ansible_user: ubuntu
        web02:
```

### Format INI

```ini
[webservers]
web01 ansible_user=ubuntu
web02

[webservers:vars]
ansible_become=true

[production:children]
webservers
```

Les sections `:vars` et `:children` sont supportées.

---

## Layout BlueBanquise

bbui détecte automatiquement le layout BlueBanquise dès que le répertoire passé à `-I` contient `cluster/nodes/` ou `cluster/groups/`.

> **Important** : passer `-I` au parent de `cluster/`, pas à `cluster/` lui-même.

```
inventory-root/           ← passer ce chemin à -I
├── cluster/
│   ├── nodes/
│   │   ├── compute.yml   # hôtes fn_compute + leurs vars
│   │   ├── login.yml     # hôtes fn_login + leurs vars
│   │   └── management.yml
│   └── groups/
│       ├── fn            # déclarations fn_* (INI, sans extension)
│       ├── hw            # déclarations hw_*
│       ├── os            # déclarations os_*
│       └── others        # groupes utilisateur (bucket par défaut)
└── group_vars/
    └── ...
```

### Groupes obligatoires

Chaque hôte doit appartenir à **exactement un** groupe de chacun des trois préfixes :

| Préfixe | Rôle | Exemples |
|---|---|---|
| `fn_` | Fonction (rôle fonctionnel) | `fn_compute`, `fn_management`, `fn_login` |
| `hw_` | Type matériel | `hw_cpu_server_type_A`, `hw_gpu_type_B` |
| `os_` | Système d'exploitation | `os_ubuntu_24`, `os_rhel_9` |

```bash
# Correct — les trois préfixes présents
bbcli host add 'c[001:010]' --groups fn_compute,hw_typeA,os_ubuntu -I ./inventory-root/

# Erreur — groupe hw_* manquant
bbcli host add c011 --groups fn_compute,os_ubuntu -I ./inventory-root/

# Erreur — deux groupes fn_*
bbcli host add c012 --groups fn_compute,fn_login,hw_typeA,os_ubuntu -I ./inventory-root/
```

### Routage des fichiers

#### Fichiers de nœuds (`cluster/nodes/`)

Chaque fichier de nœuds est un YAML Ansible standard dont la clé racine est `all` :

```yaml
all:
  hosts:
    c001:
      bmc_ip: 10.0.0.1
    c002:
```

- Les hôtes **existants** sont réécrits dans le fichier source d'où ils ont été chargés.
- Les **nouveaux** hôtes rejoignent le fichier de leurs pairs de même groupe `fn_*` (premier fichier par ordre alphabétique).
- Si aucun pair n'existe encore, un nouveau fichier `<fn_suffix>.yml` est créé.

#### Fichiers de groupes (`cluster/groups/`)

Les fichiers de groupes sont en format INI (sans extension).  
Les hôtes y apparaissent sous forme de **NodeSet Ansible** (`node[01:10]`) plutôt qu'un par ligne.

```ini
[fn_compute]
c[001:004]

[fn_management]
mgt[1:2]
```

- Les groupes `fn_*`, `hw_*`, `os_*` sont toujours écrits dans leurs fichiers canoniques (`fn`, `hw`, `os`).
- Les groupes utilisateur chargés depuis un fichier nommé y sont réécrits.
- Les groupes utilisateur créés ex nihilo vont dans `cluster/groups/others`.

### Cache

bbui maintient deux caches sous `<inventory-root>/.bbui/` :

| Fichier | Rôle |
|---|---|
| `inventory_cache.pkl` | Inventaire parsé (cache lecture). Invalidé si un fichier source est plus récent. |
| `cache.pkl` | Mutations stagées. Présent uniquement entre `stage` et `commit` / `discard`. |

Les caches sont invalidés automatiquement lorsque le type de layout change (ex. après une migration vers le layout BlueBanquise).
