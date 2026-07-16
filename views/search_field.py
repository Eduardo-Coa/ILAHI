"""Buscador tipo píldora y chip de filtro, compartidos por Canciones y Autores.

La píldora es un ``Container`` propio con un ``TextField`` sin bordes: el
``suffix`` de ``ft.TextField`` **no se pinta en Android**, así que la lupa y el
menú de filtros van como hermanos dentro de un ``Row``.
"""

from __future__ import annotations
from typing import Callable
import flet as ft

import theme


def search_pill(hint: str, on_change: Callable, trailing: ft.Control | None = None,
                value: str = "") -> ft.Control:
    """Píldora de búsqueda: lupa · campo · (opcional) control de filtros a la derecha."""
    field = ft.TextField(
        value=value, hint_text=hint, on_change=on_change,
        expand=True, border=ft.InputBorder.NONE, dense=True,
        content_padding=ft.Padding.symmetric(vertical=10),
        color=theme.THEME["text"], cursor_color=theme.THEME["accent"],
        hint_style=ft.TextStyle(color=theme.THEME["text_muted"], size=15),
    )
    controls: list[ft.Control] = [
        ft.Icon(ft.Icons.SEARCH, size=20, color=theme.THEME["text_muted"]),
        field,
    ]
    if trailing is not None:
        controls.append(trailing)
    return ft.Container(
        margin=ft.Margin.symmetric(horizontal=12, vertical=6),
        padding=ft.Padding.only(left=16, right=6 if trailing is not None else 16),
        bgcolor=theme.THEME["surface"], border_radius=28,
        border=ft.Border.all(1, theme.THEME["border"]),
        content=ft.Row(
            vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=8,
            controls=controls,
        ),
    )


def filter_menu(items: list[ft.PopupMenuItem]) -> ft.Control:
    """Embudo de filtros que cuelga a la derecha de la píldora."""
    return ft.PopupMenuButton(icon=ft.Icons.FILTER_ALT_OUTLINED,
                              icon_color=theme.THEME["text_muted"],
                              tooltip="Filtros", items=items)


def filter_chip(label: str, on_clear: Callable[[], None],
                visible: bool = True) -> ft.Container:
    """Chip del filtro activo, con ✕ para quitarlo."""
    return ft.Container(
        visible=visible,
        margin=ft.Margin.only(left=12, right=12, bottom=2),
        padding=ft.Padding.only(left=12, right=2),
        bgcolor=theme.THEME["chord_bg"], border_radius=20,
        border=ft.Border.all(1, theme.THEME["chord"]),
        content=ft.Row(tight=True, spacing=6, controls=[
            ft.Icon(ft.Icons.PERSON_OUTLINE, size=15, color=theme.THEME["chord"]),
            ft.Text(label, size=13, color=theme.THEME["chord"]),
            ft.IconButton(icon=ft.Icons.CLOSE, icon_size=15,
                          icon_color=theme.THEME["text_muted"],
                          tooltip="Quitar filtro",
                          on_click=lambda _e: on_clear()),
        ]),
    )
