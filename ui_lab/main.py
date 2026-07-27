"""Laboratorio de interfaz de Ilahi: probar maquetas SIN tocar la app ni tus canciones.

    flet run ui_lab/main.py            (escritorio)
    flet build apk ui_lab/main.py      (si alguna vez querés verlo en el teléfono)

Arriba hay una barra fina con el selector de maquetas y el tema; abajo, la maqueta
elegida dentro de un lienzo del tamaño de un teléfono. La barra se puede ocultar para
ver la pantalla limpia.

SEGURIDAD: este laboratorio no abre la base de datos. Importar ``database`` desde aquí
revienta a propósito (ver ``_prohibir_base_real``), para que ninguna prueba pueda
estropear las canciones de verdad.
"""

from __future__ import annotations
import sys
from pathlib import Path

# Permite ejecutarlo como `flet run ui_lab/main.py` desde la raíz del proyecto.
RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))


def _prohibir_base_real() -> None:
    """Deja una trampa en ``sys.modules``: si una maqueta importa ``database``, falla
    con un mensaje claro en vez de abrir el archivo real de canciones."""
    class _Prohibido:
        def __getattr__(self, nombre):
            raise RuntimeError(
                "El laboratorio de interfaz no puede usar la base real. "
                "Usá la BaseFalsa de ui_lab/datos.py.")

    sys.modules.setdefault("database", _Prohibido())
    sys.modules.setdefault("database.db", _Prohibido())


_prohibir_base_real()

import flet as ft                      # noqa: E402  (después de fijar sys.path)

import theme                           # noqa: E402
from ui_lab.datos import BaseFalsa     # noqa: E402
from ui_lab.maquetas import MAQUETAS   # noqa: E402


def main(page: ft.Page) -> None:
    page.title = "Ilahi · laboratorio de interfaz"
    page.padding = 0

    db = BaseFalsa()
    estado = {"maqueta": 0, "barra": True}   # 0 = primera de MAQUETAS

    def pintar_pagina() -> None:
        """Mismos colores de página que la app (fondo, modo y ColorScheme Material)."""
        page.bgcolor = theme.THEME["bg"]
        page.theme_mode = ft.ThemeMode.DARK if theme.is_dark() else ft.ThemeMode.LIGHT
        page.theme = ft.Theme(color_scheme=ft.ColorScheme(
            primary=theme.THEME["accent"],
            on_primary=theme.THEME["bg"],
            secondary=theme.THEME["chord"]))

    pintar_pagina()

    if page.platform is not None and page.platform.is_desktop():
        page.window.width = 412        # mismo lienzo que usa la app en escritorio
        page.window.height = 915
        page.window.min_width = 320
        page.window.min_height = 640

    lienzo = ft.Container(expand=True)

    def render() -> None:
        modulo = MAQUETAS[estado["maqueta"]]
        lienzo.content = modulo.construir(page, db)
        etiqueta.value = modulo.NOMBRE
        detalle.value = getattr(modulo, "DESCRIPCION", "")
        page.update()

    def elegir(i: int) -> None:
        estado["maqueta"] = i
        render()

    def cambiar_tema(nombre: str) -> None:
        theme.set_theme(nombre)
        pintar_pagina()
        render()                        # la maqueta se rehace con los colores nuevos

    def alternar_barra(_e=None) -> None:
        estado["barra"] = not estado["barra"]
        barra.visible = estado["barra"]
        pestania.visible = not estado["barra"]
        page.update()

    etiqueta = ft.Text("", size=12, weight=ft.FontWeight.W_600,
                       color=theme.THEME["text"], no_wrap=True)
    detalle = ft.Text("", size=10, color=theme.THEME["text_muted"], no_wrap=True)

    barra = ft.Container(
        bgcolor="#101010", padding=ft.Padding.symmetric(horizontal=8, vertical=4),
        content=ft.Row(
            vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=4,
            controls=[
                ft.PopupMenuButton(
                    icon=ft.Icons.DASHBOARD_CUSTOMIZE, icon_color="#cccccc",
                    tooltip="Elegir maqueta",
                    items=[ft.PopupMenuItem(content=m.NOMBRE,
                                            on_click=lambda _e, i=i: elegir(i))
                           for i, m in enumerate(MAQUETAS)]),
                ft.Column([etiqueta, detalle], spacing=0, tight=True, expand=True),
                ft.PopupMenuButton(
                    icon=ft.Icons.PALETTE_OUTLINED, icon_color="#cccccc",
                    tooltip="Tema",
                    items=[ft.PopupMenuItem(content=n,
                                            on_click=lambda _e, n=n: cambiar_tema(n))
                           for n in theme.USER_THEMES]),
                ft.IconButton(ft.Icons.KEYBOARD_ARROW_UP, icon_color="#cccccc",
                              icon_size=18, tooltip="Ocultar esta barra",
                              on_click=alternar_barra),
            ]))

    # Pestañita para traer la barra de vuelta cuando está oculta.
    pestania = ft.Container(
        visible=False, bgcolor="#101010", alignment=ft.Alignment.CENTER, height=14,
        on_click=alternar_barra,
        content=ft.Icon(ft.Icons.KEYBOARD_ARROW_DOWN, size=12, color="#cccccc"))

    page.add(ft.Column([barra, pestania, lienzo], expand=True, spacing=0))
    render()


ft.run(main)
