"""Editor de temas EN VIVO (solo desarrollo).

Herramienta para definir los colores de los temas probándolos en el teléfono, sin
recompilar por cada ajuste: corre dentro del APK real, así que lo que se ve ES el
render del dispositivo (a diferencia de ``flet run`` en escritorio).

Cómo funciona: se elige qué paleta editar (una de las cuatro definitivas o la
``scratch`` de pruebas). Esa paleta pasa a ser el tema ACTIVO, de modo que toda la
app se pinta con ella. Se toca un color de la lista y se ajusta con tres deslizadores
R/G/B (o escribiendo el hex); el cambio se aplica al instante —la vista previa de
arriba y, al volver, la app entera—. Todo se guarda en preferencias (``persist``), así
no se pierde al cerrar. «Exportar» vuelca las paletas como código pegable en
``theme.py``.

Es andamiaje: se activa con ``theme.DEV_THEME_EDITOR`` y se quita antes de publicar.
Por eso vive aparte y no se enreda con el resto de las vistas.
"""

from __future__ import annotations
from typing import Awaitable, Callable
import flet as ft

import theme
from views.widgets import back_button, show_toast, _safe_update


class ThemeEditorScreen:
    """Pantalla del editor: selector de paleta, vista previa, lista de colores y el
    ajuste R/G/B del color elegido."""

    def __init__(self, page: ft.Page, on_back: Callable[[], None],
                 refresh_page: Callable[[], None],
                 persist: Callable[[], None],
                 export: Callable[[], Awaitable[str]]) -> None:
        self.page = page
        self.on_back = on_back
        # refresh_page: reaplica el tema a nivel de página (fondo + ColorScheme de los
        # widgets Material), que no leen theme.THEME. Lo provee main._apply_page_theme.
        self.refresh_page = refresh_page
        self.persist = persist          # guarda las paletas (y el tema activo) en prefs
        self.export = export            # async: vuelca el snippet a Descargas
        # Color en edición: su clave, o el primero por defecto.
        self._sel_key = theme.EDITABLE_COLORS[0][0]
        self._preview: ft.Container | None = None
        self._swatches: dict[str, ft.Container] = {}   # muestra por clave, para repintar
        self._sliders: dict[str, ft.Slider] = {}       # r/g/b
        self._hex_field: ft.TextField | None = None
        self._sel_title: ft.Text | None = None

    # ------------------------------------------------------------------
    def build(self) -> ft.Control:
        header = ft.Container(
            padding=ft.Padding.only(left=8, right=12, top=8, bottom=8),
            content=ft.Row(vertical_alignment=ft.CrossAxisAlignment.CENTER, controls=[
                back_button(self.on_back),
                ft.Container(expand=True, padding=ft.Padding.only(left=8),
                             content=ft.Text("Editor de temas · dev", size=18,
                                              weight=ft.FontWeight.BOLD,
                                              color=theme.THEME["accent"])),
                ft.IconButton(ft.Icons.IOS_SHARE, icon_size=22,
                              icon_color=theme.THEME["text"],
                              tooltip="Exportar a Descargas", on_click=self._on_export),
            ]))
        self._preview = ft.Container(content=self._build_preview())
        body = ft.ListView(expand=True, padding=ft.Padding.only(bottom=24), controls=[
            self._palette_selector(),
            self._preview,
            self._color_editor(),
            self._color_list(),
            self._reset_row(),
        ])
        return ft.Column([header, body], expand=True, spacing=0)

    # -- selector de paleta --------------------------------------------
    def _palette_selector(self) -> ft.Control:
        chips: list[ft.Control] = []
        for name in theme.PALETTES:
            activa = name == theme.active_theme()
            chips.append(ft.Container(
                ink=True, border_radius=14, on_click=lambda _e, n=name: self._select_palette(n),
                padding=ft.Padding.symmetric(horizontal=14, vertical=8),
                bgcolor=theme.THEME["accent"] if activa else theme.THEME["surface"],
                border=ft.Border.all(1, theme.THEME["border"]),
                content=ft.Text(theme.LABELS[name], size=13,
                                weight=ft.FontWeight.W_600,
                                color=theme.THEME["bg"] if activa else theme.THEME["text"])))
        return ft.Container(
            padding=ft.Padding.symmetric(horizontal=12, vertical=6),
            content=ft.Column(spacing=6, controls=[
                ft.Text("Editando", size=12, weight=ft.FontWeight.W_600,
                        color=theme.THEME["text_muted"]),
                ft.Row(chips, spacing=8, wrap=True),
            ]))

    def _select_palette(self, name: str) -> None:
        """Cambia la paleta que se edita: la vuelve el tema activo y repinta todo."""
        theme.set_theme(name)
        self.refresh_page()
        self.persist()                  # recuerda qué paleta se estaba editando
        self._rebuild_all()

    # -- vista previa ---------------------------------------------------
    def _build_preview(self) -> ft.Control:
        """Un muestrario de los componentes reales para juzgar los colores de un vistazo:
        tarjeta de canción, toggle, acorde sobre letra, etiqueta de sección y botones."""
        T = theme.THEME
        tarjeta = ft.Container(
            bgcolor=T["surface"], border_radius=14,
            padding=ft.Padding.symmetric(horizontal=10, vertical=8),
            content=ft.Row(vertical_alignment=ft.CrossAxisAlignment.CENTER, controls=[
                ft.Icon(ft.Icons.STAR, size=20, color=T["accent"]),
                ft.Container(expand=True, padding=ft.Padding.symmetric(horizontal=8),
                             content=ft.Column(spacing=2, tight=True, controls=[
                    ft.Text("Cantad alegres al Señor", size=16, color=T["text"]),
                    ft.Text("mortales todos por doquier", size=12, color=T["text_muted"]),
                ])),
                ft.Container(bgcolor=T["chord_bg"], border_radius=8,
                             border=ft.Border.all(1, T["chord"]),
                             padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                             content=ft.Text("Sol", size=13, color=T["chord"])),
            ]))
        toggle = ft.Container(
            bgcolor=T["surface"], border_radius=18, padding=ft.Padding.all(3),
            content=ft.Row(spacing=0, controls=[
                ft.Container(expand=1, height=30, border_radius=16, bgcolor=T["accent"],
                             alignment=ft.Alignment.CENTER,
                             content=ft.Text("Autores", size=13, color=T["bg"],
                                             weight=ft.FontWeight.W_600)),
                ft.Container(expand=1, height=30, alignment=ft.Alignment.CENTER,
                             content=ft.Text("Canciones", size=13, color=T["text_muted"],
                                             weight=ft.FontWeight.W_600)),
            ]))
        acorde = ft.Container(
            bgcolor=T["verse_bg"], border_radius=10, padding=10,
            content=ft.Column(spacing=0, tight=True, controls=[
                ft.Text("SECCIÓN · CORO", size=11, color=T["section_label"],
                        weight=ft.FontWeight.W_600),
                ft.Text("Do        Sol", size=15, color=T["chord"],
                        font_family=theme.FONT_MONO),
                ft.Text("Cantaré tu amor", size=15, color=T["text"],
                        font_family=theme.FONT_MONO),
            ]))
        botones = ft.Row(spacing=10, controls=[
            ft.Container(bgcolor=T["accent"], border_radius=14,
                         padding=ft.Padding.symmetric(horizontal=16, vertical=10),
                         content=ft.Text("Acento", size=13, color=T["bg"],
                                         weight=ft.FontWeight.W_600)),
            ft.Container(border_radius=14, border=ft.Border.all(1, T["danger"]),
                         padding=ft.Padding.symmetric(horizontal=16, vertical=10),
                         content=ft.Text("Peligro", size=13, color=T["danger"])),
            ft.Container(width=22, height=22, border_radius=11, bgcolor=T["beat_one"],
                         tooltip="Metrónomo golpe 1"),
        ])
        return ft.Container(
            bgcolor=T["bg"], border_radius=16, margin=ft.Margin.symmetric(horizontal=12),
            border=ft.Border.all(1, T["border"]), padding=12,
            content=ft.Column(spacing=10, controls=[tarjeta, toggle, acorde, botones]))

    # -- editor R/G/B del color elegido --------------------------------
    def _color_editor(self) -> ft.Control:
        r, g, b = theme.hex_to_rgb(theme.THEME[self._sel_key])
        self._sel_title = ft.Text(self._sel_label(), size=14, weight=ft.FontWeight.W_600,
                                  color=theme.THEME["text"])
        self._hex_field = ft.TextField(
            value=theme.THEME[self._sel_key], dense=True, width=120,
            text_size=13, color=theme.THEME["text"],
            border_color=theme.THEME["border"], on_submit=self._on_hex_submit)
        filas = [ft.Row(vertical_alignment=ft.CrossAxisAlignment.CENTER, controls=[
            self._sel_title,
            ft.Container(expand=True),
            self._hex_field,
        ])]
        for canal, val in (("r", r), ("g", g), ("b", b)):
            s = ft.Slider(min=0, max=255, divisions=255, value=val, expand=True,
                          label="{value}", active_color=self._channel_color(canal),
                          on_change=lambda e, c=canal: self._on_slider(c),
                          on_change_end=lambda _e: self.persist())
            self._sliders[canal] = s
            filas.append(ft.Row(vertical_alignment=ft.CrossAxisAlignment.CENTER, controls=[
                ft.Container(width=20, content=ft.Text(canal.upper(), size=13,
                             weight=ft.FontWeight.W_600,
                             color=theme.THEME["text_muted"])),
                s,
            ]))
        return ft.Container(
            margin=ft.Margin.symmetric(horizontal=12, vertical=8),
            padding=12, bgcolor=theme.THEME["surface2"], border_radius=14,
            border=ft.Border.all(1, theme.THEME["border"]),
            content=ft.Column(filas, spacing=2))

    def _channel_color(self, canal: str) -> str:
        return {"r": "#e05a5a", "g": "#5ad06a", "b": "#5a8ae0"}[canal]

    def _sel_label(self) -> str:
        for key, label in theme.EDITABLE_COLORS:
            if key == self._sel_key:
                return label
        return self._sel_key

    # -- lista de colores ----------------------------------------------
    def _color_list(self) -> ft.Control:
        filas: list[ft.Control] = []
        for key, label in theme.EDITABLE_COLORS:
            sw = ft.Container(width=28, height=28, border_radius=8,
                              bgcolor=theme.THEME[key],
                              border=ft.Border.all(1, theme.THEME["border"]))
            self._swatches[key] = sw
            elegido = key == self._sel_key
            filas.append(ft.Container(
                ink=True, border_radius=10, on_click=lambda _e, k=key: self._select_color(k),
                bgcolor=theme.THEME["surface"] if elegido else None,
                padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                margin=ft.Margin.symmetric(horizontal=12, vertical=2),
                content=ft.Row(spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER,
                               controls=[
                    sw,
                    ft.Container(expand=True, content=ft.Text(label, size=14,
                                 color=theme.THEME["text"])),
                    ft.Text(theme.THEME[key], size=12, color=theme.THEME["text_muted"]),
                ])))
        return ft.Column(filas, spacing=0)

    def _select_color(self, key: str) -> None:
        self._sel_key = key
        self._rebuild_all()

    # -- restablecer ----------------------------------------------------
    def _reset_row(self) -> ft.Control:
        return ft.Container(
            margin=ft.Margin.only(left=12, right=12, top=8),
            content=ft.OutlinedButton(
                "Restablecer esta paleta", icon=ft.Icons.RESTART_ALT,
                on_click=self._on_reset))

    def _on_reset(self, _e=None) -> None:
        theme.reset_palette(theme.active_theme())
        self.refresh_page()
        self.persist()
        self._rebuild_all()
        show_toast(self.page, "✓ Paleta restablecida")

    # -- aplicación de cambios -----------------------------------------
    def _apply_color(self, value: str) -> None:
        """Escribe el color elegido en el tema activo y repinta lo mínimo en vivo (vista
        previa, muestra y hex) sin reconstruir los deslizadores (para no cortar el arrastre)."""
        theme.set_active_color(self._sel_key, value)
        self.refresh_page()
        if self._preview is not None:
            self._preview.content = self._build_preview()
            _safe_update(self._preview)
        sw = self._swatches.get(self._sel_key)
        if sw is not None:
            sw.bgcolor = value
            _safe_update(sw)
        if self._hex_field is not None and self._hex_field.value != value:
            self._hex_field.value = value
            _safe_update(self._hex_field)

    def _on_slider(self, _canal: str) -> None:
        rgb = tuple(int(self._sliders[c].value) for c in ("r", "g", "b"))
        self._apply_color(theme.rgb_to_hex(*rgb))

    def _on_hex_submit(self, e) -> None:
        raw = (e.control.value or "").strip()
        if not raw.startswith("#"):
            raw = "#" + raw
        if len(raw.lstrip("#")) < 6:
            show_toast(self.page, "✗ Hex inválido (usa #rrggbb)")
            return
        value = theme.rgb_to_hex(*theme.hex_to_rgb(raw))     # normaliza
        r, g, b = theme.hex_to_rgb(value)
        for canal, v in (("r", r), ("g", g), ("b", b)):
            self._sliders[canal].value = v
            _safe_update(self._sliders[canal])
        self._apply_color(value)
        self.persist()

    # -- reconstrucción -------------------------------------------------
    def _rebuild_all(self) -> None:
        """Reconstruye la pantalla en sitio: cambió la paleta o el color elegido, así que
        el selector, la vista previa, los deslizadores y la lista deben rehacerse."""
        self.page.controls.clear()
        self.page.add(ft.SafeArea(content=self.build(), expand=True))
        _safe_update(self.page)

    async def _on_export(self, _e=None) -> None:
        msg = await self.export()
        show_toast(self.page, msg or "✓ Paletas exportadas a Descargas")
