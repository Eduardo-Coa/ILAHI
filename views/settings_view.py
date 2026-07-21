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
from views.widgets import logo_header, _safe_update, sheet_dialog, stepper_row


# Paleta de colores sugeridos para «Color de Acordes» (además del hex manual).
_CHORD_PALETTE = [
    "#00ffff", "#ff00ff", "#ffff00", "#00ff00", "#ff7f00",
    "#ff7fff", "#007fff", "#ffc000", "#ffa3a4",
]


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
                 on_theme_change: Callable[[str], None] | None = None,
                 on_open_theme_editor: Callable[[], None] | None = None,
                 stage_size: int = theme.SIZE_STAGE,
                 on_size_change: Callable[[int], None] | None = None,
                 refresh_page: Callable[[], None] | None = None,
                 persist_theme: Callable[[], None] | None = None,
                 detect_chords: bool = True,
                 on_detect_chords_change: Callable[[bool], None] | None = None,
                 on_export_backup: Callable[[], None] | None = None,
                 on_import_backup: Callable[[], None] | None = None,
                 on_show_data_location: Callable[[], None] | None = None,
                 embedded: bool = False) -> None:
        self.page = page
        self.db = db
        self.on_tab = on_tab
        self.on_theme_change = on_theme_change
        # Abre el editor de temas en vivo (solo desarrollo; ver theme.DEV_THEME_EDITOR).
        self.on_open_theme_editor = on_open_theme_editor
        # Tamaño de letra por defecto (compartido por canción y escenario). ``on_size_change``
        # lo persiste (main.save_stage_size); aquí se muestra y se ajusta.
        self.stage_size = stage_size
        self.on_size_change = on_size_change or (lambda _s: None)
        # Para «Color de Acordes»: reaplicar el ColorScheme de la página (refresh_page)
        # y guardar los overrides del tema (persist_theme). Los inyecta ``main``.
        self.refresh_page = refresh_page or (lambda: None)
        self.persist_theme = persist_theme or (lambda: None)
        # «Detectar acordes al pegar»: valor actual y callback que lo persiste (main).
        self.detect_chords = detect_chords
        self.on_detect_chords_change = on_detect_chords_change or (lambda _v: None)
        # Sección «Datos»: exportar/restaurar copia de seguridad y ver la ubicación.
        self.on_export_backup = on_export_backup
        self.on_import_backup = on_import_backup
        self.on_show_data_location = on_show_data_location
        # Embebida en el shell: el logo lo fija el shell (aquí se omite).
        self.embedded = embedded
        # Refs para actualizar en vivo (sin reconstruir la vista entera).
        self._size_value: ft.Text | None = None       # número junto a «Tamaño de letra»
        self._chord_swatch: ft.Container | None = None  # muestra junto a «Color de Acordes»
        # Estado del cuadro «Color de Acordes» (se rellena al abrirlo).
        self._cc_key = "chord"
        self._cc_hex: ft.TextField | None = None
        self._cc_badge: ft.Container | None = None
        self._cc_badge_text: ft.Text | None = None
        self._cc_line: ft.Text | None = None
        self._cc_editor_box: ft.Container | None = None

    def build(self) -> ft.Control:
        body = ft.ListView(
            expand=True, padding=ft.Padding.only(top=2, bottom=16),
            controls=[
                _section("Apariencia"),
                _row(ft.Icons.PALETTE_OUTLINED, "Tema",
                     theme.DESCRIPTIONS[theme.active_theme()],
                     trailing=_value(theme.LABELS[theme.active_theme()]),
                     on_click=(lambda _e: self._open_theme_sheet())
                     if self.on_theme_change is not None else None),
                _row(ft.Icons.MUSIC_NOTE, "Color de Acordes",
                     "El color de los acordes",
                     trailing=self._chord_trailing(),
                     on_click=lambda _e: self._open_chord_sheet()),
                _row(ft.Icons.FORMAT_SIZE, "Tamaño de letra en Canción",
                     "Tamaño del texto en canción y escenario",
                     trailing=self._size_trailing(),
                     on_click=lambda _e: self._open_size_sheet()),

                _section("Edición"),
                _row(ft.Icons.MUSIC_NOTE, "Detectar acordes al pegar",
                     "Reconoce acordes de Cifra Club y similares",
                     trailing=ft.Switch(
                         value=self.detect_chords, active_color=theme.THEME["accent"],
                         on_change=lambda e: self.on_detect_chords_change(
                             e.control.value))),

                _section("Datos"),
                _row(ft.Icons.UPLOAD, "Exportar copia de seguridad",
                     "Todas las canciones y listas", trailing=_chevron(),
                     on_click=(lambda _e: self.on_export_backup())
                     if self.on_export_backup is not None else None),
                _row(ft.Icons.DOWNLOAD, "Importar copia de seguridad",
                     "Restaurar desde un archivo", trailing=_chevron(),
                     on_click=(lambda _e: self.on_import_backup())
                     if self.on_import_backup is not None else None),
                _row(ft.Icons.FOLDER_OUTLINED, "Ubicación de datos",
                     "Dónde se guardan tus canciones y listas",
                     trailing=_chevron(),
                     on_click=(lambda _e: self.on_show_data_location())
                     if self.on_show_data_location is not None else None),

                _section("Acerca de"),
                _row(ft.Icons.INFO_OUTLINE, "Versión",
                     trailing=_value("1.0", chevron=False)),
                _row(ft.Icons.FAVORITE_BORDER, "Acerca de Ilahi",
                     "Qué es la app y quién la hizo", trailing=_chevron(),
                     on_click=lambda _e: self._open_about_sheet()),
            ],
        )
        # Editor de temas: solo en desarrollo (theme.DEV_THEME_EDITOR). Es andamiaje para
        # afinar los colores en el teléfono; se quita antes de publicar.
        if theme.DEV_THEME_EDITOR and self.on_open_theme_editor is not None:
            body.controls.extend([
                _section("Desarrollo"),
                _row(ft.Icons.COLOR_LENS_OUTLINED, "Editor de temas",
                     "Afinar los colores en vivo", trailing=_chevron(),
                     on_click=lambda _e: self.on_open_theme_editor()),
            ])
        children: list[ft.Control] = []
        if not self.embedded:                # embebida: el logo lo fija el shell
            children.append(logo_header())
        children.append(body)
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
        dialog = sheet_dialog(
            title="Tema",
            content_padding=ft.Padding.only(left=8, right=8, bottom=8),
            content=ft.Column(tight=True, spacing=2,
                              controls=[self._theme_option(k)
                                        for k in theme.USER_THEMES]),
        )
        self.page.show_dialog(dialog)

    # ------------------------------------------------------------------
    # Acerca de Ilahi
    # ------------------------------------------------------------------
    def _open_about_sheet(self) -> None:
        """Cuadro «Acerca de Ilahi»: qué es la app, qué hace y su autor."""
        def parrafo(texto: str, destacado: bool = False) -> ft.Control:
            return ft.Text(texto, size=13,
                           color=theme.THEME["text"] if destacado
                           else theme.THEME["text_muted"])

        def vineta(texto: str) -> ft.Control:
            return ft.Row(spacing=8, vertical_alignment=ft.CrossAxisAlignment.START,
                          controls=[
                ft.Text("•", size=13, color=theme.THEME["accent"]),
                ft.Text(texto, size=13, color=theme.THEME["text_muted"], expand=True),
            ])

        funciones = [
            "Guardar tu repertorio y buscarlo por canción o por autor.",
            "Ver los acordes alineados sobre la letra y transponerlos al tono que te "
            "quede cómodo.",
            "Pegar la letra de canciones (con o sin acordes) y dejar que la app la "
            "prepare sola: la divide en sílabas y reconoce los acordes.",
            "Armar listas para cada culto o ensayo.",
            "Usar el modo escenario: la letra a pantalla completa, con desplazamiento "
            "automático y metrónomo.",
            "Marcar favoritos, ajustar el tamaño de la letra y elegir entre varios temas "
            "de color, e incluso personalizar el color de los acordes.",
            "Exportar e importar tu biblioteca para tenerla siempre a salvo.",
        ]
        cuerpo = ft.Column(
            spacing=10, scroll=ft.ScrollMode.AUTO,
            # Alto acotado según la pantalla: si el texto no cabe, se desplaza.
            height=min(460, int((getattr(self.page, "height", None) or 700) * 0.6)),
            controls=[
                ft.Text("Ilahi", size=22, weight=ft.FontWeight.BOLD,
                        color=theme.THEME["accent"]),
                parrafo("Ilahi es una app pensada para guitarristas y otros "
                        "instrumentistas de cuerda de la iglesia. Reúne tus himnos y "
                        "canciones con sus acordes en un solo lugar, listos para tocar.",
                        destacado=True),
                parrafo("Con Ilahi puedes:", destacado=True),
                *[vineta(f) for f in funciones],
                parrafo("Todo funciona sin conexión: tu música siempre está contigo.",
                        destacado=True),
                ft.Container(height=2),
                ft.Text("Hecha con dedicación por Eduardo Coa.", size=13,
                        weight=ft.FontWeight.W_600, color=theme.THEME["text"]),
            ])
        dialog = sheet_dialog(
            cuerpo,
            title="Acerca de Ilahi",
            content_padding=ft.Padding.only(left=16, right=16, bottom=8),
            actions=[ft.TextButton("Cerrar",
                                   on_click=lambda _e: self.page.pop_dialog())],
        )
        self.page.show_dialog(dialog)

    # ------------------------------------------------------------------
    # Tamaño de letra (mismo valor por defecto para canción y escenario)
    # ------------------------------------------------------------------
    def _size_trailing(self) -> ft.Control:
        """Número actual + ▸; se guarda la ref para refrescarlo sin reconstruir la vista."""
        self._size_value = ft.Text(str(self.stage_size), size=14,
                                   color=theme.THEME["chord"], weight=ft.FontWeight.W_500)
        return ft.Container(
            padding=ft.Padding.only(right=6),
            content=ft.Row([self._size_value,
                            ft.Icon(ft.Icons.CHEVRON_RIGHT, size=20,
                                    color=theme.THEME["text_muted"])],
                           spacing=2, tight=True,
                           vertical_alignment=ft.CrossAxisAlignment.CENTER))

    def _set_size(self, value: int) -> None:
        """Fija el tamaño (12–48), lo refleja en la fila y lo persiste (main). Al abrir
        una canción o el escenario, ambos parten de este valor."""
        self.stage_size = max(12, min(48, value))
        if self._size_value is not None:
            self._size_value.value = str(self.stage_size)
            _safe_update(self._size_value)
        self.on_size_change(self.stage_size)

    def _open_size_sheet(self) -> None:
        """Cuadro «Tamaño de letra»: A− · número · A+ · Restablecer. Es el mismo valor
        que ajusta el botón «Aa» de la canción."""
        num = ft.Text(str(self.stage_size), size=26, weight=ft.FontWeight.BOLD,
                      color=theme.THEME["text"])

        def paint() -> None:
            num.value = str(self.stage_size)
            _safe_update(num)

        def resize(delta: int) -> None:
            self._set_size(self.stage_size + delta)
            paint()

        def reset() -> None:
            self._set_size(theme.SIZE_STAGE)
            paint()

        dialog = sheet_dialog(
            content_padding=ft.Padding.only(left=16, right=16, top=8, bottom=8),
            content=ft.Column(tight=True, spacing=10,
                              horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                              controls=[
                ft.Text("Tamaño de letra", size=16, color=theme.THEME["text"]),
                ft.Text("En canción y escenario", size=12,
                        color=theme.THEME["text_muted"]),
                stepper_row("A−", lambda _e: resize(-2), num,
                            "A+", lambda _e: resize(2)),
                ft.TextButton("Restablecer", on_click=lambda _e: reset()),
            ]),
        )
        self.page.show_dialog(dialog)

    # ------------------------------------------------------------------
    # Color de Acordes (edita chord del tema activo, y persiste)
    # ------------------------------------------------------------------
    def _chord_trailing(self) -> ft.Control:
        """Muestra del color del acorde + ▸ (ref guardada para refrescar en vivo)."""
        self._chord_swatch = ft.Container(
            width=22, height=22, border_radius=6, bgcolor=theme.THEME["chord"],
            border=ft.Border.all(1, theme.THEME["border"]))
        return ft.Container(
            padding=ft.Padding.only(right=6),
            content=ft.Row([self._chord_swatch,
                            ft.Icon(ft.Icons.CHEVRON_RIGHT, size=20,
                                    color=theme.THEME["text_muted"])],
                           spacing=8, tight=True,
                           vertical_alignment=ft.CrossAxisAlignment.CENTER))

    def _open_chord_sheet(self) -> None:
        """Cuadro «Color de Acordes»: vista previa + paleta + hex. Cambia ``chord`` del
        tema activo, en vivo, y lo guarda en las preferencias."""
        self._cc_key = "chord"
        self._cc_badge_text = ft.Text("Sol", size=15, color=theme.THEME["chord"])
        self._cc_badge = ft.Container(
            bgcolor=theme.THEME["chord_bg"], border_radius=8,
            border=ft.Border.all(1, theme.THEME["chord"]),
            padding=ft.Padding.symmetric(horizontal=12, vertical=6),
            content=self._cc_badge_text)
        self._cc_line = ft.Text("Do        Sol", size=16, color=theme.THEME["chord"],
                                font_family=theme.FONT_MONO)
        preview = ft.Container(
            bgcolor=theme.THEME["verse_bg"], border_radius=10, padding=14,
            border=ft.Border.all(1, theme.THEME["border"]),
            content=ft.Row(alignment=ft.MainAxisAlignment.CENTER, spacing=18,
                           vertical_alignment=ft.CrossAxisAlignment.CENTER,
                           controls=[self._cc_badge, self._cc_line]))
        self._cc_editor_box = ft.Container(content=self._cc_editor())
        dialog = sheet_dialog(
            ft.Column(tight=True, spacing=12, width=320,
                      controls=[preview, self._cc_editor_box]),
            title="Color de Acordes",
            content_padding=ft.Padding.only(left=16, right=16, bottom=8),
        )
        self.page.show_dialog(dialog)

    def _cc_editor(self) -> ft.Control:
        """Paleta de colores sugeridos + casilla hex del color del acorde. Tocar una
        muestra fija ese color; el hex permite cualquier otro."""
        current = theme.THEME[self._cc_key].lower()
        muestras: list[ft.Control] = []
        for color in _CHORD_PALETTE:
            elegido = color.lower() == current
            muestras.append(ft.Container(
                width=42, height=42, border_radius=10, bgcolor=color, ink=True,
                on_click=lambda _e, c=color: self._cc_pick(c),
                border=ft.Border.all(3 if elegido else 1,
                                     theme.THEME["text"] if elegido
                                     else theme.THEME["border"])))
        self._cc_edit_swatch = ft.Container(
            width=26, height=26, border_radius=6, bgcolor=theme.THEME[self._cc_key],
            border=ft.Border.all(1, theme.THEME["border"]))
        self._cc_hex = ft.TextField(
            value=theme.THEME[self._cc_key], dense=True, width=130, text_size=13,
            color=theme.THEME["text"], border_color=theme.THEME["border"],
            hint_text="#rrggbb", on_submit=self._cc_hex_submit)
        return ft.Column(spacing=12, controls=[
            ft.Row(muestras, wrap=True, spacing=8, run_spacing=8,
                   alignment=ft.MainAxisAlignment.CENTER),
            ft.Row(vertical_alignment=ft.CrossAxisAlignment.CENTER,
                   controls=[self._cc_edit_swatch, ft.Container(expand=True),
                             self._cc_hex]),
        ])

    def _cc_refresh_editor(self) -> None:
        """Rehace la paleta y el hex (resaltado de la muestra activa y valor actual)."""
        if self._cc_editor_box is not None:
            self._cc_editor_box.content = self._cc_editor()
            _safe_update(self._cc_editor_box)

    def _cc_pick(self, color: str) -> None:
        """Elige un color de la paleta para el acorde."""
        self._apply_chord_color(color)
        self._cc_commit()
        self._cc_refresh_editor()

    def _cc_hex_submit(self, e) -> None:
        raw = (e.control.value or "").strip()
        if not raw.startswith("#"):
            raw = "#" + raw
        if len(raw.lstrip("#")) < 6:
            return                                   # hex incompleto: se ignora
        value = theme.rgb_to_hex(*theme.hex_to_rgb(raw))     # normaliza
        self._apply_chord_color(value)
        self._cc_commit()
        self._cc_refresh_editor()

    def _apply_chord_color(self, value: str) -> None:
        """Escribe el color en el tema activo y repinta la vista previa y la muestra de la
        fila de Ajustes en vivo."""
        theme.set_active_color(self._cc_key, value)
        if self._cc_badge is not None:
            self._cc_badge.bgcolor = theme.THEME["chord_bg"]
            self._cc_badge.border = ft.Border.all(1, theme.THEME["chord"])
            _safe_update(self._cc_badge)
        if self._cc_badge_text is not None:
            self._cc_badge_text.color = theme.THEME["chord"]
            _safe_update(self._cc_badge_text)
        if self._cc_line is not None:
            self._cc_line.color = theme.THEME["chord"]
            _safe_update(self._cc_line)
        if self._chord_swatch is not None:
            self._chord_swatch.bgcolor = theme.THEME["chord"]
            _safe_update(self._chord_swatch)

    def _cc_commit(self) -> None:
        """Tras elegir un color (paleta o hex): reaplica el ColorScheme y guarda."""
        self.refresh_page()
        self.persist_theme()
