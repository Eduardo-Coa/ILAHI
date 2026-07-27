"""Maqueta: SOLO el botón «Guardar cambios» flota (como el ＋ de «Añadir»), no un
panel/barra que lo envuelve.

Intento anterior (ya descartado): el botón se sacaba del área con scroll y se ponía
como HERMANO fijo al final de la columna — funcionaba (nunca se tapaba), pero seguía
ocupando su propia fila fija en el layout, así que se veía como una barra/panel
pegada abajo, no como algo flotando sobre el contenido.

Esta vez: mismo patrón que ``views.widgets.accent_fab`` / el ＋ de «Añadir»
(``views/song_list_view.py::_fab``) — ``ft.Stack`` con el contenido que hace scroll
como primer hijo y el botón como segundo hijo, posicionado con ``left/right/bottom``
por ENCIMA del contenido (no reservándole su propia fila). El contenido con scroll
lleva ``padding`` inferior (``_CLEARANCE``) para que su último elemento pueda
desplazarse por completo por encima del botón, y nunca quede tapado detrás.
"""

from __future__ import annotations
import flet as ft

import theme
from views.edit_view import _themed_field, _pill_button, _section_insert_row
from views.widgets import logo_header, back_button, centered_header

NOMBRE = "Botón Guardar flotante (spike)"
DESCRIPCION = "Solo el botón flota sobre el contenido, como el ＋ de Añadir — no un panel."

# Alto del botón (46) + aire abajo (16) + margen antes del contenido (16).
_CLEARANCE = 78


def _campo_ancho(label: str, value: str = "") -> ft.TextField:
    campo = _themed_field(label, value)
    campo.width = None
    campo.expand = True
    return campo


def _seccion_tono() -> ft.Control:
    return ft.Column(spacing=4, controls=[
        ft.Text("Tono", size=12, color=theme.THEME["text_muted"]),
        ft.Container(height=1, bgcolor=theme.THEME["border"]),
    ])


def _cuerpo_editar_letra() -> ft.Control:
    """Réplica del cuerpo de EditLyricsScreen (campos + caja de letra + chips),
    para probar el botón flotante en un contexto real de scroll."""
    caja = ft.Container(
        height=260, bgcolor=theme.THEME["surface"], border_radius=16,
        border=ft.Border.all(1, theme.THEME["border"]),
        padding=14,
        content=ft.Text(
            "[Estrofa 1]\nG          Em C6 D7 G  C G     C6    D7 G\n"
            "¡Señor, yo te conozco! La noche azul, serena,\n"
            "        Em C6 D7 G  C  Em Dsus4 D   G\n"
            "me dice desde lejos: \"Tu Dios se esconde allí\".",
            font_family=theme.FONT_MONO, size=13, color=theme.THEME["text"]))
    return ft.Column(spacing=12, controls=[
        _campo_ancho("Título", "067 - ¡Señor, yo te conozco!"),
        ft.Row([_campo_ancho("Autor", "Himnario Adventista"),
               _campo_ancho("Álbum", "")], spacing=10),
        _seccion_tono(),
        ft.Row([_campo_ancho("Círculo", "G"), _campo_ancho("Original", "G"),
               _campo_ancho("Capo", "0")], spacing=10),
        ft.Row([_campo_ancho("Ritmo", "4/4"), _campo_ancho("BPM", "")], spacing=10),
        ft.Text("Los acordes de las líneas que no cambies se conservan.",
                size=12, color=theme.THEME["text_muted"]),
        caja,
        _section_insert_row(ft.TextField(value="")),
    ])


def construir(page: ft.Page, db) -> ft.Control:
    cuerpo = _cuerpo_editar_letra()
    contenido = ft.Column(
        expand=True, scroll=ft.ScrollMode.AUTO,
        controls=[ft.Container(
            padding=ft.Padding.only(left=12, right=12, top=12, bottom=_CLEARANCE),
            content=cuerpo)])

    guardar_flotante = ft.Container(
        left=12, right=12, bottom=16,
        content=_pill_button(ft.Icons.CHECK, "Guardar cambios", lambda _e: None))

    pantalla = ft.Stack(expand=True, controls=[contenido, guardar_flotante])

    header = centered_header("Editar letra", left=back_button(lambda: None))
    return ft.Column(expand=True, spacing=0, controls=[
        logo_header(),
        ft.Container(
            padding=ft.Padding.symmetric(horizontal=12, vertical=4),
            content=ft.Text(
                "El botón flota SOBRE el contenido (Stack), no reserva su propia "
                "fila. Desplazá hasta el final: el último chip queda visible por "
                "completo por encima del botón, nunca tapado.",
                size=11, color=theme.THEME["text_muted"]),
        ),
        ft.Container(expand=True, bgcolor=theme.THEME["bg"], content=ft.Column(
            expand=True, spacing=0, controls=[header, pantalla])),
    ])
