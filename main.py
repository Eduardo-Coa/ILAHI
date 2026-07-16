"""Punto de entrada de HymnChords móvil (Flet).

Fase 5: importar/exportar `.hymnchords` (el puente con el escritorio, sin nube).
Reutiliza `utils.song_io` (canción suelta o cancionero/bundle). El FilePicker de
Flet 0.85 es un servicio con métodos async que devuelven el resultado directo.

Navegación:
  Canciones (buscar · importar · exportar) ─┬─> Escenario (transponer, exportar)
                                            └─> Listas ─> Detalle (tocar/editar) ─> Escenario

Correr en escritorio:   flet run main.py
"""

from __future__ import annotations
from pathlib import Path
import flet as ft

from database.config import load_config
from database.db import Database, UNKNOWN_AUTHOR, author_display
from models.transposer import transpose_song
import theme
from sample_data import sample_songs, sample_setlist
from views.song_list_view import SongsScreen
from views.author_list_view import AuthorsScreen
from views.setlist_view import build_setlists, SetlistDetailScreen, SongPickerScreen
from views.stage_view import StageScreen, PresentScreen
from views.edit_view import NewSongScreen, EditSongScreen, EditLyricsScreen
from views.settings_view import SettingsScreen
from views.widgets import show_toast
from utils.prefs import get_pref, set_pref
from utils.song_io import (
    load_songs, song_to_bytes, bundle_to_bytes, suggested_filename,
    bundle_filename, SONG_FILE_EXTENSION, SongIOError,
)

try:
    from utils.logging_setup import setup_logging
except Exception:  # logging es opcional; nunca debe impedir arrancar
    setup_logging = None


def bootstrap_db() -> Database:
    """Abre la BD (carpeta aislada), crea el esquema y siembra ejemplos si falta."""
    if setup_logging is not None:
        try:
            setup_logging()
        except Exception:
            pass
    db = Database(load_config())
    db.init_schema()
    if not db.list_songs():
        for song in sample_songs():
            db.save_song(song)
    if not db.list_setlists():
        song_ids = [s["id"] for s in db.list_songs()]
        if song_ids:
            db.save_setlist(sample_setlist(song_ids))
    return db


def _ensure_ext(path: str) -> str:
    """Garantiza que la ruta termine en .hymnchords."""
    return path if path.lower().endswith(SONG_FILE_EXTENSION) else path + SONG_FILE_EXTENSION


def main(page: ft.Page) -> None:
    """Arranca la app, registra el FilePicker y gestiona la navegación."""
    page.title = "Ilahi"
    page.padding = 0

    # Tema guardado en preferencias: se activa ANTES de pintar nada.
    saved_theme = get_pref("theme", theme.DEFAULT_THEME)
    if saved_theme in theme.PALETTES:
        theme.set_theme(saved_theme)

    # Tamaño del texto de la canción, también guardado. Se valida al leerlo: un
    # archivo de preferencias editado a mano o de una versión vieja no debe dejar
    # la letra ilegible. El rango es el mismo que aplica el botón «Aa».
    stage_size = get_pref("stage_size", theme.SIZE_STAGE)
    if not isinstance(stage_size, int) or isinstance(stage_size, bool) \
            or not (12 <= stage_size <= 48):
        stage_size = theme.SIZE_STAGE

    def save_stage_size(size: int) -> None:
        """Recuerda el tamaño del texto entre vistas y entre sesiones."""
        nonlocal stage_size
        stage_size = size
        set_pref("stage_size", size)

    def _apply_page_theme() -> None:
        """Colores a nivel de página: fondo, modo, y un ColorScheme mínimo para
        los widgets Material (Slider, Switch, botones de diálogo…), que no leen
        ``theme.THEME``."""
        page.bgcolor = theme.THEME["bg"]
        page.theme_mode = ft.ThemeMode.DARK if theme.is_dark() else ft.ThemeMode.LIGHT
        page.theme = ft.Theme(color_scheme=ft.ColorScheme(
            primary=theme.THEME["accent"],
            on_primary=theme.THEME["bg"],
            secondary=theme.THEME["chord"],
        ))

    _apply_page_theme()

    def change_theme(name: str) -> None:
        """Activa un tema, lo persiste y repinta (la vista de Ajustes se
        reconstruye ya con los colores nuevos)."""
        theme.set_theme(name)
        set_pref("theme", name)
        _apply_page_theme()
        go_settings()

    # Solo en escritorio (`flet run`): abrir con tamaño de teléfono para simular la
    # pantalla. En Android/iOS se ignora (la app va a pantalla completa).
    if page.platform is not None and page.platform.is_desktop():
        page.window.width = 412
        page.window.height = 915
        page.window.min_width = 320
        page.window.min_height = 640

    db = bootstrap_db()
    file_picker = ft.FilePicker()
    page.services.append(file_picker)

    def show(control: ft.Control) -> None:
        page.controls.clear()
        # SafeArea: evita que la barra de estado/notch se sobreponga a la barra superior
        page.add(ft.SafeArea(content=control, expand=True))

    # ------------------------------------------------------------------
    # Importar / exportar (.hymnchords) — FilePicker async de Flet 0.85
    # ------------------------------------------------------------------
    async def do_import(_e=None) -> None:
        files = await file_picker.pick_files(
            dialog_title="Importar .hymnchords",
            allowed_extensions=["hymnchords"], allow_multiple=False)
        if not files:
            return
        try:
            songs = load_songs(files[0].path)
            for s in songs:
                db.save_song(s)          # id=None -> entra como copia nueva
            go_home(status=f"✓ Importadas {len(songs)} canción(es)")
        except SongIOError as ex:
            go_home(status=f"✗ {ex}")

    async def save_bytes(data: bytes, dialog_title: str, file_name: str) -> str:
        """Guarda ``data`` con el diálogo nativo. Devuelve "" si salió bien.

        En Android/iOS (y web) el sistema escribe el archivo y por eso exige
        ``src_bytes``; en escritorio el diálogo solo devuelve la ruta elegida y
        el archivo lo escribimos nosotros.
        """
        path = await file_picker.save_file(
            dialog_title=dialog_title, file_name=file_name,
            allowed_extensions=["hymnchords"], src_bytes=data)
        if not path:
            return "Exportación cancelada"
        if not (page.web or page.platform.is_mobile()):
            try:
                Path(_ensure_ext(path)).write_bytes(data)
            except OSError as ex:
                return f"✗ No se pudo guardar el archivo: {ex}"
        return ""

    async def do_export_all(_e=None) -> None:
        rows = db.list_songs()
        if not rows:
            go_home(status="No hay canciones para exportar")
            return
        try:
            songs = [db.load_song(r["id"]) for r in rows]
            msg = await save_bytes(bundle_to_bytes(songs), "Exportar cancionero",
                                   "cancionero" + SONG_FILE_EXTENSION)
            go_home(status=msg or f"✓ Exportadas {len(songs)} canciones")
        except SongIOError as ex:
            go_home(status=f"✗ {ex}")

    async def export_song_fn(song) -> str:
        """Exporta una canción; devuelve el mensaje de estado para el escenario."""
        try:
            msg = await save_bytes(song_to_bytes(song), "Exportar canción",
                                   suggested_filename(song))
        except SongIOError as ex:
            return f"✗ {ex}"
        return msg or "✓ Canción exportada"

    async def do_export_song(song_id: int) -> None:
        """Exporta una canción desde el menú ⋮ de la lista."""
        go_home(status=await export_song_fn(db.load_song(song_id)))

    # ------------------------------------------------------------------
    # Navegación
    # ------------------------------------------------------------------
    def go_home(status: str = "", tab: str = "library",
                author: str | None = None) -> None:
        show(SongsScreen(
            page, db, on_open_song=go_stage, on_open_setlists=go_setlists,
            on_import=do_import, on_export_all=do_export_all,
            on_new_song=go_new_song, on_edit_song=go_edit_song,
            on_export_song=do_export_song, on_open_authors=go_authors,
            on_open_settings=go_settings,
            tab=tab, author=author,
        ).build())
        if status:
            show_toast(page, status)     # confirmación flotante (toast)

    def go_authors() -> None:
        show(AuthorsScreen(
            page, db, on_open_author=lambda name: go_home(author=name),
            on_back=go_home, on_export_author=export_author_fn,
            on_tab=tab_from_authors,
        ).build())

    def tab_from_authors(key: str) -> None:
        """Pestañas desde la lista de autores."""
        if key == "library":
            go_home()
        elif key == "favorites":
            go_home(tab="favorites")
        elif key == "setlists":
            go_setlists()
        elif key == "settings":
            go_settings()

    async def export_author_fn(author: str) -> str:
        """Exporta el cancionero de un autor; devuelve el mensaje de estado."""
        etiqueta = author_display(author)
        rows = db.list_songs(filters={"author": author})
        if not rows:
            return f"«{etiqueta}» no tiene canciones"
        # El bundle no lleva nombre de autor si es el grupo «Desconocido».
        bundle_author = None if author == UNKNOWN_AUTHOR else author
        try:
            songs = [db.load_song(r["id"]) for r in rows]
            msg = await save_bytes(bundle_to_bytes(songs, bundle_author),
                                   f"Exportar cancionero de {etiqueta}",
                                   bundle_filename(bundle_author))
        except SongIOError as ex:
            return f"✗ {ex}"
        return msg or f"✓ Exportadas {len(songs)} canciones de «{etiqueta}»"

    def go_new_song() -> None:
        show(NewSongScreen(db, on_created=go_edit_song, on_back=go_home).build())

    def go_edit_song(song_id: int, on_done=None) -> None:
        # Al cerrar el editor se vuelve a la vista de canción; ``on_done`` permite
        # volver a la vista de una lista (con su navegación y tono), no a la suelta.
        volver = on_done or (lambda: go_stage(song_id))
        song = db.load_song(song_id)
        show(EditSongScreen(db, song, on_back=volver,
                            on_edit_lyrics=lambda sid: go_edit_lyrics(sid, on_done),
                            page=page).build())

    def go_edit_lyrics(song_id: int, on_done=None) -> None:
        song = db.load_song(song_id)
        show(EditLyricsScreen(db, song,
                              on_saved=lambda sid: go_edit_song(sid, on_done),
                              on_back=lambda: go_edit_song(song_id, on_done)).build())

    def persist_transpose(song, delta: int):
        """Transpone la canción y la guarda como su nuevo tono. Devuelve la recargada."""
        transposed = transpose_song(song, delta)
        db.save_song(transposed)
        return db.load_song(transposed.id)

    def go_stage(song_id: int) -> None:
        song = db.load_song(song_id)
        show(StageScreen(page, song, on_back=go_home,
                         on_edit=go_edit_song, on_edit_lyrics=go_edit_lyrics,
                         on_present=go_present,
                         on_persist_key=persist_transpose,
                         size=stage_size, on_size_change=save_stage_size).build())

    def go_present(song, offset: int, size: int | None = None) -> None:
        # ``size`` viene del «Aa» de la vista de canción: el escenario hereda su
        # fuente. Si no viene, se usa la guardada en preferencias.
        show(PresentScreen(page, song, offset, on_exit=lambda: go_stage(song.id),
                           size=size if size is not None else stage_size).build())

    def go_setlists(status: str = "") -> None:
        show(build_setlists(db.list_setlists(), on_open=go_setlist_detail,
                            on_back=go_home, on_new=create_list,
                            on_tab=tab_from_setlists,
                            page=page, db=db, refresh=go_setlists))
        if status:
            show_toast(page, status)     # confirmación flotante (toast)

    def tab_from_setlists(key: str) -> None:
        """Pestañas de la barra inferior desde la vista de listas."""
        if key == "library":
            go_home()
        elif key == "favorites":
            go_home(tab="favorites")
        elif key == "settings":
            go_settings()
        # "setlists": ya estamos aquí

    def go_settings() -> None:
        show(SettingsScreen(page, db=db, on_tab=tab_from_settings,
                            on_theme_change=change_theme).build())

    def tab_from_settings(key: str) -> None:
        """Pestañas de la barra inferior desde Ajustes."""
        if key == "library":
            go_home()
        elif key == "favorites":
            go_home(tab="favorites")
        elif key == "setlists":
            go_setlists()
        # "settings": ya estamos aquí

    def create_list() -> None:
        # Primero se pide el nombre con un cuadro flotante (mismo diseño que los demás).
        field = ft.TextField(
            hint_text="Nombre de la lista", autofocus=True, dense=True,
            border_color=theme.THEME["border"],
            focused_border_color=theme.THEME["accent"], color=theme.THEME["text"])

        def crear(_e=None) -> None:
            name = (field.value or "").strip() or "Nueva lista"
            page.pop_dialog()
            new_id = db.create_setlist(name)
            go_setlist_detail(new_id)

        field.on_submit = crear
        page.show_dialog(ft.AlertDialog(
            modal=True, shape=ft.RoundedRectangleBorder(radius=18),
            bgcolor=theme.THEME["surface2"],
            title=ft.Text("Nueva lista", color=theme.THEME["text"]),
            content=field,
            actions=[
                ft.TextButton("Cancelar", on_click=lambda _e: page.pop_dialog()),
                ft.TextButton("Crear", on_click=crear),
            ]))

    def go_setlist_detail(setlist_id: int, editing: bool = False) -> None:
        setlist = db.load_setlist(setlist_id)
        show(SetlistDetailScreen(
            db, setlist, on_back=go_setlists,
            on_play_item=go_stage_in_setlist, on_add=go_add_songs,
            on_deleted=go_setlists, editing=editing,
            on_present=go_present_in_setlist,       # ▶ → escenario de la lista
            page=page,
        ).build())

    def go_add_songs(setlist_id: int) -> None:
        show(SongPickerScreen(
            db, setlist_id, page=page,
            on_back=lambda: go_setlist_detail(setlist_id),
        ).build())

    def go_stage_in_setlist(setlist, index: int) -> None:
        item = setlist.items[index]
        song = db.load_song(item.song_id)
        on_prev = (lambda: go_stage_in_setlist(setlist, index - 1)) if index > 0 else None
        last = len(setlist.items) - 1
        on_next = (lambda: go_stage_in_setlist(setlist, index + 1)) if index < last else None

        def save_offset(offset: int) -> None:
            # El tono queda en la COPIA de la lista (no toca la canción original).
            setlist.items[index].transpose = offset
            db.save_setlist(setlist)

        volver_aqui = lambda: go_stage_in_setlist(setlist, index)
        show(StageScreen(
            page, song, on_back=lambda: go_setlist_detail(setlist.id),
            initial_offset=item.transpose, on_prev=on_prev, on_next=on_next,
            position_label=f"{index + 1}/{len(setlist.items)}",
            # Editar y volver mantiene el contexto de la lista (nav y tono).
            on_edit=lambda sid: go_edit_song(sid, volver_aqui),
            on_edit_lyrics=lambda sid: go_edit_lyrics(sid, volver_aqui),
            on_offset_change=save_offset,       # guarda el tono en la lista al transponer
            # El ▶ abre el escenario CON navegación de lista; al salir vuelve aquí.
            # El 3er argumento es el tamaño de fuente que trae esta vista («Aa»).
            on_present=lambda s, o, size: go_present_in_setlist(setlist, index, size),
            size=stage_size, on_size_change=save_stage_size,
        ).build())

    def go_present_in_setlist(setlist, index: int,
                              size: int | None = None) -> None:
        """Escenario (pantalla completa) de una canción de la lista, con ‹/› para
        pasar de canción, swipe, y salida a la vista de canción con navegación.

        ``size`` es el tamaño de fuente heredado de la vista de canción; se conserva
        al pasar a la anterior/siguiente. Desde el ▶ del detalle de la lista no hay
        una vista previa de donde heredarlo, así que se usa el guardado.
        """
        if size is None:
            size = stage_size
        item = setlist.items[index]
        song = db.load_song(item.song_id)
        on_prev = ((lambda: go_present_in_setlist(setlist, index - 1, size))
                   if index > 0 else None)
        last = len(setlist.items) - 1
        on_next = ((lambda: go_present_in_setlist(setlist, index + 1, size))
                   if index < last else None)
        show(PresentScreen(
            page, song, item.transpose,
            on_exit=lambda: go_stage_in_setlist(setlist, index),
            on_prev=on_prev, on_next=on_next,
            position_label=f"{index + 1}/{len(setlist.items)}",
            size=size,
        ).build())

    go_home()


if __name__ == "__main__":
    ft.run(main)
