"""Pruebas de la lógica del editor de temas en vivo (solo desarrollo).

La UI (deslizadores, vista previa) no se prueba headless; sí la lógica que la
sostiene: los helpers de ``theme`` que editan/guardan/exportan paletas y la
conversión hex↔RGB del editor. El editor muta estado global de ``theme``, así que
una fixture restaura las paletas después de cada prueba.
"""

from __future__ import annotations
import pytest

import theme
from views.theme_editor import _hex_to_rgb, _rgb_to_hex


@pytest.fixture(autouse=True)
def _restaura_tema():
    """Fotografía las paletas y el tema activo, y los devuelve al terminar: así una
    prueba que retoca colores no filtra su estado a las demás."""
    snapshot = theme.export_palettes()
    activo = theme.active_theme()
    yield
    theme.apply_overrides(snapshot)
    theme.set_theme(activo)


def test_scratch_esta_en_las_paletas_pero_no_en_las_del_usuario():
    """La paleta de pruebas existe para el editor, pero no la ve el usuario final."""
    assert "scratch" in theme.PALETTES
    assert "scratch" not in theme.USER_THEMES
    assert set(theme.USER_THEMES) == {"noche", "oscuro", "medianoche", "alba"}


def test_editar_un_color_toca_el_tema_activo_y_su_paleta():
    """``set_active_color`` escribe en lo que pinta la app (THEME) y en la paleta de
    origen (para que persista y se exporte)."""
    theme.set_theme("alba")
    theme.set_active_color("accent", "#123456")
    assert theme.THEME["accent"] == "#123456"
    assert theme.PALETTES["alba"]["accent"] == "#123456"


def test_editar_una_paleta_no_toca_las_otras():
    theme.set_theme("scratch")
    theme.set_active_color("bg", "#abcdef")
    assert theme.PALETTES["noche"]["bg"] != "#abcdef"      # Noche quedó intacta


def test_restablecer_vuelve_la_paleta_a_fabrica():
    theme.set_theme("noche")
    original = theme.PALETTES["noche"]["accent"]
    theme.set_active_color("accent", "#000fff")
    theme.reset_palette("noche")
    assert theme.PALETTES["noche"]["accent"] == original
    assert theme.THEME["accent"] == original               # el activo también se refresca


def test_exportar_y_reaplicar_es_ida_y_vuelta():
    theme.set_theme("alba")
    theme.set_active_color("text", "#0a0b0c")
    guardado = theme.export_palettes()
    theme.reset_palette("alba")
    assert theme.PALETTES["alba"]["text"] != "#0a0b0c"
    theme.apply_overrides(guardado)
    assert theme.PALETTES["alba"]["text"] == "#0a0b0c"


def test_apply_overrides_ignora_paletas_y_claves_desconocidas():
    """Un archivo de una versión vieja (claves/temas que ya no existen) no debe romper."""
    theme.set_theme("noche")
    theme.apply_overrides({
        "noche": {"accent": "#111111", "clave_muerta": "#999999"},
        "tema_fantasma": {"bg": "#000000"},
        "basura": "no es un dict",
    })
    assert theme.PALETTES["noche"]["accent"] == "#111111"   # lo válido se aplicó
    assert "clave_muerta" not in theme.PALETTES["noche"]    # lo desconocido se ignoró


def test_apply_overrides_tolera_none():
    """Sin nada guardado, ``get_pref`` devuelve None: no debe explotar."""
    theme.apply_overrides(None)          # no lanza


def test_el_snippet_exportado_incluye_cada_paleta_y_color():
    theme.set_theme("noche")
    snippet = theme.palette_source_snippet()
    assert "DARK: dict[str, str] = {" in snippet
    assert "SCRATCH: dict[str, str] = {" in snippet
    for key, _label in theme.EDITABLE_COLORS:
        assert f'"{key}":' in snippet


def test_hex_a_rgb_y_vuelta():
    assert _hex_to_rgb("#ff8800") == (255, 136, 0)
    assert _rgb_to_hex(255, 136, 0) == "#ff8800"
    assert _hex_to_rgb("#000000") == (0, 0, 0)
    assert _hex_to_rgb("#ffffff") == (255, 255, 255)


def test_hex_a_rgb_tolera_entradas_raras():
    assert _hex_to_rgb("ff8800") == (255, 136, 0)       # sin almohadilla
    assert _hex_to_rgb("#f3d365ff") == (243, 211, 101)  # con alfa: usa los 6 primeros
    assert _hex_to_rgb("#zzz") == (0, 0, 0)             # inválido: negro, no revienta
