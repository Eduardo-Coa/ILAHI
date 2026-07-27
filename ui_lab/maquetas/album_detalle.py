"""Maqueta: tocar un álbum (o un autor) abre su VISTA PROPIA.

Hoy, tocar «Himnario Adventista» en la pestaña Álbumes se queda en la misma vista:
filtra la lista en el sitio y aparece un chip naranja con el nombre. La propuesta
lo reemplaza por una pantalla dedicada, con la misma forma que el detalle de una
lista (``views.setlist_view.SetlistDetailScreen``): ← volver, el nombre centrado
arriba, las canciones debajo… y donde la lista tiene el ▶ de reproducir, aquí va
un ＋ para agregar canciones a ese álbum (o a ese autor).

El ＋ abre un cuadro con dos caminos, como el ＋ de Canciones:
  · «Nueva canción»      → el formulario de siempre, con el álbum/autor ya puesto.
  · «Elegir existentes»  → selector estilo lista (buscador + filas con ＋) que le
                           asigna ese álbum/autor a las canciones que toques.

Se recorre entera: tocá un álbum, después el ＋, después «Elegir existentes».
Los datos son falsos y viven en memoria (regla del laboratorio); lo que se toque
aquí no altera ninguna canción de verdad.
"""

from __future__ import annotations
import flet as ft

import theme
from views.widgets import (logo_header, back_button, centered_header, list_row_card,
                           key_badge, accent_fab, sheet_dialog, sheet_option,
                           show_toast, _safe_update, SlidingToggle,
                           FAB_CLEARANCE, SONG_ROW_HEIGHT)
from views.search_field import search_pill

NOMBRE = "Detalle de álbum/autor (spike)"
DESCRIPCION = "Tocar un álbum abre su vista propia, con ＋ para agregar canciones."

# Solo para sacar capturas: "album" o "autor" arranca directo en esa vista, sin tener
# que tocar la fila. None = flujo normal (empieza en la lista de Álbumes).
_ARRANCAR_EN: str | None = None


def _icono_de(tipo: str, fav: bool = False) -> str:
    """Disco para álbum, persona para autor (igual que la lista de Álbumes)."""
    if tipo == "album":
        return ft.Icons.ALBUM if fav else ft.Icons.ALBUM_OUTLINED
    return ft.Icons.PERSON if fav else ft.Icons.PERSON_OUTLINE


def _campo_de(tipo: str) -> str:
    """Columna de ``songs`` que agrupa a esa entrada."""
    return "album" if tipo == "album" else "author"


def _etiqueta_de(tipo: str) -> str:
    return "álbum" if tipo == "album" else "autor"


# ---------------------------------------------------------------------------
# Filas
# ---------------------------------------------------------------------------

def _fila_entrada(entrada: dict, on_open) -> ft.Control:
    """Fila de la lista de Álbumes: al tocarla se abre su vista propia."""
    tipo = entrada["tipo"]
    fav = bool(entrada.get("favorite"))
    return list_row_card([
        ft.IconButton(
            icon=_icono_de(tipo, fav), icon_size=22,
            icon_color=theme.THEME["accent"] if fav else theme.THEME["text_muted"]),
        ft.Container(
            expand=True, ink=True, border_radius=10,
            on_click=lambda _e: on_open(entrada),
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
        ft.PopupMenuButton(icon=ft.Icons.MORE_VERT,
                           icon_color=theme.THEME["text_muted"],
                           items=[ft.PopupMenuItem(content="Editar nombre")]),
    ], key=f"{tipo}-{entrada['name']}")


def _fila_cancion(cancion: dict) -> ft.Control:
    """Fila de canción dentro del detalle: igual que en la biblioteca."""
    fav = bool(cancion.get("favorite"))
    return list_row_card([
        ft.IconButton(
            icon=ft.Icons.STAR if fav else ft.Icons.MUSIC_NOTE, icon_size=22,
            icon_color=theme.THEME["accent"] if fav else theme.THEME["text_muted"]),
        ft.Container(
            expand=True, ink=True, border_radius=10,
            padding=ft.Padding.symmetric(horizontal=4, vertical=4),
            content=ft.Column([
                ft.Text(cancion["title"], size=16, weight=ft.FontWeight.W_500,
                        color=theme.THEME["text"], no_wrap=True),
                ft.Text(cancion.get("author") or cancion.get("album") or "Desconocido",
                        size=12, color=theme.THEME["text_muted"], no_wrap=True),
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


def _fila_seleccionable(cancion: dict, on_add) -> ft.Control:
    """Fila del selector: sin favorito ni ritmo, con el badge ＋ a la derecha
    (mismo diseño que el selector de canciones de una lista)."""
    return list_row_card([
        ft.Container(width=40, alignment=ft.Alignment.CENTER,
                     content=ft.Icon(ft.Icons.MUSIC_NOTE, size=22,
                                     color=theme.THEME["text_muted"])),
        ft.Container(
            expand=True, padding=ft.Padding.symmetric(horizontal=4, vertical=4),
            content=ft.Column([
                ft.Text(cancion["title"], size=16, weight=ft.FontWeight.W_500,
                        color=theme.THEME["text"], no_wrap=True),
                # Igual que en la biblioteca: si no hay autor se cae al ÁLBUM antes
                # que a «Desconocido» — si no, los 628 himnos (que tienen álbum y no
                # autor) se leían todos como «Desconocido» aquí dentro.
                ft.Text(cancion.get("author") or cancion.get("album") or "Desconocido",
                        size=12, color=theme.THEME["text_muted"], no_wrap=True),
            ], spacing=1, tight=True)),
        ft.Container(
            width=52, height=52, ink=True, alignment=ft.Alignment.CENTER,
            border=ft.Border.all(1, theme.THEME["chord"]), border_radius=12,
            bgcolor=theme.THEME["chord_bg"], tooltip="Agregar",
            on_click=lambda _e: on_add(cancion),
            content=ft.Column([
                ft.Icon(ft.Icons.ADD, size=20, color=theme.THEME["chord"]),
                ft.Text("Agregar", size=8, color=theme.THEME["text_muted"]),
            ], spacing=0, tight=True,
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER)),
    ], key=f"pick-{cancion['id']}", height=SONG_ROW_HEIGHT)


# ---------------------------------------------------------------------------
# Maqueta
# ---------------------------------------------------------------------------

def construir(page: ft.Page, db) -> ft.Control:
    lienzo = ft.Container(expand=True)

    # -- 1) Lista de álbumes y autores (como está hoy, salvo a dónde lleva tocar) --
    def pantalla_albumes() -> ft.Control:
        toggle = SlidingToggle("Álbumes", "Canciones",
                               on_left=lambda: None, on_right=lambda: None,
                               active="left")
        lista = ft.ListView(
            expand=True, padding=ft.Padding.only(bottom=FAB_CLEARANCE),
            controls=[_fila_entrada(e, abrir_detalle)
                      for e in db.list_albumes_y_autores()])
        return ft.Column(expand=True, spacing=0, controls=[
            logo_header(),
            ft.Container(content=toggle.build()),
            search_pill("Buscar álbum o autor…", lambda e: None),
            lista,
        ])

    # -- 2) Vista propia del álbum/autor (la propuesta) --
    def pantalla_detalle(entrada: dict) -> ft.Control:
        tipo, nombre = entrada["tipo"], entrada["name"]
        canciones = db.list_songs(filters={_campo_de(tipo): nombre})
        cuerpo: ft.Control
        if canciones:
            cuerpo = ft.ListView(
                expand=True, padding=ft.Padding.only(top=4, bottom=FAB_CLEARANCE),
                controls=[_fila_cancion(c) for c in canciones])
        else:
            cuerpo = ft.Container(
                expand=True, padding=24,
                content=ft.Text(
                    f"(este {_etiqueta_de(tipo)} no tiene canciones — "
                    "tocá ＋ para agregar)",
                    color=theme.THEME["text_muted"]))
        columna = ft.Column(expand=True, spacing=0, controls=[
            centered_header(nombre, left=back_button(volver_a_albumes)),
            cuerpo,
        ])
        # Donde el detalle de una lista tiene el ▶, aquí va el ＋.
        fab = ft.Container(
            right=18, bottom=24,
            content=accent_fab(ft.Icons.ADD, f"Agregar canciones a este {_etiqueta_de(tipo)}",
                               lambda _e: abrir_cuadro_agregar(entrada)))
        return ft.Stack(expand=True, controls=[columna, fab])

    # -- 3) El cuadro del ＋: nueva canción · elegir de la biblioteca --
    def abrir_cuadro_agregar(entrada: dict) -> None:
        tipo = entrada["tipo"]

        def nueva(_e=None) -> None:
            page.pop_dialog()
            show_toast(page, f"(maqueta) «Nueva canción» con el {_etiqueta_de(tipo)} "
                             f"«{entrada['name']}» ya puesto")

        def elegir(_e=None) -> None:
            page.pop_dialog()
            abrir_selector(entrada)

        page.show_dialog(sheet_dialog(
            title=f"Agregar a «{entrada['name']}»",
            content_padding=ft.Padding.only(left=8, right=8, bottom=8),
            content=ft.Column(tight=True, spacing=2, controls=[
                sheet_option(ft.Icons.ADD, "Nueva canción",
                             f"Escribe o pega la letra, con el {_etiqueta_de(tipo)} puesto",
                             nueva),
                sheet_option(ft.Icons.LIBRARY_MUSIC, "Elegir existentes",
                             "De las canciones que ya tienes", elegir),
            ])))

    # -- 4) Selector: asigna ese álbum/autor a lo que toques --
    def abrir_selector(entrada: dict) -> None:
        tipo, nombre = entrada["tipo"], entrada["name"]
        campo = _campo_de(tipo)
        estado = {"query": ""}
        lista = ft.ListView(expand=True, controls=[])

        def agregar(cancion: dict) -> None:
            db.set_campo(cancion["id"], campo, nombre)
            refill()
            show_toast(page, f"✓ «{cancion['title']}» agregada a «{nombre}»")

        def refill() -> None:
            # Solo las que TODAVÍA no pertenecen a esta entrada.
            candidatas = [c for c in db.list_songs(estado["query"])
                          if c.get(campo) != nombre]
            lista.controls = ([_fila_seleccionable(c, agregar) for c in candidatas]
                              or [ft.Container(padding=20, content=ft.Text(
                                  "(no hay más canciones para agregar)",
                                  color=theme.THEME["text_muted"]))])
            _safe_update(lista)

        def on_query(e) -> None:
            estado["query"] = e.control.value or ""
            refill()

        refill()
        lienzo.content = ft.Column(expand=True, spacing=0, controls=[
            centered_header(f"Agregar al {_etiqueta_de(tipo)}",
                            left=back_button(lambda: abrir_detalle(entrada))),
            search_pill("Buscar canción…", on_query, ft.Container(width=2)),
            lista,
        ])
        page.update()

    # -- navegación de la maqueta --
    def abrir_detalle(entrada: dict) -> None:
        lienzo.content = pantalla_detalle(entrada)
        page.update()

    def volver_a_albumes() -> None:
        lienzo.content = pantalla_albumes()
        page.update()

    lienzo.content = pantalla_albumes()
    if _ARRANCAR_EN:                      # solo para capturas; None = flujo normal
        entrada = next(e for e in db.list_albumes_y_autores()
                       if e["tipo"] == _ARRANCAR_EN)
        lienzo.content = pantalla_detalle(entrada)
    return lienzo
