"""Línea de datos bajo el título de una canción (original · ritmo · capo · autor).

Dos cosas: el ORDEN (adelante lo que hace falta para tocar, el autor al final) y que
esa línea se pueda leer entera aunque no entre, deslizándose sola una vez.
"""

from __future__ import annotations

import flet as ft

from models.song import Song
from views.stage_view import _song_meta
from views.widgets import title_block


class _PageQueRegistra:
    """Página falsa que anota las tareas que se le piden (la animación es una)."""

    def __init__(self) -> None:
        self.tasks: list[tuple] = []

    def run_task(self, fn, *args):
        self.tasks.append((fn, args))

    def update(self):
        pass


# -- orden de los datos -------------------------------------------------------

def test_el_autor_va_al_final():
    """La línea se recorta por la derecha, así que adelante van los datos de tocar."""
    song = Song(id=1, title="T", author="Un Corazón", original_key="A",
                rhythm="4/4", capo=1)

    assert _song_meta(song) == ["Original: A", "Ritmo: 4/4", "Capo: T1", "Un Corazón"]


def test_se_omite_lo_que_la_cancion_no_tiene():
    song = Song(id=2, title="T", rhythm="3/4")
    assert _song_meta(song) == ["Ritmo: 3/4"]


def test_sin_capo_no_se_menciona_el_capo():
    """``capo=0`` es «sin capo», no «capo cero»."""
    song = Song(id=3, title="T", author="Ana", capo=0)
    assert _song_meta(song) == ["Ana"]


# -- deslizamiento de la línea ------------------------------------------------

def _fila_meta(controls: list[ft.Control]) -> ft.Row | None:
    return next((c for c in controls if isinstance(c, ft.Row)), None)


def test_con_page_la_linea_es_desplazable_y_se_programa_el_deslizamiento():
    page = _PageQueRegistra()

    controls = title_block("Viene el Día", ["Original: A", "Un Corazón"], page)

    fila = _fila_meta(controls)
    assert fila is not None
    assert fila.scroll == ft.ScrollMode.HIDDEN      # se desplaza, pero sin barra
    assert len(page.tasks) == 1                     # una sola vez, no en bucle
    fn, args = page.tasks[0]
    assert args == (fila,)


def test_sin_page_la_linea_queda_como_antes():
    """Los encabezados que no pasan ``page`` (p. ej. sin animación) siguen igual."""
    controls = title_block("Viene el Día", ["Original: A", "Un Corazón"])

    assert _fila_meta(controls) is None
    assert [c.value for c in controls] == ["Viene el Día", "Original: A · Un Corazón"]


def test_sin_datos_no_hay_linea_ni_animacion():
    page = _PageQueRegistra()

    controls = title_block("Viene el Día", [], page)

    assert len(controls) == 1                       # solo el título
    assert page.tasks == []
