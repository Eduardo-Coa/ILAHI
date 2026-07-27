"""Maqueta: reorganizar las casillas de metadatos de «Editar letra» (Autor, Tono,
Ritmo, BPM, Capo) y sumar el campo «Álbum» que falta.

Hoy (``views.edit_view.EditLyricsScreen.build``): el renglón Ritmo/BPM/Capo tiene
anchos fijos (140+90+100 + espacios) SIN ``wrap``, así que en una pantalla angosta
Capo se sale — se ve tal cual en la maqueta "Hoy" de abajo, con el mismo ancho de
pantalla que usa la app real.

Propuesta: los mismos campos con ancho FLEXIBLE (``expand``, no píxeles fijos), así
nunca se salen sin importar el ancho de pantalla; agrupados como en el mockup que
pediste (Autor+Álbum · separador "Tono" · Círculo+Original+Capo · Ritmo+BPM).
"""

from __future__ import annotations
import flet as ft

import theme
from views.edit_view import _themed_field, _section_insert_row
from views.widgets import logo_header

NOMBRE = "Campos de metadatos (spike)"
DESCRIPCION = "Hoy (Capo se sale) vs. propuesta (Álbum + anchos flexibles, sin overflow)."


def _seccion(titulo: str, ancho: float | None = None) -> ft.Control:
    """Separador con etiqueta, como el «Tono» del mockup: texto chico + línea fina."""
    return ft.Column(spacing=4, controls=[
        ft.Text(titulo, size=12, color=theme.THEME["text_muted"]),
        ft.Container(height=1, bgcolor=theme.THEME["border"], width=ancho),
    ])


def _field(label: str, value: str = "", expand: int = 1) -> ft.TextField:
    """Igual a ``_themed_field`` pero con ancho FLEXIBLE en vez de fijo en píxeles."""
    campo = _themed_field(label, value)
    campo.width = None
    campo.expand = expand
    return campo


# --- Reproducción fiel de hoy (mismos anchos fijos, mismo Row sin wrap) --------
def _hoy() -> ft.Control:
    author = _themed_field("Autor", "Himnario Adventista")
    key = _themed_field("Tono (círculo)", "D", width=150)
    original_key = _themed_field("Tono original", "D", width=150)
    rhythm = _themed_field("Ritmo", "3/4", width=140)
    bpm = _themed_field("BPM", "", width=90)
    capo = _themed_field("Capo", "0", width=100)
    return ft.Column(spacing=12, controls=[
        author,
        ft.Row([key, original_key], spacing=10, wrap=True),
        ft.Row([rhythm, bpm, capo], spacing=10),   # sin wrap: esto es lo que desborda
    ])


# --- Propuesta: Álbum nuevo + anchos flexibles + agrupado como el mockup -------
def _propuesta() -> ft.Control:
    title = _field("Título", "067 - ¡Señor, yo te conozco!", expand=1)
    author = _field("Autor", "Himnario Adventista", expand=1)
    album = _field("Álbum", "", expand=1)
    key = _field("Círculo", "D", expand=1)
    original_key = _field("Original", "D", expand=1)
    capo = _field("Capo", "0", expand=1)
    rhythm = _field("Ritmo", "3/4", expand=1)
    bpm = _field("BPM", "", expand=1)
    return ft.Column(spacing=12, controls=[
        title,
        ft.Row([author, album], spacing=10),
        _seccion("Tono"),
        ft.Row([key, original_key, capo], spacing=10),
        ft.Row([rhythm, bpm], spacing=10),
    ])


# --- «Insertar sección»: hoy 5 botones en 2 filas (Estrofa/Coro/Puente/Interludio/
# Final); propuesta: solo Intro/Estrofa/Coro/Interludio, en UNA fila centrada. ------
_SECTION_INSERTS_NUEVO = ["Intro", "Estrofa", "Coro", "Interludio"]


def _section_insert_row_nuevo(field: ft.TextField) -> ft.Control:
    """Igual a ``_section_insert_row`` (misma lógica de inserción por cursor), pero
    con la lista recortada y en una sola fila centrada en vez de envolver en 2."""
    state = {"sel": None}

    def on_sel(e) -> None:
        sel = getattr(e, "selection", None)
        if sel is not None and sel.base_offset is not None:
            state["sel"] = (sel.base_offset, sel.extent_offset)
    field.on_selection_change = on_sel

    def insert(label: str) -> None:
        text = field.value or ""
        if state["sel"] is None:
            start = end = len(text)
        else:
            a, b = state["sel"]
            start, end = sorted((a, b))
            start = max(0, min(start, len(text)))
            end = max(0, min(end, len(text)))
        before, after = text[:start], text[end:]
        prefix = "\n" if before and not before.endswith("\n") else ""
        suffix = "" if after.startswith("\n") else "\n"
        header = f"[{label}]{suffix}"
        field.value = before + prefix + header + after
        pos = len(before) + len(prefix) + len(header)
        state["sel"] = (pos, pos)
        try:
            field.selection = ft.TextSelection(base_offset=pos, extent_offset=pos)
        except Exception:
            pass
        _safe_update_local(field)

    def _safe_update_local(control) -> None:
        try:
            control.update()
        except Exception:
            pass

    # Sin el ícono «+»: son 4 en una sola fila y el texto solo ya deja margen de
    # sobra (antes «Interludio» quedaba pegado al borde con el ícono + el espaciado).
    chips = [
        ft.Container(
            ink=True, border_radius=16, on_click=lambda _e, l=label: insert(l),
            padding=ft.Padding.symmetric(horizontal=12, vertical=6),
            bgcolor=theme.THEME["surface"],
            border=ft.Border.all(1, theme.THEME["border"]),
            content=ft.Text(label, size=12, color=theme.THEME["chord"]))
        for label in _SECTION_INSERTS_NUEVO
    ]
    return ft.Column(spacing=6, horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                     controls=[
        ft.Text("Insertar sección:", size=11, color=theme.THEME["text_muted"]),
        ft.Row(chips, wrap=False, spacing=6, alignment=ft.MainAxisAlignment.CENTER),
    ])


def _panel(titulo: str, color: str, contenido: ft.Control) -> ft.Control:
    return ft.Container(
        padding=12, bgcolor=theme.THEME["surface2"], border_radius=12,
        border=ft.Border.all(1, theme.THEME["border"]),
        content=ft.Column(spacing=10, controls=[
            ft.Text(titulo, size=12, weight=ft.FontWeight.BOLD, color=color),
            contenido,
        ]),
    )


def construir(page: ft.Page, db) -> ft.Control:
    return ft.Column(expand=True, spacing=0, controls=[
        logo_header(),
        ft.Column(expand=True, scroll=ft.ScrollMode.AUTO, spacing=14,
                  controls=[
            ft.Container(
                padding=ft.Padding.symmetric(horizontal=12, vertical=4),
                content=ft.Text(
                    "Mismo ancho de pantalla que la app real. Fijate que en \"hoy\" "
                    "Capo queda cortado a la derecha; en la propuesta no, sin "
                    "importar el ancho.",
                    size=11, color=theme.THEME["text_muted"]),
            ),
            ft.Container(padding=ft.Padding.symmetric(horizontal=12),
                        content=_panel("HOY", theme.THEME["danger"], _hoy())),
            ft.Container(padding=ft.Padding.symmetric(horizontal=12),
                        content=_panel("PROPUESTA", theme.THEME["accent"], _propuesta())),
            ft.Container(
                padding=ft.Padding.symmetric(horizontal=12, vertical=4),
                content=ft.Text(
                    "\"Insertar sección\": hoy son 5 botones en 2 filas (queda Puente y "
                    "Final); la propuesta deja solo Intro/Estrofa/Coro/Interludio, en "
                    "una sola fila centrada.",
                    size=11, color=theme.THEME["text_muted"]),
            ),
            ft.Container(padding=ft.Padding.symmetric(horizontal=12),
                        content=_panel("HOY", theme.THEME["danger"],
                                      _section_insert_row(ft.TextField(value="")))),
            ft.Container(padding=ft.Padding.symmetric(horizontal=12),
                        content=_panel("PROPUESTA", theme.THEME["accent"],
                                      _section_insert_row_nuevo(ft.TextField(value="")))),
        ]),
    ])
