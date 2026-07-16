"""Pruebas del metrónomo integrado en el modo escenario (``PresentScreen``).

Headless: no se ejecuta la app real, solo se construye el árbol de controles con
una página falsa (sin ventana) y se inspecciona su estructura, igual que
``test_stage_align.py`` hace con la alineación de acordes.
"""

from __future__ import annotations

import flet as ft

from models.song import Song
from views.stage_view import PresentScreen
import theme


class _FakePage:
    width = 412
    bgcolor = None

    def update(self):
        pass

    def run_task(self, fn, *a):
        pass


def _rows_column(screen: PresentScreen) -> ft.Column:
    """Column de filas (velocidad / fuente / metrónomo) dentro del panel fijo.

    Se toma el panel de ``_panel_box`` (y no navegando el árbol por índices) para
    que la prueba no dependa de cómo esté armado el layout: el título pasó a
    flotar en un ``Stack`` y el panel dejó de ser el 3er hijo de una Column.
    """
    screen.build()
    return screen._panel_box.content.controls[0]


def test_panel_tiene_tres_filas_con_bpm_valido():
    song = Song(id=1, title="X", bpm=90, rhythm="4/4", sections=[])
    screen = PresentScreen(_FakePage(), song, 0, on_exit=lambda: None)

    filas = _rows_column(screen)

    assert len(filas.controls) == 3


def test_panel_tiene_dos_filas_sin_bpm():
    song = Song(id=2, title="Y", bpm=None, rhythm="4/4", sections=[])
    screen = PresentScreen(_FakePage(), song, 0, on_exit=lambda: None)

    filas = _rows_column(screen)

    assert len(filas.controls) == 2


def test_on_metro_beat_acento_en_el_primer_golpe():
    song = Song(id=1, title="X", bpm=90, rhythm="4/4", sections=[])
    screen = PresentScreen(_FakePage(), song, 0, on_exit=lambda: None)
    screen.build()

    screen._on_metro_beat(0)
    assert screen._metro_dot.bgcolor == theme.THEME["accent"]

    screen._on_metro_beat(1)
    assert screen._metro_dot.bgcolor == theme.THEME["chord"]
