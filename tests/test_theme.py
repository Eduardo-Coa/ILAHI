"""Tests del sistema de temas: paletas, cambio en caliente y preferencias."""

from __future__ import annotations
import pytest

import theme
from utils.prefs import get_pref, set_pref, load_prefs


def test_paletas_mismas_claves():
    """Todos los temas definen exactamente las mismas claves que el oscuro."""
    claves = set(theme.DARK)
    for nombre, paleta in theme.PALETTES.items():
        assert set(paleta) == claves, f"claves distintas en «{nombre}»"


def test_todos_los_temas_con_etiqueta_y_descripcion():
    assert set(theme.LABELS) == set(theme.PALETTES) == set(theme.DESCRIPTIONS)


def test_set_theme_muta_en_sitio():
    """Cambiar de tema muta THEME (mismo objeto) y nunca corrompe las paletas."""
    original = dict(theme.THEME)
    ident = id(theme.THEME)
    try:
        theme.set_theme("pergamino")
        assert id(theme.THEME) == ident            # mismo dict, mutado en sitio
        assert theme.THEME["bg"] == theme.PARCHMENT["bg"]
        assert theme.active_theme() == "pergamino"
        assert theme.DARK["bg"] == "#000000"       # la paleta original, intacta
    finally:
        theme.set_theme(theme.DEFAULT_THEME)
    assert dict(theme.THEME) == original


def test_set_theme_nombre_invalido():
    with pytest.raises(ValueError):
        theme.set_theme("neon")


def test_is_dark_por_tema():
    esperado = {"noche": True, "medianoche": True,
                "pergamino": False, "alba": False}
    try:
        for nombre, oscuro in esperado.items():
            theme.set_theme(nombre)
            assert theme.is_dark() == oscuro, nombre
    finally:
        theme.set_theme(theme.DEFAULT_THEME)


def test_prefs_ida_y_vuelta(tmp_path):
    p = tmp_path / "preferences.json"
    assert get_pref("theme", "noche", path=p) == "noche"    # sin archivo → default
    set_pref("theme", "alba", path=p)
    set_pref("otra", 3, path=p)                             # no pisa la primera
    assert get_pref("theme", path=p) == "alba"
    assert load_prefs(p) == {"theme": "alba", "otra": 3}


def test_prefs_corruptas_no_explotan(tmp_path):
    p = tmp_path / "preferences.json"
    p.write_text("{esto no es json", encoding="utf-8")
    assert load_prefs(p) == {}
    set_pref("theme", "noche", path=p)                      # sobrescribe sin error
    assert get_pref("theme", path=p) == "noche"
