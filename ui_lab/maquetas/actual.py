"""Maqueta de REFERENCIA: la interfaz tal como está hoy en la app.

Está aquí para comparar: cualquier propuesta nueva se mira contra esta. Reproduce el
armado real del shell —chrome FIJO arriba (logo · toggle · buscador), solo el cuerpo
se desliza, barra abajo y ＋ flotante— usando los widgets de verdad, así que se ve
igual que la app.
"""

from __future__ import annotations
import flet as ft

import theme
from views.bottom_bar import build_bottom_bar
from views.search_field import search_pill
from views.widgets import (logo_header, SlidingToggle, list_row_card, key_badge,
                           accent_fab, FAB_CLEARANCE, SONG_ROW_HEIGHT)

NOMBRE = "Actual (referencia)"
DESCRIPCION = "Chrome fijo arriba; solo el cuerpo se desliza. Favoritos no lleva toggle."


def _fila(cancion: dict) -> ft.Control:
    """Fila de canción, con la misma pinta que en la app."""
    fav = bool(cancion.get("favorite"))
    return list_row_card([
        ft.IconButton(
            icon=ft.Icons.STAR if fav else ft.Icons.MUSIC_NOTE,
            icon_color=theme.THEME["accent"] if fav else theme.THEME["text_muted"],
            icon_size=22),
        ft.Container(
            expand=True, ink=True, border_radius=10,
            padding=ft.Padding.symmetric(horizontal=4, vertical=4),
            content=ft.Column([
                ft.Text(cancion["title"], size=16, weight=ft.FontWeight.W_500,
                        color=theme.THEME["text"], no_wrap=True),
                ft.Text(cancion.get("author") or "Desconocido", size=12,
                        color=theme.THEME["text_muted"], no_wrap=True),
                ft.Row([
                    ft.Icon(ft.Icons.GRAPHIC_EQ, size=12,
                            color=theme.THEME["text_muted"]),
                    ft.Text(cancion.get("rhythm") or "—", size=11,
                            color=theme.THEME["text_muted"]),
                ], spacing=4, tight=True),
            ], spacing=1, tight=True)),
        key_badge(cancion.get("key")),
        ft.PopupMenuButton(icon=ft.Icons.MORE_VERT,
                           icon_color=theme.THEME["text_muted"],
                           items=[ft.PopupMenuItem(content="Editar")]),
    ], key=f"song-{cancion['id']}", height=SONG_ROW_HEIGHT)


def _lista(canciones: list[dict]) -> ft.Control:
    return ft.ListView(expand=True, controls=[_fila(c) for c in canciones],
                       padding=ft.Padding.only(bottom=FAB_CLEARANCE))


def construir(page: ft.Page, db) -> ft.Control:
    """Arma la maqueta. ``db`` es la ``BaseFalsa`` del laboratorio."""
    canciones = db.list_songs()
    favoritas = [c for c in canciones if c["favorite"]]

    estado = {"i": 1}       # 0 Autores · 1 Canciones · 2 Favoritos

    toggle = SlidingToggle("Autores", "Canciones",
                           on_left=lambda: ir(0), on_right=lambda: ir(1),
                           active="right")
    toggle_holder = ft.Container(content=toggle.build(), visible=True)
    buscador = search_pill("Buscar himno o autor…", lambda e: None)
    cuerpo = ft.Container(expand=True, content=_lista(canciones))
    barra = ft.Row(spacing=0)

    def ir(i: int) -> None:
        estado["i"] = i
        toggle_holder.visible = i in (0, 1)
        if i in (0, 1):
            toggle.set_active("right" if i == 1 else "left")
        cuerpo.content = _lista(favoritas if i == 2 else canciones)
        page.update()

    barra_ctrl = build_bottom_bar("library", lambda k: ir(2 if k == "favorites" else 1),
                                  row=barra)
    columna = ft.Column([
        logo_header(),
        toggle_holder,
        buscador,
        cuerpo,
        barra_ctrl,
    ], expand=True, spacing=0)
    fab = ft.Container(right=18, bottom=90,
                       content=accent_fab(ft.Icons.ADD, "Añadir", lambda _e: None))
    return ft.Stack(expand=True, controls=[columna, fab])
