"""Pruebas de la lógica de Ajustes: tamaño de letra y color de acordes.

Headless: no se corre la app; los diálogos (con deslizadores) no se prueban, sí la
lógica que sostienen. ``_apply_chord_color`` muta estado global de ``theme``, así que
una fixture lo restaura tras cada prueba.
"""

from __future__ import annotations
import pytest
import flet as ft

import theme
from views.settings_view import SettingsScreen


def _find(control, cls) -> list:
    """Recorre el árbol de controles y junta los del tipo ``cls`` (para inspeccionar
    la UI sin depender de índices)."""
    hallados: list = []

    def walk(c) -> None:
        if isinstance(c, cls):
            hallados.append(c)
        hijos = getattr(c, "controls", None)
        if isinstance(hijos, list):
            for x in hijos:
                walk(x)
        contenido = getattr(c, "content", None)
        if contenido is not None and not isinstance(contenido, str):
            walk(contenido)

    walk(control)
    return hallados


class _FakePage:
    height = 700

    def __init__(self):
        self.dialogs = []

    def update(self):
        pass

    def show_dialog(self, dialog):
        self.dialogs.append(dialog)

    def pop_dialog(self):
        pass


@pytest.fixture(autouse=True)
def _restaura_tema():
    snapshot = theme.export_palettes()
    activo = theme.active_theme()
    yield
    theme.apply_overrides(snapshot)
    theme.set_theme(activo)


def _settings():
    """SettingsScreen con la lista de tamaños persistidos que va registrando."""
    guardados: list[int] = []
    scr = SettingsScreen(_FakePage(), on_size_change=guardados.append)
    return scr, guardados


def test_el_tamano_se_limita_al_rango_valido():
    scr, guardados = _settings()
    scr._set_size(999)
    assert scr.stage_size == 48        # tope superior
    scr._set_size(1)
    assert scr.stage_size == 12        # tope inferior
    assert guardados == [48, 12]       # cada cambio se persistió


def test_el_tamano_persiste_el_valor_elegido():
    scr, guardados = _settings()
    scr._set_size(30)
    assert scr.stage_size == 30 and guardados == [30]


def test_color_de_acordes_edita_el_tema_activo_y_su_paleta():
    theme.set_theme("noche")
    scr, _ = _settings()
    scr._cc_key = "chord"
    scr._apply_chord_color("#abcdef")
    assert theme.THEME["chord"] == "#abcdef"
    assert theme.PALETTES["noche"]["chord"] == "#abcdef"


def test_acerca_de_muestra_el_nombre_y_el_autor():
    """El cuadro «Acerca de Ilahi» presenta la app y el crédito a Eduardo Coa."""
    page = _FakePage()
    scr = SettingsScreen(page)
    scr._open_about_sheet()
    assert len(page.dialogs) == 1
    textos = " ".join(t.value for t in _find(page.dialogs[0], ft.Text) if t.value)
    assert "Ilahi" in textos
    assert "Eduardo Coa" in textos
    assert "sin conexión" in textos


def test_el_interruptor_de_detectar_acordes_refleja_y_persiste():
    """El único interruptor de EDICIÓN muestra el valor actual y, al cambiarlo, avisa
    para que se persista."""
    recibido: list[bool] = []
    scr = SettingsScreen(_FakePage(), detect_chords=False,
                         on_detect_chords_change=recibido.append)
    tree = scr.build()
    switches = _find(tree, ft.Switch)
    assert len(switches) == 1                      # ya no está el de «Silabación»
    assert switches[0].value is False              # refleja el estado guardado
    switches[0].on_change(type("E", (), {"control": type("C", (), {"value": True})()})())
    assert recibido == [True]                      # el cambio se propaga


def test_color_de_acordes_no_toca_el_fondo():
    """El editor solo cambia el color del acorde; el fondo del acorde queda igual."""
    theme.set_theme("noche")
    fondo_antes = theme.THEME["chord_bg"]
    scr, _ = _settings()
    scr._cc_key = "chord"
    scr._apply_chord_color("#010203")
    assert theme.THEME["chord"] == "#010203"
    assert theme.THEME["chord_bg"] == fondo_antes
