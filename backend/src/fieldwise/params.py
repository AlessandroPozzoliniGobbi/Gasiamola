"""Caricatore e validatore dei parametri del modello (contratto: params/SCHEMA.md).

Una "voce parametro" e' un dizionario che contiene la chiave `valore`; tutto cio'
che sta sopra e' struttura. `load_params()` restituisce `{nome_file: albero}`;
le funzioni lavorano sia su quel dizionario sia sull'albero di un singolo file.

Uso da riga di comando:
    python -m fieldwise.params --check   # riepilogo + errori (exit 1 se ci sono errori)
    python -m fieldwise.params --table   # scrive reports/params_table.md
"""
from __future__ import annotations

import argparse
import copy
import math
import re
import sys
from pathlib import Path
from typing import Any, Iterator

import yaml

from . import config

META_KEY = "_meta"
VALUE_KEY = "valore"
# chiavi tipiche di una voce: se compaiono senza `valore` la voce e' incompleta
_ENTRY_KEYS = {"unita", "fonte", "riferimento", "url", "nota", "verificato",
               "assunzione", "motivazione", "sensibilita", "intervallo"}
_INDEX_RE = re.compile(r"^(?P<key>.*)\[(?P<idx>\d+)\]$")


# ---------------------------------------------------------------- utilita'

def is_entry(node: Any) -> bool:
    """True se `node` e' una voce parametro (dizionario con la chiave `valore`)."""
    return isinstance(node, dict) and VALUE_KEY in node


def _is_number(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _nonempty_str(x: Any) -> bool:
    return isinstance(x, str) and x.strip() != ""


def _join(path: str, key: Any) -> str:
    return f"{path}.{key}" if path else str(key)


# ---------------------------------------------------------------- caricamento

def load_params(params_dir: str | Path | None = None) -> dict:
    """Carica tutti i `*.yaml` della cartella in `{nome_file_senza_estensione: albero}`.

    Un file vuoto diventa `{}`. Un YAML sintatticamente rotto solleva `ValueError`
    con il nome del file; una cartella inesistente solleva `FileNotFoundError`.
    """
    folder = Path(params_dir) if params_dir is not None else config.PARAMS_DIR
    if not folder.is_dir():
        raise FileNotFoundError(f"cartella dei parametri non trovata: {folder}")
    out: dict = {}
    for path in sorted(folder.glob("*.yaml")):
        try:
            with path.open(encoding="utf-8") as fh:
                data = yaml.safe_load(fh)
        except yaml.YAMLError as exc:
            raise ValueError(f"{path.name}: YAML non valido: {exc}") from exc
        out[path.stem] = {} if data is None else data
    return out


# ---------------------------------------------------------------- navigazione

def iter_entries(tree: Any, _prefix: str = "") -> Iterator[tuple[str, dict]]:
    """Itera `(percorso_puntato, voce)` su tutto l'albero; salta `_meta`."""
    if not isinstance(tree, dict):
        return
    for key, child in tree.items():
        if key == META_KEY:
            continue
        path = _join(_prefix, key)
        if is_entry(child):
            yield path, child
        elif isinstance(child, dict):
            yield from iter_entries(child, path)


def values(tree: Any) -> Any:
    """Stesso albero con ogni voce sostituita dal suo `valore`, senza `_meta`."""
    if is_entry(tree):
        return tree[VALUE_KEY]
    if isinstance(tree, dict):
        return {k: values(v) for k, v in tree.items() if k != META_KEY}
    return tree


def _split_path(path: str) -> tuple[list[str], int | None]:
    """'a.b.c[2]' -> (['a','b','c'], 2). L'indice e' ammesso solo sull'ultimo segmento."""
    idx: int | None = None
    m = _INDEX_RE.match(path)
    if m:
        path, idx = m.group("key"), int(m.group("idx"))
    return path.split("."), idx


def _lookup(tree: Any, keys: list[str], full_path: str) -> Any:
    node = tree
    for key in keys:
        if not isinstance(node, dict) or key not in node:
            raise KeyError(f"parametro non trovato: {full_path}")
        node = node[key]
    return node


def get(tree: Any, path: str) -> Any:
    """Valore del parametro `path` (es. 'crops.mais.kc.mid' o 'x.y[1]').

    Funziona sull'albero grezzo (con le voci) e su quello di `values()`.
    Se `path` punta a una sezione restituisce il sottoalbero dei valori.
    `KeyError` con il percorso completo se manca.
    """
    keys, idx = _split_path(path)
    node = _lookup(tree, keys, path)
    if is_entry(node):
        node = node[VALUE_KEY]
    elif isinstance(node, dict):
        node = values(node)
    if idx is not None:
        if not isinstance(node, list) or idx >= len(node):
            raise KeyError(f"parametro non trovato: {path}")
        node = node[idx]
    return node


# ---------------------------------------------------------------- validazione

def _validate_value(value: Any) -> str | None:
    if _is_number(value) or isinstance(value, str):
        return None
    if isinstance(value, list):
        if value and all(_is_number(v) for v in value):
            return None
        return "'valore' lista non valida (deve essere una lista non vuota di numeri)"
    return (f"'valore' di tipo {type(value).__name__} non ammesso "
            "(numero, lista di numeri o stringa; le date vanno tra virgolette)")


def _validate_entry(entry: dict, path: str) -> list[str]:
    errs: list[str] = []

    msg = _validate_value(entry[VALUE_KEY])
    if msg:
        errs.append(f"{path}: {msg}")

    if not _nonempty_str(entry.get("unita")):
        errs.append(f"{path}: 'unita' mancante o vuota (usare \"-\" se adimensionale)")
    if not isinstance(entry.get("nota"), str):
        errs.append(f"{path}: 'nota' mancante (puo' essere \"\" ma deve esserci)")
    if "verificato" not in entry:
        errs.append(f"{path}: 'verificato' mancante")
    elif not isinstance(entry["verificato"], bool):
        errs.append(f"{path}: 'verificato' deve essere true/false")

    for flag in ("assunzione", "sensibilita"):
        if flag in entry and not isinstance(entry[flag], bool):
            errs.append(f"{path}: '{flag}' deve essere true/false")

    # regola 1: (fonte + riferimento + url) oppure (assunzione: true + motivazione)
    missing = [k for k in ("fonte", "riferimento", "url") if not _nonempty_str(entry.get(k))]
    is_assumption = entry.get("assunzione") is True
    if missing and not is_assumption:
        errs.append(
            f"{path}: mancano {'/'.join(missing)} non vuoti "
            "(oppure 'assunzione: true' con 'motivazione')")
    elif missing and not _nonempty_str(entry.get("motivazione")):
        errs.append(f"{path}: 'assunzione: true' senza 'motivazione' non vuota")

    url = entry.get("url")
    if url not in (None, "") and not (isinstance(url, str) and url.startswith("http")):
        errs.append(f"{path}: 'url' deve iniziare con http")

    if "intervallo" in entry:
        iv = entry["intervallo"]
        if not (isinstance(iv, (list, tuple)) and len(iv) == 2
                and all(_is_number(x) for x in iv) and iv[0] < iv[1]):
            errs.append(f"{path}: 'intervallo' deve essere [min, max] con due numeri crescenti")
    return errs


def _validate_node(node: dict, path: str, errs: list[str]) -> None:
    for key, child in node.items():
        if key == META_KEY:
            continue
        p = _join(path, key)
        if is_entry(child):
            errs.extend(_validate_entry(child, p))
        elif isinstance(child, dict):
            if _ENTRY_KEYS & set(child):
                errs.append(f"{p}: voce senza la chiave 'valore'")
            else:
                _validate_node(child, p, errs)
        else:
            errs.append(f"{p}: non e' una voce parametro ne' una sezione (manca 'valore')")


def validate_params(tree: Any) -> list[str]:
    """Elenco degli errori (stringhe con il percorso puntato); vuoto se tutto e' valido."""
    if not isinstance(tree, dict):
        return ["radice: l'albero dei parametri non e' un dizionario"]
    errs: list[str] = []
    _validate_node(tree, "", errs)
    return errs


# ---------------------------------------------------------------- sensibilita'

def _in_sensitivity(entry: dict) -> bool:
    return entry.get("assunzione") is True or entry.get("sensibilita") is True


def sensitivity_entries(tree: Any) -> list[tuple[str, dict]]:
    """Voci con `assunzione: true` o `sensibilita: true` e valore numerico.

    Le liste numeriche si espandono in `percorso[i]`; la voce restituita per
    ogni elemento e' una copia con `valore` = quell'elemento.
    """
    out: list[tuple[str, dict]] = []
    for path, entry in iter_entries(tree):
        if not _in_sensitivity(entry):
            continue
        v = entry[VALUE_KEY]
        if _is_number(v):
            out.append((path, entry))
        elif isinstance(v, list):
            for i, el in enumerate(v):
                if _is_number(el):
                    out.append((f"{path}[{i}]", {**entry, VALUE_KEY: el}))
    return out


def override(tree: dict, modifiche: dict[str, Any]) -> dict:
    """Copia profonda di `tree` con i `valore` sostituiti.

    Le chiavi di `modifiche` sono percorsi puntati, anche `percorso[i]` per un
    elemento di lista. L'originale non viene modificato. `KeyError` se un
    percorso non esiste o non e' una voce parametro.
    """
    new = copy.deepcopy(tree)
    for path, nuovo in modifiche.items():
        keys, idx = _split_path(path)
        entry = _lookup(new, keys, path)
        if not is_entry(entry):
            raise KeyError(f"parametro non trovato: {path}")
        if idx is None:
            entry[VALUE_KEY] = nuovo
        else:
            lst = entry[VALUE_KEY]
            if not isinstance(lst, list) or idx >= len(lst):
                raise KeyError(f"parametro non trovato: {path}")
            lst[idx] = nuovo
    return new


# ---------------------------------------------------------------- riepilogo e tabella

def summary(tree: dict) -> dict[str, dict[str, int]]:
    """Per ogni file: voci, con_fonte, assunzioni, non_verificati, in_sensibilita.

    `in_sensibilita` conta le voci (non gli elementi di lista) che producono
    almeno una riga in `sensitivity_entries`.
    """
    out: dict[str, dict[str, int]] = {}
    for fname, sub in tree.items():
        entries = [e for _, e in iter_entries(sub)]
        out[fname] = {
            "voci": len(entries),
            "con_fonte": sum(all(_nonempty_str(e.get(k)) for k in ("fonte", "riferimento", "url"))
                             for e in entries),
            "assunzioni": sum(e.get("assunzione") is True for e in entries),
            "non_verificati": sum(e.get("verificato") is False for e in entries),
            "in_sensibilita": len({p.split("[")[0] for p, _ in sensitivity_entries(sub)}),
        }
    return out


def _cell(x: Any) -> str:
    if x is None or x == "":
        return "-"
    s = str(x).replace("|", "\\|").replace("\n", " ").strip()
    return s or "-"


def build_table(tree: dict) -> str:
    """Tabelle Markdown (una per file) con le voci dei parametri."""
    lines = ["# Tabella dei parametri", ""]
    for fname, sub in tree.items():
        lines += [f"## {fname}", "",
                  "| Percorso | Valore | Unita' | Fonte | Riferimento | Assunzione | Verificato |",
                  "|---|---|---|---|---|---|---|"]
        for path, e in iter_entries(sub):
            lines.append("| " + " | ".join([
                f"`{path}`", _cell(e.get(VALUE_KEY)), _cell(e.get("unita")),
                _cell(e.get("fonte")), _cell(e.get("riferimento")),
                "si" if e.get("assunzione") is True else "no",
                "si" if e.get("verificato") is True else "no",
            ]) + " |")
        lines.append("")
    return "\n".join(lines)


def write_table(tree: dict, out_path: str | Path | None = None) -> Path:
    path = Path(out_path) if out_path is not None else config.REPORTS_DIR / "params_table.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_table(tree), encoding="utf-8")
    return path


# ---------------------------------------------------------------- CLI

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m fieldwise.params",
                                 description="Controllo e tabella dei parametri.")
    ap.add_argument("--check", action="store_true", help="riepilogo ed errori (default)")
    ap.add_argument("--table", action="store_true", help="scrive reports/params_table.md")
    ap.add_argument("--dir", default=None, help=f"cartella dei YAML (default {config.PARAMS_DIR})")
    args = ap.parse_args(argv)
    if not args.table:
        args.check = True

    try:
        tree = load_params(args.dir)
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERRORE: {exc}")
        return 1

    code = 0
    if args.check:
        if not tree:
            print("Nessun file YAML trovato.")
        for fname, s in summary(tree).items():
            print(f"{fname}: {s['voci']} voci, {s['con_fonte']} con fonte, "
                  f"{s['assunzioni']} assunzioni, {s['non_verificati']} non verificate, "
                  f"{s['in_sensibilita']} in sensibilita'")
        errors = validate_params(tree)
        for e in errors:
            print(f"ERRORE: {e}")
        print(f"{len(errors)} errori." if errors else "Nessun errore.")
        if errors:
            code = 1
    if args.table:
        print(f"Scritto {write_table(tree)}")
    return code


if __name__ == "__main__":
    sys.exit(main())
