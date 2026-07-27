"""Maqueta: la pestaña «Autores» pasa a llamarse «Álbumes».

Cambios respecto de la maqueta ``actual``:
  · El toggle dice «Álbumes | Canciones» en vez de «Autores | Canciones».
  · Estando en Álbumes, el buscador sugiere «Buscar álbum o autor…».
  · La lista mezcla ÁLBUMES y AUTORES, y el ícono los distingue: disco para el
    álbum (agrupa canciones de varios autores), persona para el autor.
  · «Himnario Adventista» va fijado al principio: es la biblioteca que viene
    incluida en la app.

Un álbum y un autor son datos DISTINTOS: una canción del Himnario Adventista (álbum)
puede ser de Martín Lutero (autor), y aparece bajo los dos. Eso implica un campo
``album`` nuevo en las canciones —con migración de base y lugar en el editor—, así
que esto es la maqueta de cómo se vería, no algo que ya funcione en la app.
"""

from __future__ import annotations
import flet as ft

import theme
from views.bottom_bar import build_bottom_bar
from views.search_field import search_pill
from views.widgets import (logo_header, SlidingToggle, list_row_card, key_badge,
                           accent_fab, FAB_CLEARANCE, SONG_ROW_HEIGHT)

NOMBRE = "Álbumes (antes Autores)"
DESCRIPCION = "Toggle «Álbumes | Canciones» y buscador «Buscar álbum o autor…»."

# Los textos que cambian, juntos para poder probar otras variantes de un vistazo.
ETIQUETA_ALBUMES = "Álbumes"
PISTA_ALBUMES = "Buscar álbum o autor…"
PISTA_CANCIONES = "Buscar himno o autor…"


def _fila_entrada(entrada: dict) -> ft.Control:
    """Fila de la pestaña Álbumes: sirve tanto para un álbum como para un autor.

    Lo único que cambia entre los dos es el ícono —disco o persona— y la palabra del
    menú; el formato de tres líneas es el mismo que el de una canción."""
    es_album = entrada["tipo"] == "album"
    fav = bool(entrada.get("favorite"))
    if es_album:
        icono = ft.Icons.ALBUM if fav else ft.Icons.ALBUM_OUTLINED
    else:
        icono = ft.Icons.PERSON if fav else ft.Icons.PERSON_OUTLINE
    return list_row_card([
        ft.IconButton(
            icon=icono,
            icon_color=theme.THEME["accent"] if fav else theme.THEME["text_muted"],
            icon_size=22,
            tooltip="Quitar de favoritos" if fav else "Añadir a favoritos"),
        ft.Container(
            expand=True, ink=True, border_radius=10,
            padding=ft.Padding.symmetric(horizontal=4, vertical=4),
            content=ft.Column([
                ft.Text(entrada["name"], size=16, weight=ft.FontWeight.W_500,
                        color=theme.THEME["text"], no_wrap=True),
                ft.Text("Canciones:", size=12, color=theme.THEME["text_muted"],
                        no_wrap=True),
                ft.Row([
                    ft.Icon(ft.Icons.LIBRARY_MUSIC_OUTLINED, size=12,
                            color=theme.THEME["text_muted"]),
                    ft.Text(str(entrada["song_count"]), size=11,
                            color=theme.THEME["text_muted"]),
                ], spacing=4, tight=True),
            ], spacing=1, tight=True)),
        ft.PopupMenuButton(
            icon=ft.Icons.MORE_VERT, icon_color=theme.THEME["text_muted"],
            items=[ft.PopupMenuItem(
                content="Exportar álbum" if es_album else "Exportar autor")]),
    ], key=f"{entrada['tipo']}-{entrada['name']}")


def _fila_cancion(cancion: dict) -> ft.Control:
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


def construir(page: ft.Page, db) -> ft.Control:
    canciones = db.list_songs()
    # Álbumes y autores juntos, con el Himnario Adventista fijado al principio.
    entradas = db.list_albumes_y_autores()
    estado = {"i": 0}                    # 0 Álbumes · 1 Canciones

    buscador = search_pill(PISTA_ALBUMES, lambda e: None)
    campo = buscador.content.controls[1]
    toggle = SlidingToggle(ETIQUETA_ALBUMES, "Canciones",
                           on_left=lambda: ir(0), on_right=lambda: ir(1),
                           active="left")
    cuerpo = ft.Container(expand=True)
    barra = ft.Row(spacing=0)

    def ir(i: int) -> None:
        estado["i"] = i
        toggle.set_active("right" if i == 1 else "left")
        campo.hint_text = PISTA_CANCIONES if i == 1 else PISTA_ALBUMES
        cuerpo.content = ft.ListView(
            expand=True, padding=ft.Padding.only(bottom=FAB_CLEARANCE),
            controls=([_fila_cancion(c) for c in canciones] if i == 1
                      else [_fila_entrada(e) for e in entradas]))
        page.update()

    ir(0)
    columna = ft.Column([
        logo_header(),
        ft.Container(content=toggle.build()),
        buscador,
        cuerpo,
        build_bottom_bar("library", lambda k: None, row=barra),
    ], expand=True, spacing=0)
    fab = ft.Container(right=18, bottom=90,
                       content=accent_fab(ft.Icons.ADD, "Añadir", lambda _e: None))
    return ft.Stack(expand=True, controls=[columna, fab])
