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
from datetime import datetime
from pathlib import Path
import flet as ft

from database.config import load_config
from database.db import Database, UNKNOWN_AUTHOR, author_display
from models.transposer import transpose_song
import theme
from sample_data import sample_songs, sample_setlist
from views.song_list_view import SongsScreen, show_add_sheet
from views.author_list_view import AuthorsScreen
from views.setlist_view import build_setlists, SetlistDetailScreen, SongPickerScreen
from views.stage_view import StageScreen, PresentScreen
from views.edit_view import NewSongScreen, EditSongScreen, EditLyricsScreen
from views.settings_view import SettingsScreen
from views.theme_editor import ThemeEditorScreen
from views.main_shell import MainShell, HOME_INDEX
from views.widgets import show_toast, confirm_dialog, sheet_dialog
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


# Extensión de la copia de seguridad COMPLETA (SQLite): distinta de la del cancionero
# (.hymnchords, solo canciones) para no confundir un backup con un cancionero.
BACKUP_EXTENSION = ".hymnbak"


def main(page: ft.Page) -> None:
    """Arranca la app, registra el FilePicker y gestiona la navegación."""
    page.title = "Ilahi"
    page.padding = 0

    # Tema guardado en preferencias: se activa ANTES de pintar nada.
    saved_theme = get_pref("theme", theme.DEFAULT_THEME)
    if saved_theme in theme.PALETTES:
        theme.set_theme(saved_theme)
    # Ajustes de color hechos con el editor de temas (solo desarrollo): se aplican
    # sobre las paletas ya activas. Tolerante a claves viejas (apply_overrides).
    theme.apply_overrides(get_pref("theme_overrides"))

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

    # «Detectar acordes al pegar» (Ajustes): si está apagado, al pegar letra nueva no se
    # interpretan las líneas de acordes. Por defecto encendido.
    detect_chords = get_pref("detect_chords", True)
    if not isinstance(detect_chords, bool):
        detect_chords = True

    def save_detect_chords(value: bool) -> None:
        nonlocal detect_chords
        detect_chords = bool(value)
        set_pref("detect_chords", detect_chords)

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

    # -- Editor de temas en vivo (solo desarrollo; ver theme.DEV_THEME_EDITOR) ----
    def persist_theme_state() -> None:
        """Guarda qué paleta se edita y los colores de TODAS las paletas, para que el
        trabajo del editor sobreviva a cerrar la app."""
        set_pref("theme", theme.active_theme())
        set_pref("theme_overrides", theme.export_palettes())

    async def export_palette() -> str:
        """Vuelca las paletas como código pegable en ``theme.py``, a un archivo elegido
        (en el teléfono, Descargas). Devuelve el mensaje de estado."""
        data = theme.palette_source_snippet().encode("utf-8")
        # ext=None: se guarda con el nombre que elija el usuario, sin forzar «.py».
        msg = await save_bytes(data, "Exportar paletas", "theme_palettes.py",
                               ext=None, allowed_extensions=["py", "txt"])
        return msg or "✓ Paletas exportadas a Descargas"

    def go_theme_editor() -> None:
        editor = ThemeEditorScreen(
            page, on_back=go_settings, refresh_page=_apply_page_theme,
            persist=persist_theme_state, export=export_palette)
        show(editor.build(), on_back=go_settings)

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

    # Estado de navegación: ``back`` = a dónde lleva el «atrás» del sistema desde la
    # pantalla actual; ``leave`` = limpieza al abandonarla (p. ej. detener el
    # metrónomo); ``is_main`` = estamos en el panel principal (el shell), donde el
    # «atrás» tiene su propia lógica (ver _system_back).
    _nav = {"back": None, "leave": None, "is_main": False}

    async def _system_back(_e=None) -> None:
        """Intercepta el «atrás» del sistema (gesto o botón) y navega DENTRO de la app,
        en vez de dejar que Android cierre la app (que mandaba al inicio del teléfono,
        porque la navegación es propia y no una pila de vistas de Flet).

        - En el panel principal (shell): si no estamos en Canciones, va a Canciones;
          si ya estamos ahí, se deja salir de la app (``confirm_pop(True)``).
        - En una pantalla interna: ejecuta su «volver».

        ``confirm_pop(False)`` cancela la salida pendiente (si no, expiraría por timeout)."""
        if _nav["is_main"]:
            shell = shell_state["shell"]
            if shell is not None and shell.index != HOME_INDEX:
                shell.goto(HOME_INDEX)
                await page.views[0].confirm_pop(False)
            else:
                await page.views[0].confirm_pop(True)     # Canciones → cerrar la app
            return
        volver = _nav["back"]
        if volver is not None:
            volver()
        await page.views[0].confirm_pop(False)

    # La vista raíz siempre existe (page.controls es page.views[0].controls). Se le
    # engancha el interceptor una vez; ``can_pop`` se alterna por pantalla en show().
    page.views[0].on_confirm_pop = _system_back

    def show(control: ft.Control, on_back=None, on_leave=None,
             is_main: bool = False) -> None:
        # Antes de reemplazar la pantalla se corre la limpieza de la SALIENTE (p. ej.
        # el escenario detiene el metrónomo y el autoscroll), sin importar qué disparó
        # la navegación —su ✕, un cambio de canción o el «atrás» del sistema, que salta
        # el _exit de la vista—. Así el metrónomo no sigue sonando en la pantalla nueva.
        leave = _nav["leave"]
        if leave is not None:
            leave()
        _nav["back"] = on_back
        _nav["leave"] = on_leave
        _nav["is_main"] = is_main
        # can_pop=False → el back lo maneja _system_back (navegar). Solo sería True si
        # una pantalla no-principal no tuviera «volver», caso que hoy no existe.
        page.views[0].can_pop = on_back is None and not is_main
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

    async def save_bytes(data: bytes, dialog_title: str, file_name: str,
                         ext: str | None = SONG_FILE_EXTENSION,
                         allowed_extensions: list[str] | None = None) -> str:
        """Guarda ``data`` con el diálogo nativo. Devuelve "" si salió bien, o el
        mensaje de estado. ÚNICO punto donde se escribe un archivo elegido por el
        usuario (cancionero, copia de seguridad y paletas), así que es también el único
        lugar a tocar si iOS necesita otro trato.

        En Android/iOS (y web) el sistema escribe el archivo y por eso exige
        ``src_bytes``; en escritorio el diálogo solo devuelve la ruta elegida y el
        archivo lo escribimos nosotros, agregando ``ext`` si falta. Con ``ext=None`` se
        respeta la ruta tal cual (lo que necesita la exportación de paletas).
        """
        path = await file_picker.save_file(
            dialog_title=dialog_title, file_name=file_name,
            allowed_extensions=allowed_extensions
            or [SONG_FILE_EXTENSION.lstrip(".")], src_bytes=data)
        if not path:
            return "Exportación cancelada"
        if not (page.web or page.platform.is_mobile()):
            try:
                dest = (path if ext is None or path.lower().endswith(ext)
                        else path + ext)
                Path(dest).write_bytes(data)
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
    # Copia de seguridad completa (Ajustes › Datos): toda la base en un archivo
    # ``.hymnbak`` (SQLite). Distinto del cancionero ``.hymnchords`, que solo lleva
    # canciones: el backup incluye también listas y favoritos, y restaurar REEMPLAZA.
    # ------------------------------------------------------------------
    async def do_export_backup() -> None:
        """Exporta toda la base (canciones + listas + favoritos) a un archivo elegido."""
        try:
            data = db.export_bytes()
        except Exception as ex:                       # snapshot fallido: nunca reventar
            show_toast(page, f"✗ No se pudo preparar la copia: {ex}")
            return
        name = f"hymnchords-backup-{datetime.now():%Y%m%d-%H%M}{BACKUP_EXTENSION}"
        try:
            msg = await save_bytes(
                data, "Exportar copia de seguridad", name, ext=BACKUP_EXTENSION,
                allowed_extensions=[BACKUP_EXTENSION.lstrip(".")])
        except Exception as ex:                       # el diálogo nativo falló
            show_toast(page, f"✗ {ex}")
            return
        show_toast(page, msg or "✓ Copia de seguridad exportada")

    def do_import_backup() -> None:
        """Restaurar reemplaza TODO, así que primero se confirma."""
        def confirmar(_e=None) -> None:
            page.pop_dialog()
            page.run_task(_run_import_backup)

        # modal=True aunque use el chrome de «hoja»: restaurar es destructivo y no debe
        # descartarse tocando fuera del cuadro.
        dialog = sheet_dialog(
            ft.Text(
                "Reemplaza TODAS tus canciones y listas por las del archivo. Se guarda "
                "una copia de lo actual por si acaso.", size=14,
                color=theme.THEME["text_muted"]),
            title="Restaurar copia", modal=True,
            actions=[
                ft.TextButton("Cancelar", on_click=lambda _e: page.pop_dialog()),
                ft.TextButton("Restaurar", on_click=confirmar),
            ])
        page.show_dialog(dialog)

    async def _run_import_backup() -> None:
        files = await file_picker.pick_files(
            dialog_title="Restaurar copia de seguridad",
            allowed_extensions=[BACKUP_EXTENSION.lstrip(".")], allow_multiple=False)
        if not files:
            return
        try:
            data = Path(files[0].path).read_bytes()
            db.restore_bytes(data)
        except ValueError as ex:                      # archivo no válido
            show_toast(page, f"✗ {ex}")
            return
        except Exception as ex:
            show_toast(page, f"✗ No se pudo restaurar: {ex}")
            return
        go_home(status="✓ Copia de seguridad restaurada")

    def show_data_location() -> None:
        """Cuadro informativo: dónde vive la base (carpeta privada de la app)."""
        carpeta = str(db.db_path.parent)
        dialog = sheet_dialog(
            title="Ubicación de datos",
            content=ft.Column(tight=True, spacing=10, controls=[
                ft.Text("Tus canciones y listas se guardan en la carpeta privada de la "
                        "app (sobrevive a actualizar, se borra al desinstalar):",
                        size=13, color=theme.THEME["text_muted"]),
                ft.Container(
                    bgcolor=theme.THEME["surface"], border_radius=10, padding=10,
                    border=ft.Border.all(1, theme.THEME["border"]),
                    content=ft.Text(carpeta, size=12, color=theme.THEME["text"],
                                    selectable=True, font_family=theme.FONT_MONO)),
                ft.Text("Usa «Exportar copia de seguridad» para guardar un respaldo que "
                        "puedas mover o compartir.", size=12,
                        color=theme.THEME["text_muted"]),
            ]),
            actions=[ft.TextButton("Cerrar", on_click=lambda _e: page.pop_dialog())])
        page.show_dialog(dialog)

    # ------------------------------------------------------------------
    # Panel principal: shell con las 5 vistas (swipe + deslizamiento + barra fija).
    # Secuencia: Autores · Canciones · Favoritos · Listas · Ajustes. Las funciones
    # go_* siguen siendo los puntos de entrada (las pantallas hoja las usan para
    # «volver» al panel en la vista correcta).
    # ------------------------------------------------------------------
    shell_state = {"shell": None}          # el MainShell activo (para el back del sistema)
    main_state = {"author": None}          # autor elegido en Autores (drill-down)

    def open_author_songs(name: str) -> None:
        """Toca un autor → se QUEDA en Autores mostrando sus canciones (con el chip
        debajo del buscador). No cambia de pestaña ni desliza: refresh en el sitio."""
        main_state["author"] = name
        if shell_state["shell"] is not None:
            shell_state["shell"].refresh()

    def clear_author() -> None:
        """Quita el filtro por autor → vuelve a la lista de autores (misma vista)."""
        main_state["author"] = None
        if shell_state["shell"] is not None:
            shell_state["shell"].refresh()

    def _on_navigate(i: int) -> None:
        """Al salir de Autores (deslizando o tocando otra pestaña) se suelta el autor
        elegido, para que al volver se vea la lista de autores y no el drill-down."""
        if i != 0:
            main_state["author"] = None

    def refresh_shell(status: str = "") -> None:
        """Reconstruye la vista actual del shell (tras borrar/renombrar) + toast."""
        if shell_state["shell"] is not None:
            shell_state["shell"].rebuild()
        if status:
            show_toast(page, status)

    def _goto(n: int) -> None:
        if shell_state["shell"] is not None:
            shell_state["shell"].goto(n)

    def _invalidate_others() -> None:
        """Un cambio de datos en la vista actual (favorito, borrado) deja obsoletas a
        las demás: Biblioteca y Favoritos son pantallas distintas y viven a la vez."""
        if shell_state["shell"] is not None:
            shell_state["shell"].invalidate_others()

    def _songs_body(tab: str, query: str, author: str | None = None) -> ft.Control:
        """Cuerpo de una lista de canciones embebida (buscador fijo del shell)."""
        return SongsScreen(
            page, db, on_open_song=go_stage, on_open_setlists=lambda: _goto(3),
            on_import=do_import, on_export_all=do_export_all,
            on_new_song=go_new_song, on_edit_song=go_edit_song,
            on_export_song=do_export_song, on_open_authors=lambda: _goto(0),
            on_open_settings=lambda: _goto(4), tab=tab, author=author,
            embedded=True, external_search=True, query=query,
            on_clear_author=clear_author if author else None,
            on_data_changed=_invalidate_others).build()

    def build_main_page(i: int, query: str = "") -> ft.Control:
        """Cuerpo de la vista ``i`` filtrado por ``query`` (logo, toggle, buscador y
        barra los pone el shell). En Autores con un autor elegido se muestran sus
        canciones (drill-down); Favoritos/Listas traen su propio buscador."""
        if i == 0 and main_state["author"] is None:     # Autores: lista de autores
            return AuthorsScreen(
                page, db, on_open_author=open_author_songs,
                on_back=lambda: _goto(1), on_export_author=export_author_fn,
                on_tab=None, embedded=True, external_search=True, query=query).build()
        if i == 0:                          # Autores + autor elegido: SUS canciones
            return _songs_body("library", query, author=main_state["author"])
        if i == 1:                          # Canciones (todas)
            return _songs_body("library", query)
        if i == 2:                          # Favoritos
            return _songs_body("favorites", query)
        if i == 3:                          # Listas
            return build_setlists(
                db.list_setlists(), on_open=go_setlist_detail,
                on_back=lambda: _goto(1), on_new=create_list,
                on_tab=None, page=page, db=db, refresh=refresh_shell,
                embedded=True, external_search=True, query=query)
        return SettingsScreen(              # Ajustes
            page, db=db, on_tab=None, on_theme_change=change_theme,
            on_open_theme_editor=go_theme_editor,
            stage_size=stage_size, on_size_change=save_stage_size,
            refresh_page=_apply_page_theme, persist_theme=persist_theme_state,
            detect_chords=detect_chords, on_detect_chords_change=save_detect_chords,
            on_export_backup=lambda: page.run_task(do_export_backup),
            on_import_backup=do_import_backup,
            on_show_data_location=show_data_location,
            embedded=True).build()

    def search_hint(i: int) -> str | None:
        """Placeholder del buscador fijo por vista (None solo en Ajustes)."""
        if i == 0:
            return "Buscar himno…" if main_state["author"] else "Buscar autor…"
        if i == 1:
            return "Buscar himno o autor…"
        if i == 2:
            return "Buscar en favoritos…"
        if i == 3:
            return "Buscar lista…"
        return None

    def open_add_sheet() -> None:
        """Cuadro «Añadir» (nueva canción / importar / exportar), desde el ＋ del shell."""
        show_add_sheet(page, go_new_song, do_import, do_export_all)

    def fab_action(i: int):
        """Qué hace el ＋ fijo por vista: en Canciones/Favoritos abre «Añadir»; en
        Listas crea una lista; en Autores/Ajustes no hay ＋ (None → oculto)."""
        if i in (1, 2):
            return open_add_sheet
        if i == 3:
            return create_list
        return None

    def show_main(index: int = HOME_INDEX, status: str = "") -> None:
        """Muestra el panel principal (shell) en la vista ``index``."""
        shell = MainShell(page, build_main_page, search_hint=search_hint,
                          on_navigate=_on_navigate, fab_action=fab_action, index=index)
        shell_state["shell"] = shell
        show(shell.build(), is_main=True)
        if status:
            show_toast(page, status)         # confirmación flotante (toast)

    def go_home(status: str = "", tab: str = "library",
                author: str | None = None) -> None:
        main_state["author"] = author        # None normalmente: suelta el drill-down
        if author is not None:
            show_main(0, status=status)      # Autores con ese autor (drill-down)
        else:
            show_main(2 if tab == "favorites" else HOME_INDEX, status=status)

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
        show(NewSongScreen(db, on_created=go_edit_song, on_back=go_home,
                           detect_chords=detect_chords).build(),
             on_back=go_home)

    def go_edit_song(song_id: int, on_done=None) -> None:
        # Al cerrar el editor se vuelve a la vista de canción; ``on_done`` permite
        # volver a la vista de una lista (con su navegación y tono), no a la suelta.
        volver = on_done or (lambda: go_stage(song_id))
        song = db.load_song(song_id)
        show(EditSongScreen(db, song, on_back=volver,
                            on_edit_lyrics=lambda sid: go_edit_lyrics(sid, on_done),
                            page=page).build(), on_back=volver)

    def go_edit_lyrics(song_id: int, on_done=None) -> None:
        volver = lambda: go_edit_song(song_id, on_done)
        song = db.load_song(song_id)
        show(EditLyricsScreen(db, song,
                              on_saved=lambda sid: go_edit_song(sid, on_done),
                              on_back=volver).build(), on_back=volver)

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
                         size=stage_size, on_size_change=save_stage_size).build(),
             on_back=go_home)

    def go_present(song, offset: int, size: int | None = None) -> None:
        # ``size`` viene del «Aa» de la vista de canción: el escenario hereda su
        # fuente. Si no viene, se usa la guardada en preferencias.
        volver = lambda: go_stage(song.id)
        screen = PresentScreen(page, song, offset, on_exit=volver,
                               size=size if size is not None else stage_size)
        # on_leave: al abandonar el escenario (incluido el «atrás» del sistema) se
        # detiene el metrónomo/autoscroll, que si no seguían en la pantalla anterior.
        show(screen.build(), on_back=volver, on_leave=screen.stop)

    def go_setlists(status: str = "") -> None:
        show_main(3, status=status)

    def go_settings() -> None:
        show_main(4)

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
        page.show_dialog(confirm_dialog(
            "Nueva lista", field,
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
        ).build(), on_back=go_setlists)

    def go_add_songs(setlist_id: int) -> None:
        volver = lambda: go_setlist_detail(setlist_id)
        show(SongPickerScreen(
            db, setlist_id, page=page, on_back=volver,
        ).build(), on_back=volver)

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
        ).build(), on_back=lambda: go_setlist_detail(setlist.id))

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
        volver = lambda: go_stage_in_setlist(setlist, index)
        screen = PresentScreen(
            page, song, item.transpose,
            on_exit=volver,
            on_prev=on_prev, on_next=on_next,
            position_label=f"{index + 1}/{len(setlist.items)}",
            size=size,
        )
        show(screen.build(), on_back=volver, on_leave=screen.stop)

    go_home()


if __name__ == "__main__":
    ft.run(main)
