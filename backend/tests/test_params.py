"""Test del caricatore/validatore dei parametri (contratto: params/SCHEMA.md)."""
from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml

from fieldwise import params as P
from fieldwise.config import PARAMS_DIR

SRC = {
    "fonte": "Allen et al. (1998). FAO-56",
    "riferimento": "Tabella 12",
    "url": "https://www.fao.org/4/x0490e/x0490e0b.htm",
}


def sourced(valore, **extra):
    return {"valore": valore, "unita": "-", **SRC, "nota": "", "verificato": True, **extra}


def assumed(valore, **extra):
    return {"valore": valore, "unita": "-", "nota": "", "verificato": False,
            "assunzione": True, "motivazione": "nessuna fonte ufficiale", **extra}


def make_tree():
    return {
        "colture": {
            "_meta": {"descrizione": "test"},
            "mais": {
                "kc": {"mid": sourced(1.2), "ini": assumed(0.3)},
                "zr": sourced([0.3, 0.6, 1.0], sensibilita=True),
                "semina": sourced("04-10"),
            },
        },
        "suolo": {"taw": sourced(150.0)},
    }


def write_yaml(folder: Path, name: str, data) -> None:
    (folder / f"{name}.yaml").write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")


# ---------------------------------------------------------------- caricamento

def test_load_params(tmp_path):
    write_yaml(tmp_path, "colture", make_tree()["colture"])
    write_yaml(tmp_path, "suolo", make_tree()["suolo"])
    (tmp_path / "vuoto.yaml").write_text("", encoding="utf-8")
    (tmp_path / "ignorato.txt").write_text("x", encoding="utf-8")
    tree = P.load_params(tmp_path)
    assert set(tree) == {"colture", "suolo", "vuoto"}
    assert tree["vuoto"] == {}
    assert "_meta" in tree["colture"]  # resta nell'albero
    assert P.validate_params(tree) == []


def test_load_params_bad_yaml_and_missing_dir(tmp_path):
    (tmp_path / "rotto.yaml").write_text("a: [1, 2", encoding="utf-8")
    with pytest.raises(ValueError, match="rotto.yaml"):
        P.load_params(tmp_path)
    with pytest.raises(FileNotFoundError):
        P.load_params(tmp_path / "non_esiste")


# ---------------------------------------------------------------- validazione

def test_valid_entries():
    assert P.validate_params(make_tree()) == []
    # niente url ammesso se e' un'assunzione
    assert P.validate_params({"a": {"x": assumed(2)}}) == []


def one_error(entry, key="x"):
    errs = P.validate_params({"f": {key: entry}})
    assert errs, "atteso almeno un errore"
    assert all(e.startswith(f"f.{key}:") for e in errs)
    return " | ".join(errs)


def test_missing_required_keys():
    for key in ("unita", "nota", "verificato"):
        e = sourced(1)
        del e[key]
        assert f"'{key}'" in one_error(e)


def test_source_rule():
    for key in ("fonte", "riferimento", "url"):
        e = sourced(1)
        e[key] = ""
        assert key in one_error(e)
    e = sourced(1)
    del e["fonte"]
    assert "fonte" in one_error(e)
    # assunzione senza motivazione
    e = assumed(1)
    e["motivazione"] = "  "
    assert "motivazione" in one_error(e)
    del e["motivazione"]
    assert "motivazione" in one_error(e)
    # assunzione: false senza fonte
    e = assumed(1, assunzione=False)
    assert "fonte" in one_error(e)


def test_verificato_must_be_bool():
    assert "verificato" in one_error(sourced(1, verificato="si"))


def test_value_types():
    for bad in (None, True, [], [1, "a"], {"a": 1}, float("nan")):
        assert "valore" in one_error(sourced(bad)), bad
    for ok in (1, 2.5, "04-10", [1, 2.5]):
        assert P.validate_params({"f": {"x": sourced(ok)}}) == []


def test_interval_rule():
    for bad in ([1], [2, 1], [1, 1], [1, 2, 3], ["a", "b"], 5):
        assert "intervallo" in one_error(sourced(1, intervallo=bad)), bad
    assert P.validate_params({"f": {"x": sourced(1.5, intervallo=[1, 2])}}) == []


def test_url_must_start_with_http():
    assert "url" in one_error(sourced(1, url="www.fao.org"))
    assert "url" in one_error(assumed(1, url="ftp://x"))


def test_error_reports_dotted_path():
    tree = {"colture": {"mais": {"kc": {"mid": sourced(1, url="x")}}}}
    errs = P.validate_params(tree)
    assert errs and errs[0].startswith("colture.mais.kc.mid:")


def test_incomplete_structures():
    errs = P.validate_params({"f": {"x": {"unita": "-", "fonte": "a"}}})
    assert any("f.x" in e and "valore" in e for e in errs)
    errs = P.validate_params({"f": {"y": 3}})
    assert any(e.startswith("f.y:") for e in errs)
    assert P.validate_params([1, 2])  # radice non dizionario


# ---------------------------------------------------------------- navigazione

def test_iter_entries_skips_meta():
    paths = [p for p, _ in P.iter_entries(make_tree())]
    assert paths == ["colture.mais.kc.mid", "colture.mais.kc.ini", "colture.mais.zr",
                     "colture.mais.semina", "suolo.taw"]
    assert not any("_meta" in p for p in paths)


def test_values_and_get():
    tree = make_tree()
    v = P.values(tree)
    assert v["colture"]["mais"]["kc"]["mid"] == 1.2
    assert v["colture"]["mais"]["zr"] == [0.3, 0.6, 1.0]
    assert "_meta" not in v["colture"]
    assert P.get(tree, "colture.mais.kc.mid") == 1.2
    assert P.get(v, "colture.mais.kc.mid") == 1.2  # anche sull'albero dei valori
    assert P.get(tree, "colture.mais.zr[1]") == 0.6
    assert P.get(tree, "colture.mais.kc") == {"mid": 1.2, "ini": 0.3}
    with pytest.raises(KeyError, match=r"colture\.mais\.kc\.late"):
        P.get(tree, "colture.mais.kc.late")
    with pytest.raises(KeyError, match=r"zr\[7\]"):
        P.get(tree, "colture.mais.zr[7]")


# ---------------------------------------------------------------- sensibilita'

def test_sensitivity_entries():
    got = dict(P.sensitivity_entries(make_tree()))
    # assunzione scalare + lista con sensibilita: true espansa; il resto escluso
    assert set(got) == {"colture.mais.kc.ini", "colture.mais.zr[0]",
                        "colture.mais.zr[1]", "colture.mais.zr[2]"}
    assert got["colture.mais.zr[1]"]["valore"] == 0.6
    # le stringhe non entrano anche se sono assunzioni
    t = {"f": {"d": assumed("04-10"), "n": assumed(3)}}
    assert [p for p, _ in P.sensitivity_entries(t)] == ["f.n"]


# ---------------------------------------------------------------- override

def test_override_scalar_and_list_element():
    tree = make_tree()
    before = copy.deepcopy(tree)
    new = P.override(tree, {"colture.mais.kc.mid": 1.5, "colture.mais.zr[1]": 0.9})
    assert tree == before  # originale intatto
    assert P.get(new, "colture.mais.kc.mid") == 1.5
    assert P.get(new, "colture.mais.zr") == [0.3, 0.9, 1.0]
    assert P.get(tree, "colture.mais.zr") == [0.3, 0.6, 1.0]
    assert new["colture"]["mais"]["kc"]["mid"]["fonte"] == SRC["fonte"]  # resto della voce preservato


def test_override_errors():
    tree = make_tree()
    with pytest.raises(KeyError, match="colture.mais.kc.late"):
        P.override(tree, {"colture.mais.kc.late": 1})
    with pytest.raises(KeyError):
        P.override(tree, {"colture.mais.kc": 1})  # sezione, non voce
    with pytest.raises(KeyError):
        P.override(tree, {"colture.mais.zr[9]": 1})


# ---------------------------------------------------------------- riepilogo, tabella, CLI

def test_summary():
    s = P.summary(make_tree())
    assert s["colture"] == {"voci": 4, "con_fonte": 3, "assunzioni": 1,
                            "non_verificati": 1, "in_sensibilita": 2}
    assert s["suolo"]["voci"] == 1


def test_table_and_cli(tmp_path, capsys):
    tree = make_tree()
    tree["suolo"]["taw"]["fonte"] = "a | b"  # il pipe va protetto
    out = P.write_table(tree, tmp_path / "sub" / "t.md")
    text = out.read_text(encoding="utf-8")
    assert "## colture" in text and "`mais.kc.mid`" in text
    assert "a \\| b" in text

    folder = tmp_path / "p"
    folder.mkdir()
    assert P.main(["--check", "--dir", str(folder)]) == 0  # cartella senza YAML
    assert "Nessun file YAML" in capsys.readouterr().out

    write_yaml(folder, "colture", make_tree()["colture"])
    assert P.main(["--check", "--dir", str(folder)]) == 0

    bad = {"x": {"valore": 1}}  # YAML incompleto
    write_yaml(folder, "rotto", bad)
    assert P.main(["--check", "--dir", str(folder)]) == 1
    assert "rotto.x" in capsys.readouterr().out

    (folder / "sintassi.yaml").write_text("a: [1", encoding="utf-8")
    assert P.main(["--check", "--dir", str(folder)]) == 1  # niente crash
    assert P.main(["--check", "--dir", str(tmp_path / "manca")]) == 1


# ---------------------------------------------------------------- file veri

def test_real_params_are_valid():
    if not any(PARAMS_DIR.glob("*.yaml")):
        pytest.skip("nessun YAML in params/")
    errors = P.validate_params(P.load_params())
    assert errors == [], "\n".join(errors)
