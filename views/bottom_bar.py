"""Barra inferior de navegación: Biblioteca · Favoritos · Listas · Ajustes.

Compartida por la pantalla de canciones y la de listas, para que el panel no
desaparezca al cambiar de sección.

Se arma con un ``Row`` propio en vez de ``ft.NavigationBar`` porque el diseño no
lleva la «píldora» de Material y así los colores salen del ``THEME``.

Cada pestaña lleva ``key`` estable: sin ella Flet reconcilia los hijos por
posición y puede reutilizar un control (y su handler) al reconstruir la fila.
"""

from __future__ import annotations
from typing import Callable
import flet as ft

import theme

# (clave, etiqueta, ícono). Íconos Material: los glifos Unicode exóticos salen ▯.
TABS = [
    ("library", "Biblioteca", ft.Icons.LIBRARY_MUSIC),
    ("favorites", "Favoritos", ft.Icons.FAVORITE_BORDER),
    ("setlists", "Listas", ft.Icons.FORMAT_LIST_BULLETED),
    ("settings", "Ajustes", ft.Icons.SETTINGS),
]


def tab_button(key: str, label: str, icon: str, active: bool,
               on_select: Callable[[str], None]) -> ft.Control:
    """Una pestaña: dorada si está activa, gris si no."""
    color = theme.THEME["accent"] if active else theme.THEME["text_muted"]
    return ft.Container(
        key=f"tab-{key}",
        expand=True, ink=True, border_radius=10,
        padding=ft.Padding.symmetric(vertical=6),
        on_click=lambda _e: on_select(key),
        content=ft.Column([
            ft.Icon(icon, size=22, color=color),
            ft.Text(label, size=11, color=color,
                    weight=ft.FontWeight.W_500 if active else ft.FontWeight.NORMAL),
        ], spacing=3, tight=True,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER),
    )


def fill_bar(row: ft.Row, active: str, on_select: Callable[[str], None]) -> ft.Row:
    """Rellena (o repinta) la fila de pestañas marcando la activa."""
    row.controls = [tab_button(k, label, icon, k == active, on_select)
                    for k, label, icon in TABS]
    return row


def build_bottom_bar(active: str, on_select: Callable[[str], None],
                     row: ft.Row | None = None) -> ft.Control:
    """Panel anclado abajo, con las esquinas superiores redondeadas.

    El borde debe ser **uniforme**: Flutter no acepta ``borderRadius`` sobre un
    borde de un solo lado.
    """
    row = fill_bar(row if row is not None else ft.Row(spacing=0), active, on_select)
    return ft.Container(
        bgcolor=theme.THEME["surface"],
        border=ft.Border.all(1, theme.THEME["border"]),
        border_radius=ft.BorderRadius.only(top_left=18, top_right=18),
        padding=ft.Padding.symmetric(vertical=6),
        content=row,
    )
