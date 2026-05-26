# Workflow de staging

bbui utilise un système de staging inspiré de git : les modifications sont accumulées en mémoire et ne sont jamais écrites sur disque sans un `commit` explicite.

Le staging est activé dès que vous utilisez `--inventory-dir` / `-I`.  
Avec `--inventory` / `-i` (fichier unique), les modifications sont écrites immédiatement.

---

## Vue d'ensemble

```
bbcli host add 'c[011:020]' --groups fn_compute,hw_typeA,os_ubuntu -I ./inventory/
      │
      ▼
  [staging cache]   ←  inventory_cache.pkl (lecture) + cache.pkl (mutations)
      │
      ├──  bbcli pending   →  aperçu des changements et des fichiers cibles
      │
      ├──  bbcli commit    →  écriture sur disque, nettoyage du cache
      │
      └──  bbcli discard   →  abandon des changements, nettoyage du cache
```

---

## Les deux caches

Les caches vivent sous `<inventory-dir>/.bbui/` :

| Fichier | Rôle | Cycle de vie |
|---|---|---|
| `inventory_cache.pkl` | Inventaire parsé (accélère les lectures successives) | Invalidé dès qu'un fichier source est plus récent |
| `cache.pkl` | Mutations stagées (inventaire modifié + liste des changements) | Créé par `stage`, supprimé par `commit` ou `discard` |

Quand `cache.pkl` est présent, toutes les commandes de lecture (`host list`, `host show`, etc.) l'utilisent et affichent un avertissement indiquant que des changements non commités sont actifs.

---

## Commandes

### `bbcli pending`

Affiche les changements stagés et les fichiers qui seront écrits.

```
┌─ Pending changes ────────────────────────────────────┐
│   │ Type       │ Nodeset / Subject │ Detail           │
│ + │ host added │ c[011:020]        │ groups=[...]     │
└──────────────────────────────────────────────────────┘

┌─ Files to be written ──────────────────────────────────┐
│ File                              │ Changes             │
│ inventory/cluster/nodes/nodes.yml │ + c[011:020]        │
│ inventory/cluster/groups/fn       │ + c[011:020]        │
│ inventory/cluster/groups/hw       │ + c[011:020]        │
│ inventory/cluster/groups/os       │ + c[011:020]        │
└────────────────────────────────────────────────────────┘
```

### `bbcli commit`

Écrit toutes les mutations sur disque et supprime `cache.pkl`.

En layout BlueBanquise, chaque hôte est réécrit dans le fichier dont il provient.  
Les nouveaux hôtes rejoignent le fichier de leurs pairs `fn_*` existants.

```bash
bbcli commit -I ./inventory/
# ✓ inventory/cluster/nodes/nodes.yml  (10 change(s))
# ✓ inventory/cluster/groups/fn        (1 change(s))
# Commit complete.
```

### `bbcli discard`

Abandonne toutes les mutations sans écrire sur disque.

```bash
bbcli discard -I ./inventory/          # demande confirmation
bbcli discard -I ./inventory/ --force  # sans confirmation
```

---

## Comportement en cas de changements cumulés

Plusieurs commandes successives s'accumulent dans le même `cache.pkl` :

```bash
bbcli host add 'c[011:015]' --groups fn_compute,hw_typeA,os_ubuntu -I ./inventory/
bbcli host add 'mgt3'       --groups fn_management,hw_typeC,os_rhel -I ./inventory/
bbcli host remove c005 -I ./inventory/
bbcli pending -I ./inventory/   # affiche les 3 changements ensemble
bbcli commit  -I ./inventory/   # écrit tout en une passe
```

---

## Cohérence des lectures

Tant que `cache.pkl` est présent, les commandes de lecture (`host list`, `host show`, `vars show`) retournent l'état **stagé** et non l'état disque.  
Un bandeau d'avertissement le signale :

```
⚠ Showing staged inventory (uncommitted changes present)
```
