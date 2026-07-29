"""Alineación de la letra: se elige en el «Aa» y vale para toda la app.

Se prueba que las dos pantallas que muestran una canción —la vista de canción y la
rejilla de acordes— respeten la alineación, que las etiquetas de sección queden
SIEMPRE centradas, y que el acorde vaya centrado sobre su sílaba en las dos.
"""

from __future__ import annotations

import flet as ft

from models.song import Song, Section, Line, Syllable, Chord
from views.widgets import (LYRIC_ALIGNMENTS, LYRIC_ALIGN_DEFAULT,
                           lyric_row_alignment)
from views.stage_view import stage_body_from, StageScreen
from views.edit_view import EditSongScreen


def _cancion() -> Song:
    linea = Line(id=None, position=0, syllables=[
        Syllable(id=None, position=0, text="Glo", chord=Chord(id=None, value="G")),
        Syllable(id=None, position=1, text="ria"),
    ])
    seccion = Section(id=None, position=0, type="verse", label="Estrofa 1",
                      lines=[linea])
    return Song(id=1, title="T", key="G", sections=[seccion])


class _FakePage:
    width = 412

    def update(self):
        pass


# -- el traductor de la preferencia ------------------------------------------

def test_las_dos_opciones_disponibles():
    assert set(LYRIC_ALIGNMENTS) == {"left", "center"}
    assert LYRIC_ALIGN_DEFAULT == "center"


def test_la_preferencia_se_traduce_a_la_fila():
    assert lyric_row_alignment("left") == ft.MainAxisAlignment.START
    assert lyric_row_alignment("center") == ft.MainAxisAlignment.CENTER


def test_un_valor_desconocido_cae_al_centrado():
    """Un preferences.json de otra versión o editado a mano no debe romper la letra."""
    assert lyric_row_alignment("justificado") == ft.MainAxisAlignment.CENTER
    assert lyric_row_alignment(None) == ft.MainAxisAlignment.CENTER


# -- vista de canción ---------------------------------------------------------

def _filas_de_letra(bloques: list[ft.Control]) -> list[ft.Row]:
    return [c.content for c in bloques
            if isinstance(getattr(c, "content", None), ft.Row)]


def _etiquetas(bloques: list[ft.Control]) -> list[ft.Container]:
    return [c for c in bloques
            if isinstance(getattr(c, "content", None), ft.Text)]


def test_la_cancion_respeta_la_alineacion():
    for clave, esperado in (("center", ft.MainAxisAlignment.CENTER),
                            ("left", ft.MainAxisAlignment.START)):
        bloques = stage_body_from(_cancion(), 14, 412, clave)
        assert [f.alignment for f in _filas_de_letra(bloques)] == [esperado]


def test_la_etiqueta_de_seccion_queda_centrada_aunque_la_letra_vaya_a_la_izquierda():
    """La etiqueta separa bloques; no es texto que se lea de corrido."""
    bloques = stage_body_from(_cancion(), 14, 412, "left")

    etiqueta = _etiquetas(bloques)[0]
    assert etiqueta.content.value == "ESTROFA 1"
    assert (etiqueta.alignment.x, etiqueta.alignment.y) == (0.0, 0.0)   # centrada


# -- rejilla de edición de acordes -------------------------------------------

def _rejilla(align: str) -> list[ft.Control]:
    pantalla = EditSongScreen(None, _cancion(), on_back=lambda: None,
                              page=_FakePage(), align=align)
    pantalla._fill_grid()
    return pantalla._grid.controls


def test_la_rejilla_de_edicion_respeta_la_misma_alineacion():
    for clave, esperado in (("center", ft.MainAxisAlignment.CENTER),
                            ("left", ft.MainAxisAlignment.START)):
        filas = [c for c in _rejilla(clave) if isinstance(c, ft.Row)]
        assert filas, "la rejilla no armó ninguna fila de letra"
        assert all(f.alignment == esperado for f in filas)


def test_en_la_rejilla_el_acorde_va_centrado_sobre_su_silaba():
    """Igual que en la vista de canción; antes iba pegado a la izquierda y las dos
    pantallas no coincidían."""
    fila = next(c for c in _rejilla("center") if isinstance(c, ft.Row))
    palabra = fila.controls[0]                 # Row de celdas de una palabra
    celda = palabra.controls[0]                # Container con la Column [acorde/letra]

    assert celda.content.horizontal_alignment == ft.CrossAxisAlignment.CENTER


# -- la pantalla guarda la elección ------------------------------------------

def test_elegir_una_alineacion_la_persiste_y_repinta():
    guardado: list[str] = []
    pantalla = StageScreen(_FakePage(), _cancion(), on_back=lambda: None,
                           align="center", on_align_change=guardado.append)
    pantalla._body = ft.ListView()
    pantalla.page = type("P", (), {"width": 412, "update": lambda s: None,
                                   "pop_dialog": lambda s: None})()

    pantalla._set_align("left")

    assert pantalla.align == "left"
    assert guardado == ["left"]                # se guardó para toda la app
