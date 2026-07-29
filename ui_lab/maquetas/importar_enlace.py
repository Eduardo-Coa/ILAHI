"""Maqueta: importar una canción desde un enlace de Cifra Club.

Muestra las tres pantallas del flujo:
  1. El menú «Añadir» con la opción NUEVA «Importar desde enlace» junto a las de hoy.
  2. Pegar la URL → «Importar» (baja de verdad con ``utils.web_import``).
  3. Cae en la ``NewSongScreen`` real ya rellenada (título, autor, letra), para revisar.

Es fiel: usa las mismas piezas de la app (la hoja «Añadir», el extractor real y la
pantalla de nueva canción real). Aquí SÍ se usa la red (el extractor no toca la base de
datos, así que no choca con el candado del lab); el bajado va en un hilo aparte para no
congelar la UI mientras gira el indicador —el patrón que necesitará la app.
"""

from __future__ import annotations
import asyncio
import flet as ft

import theme
from views.widgets import back_button, centered_header, sheet_option
from views.edit_view import _themed_field, _pill_button, NewSongScreen
from utils.web_import import import_song, SongImportError

NOMBRE = "Importar desde enlace"
DESCRIPCION = "Menú Añadir con la opción nueva → pegar URL → cae en Nueva canción."

# URL de ejemplo que ya sabemos que funciona, para probar sin buscar.
_EJEMPLO = "https://www.cifraclub.com/feliz7kids/chispas-de-luz/"


def construir(page: ft.Page, db) -> ft.Control:
    raiz = ft.Container(expand=True)

    # -- pantalla 1: el menú «Añadir» (con la opción nueva) ---------------
    def _mostrar_menu() -> None:
        # Mismas filas que la hoja «Añadir» real (views.song_list_view.show_add_sheet),
        # con «Importar desde enlace» agregada en segundo lugar.
        opciones = ft.Column(tight=True, spacing=2, controls=[
            sheet_option(ft.Icons.ADD, "Nueva canción",
                         "Escribe o pega la letra", lambda _e: _mostrar_url("")),
            sheet_option(ft.Icons.LINK, "Importar desde enlace",
                         "Pega el link de Cifra Club", lambda _e: _mostrar_url(_EJEMPLO)),
            sheet_option(ft.Icons.DOWNLOAD, "Importar…",
                         "Una canción o un cancionero .ilahi", lambda _e: None),
            sheet_option(ft.Icons.UPLOAD, "Exportar biblioteca",
                         "Todas tus canciones en un archivo", lambda _e: None),
        ])
        raiz.content = ft.Column([
            centered_header("Añadir"),
            ft.Container(
                margin=ft.Margin.symmetric(horizontal=12, vertical=12),
                padding=ft.Padding.all(8), border_radius=20,
                bgcolor=theme.THEME["surface2"], content=opciones),
            ft.Container(
                padding=16,
                content=ft.Text("(En la app, este menú es la hoja que sale al tocar el "
                                "＋. «Importar desde enlace» es la opción nueva.)",
                                size=12, color=theme.THEME["text_muted"])),
        ], expand=True, spacing=0)
        page.update()

    # -- pantalla 2: pegar el enlace --------------------------------------
    def _mostrar_url(valor_inicial: str) -> None:
        # «Nueva canción» (valor vacío) abre directo el formulario en blanco; «Importar
        # desde enlace» abre esta pantalla de URL con el ejemplo cargado.
        if not valor_inicial:
            _abrir_formulario(titulo="", autor="", letra="")
            return

        campo = _themed_field("Enlace de la canción (Cifra Club)",
                              value=valor_inicial, expand=True)
        estado = ft.Text("", size=13, color=theme.THEME["text_muted"])
        anillo = ft.ProgressRing(width=18, height=18, visible=False,
                                 color=theme.THEME["accent"])
        boton = _pill_button(ft.Icons.DOWNLOAD, "Importar", lambda _e: _importar())

        def _fijar(texto: str, error: bool = False) -> None:
            estado.value = texto
            estado.color = theme.THEME["danger"] if error else theme.THEME["text_muted"]
            page.update()

        def _importar() -> None:
            anillo.visible = True
            boton.disabled = True
            _fijar("Importando…")
            page.run_task(_bajar, (campo.value or "").strip())

        async def _bajar(url: str) -> None:
            try:
                imported = await asyncio.get_event_loop().run_in_executor(
                    None, import_song, url)
            except SongImportError as e:
                anillo.visible = False
                boton.disabled = False
                _fijar(e.message, error=True)
                return
            except Exception as e:
                anillo.visible = False
                boton.disabled = False
                _fijar(f"No se pudo importar: {e}", error=True)
                return
            _abrir_formulario(imported.title, imported.artist, imported.text)

        raiz.content = ft.Column([
            centered_header("Importar desde enlace",
                            left=back_button(_mostrar_menu)),
            ft.Container(padding=16, content=ft.Column(spacing=14, controls=[
                ft.Text("Pega el enlace de una canción de Cifra Club. La bajamos y la "
                        "abrimos en el editor para revisar antes de guardar.",
                        size=13, color=theme.THEME["text_muted"]),
                campo,
                ft.Row([anillo, estado], spacing=8,
                       vertical_alignment=ft.CrossAxisAlignment.CENTER),
                boton,
            ])),
        ], expand=True, spacing=0)
        page.update()

    # -- pantalla 3: NewSongScreen real, rellenada ------------------------
    def _abrir_formulario(titulo: str, autor: str, letra: str) -> None:
        pantalla = NewSongScreen(db, on_created=lambda _id: _mostrar_menu(),
                                 on_back=_mostrar_menu)
        # Prefill: NewSongScreen no recibe valores iniciales todavía; en la integración
        # real convendría que acepte un ImportedSong en el __init__.
        pantalla._title.value = titulo
        pantalla._author.value = autor
        pantalla._lyrics.value = letra
        raiz.content = pantalla.build()
        page.update()

    _mostrar_menu()
    return raiz
