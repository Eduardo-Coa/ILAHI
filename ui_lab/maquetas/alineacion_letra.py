"""Maqueta: elegir la ALINEACIÓN de la letra desde el botón «Aa» de la canción.

Hoy ese botón solo ajusta el tamaño del texto. La propuesta le suma una fila para
alinear la letra —**Izquierda** o **Centrar** (como está hoy)— y esa elección es de
la app, no de la canción: vale para todas y sobrevive a cerrarla (iría a
``utils/prefs.py``, junto al tamaño del texto y el tema).

Aplica a las DOS pantallas que muestran la canción, y por eso la maqueta trae un
toggle para verlas con la misma configuración:

  · **Canción**  — la vista de siempre (``stage_view``).
  · **Edición**  — la rejilla de acordes (``edit_view``), donde cada sílaba se toca
                   para asignarle un acorde. Se alinea igual que la otra.

Las **etiquetas de sección** (INTRODUCCIÓN, ESTROFA 1…) quedan SIEMPRE centradas, no
acompañan a la letra: son separadores del bloque, no parte del texto que se lee.

Las piezas que dibujan la línea (cajas por sílaba, guion de unión, acordes sueltos
tras la puntuación) se toman de la maqueta ``acordes_centrados``, que ya las tiene
copiadas: el laboratorio no puede importar ``views.stage_view`` porque este arrastra
``database`` y la trampa del banco de pruebas lo impide a propósito.
"""

from __future__ import annotations
import flet as ft

import theme
from models.song import Syllable, Chord
from views.widgets import (back_button, centered_header, sheet_dialog, stepper_row,
                           SlidingToggle, _safe_update)
from ui_lab.maquetas.acordes_centrados import (
    CANCION_REAL, TITULO_REAL, _group_words, _mover_sueltos_tras_puntuacion,
    _word_col_nuevo)

NOMBRE = "Alineación de la letra (spike)"
DESCRIPCION = "El botón «Aa» también alinea la letra (izquierda/centro), para toda la app."

# Las dos alineaciones que se ofrecen, y cómo se traducen a la fila de palabras.
# Las etiquetas de sección NO usan esto: van siempre centradas.
ALINEACIONES: dict[str, tuple[str, ft.MainAxisAlignment, str]] = {
    "left": ("Izquierda", ft.MainAxisAlignment.START, ft.Icons.FORMAT_ALIGN_LEFT),
    "center": ("Centrar", ft.MainAxisAlignment.CENTER, ft.Icons.FORMAT_ALIGN_CENTER),
}
ALINEACION_POR_DEFECTO = "center"


def _silabas(pares) -> list[Syllable]:
    return [Syllable(id=None, position=i, text=t,
                     chord=Chord(id=None, value=c) if c else None)
            for i, (t, c) in enumerate(pares)]


def _linea_cancion(syls: list[Syllable], size: int,
                   alineacion: ft.MainAxisAlignment) -> ft.Control:
    """Un renglón de la vista de canción, alineado como diga ``alineacion``."""
    syls = _mover_sueltos_tras_puntuacion(syls)
    chord_size = max(10, round(size * 0.8))
    cols = [_word_col_nuevo(w, size, chord_size) for w in _group_words(syls)]
    return ft.Container(
        padding=ft.Padding.only(bottom=3),
        content=ft.Row(cols, wrap=True, spacing=0, run_spacing=2,
                       alignment=alineacion,
                       vertical_alignment=ft.CrossAxisAlignment.START))


def _celda_edicion(syl: Syllable, size: int, chord_size: int) -> ft.Control:
    """Casilla tocable de la rejilla de acordes: el acorde (o «·» si está libre)
    CENTRADO sobre la sílaba. Réplica de ``edit_view.EditSongScreen._cell``, salvo
    por el centrado: allá el acorde todavía va pegado a la izquierda de su sílaba
    (``CrossAxisAlignment.START``), que es lo que desentonaba con la vista de canción
    desde que esta pasó a cajas centradas.

    Acá NO hacen falta los guiones de unión de la vista de canción: allá las sílabas
    de una palabra se dibujan juntas y el guion evita que se lea como dos palabras;
    acá cada sílaba es su propia casilla que se toca para asignarle acorde, y un guion
    entre casillas sería un blanco de toque más, confuso."""
    valor = syl.chord.value if syl.chord else ""
    return ft.Container(
        padding=ft.Padding.symmetric(horizontal=2), border_radius=4,
        content=ft.Column(
            [
                ft.Text(valor or "·", size=chord_size, weight=ft.FontWeight.BOLD,
                        color=theme.THEME["chord"] if valor else theme.THEME["text_muted"],
                        no_wrap=True),
                ft.Text(syl.text or " ", size=size, color=theme.THEME["text"],
                        no_wrap=True),
            ],
            spacing=0, tight=True,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER))


def _linea_edicion(syls: list[Syllable], size: int,
                   alineacion: ft.MainAxisAlignment) -> ft.Control:
    """Un renglón de la rejilla de edición, con la MISMA alineación que la canción."""
    chord_size = max(10, round(size * 0.8))
    palabras = [
        ft.Row([_celda_edicion(s, size, chord_size) for s in palabra],
               spacing=0, tight=True,
               vertical_alignment=ft.CrossAxisAlignment.START)
        for palabra in _group_words(syls)
    ]
    return ft.Row(palabras, wrap=True, spacing=0, run_spacing=2,
                  alignment=alineacion,
                  vertical_alignment=ft.CrossAxisAlignment.START)


def _cuerpo(size: int, clave: str, modo: str) -> list[ft.Control]:
    """La canción entera con la alineación elegida, en la vista pedida."""
    _etiqueta, fila_align, _icono = ALINEACIONES[clave]
    hacer_linea = _linea_cancion if modo == "cancion" else _linea_edicion
    blocks: list[ft.Control] = []
    for nombre, lineas in CANCION_REAL:
        # SIEMPRE centrada: la etiqueta separa bloques, no es texto que se lea de
        # corrido, así que no acompaña a la alineación de la letra.
        blocks.append(ft.Container(
            padding=ft.Padding.only(top=8, bottom=1),
            alignment=ft.Alignment.CENTER,
            content=ft.Text(nombre.upper(), size=theme.SIZE_SECTION,
                            color=theme.THEME["section_label"])))
        for pares in lineas:
            syls = _silabas(pares)
            if not any(s.text.strip() for s in syls):
                blocks.append(ft.Container(height=int(size * 0.3)))
                continue
            blocks.append(hacer_linea(syls, size, fila_align))
    return blocks


def construir(page: ft.Page, db) -> ft.Control:
    # En la app esto sale de las preferencias (vale para todas las canciones); aquí
    # vive en memoria, que alcanza para ver cómo queda.
    estado = {"size": theme.SIZE_STAGE, "align": ALINEACION_POR_DEFECTO,
              "modo": "cancion"}
    cuerpo = ft.ListView(expand=True, spacing=2,
                         padding=ft.Padding.only(left=16, right=16, top=8, bottom=90))

    def repintar() -> None:
        cuerpo.controls = _cuerpo(estado["size"], estado["align"], estado["modo"])
        _safe_update(cuerpo)
        page.update()

    def cambiar_modo(modo: str) -> None:
        estado["modo"] = modo
        repintar()

    toggle = SlidingToggle("Canción", "Edición",
                           on_left=lambda: cambiar_modo("cancion"),
                           on_right=lambda: cambiar_modo("edicion"),
                           active="left")

    # -- cuadro del «Aa»: tamaño + alineación --
    def abrir_cuadro(_e=None) -> None:
        texto_tamano = ft.Text(str(estado["size"]), size=26,
                               weight=ft.FontWeight.BOLD, color=theme.THEME["text"])

        def cambiar_tamano(delta: int) -> None:
            estado["size"] = max(12, min(48, estado["size"] + delta))
            texto_tamano.value = str(estado["size"])
            _safe_update(texto_tamano)
            repintar()

        def elegir(clave: str) -> None:
            estado["align"] = clave
            page.pop_dialog()
            repintar()

        def pildora(clave: str) -> ft.Control:
            etiqueta, _align, icono = ALINEACIONES[clave]
            activa = estado["align"] == clave
            color = theme.THEME["chord"] if activa else theme.THEME["text_muted"]
            return ft.Container(
                expand=True, ink=True, border_radius=14, height=44,
                alignment=ft.Alignment.CENTER,
                on_click=lambda _e, c=clave: elegir(c),
                bgcolor=theme.THEME["chord_bg"] if activa else theme.THEME["surface"],
                border=ft.Border.all(
                    1, theme.THEME["chord"] if activa else theme.THEME["border"]),
                content=ft.Row(tight=True, spacing=6,
                               alignment=ft.MainAxisAlignment.CENTER, controls=[
                    ft.Icon(icono, size=18, color=color),
                    ft.Text(etiqueta, size=13,
                            color=color if activa else theme.THEME["text"]),
                ]))

        page.show_dialog(sheet_dialog(
            content_padding=ft.Padding.only(left=16, right=16, top=8, bottom=8),
            content=ft.Column(
                tight=True, spacing=10,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER, controls=[
                    ft.Text("Tamaño del texto", size=16, color=theme.THEME["text"]),
                    stepper_row("A−", lambda _e: cambiar_tamano(-2), texto_tamano,
                                "A+", lambda _e: cambiar_tamano(2)),
                    ft.TextButton("Restablecer",
                                  on_click=lambda _e: cambiar_tamano(
                                      theme.SIZE_STAGE - estado["size"])),
                    ft.Container(height=1, bgcolor=theme.THEME["border"]),
                    ft.Text("Alineación de la letra", size=16,
                            color=theme.THEME["text"]),
                    ft.Row(spacing=10, controls=[pildora("left"), pildora("center")]),
                    ft.Text("Se aplica a todas las canciones, en las dos vistas",
                            size=11, color=theme.THEME["text_muted"]),
                ]),
        ))

    boton_aa = ft.Container(
        right=16, bottom=24, width=56, height=56, ink=True, border_radius=18,
        alignment=ft.Alignment.CENTER, on_click=abrir_cuadro,
        bgcolor=theme.THEME["surface"],
        border=ft.Border.all(1, theme.THEME["border"]),
        content=ft.Text("Aa", size=20, weight=ft.FontWeight.BOLD,
                        color=theme.THEME["text"]))

    cuerpo.controls = _cuerpo(estado["size"], estado["align"], estado["modo"])
    columna = ft.Column(expand=True, spacing=0, controls=[
        centered_header(TITULO_REAL, left=back_button(lambda: None)),
        ft.Container(padding=ft.Padding.symmetric(horizontal=12, vertical=6),
                     content=toggle.build()),
        cuerpo,
    ])
    return ft.Stack(expand=True, controls=[columna, boton_aa])
