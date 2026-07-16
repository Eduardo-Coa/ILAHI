"""Pantalla de Ajustes (solo la parte visual, por ahora).

Sigue el mismo lenguaje de las barras de la biblioteca (canción/autor/lista):
tarjeta ``surface`` con ícono a la izquierda, título + subtítulo, y un control a
la derecha (valor, ▸ o interruptor). Las filas van agrupadas por secciones
(«Apariencia», «Edición», «Datos», «Acerca de»).

Las interacciones (cambiar el valor, mover el interruptor, exportar…) se conectan
después; aquí solo se arma la maqueta visual.
"""

from __future__ import annotations
from typing import Callable
import flet as ft

import theme
from views.bottom_bar import build_bottom_bar


# ---------------------------------------------------------------------------
# Piezas visuales
# ---------------------------------------------------------------------------

def _section(text: str) -> ft.Control:
    """Rótulo tenue que encabeza un grupo de ajustes."""
    return ft.Container(
        padding=ft.Padding.only(left=22, top=18, bottom=4),
        content=ft.Text(text.upper(), size=12, weight=ft.FontWeight.W_600,
                        color=theme.THEME["text_muted"]),
    )


def _row(icon: str, title: str, subtitle: str | None = None,
         trailing: ft.Control | None = None,
         on_click: Callable | None = None) -> ft.Control:
    """Fila de ajuste con el mismo formato que la barra de canción:
    ícono a la izquierda · título (+ subtítulo) · control a la derecha."""
    info: list[ft.Control] = [
        ft.Text(title, size=16, weight=ft.FontWeight.W_500,
                color=theme.THEME["text"], no_wrap=True),
    ]
    if subtitle:
        info.append(ft.Text(subtitle, size=12, color=theme.THEME["text_muted"]))
    controls: list[ft.Control] = [
        ft.Container(width=44, height=44, alignment=ft.Alignment.CENTER,
                     content=ft.Icon(icon, size=22, color=theme.THEME["accent"])),
        ft.Container(expand=True, padding=ft.Padding.symmetric(horizontal=4),
                     content=ft.Column(info, spacing=2, tight=True)),
    ]
    if trailing is not None:
        controls.append(trailing)
    return ft.Container(
        bgcolor=theme.THEME["surface"], border_radius=14,
        padding=ft.Padding.symmetric(horizontal=4, vertical=8),
        margin=ft.Margin.symmetric(horizontal=12, vertical=4),
        ink=on_click is not None, on_click=on_click,
        content=ft.Row(controls, vertical_alignment=ft.CrossAxisAlignment.CENTER,
                       spacing=2),
    )


def _chevron() -> ft.Control:
    """Flecha ▸ de «entra a un detalle»."""
    return ft.Container(
        width=40, alignment=ft.Alignment.CENTER,
        content=ft.Icon(ft.Icons.CHEVRON_RIGHT, size=22,
                        color=theme.THEME["text_muted"]))


def _value(text: str, chevron: bool = True) -> ft.Control:
    """Valor actual a la derecha (p. ej. «22»), opcionalmente con ▸."""
    hijos: list[ft.Control] = [
        ft.Text(text, size=14, color=theme.THEME["chord"],
                weight=ft.FontWeight.W_500),
    ]
    if chevron:
        hijos.append(ft.Icon(ft.Icons.CHEVRON_RIGHT, size=20,
                             color=theme.THEME["text_muted"]))
    return ft.Container(
        padding=ft.Padding.only(right=6),
        content=ft.Row(hijos, spacing=2, tight=True,
                       vertical_alignment=ft.CrossAxisAlignment.CENTER))


def _switch(value: bool) -> ft.Control:
    """Interruptor dorado (maqueta: sin handler todavía)."""
    return ft.Switch(value=value, active_color=theme.THEME["accent"])


# ---------------------------------------------------------------------------
# Pantalla
# ---------------------------------------------------------------------------

class SettingsScreen:
    """Ajustes: logo arriba, filas agrupadas y la barra inferior con «Ajustes»
    activo. Primera interacción real: el selector de tema («Apariencia»); el
    resto de filas sigue siendo maqueta visual.

    ``on_theme_change(nombre)`` la provee ``main``: aplica el tema, lo persiste
    y reconstruye la vista."""

    def __init__(self, page: ft.Page, db=None,
                 on_tab: Callable[[str], None] | None = None,
                 on_theme_change: Callable[[str], None] | None = None) -> None:
        self.page = page
        self.db = db
        self.on_tab = on_tab
        self.on_theme_change = on_theme_change

    def build(self) -> ft.Control:
        # Mismo header que las demás pestañas: solo el logo centrado.
        header = ft.Container(
            padding=ft.Padding.only(top=16, bottom=6),
            alignment=ft.Alignment.CENTER,
            content=ft.Image(src="ilahi-logo.png", height=52, fit=ft.BoxFit.CONTAIN),
        )
        body = ft.ListView(
            expand=True, padding=ft.Padding.only(top=2, bottom=16),
            controls=[
                _section("Apariencia"),
                _row(ft.Icons.PALETTE_OUTLINED, "Tema",
                     theme.DESCRIPTIONS[theme.active_theme()],
                     trailing=_value(theme.LABELS[theme.active_theme()]),
                     on_click=(lambda _e: self._open_theme_sheet())
                     if self.on_theme_change is not None else None),
                _row(ft.Icons.FORMAT_SIZE, "Tamaño de letra en escenario",
                     "Tamaño inicial del texto en el escenario",
                     trailing=_value("22")),
                _row(ft.Icons.DARK_MODE, "Fondo del escenario",
                     "Negro puro para tarima", trailing=_value("Negro")),

                _section("Edición"),
                _row(ft.Icons.SPELLCHECK, "Silabación automática",
                     "Divide la letra en sílabas al pegar",
                     trailing=_switch(True)),
                _row(ft.Icons.MUSIC_NOTE, "Detectar acordes al pegar",
                     "Reconoce acordes de Cifra Club y similares",
                     trailing=_switch(True)),

                _section("Datos"),
                _row(ft.Icons.UPLOAD, "Exportar copia de seguridad",
                     "Todas las canciones y listas", trailing=_chevron()),
                _row(ft.Icons.DOWNLOAD, "Importar copia de seguridad",
                     "Restaurar desde un archivo", trailing=_chevron()),
                _row(ft.Icons.FOLDER_OUTLINED, "Ubicación de datos",
                     "Dónde se guardan tus canciones y listas",
                     trailing=_chevron()),

                _section("Acerca de"),
                _row(ft.Icons.INFO_OUTLINE, "Versión",
                     trailing=_value("1.0", chevron=False)),
                _row(ft.Icons.FAVORITE_BORDER, "Acerca de Ilahi",
                     "App para guitarristas de iglesia", trailing=_chevron()),
            ],
        )
        children: list[ft.Control] = [header, body]
        if self.on_tab is not None:
            children.append(build_bottom_bar("settings", self.on_tab))
        return ft.Column(children, expand=True, spacing=0)

    # ------------------------------------------------------------------
    # Selector de tema
    # ------------------------------------------------------------------
    def _swatch(self, palette: dict[str, str]) -> ft.Control:
        """Tres puntos con los colores clave del tema: fondo · panel · acento."""
        return ft.Row(
            [ft.Container(width=16, height=16, border_radius=8, bgcolor=c,
                          border=ft.Border.all(1, theme.THEME["border"]))
             for c in (palette["bg"], palette["surface"], palette["accent"])],
            spacing=4, tight=True)

    def _theme_option(self, key: str) -> ft.Control:
        """Fila del cuadro: muestras de color, nombre + personalidad, ✓ si activo."""
        activo = key == theme.active_theme()

        def choose(_e=None) -> None:
            self.page.pop_dialog()
            if not activo and self.on_theme_change is not None:
                self.on_theme_change(key)

        return ft.Container(
            ink=True, border_radius=12, on_click=choose,
            padding=ft.Padding.symmetric(horizontal=12, vertical=10),
            content=ft.Row(spacing=14, vertical_alignment=ft.CrossAxisAlignment.CENTER,
                           controls=[
                self._swatch(theme.PALETTES[key]),
                ft.Column(spacing=1, tight=True, expand=True, controls=[
                    ft.Text(theme.LABELS[key], size=15, color=theme.THEME["text"],
                            weight=ft.FontWeight.W_600 if activo
                            else ft.FontWeight.NORMAL),
                    ft.Text(theme.DESCRIPTIONS[key], size=11,
                            color=theme.THEME["text_muted"]),
                ]),
                ft.Icon(ft.Icons.CHECK, size=18,
                        color=theme.THEME["accent"] if activo else "#00000000"),
            ]))

    def _open_theme_sheet(self) -> None:
        """Cuadro «Tema»: una fila por tema, con el diseño de los demás cuadros."""
        dialog = ft.AlertDialog(
            modal=False,
            shape=ft.RoundedRectangleBorder(radius=20),
            bgcolor=theme.THEME["surface2"],
            title=ft.Text("Tema", size=18, weight=ft.FontWeight.BOLD,
                          color=theme.THEME["text"]),
            content_padding=ft.Padding.only(left=8, right=8, bottom=8),
            content=ft.Column(tight=True, spacing=2,
                              controls=[self._theme_option(k)
                                        for k in theme.PALETTES]),
        )
        self.page.show_dialog(dialog)
