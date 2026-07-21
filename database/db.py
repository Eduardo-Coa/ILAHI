"""Acceso a la base de datos SQLite para HymnChords."""

from __future__ import annotations
import logging
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path

from database.config import DBConfig
from models.song import Song, Section, Line, Syllable, Chord
from models.setlist import Setlist, SetlistItem

_log = logging.getLogger("hymnchords.db")

# Número de copias de seguridad a conservar (rotación).
BACKUP_KEEP = 10

# Tablas que confirman que un archivo es una copia de la app (no cualquier SQLite).
_BACKUP_REQUIRED_TABLES = {"songs", "sections", "setlists", "setlist_songs"}

# Marcador del "autor" que agrupa las canciones sin autor asignado. No es un
# nombre real (por eso el prefijo raro): distingue «filtrar sin autor» de «sin
# filtro». Se muestra como «Desconocido» en la UI.
UNKNOWN_AUTHOR = "\x00__sin_autor__"
UNKNOWN_AUTHOR_LABEL = "Desconocido"


def author_display(name: str | None) -> str:
    """Nombre a mostrar para un autor: «Desconocido» si falta o es el marcador."""
    if not name or name == UNKNOWN_AUTHOR:
        return UNKNOWN_AUTHOR_LABEL
    return name


class Database:
    """Maneja todas las operaciones de lectura y escritura contra SQLite."""

    def __init__(self, config: DBConfig) -> None:
        self._config = config
        self._conn: sqlite3.Connection | None = None

    # ------------------------------------------------------------------
    # Conexión
    # ------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        """Abre (o reutiliza) la conexión al archivo SQLite."""
        if self._conn is None:
            self._config.path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(self._config.path))
            self._conn.row_factory = sqlite3.Row
            # Necesario en SQLite para que actúen las FK ON DELETE CASCADE.
            self._conn.execute("PRAGMA foreign_keys = ON")
        return self._conn

    def close(self) -> None:
        """Cierra la conexión si está abierta."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    # ------------------------------------------------------------------
    # Copias de seguridad
    # ------------------------------------------------------------------

    def backup(self, reason: str = "") -> Path | None:
        """Crea una copia de seguridad de la BD en ``<carpeta de la BD>/backups/``.

        Usa la API de backup de SQLite (consistente aunque la conexión esté viva).
        Conserva solo las últimas ``BACKUP_KEEP`` copias. Devuelve la ruta creada,
        o None si la base aún no existe o el backup falla (un backup fallido nunca
        debe impedir la operación del usuario).
        """
        db_path = self._config.path
        if not db_path.exists():
            return None

        backups_dir = db_path.parent / "backups"
        backups_dir.mkdir(parents=True, exist_ok=True)

        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        dest_path = backups_dir / f"hymnchords-{stamp}.db"
        n = 1
        while dest_path.exists():  # evita colisiones dentro del mismo segundo
            dest_path = backups_dir / f"hymnchords-{stamp}-{n}.db"
            n += 1

        try:
            dest = sqlite3.connect(str(dest_path))
            try:
                self._connect().backup(dest)
            finally:
                dest.close()
        except sqlite3.Error:
            _log.exception("fallo al crear backup (%s)", reason or "sin motivo")
            dest_path.unlink(missing_ok=True)
            return None

        self._prune_backups(backups_dir)
        _log.info("backup creado: %s (%s)", dest_path.name, reason or "sin motivo")
        return dest_path

    @staticmethod
    def _prune_backups(backups_dir: Path) -> None:
        """Conserva solo las últimas ``BACKUP_KEEP`` copias (por fecha de modificación)."""
        backups = sorted(
            backups_dir.glob("hymnchords-*.db"), key=lambda p: p.stat().st_mtime
        )
        for old in backups[:-BACKUP_KEEP]:
            old.unlink(missing_ok=True)

    # ------------------------------------------------------------------
    # Copia de seguridad manual (exportar / restaurar a un archivo elegido)
    # ------------------------------------------------------------------

    @property
    def db_path(self) -> Path:
        """Ruta del archivo SQLite de la app (para «Ubicación de datos»)."""
        return self._config.path

    def export_bytes(self) -> bytes:
        """Snapshot CONSISTENTE de toda la base (canciones, listas, favoritos) como
        bytes, para «Exportar copia de seguridad». Usa la API de backup de SQLite a un
        archivo temporal —seguro aunque la conexión esté viva— y devuelve su contenido."""
        with tempfile.TemporaryDirectory() as tmp:
            snapshot = Path(tmp) / "export.db"
            dest = sqlite3.connect(str(snapshot))
            try:
                self._connect().backup(dest)
            finally:
                dest.close()
            return snapshot.read_bytes()

    @staticmethod
    def is_valid_backup(data: bytes) -> bool:
        """¿``data`` es una copia de seguridad de la app? Comprueba la cabecera SQLite y
        que estén las tablas propias, para no restaurar un archivo cualquiera."""
        if not data.startswith(b"SQLite format 3\x00"):
            return False
        with tempfile.TemporaryDirectory() as tmp:
            candidate = Path(tmp) / "check.db"
            candidate.write_bytes(data)
            try:
                conn = sqlite3.connect(str(candidate))
                try:
                    rows = conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    ).fetchall()
                finally:
                    conn.close()
            except sqlite3.Error:
                return False
        return _BACKUP_REQUIRED_TABLES.issubset({r[0] for r in rows})

    def restore_bytes(self, data: bytes) -> None:
        """Reemplaza la base ACTUAL por la del backup (semántica de restaurar). Antes crea
        una copia de seguridad de lo que había (red de seguridad). Lanza ``ValueError`` si
        el archivo no es una copia válida de la app.
        """
        if not self.is_valid_backup(data):
            raise ValueError("El archivo no es una copia de seguridad válida.")
        self.backup("pre-restore")           # respalda lo actual por si acaso
        self.close()
        # Limpia journals sueltos antes de pisar el archivo, para no mezclar estados.
        for suffix in ("-journal", "-wal", "-shm"):
            Path(str(self._config.path) + suffix).unlink(missing_ok=True)
        self._config.path.parent.mkdir(parents=True, exist_ok=True)
        self._config.path.write_bytes(data)
        self.init_schema()                   # reabre y asegura el esquema (idempotente)

    # ------------------------------------------------------------------
    # Inicialización del esquema
    # ------------------------------------------------------------------

    def init_schema(self) -> None:
        """
        Crea las tablas si no existen. Debe llamarse una vez al arrancar.
        SQLite crea el archivo de base de datos automáticamente al conectar.
        """
        conn = self._connect()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS songs (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                title      TEXT NOT NULL,
                author     TEXT,
                `key`      TEXT,
                rhythm       TEXT,
                bpm          INTEGER,
                capo         INTEGER DEFAULT 0,
                notes        TEXT,
                favorite     INTEGER DEFAULT 0,
                original_key TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sections (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                song_id   INTEGER NOT NULL,
                position  INTEGER NOT NULL,
                type      TEXT NOT NULL
                            CHECK(type IN ('verse','chorus','bridge','intro','outro')),
                label     TEXT,
                transpose INTEGER DEFAULT 0,
                FOREIGN KEY (song_id) REFERENCES songs(id) ON DELETE CASCADE
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS `lines` (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                section_id INTEGER NOT NULL,
                position   INTEGER NOT NULL,
                FOREIGN KEY (section_id) REFERENCES sections(id) ON DELETE CASCADE
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS syllables (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                line_id  INTEGER NOT NULL,
                position INTEGER NOT NULL,
                text     TEXT NOT NULL,
                FOREIGN KEY (line_id) REFERENCES `lines`(id) ON DELETE CASCADE
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS chords (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                syllable_id INTEGER NOT NULL UNIQUE,
                value       TEXT NOT NULL,
                FOREIGN KEY (syllable_id) REFERENCES syllables(id) ON DELETE CASCADE
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS setlists (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS setlist_songs (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                setlist_id INTEGER NOT NULL,
                song_id    INTEGER NOT NULL,
                position   INTEGER NOT NULL,
                transpose  INTEGER DEFAULT 0,
                FOREIGN KEY (setlist_id) REFERENCES setlists(id) ON DELETE CASCADE,
                FOREIGN KEY (song_id)    REFERENCES songs(id)    ON DELETE CASCADE
            )
        """)
        # Autores favoritos. El autor no es una entidad propia (es un campo de
        # `songs`), así que la marca vive aparte, referenciada por nombre.
        cur.execute("""
            CREATE TABLE IF NOT EXISTS author_favorites (
                name TEXT PRIMARY KEY
            )
        """)
        # Rastro de cada escritura a songs.favorite (bug abierto, ver ROADMAP).
        cur.execute("""
            CREATE TABLE IF NOT EXISTS fav_audit (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                song_id INTEGER NOT NULL,
                value   INTEGER NOT NULL,
                at      TEXT DEFAULT (datetime('now'))
            )
        """)
        self._migrate_section_transpose(cur)
        self._migrate_song_favorite(cur)
        self._migrate_song_original_key(cur)
        self._migrate_song_bpm(cur)
        conn.commit()

    def _migrate_section_transpose(self, cur: sqlite3.Cursor) -> None:
        """Añade la columna ``transpose`` a ``sections`` si una BD antigua no la tiene."""
        cur.execute("PRAGMA table_info(sections)")
        columns = [row[1] for row in cur.fetchall()]  # row[1] = nombre de columna
        if "transpose" not in columns:
            cur.execute("ALTER TABLE sections ADD COLUMN transpose INTEGER DEFAULT 0")

    def _migrate_song_favorite(self, cur: sqlite3.Cursor) -> None:
        """Añade la columna ``favorite`` a ``songs`` si una BD antigua no la tiene."""
        cur.execute("PRAGMA table_info(songs)")
        columns = [row[1] for row in cur.fetchall()]
        if "favorite" not in columns:
            cur.execute("ALTER TABLE songs ADD COLUMN favorite INTEGER DEFAULT 0")

    def _migrate_song_original_key(self, cur: sqlite3.Cursor) -> None:
        """Añade la columna ``original_key`` a ``songs`` si una BD antigua no la tiene."""
        cur.execute("PRAGMA table_info(songs)")
        columns = [row[1] for row in cur.fetchall()]
        if "original_key" not in columns:
            cur.execute("ALTER TABLE songs ADD COLUMN original_key TEXT")

    def _migrate_song_bpm(self, cur: sqlite3.Cursor) -> None:
        """Añade la columna ``bpm`` a ``songs`` si una BD antigua no la tiene."""
        cur.execute("PRAGMA table_info(songs)")
        columns = [row[1] for row in cur.fetchall()]
        if "bpm" not in columns:
            cur.execute("ALTER TABLE songs ADD COLUMN bpm INTEGER")

    # ------------------------------------------------------------------
    # CRUD canciones
    # ------------------------------------------------------------------

    def save_song(self, song: Song) -> int:
        """
        Inserta o actualiza una canción completa (incluyendo secciones, líneas,
        sílabas y acordes). Devuelve el id asignado.
        """
        # Normalización: quitar espacios sobrantes del autor
        if song.author is not None:
            song.author = song.author.strip() or None

        conn = self._connect()
        cur = conn.cursor()
        try:
            if song.id is None:
                cur.execute(
                    "INSERT INTO songs (title, author, `key`, original_key, rhythm, bpm, capo, notes) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (song.title, song.author, song.key, song.original_key,
                     song.rhythm, song.bpm, song.capo, song.notes),
                )
                song.id = cur.lastrowid
            else:
                cur.execute(
                    "UPDATE songs SET title=?, author=?, `key`=?, original_key=?, rhythm=?, bpm=?, "
                    "capo=?, notes=?, updated_at=datetime('now') WHERE id=?",
                    (song.title, song.author, song.key, song.original_key, song.rhythm, song.bpm,
                     song.capo, song.notes, song.id),
                )
                # Borrar secciones antiguas; el CASCADE elimina líneas/sílabas/acordes
                cur.execute("DELETE FROM sections WHERE song_id=?", (song.id,))

            self._save_sections(cur, song)
            conn.commit()
        except Exception:
            _log.exception("error al guardar canción %r (id=%s)", song.title, song.id)
            conn.rollback()
            raise
        return song.id  # type: ignore[return-value]

    def _save_sections(self, cur: sqlite3.Cursor, song: Song) -> None:
        """Inserta secciones, líneas, sílabas y acordes de la canción."""
        for section in song.sections:
            cur.execute(
                "INSERT INTO sections (song_id, position, type, label, transpose) "
                "VALUES (?, ?, ?, ?, ?)",
                (song.id, section.position, section.type, section.label,
                 section.transpose),
            )
            section.id = cur.lastrowid

            for line in section.lines:
                cur.execute(
                    "INSERT INTO `lines` (section_id, position) VALUES (?, ?)",
                    (section.id, line.position),
                )
                line.id = cur.lastrowid

                for syllable in line.syllables:
                    cur.execute(
                        "INSERT INTO syllables (line_id, position, text) VALUES (?, ?, ?)",
                        (line.id, syllable.position, syllable.text),
                    )
                    syllable.id = cur.lastrowid

                    if syllable.chord is not None:
                        cur.execute(
                            "INSERT INTO chords (syllable_id, value) VALUES (?, ?)",
                            (syllable.id, syllable.chord.value),
                        )
                        syllable.chord.id = cur.lastrowid

    def load_song(self, song_id: int) -> Song:
        """Carga una canción completa desde la base de datos."""
        conn = self._connect()
        cur = conn.cursor()
        cur.execute(
            "SELECT id, title, author, `key`, original_key, rhythm, bpm, capo, notes "
            "FROM songs WHERE id=?",
            (song_id,),
        )
        row = cur.fetchone()
        if row is None:
            raise ValueError(f"No existe la canción con id={song_id}")

        song = Song(
            id=row["id"],
            title=row["title"],
            author=row["author"],
            key=row["key"],
            original_key=row["original_key"],
            rhythm=row["rhythm"],
            bpm=row["bpm"],
            capo=row["capo"] or 0,
            notes=row["notes"],
        )

        cur.execute(
            "SELECT id, position, type, label, transpose FROM sections "
            "WHERE song_id=? ORDER BY position",
            (song_id,),
        )
        for sec_row in cur.fetchall():
            section = Section(
                id=sec_row["id"],
                position=sec_row["position"],
                type=sec_row["type"],
                label=sec_row["label"],
                transpose=sec_row["transpose"] or 0,
            )
            section.lines = self._load_lines(cur, sec_row["id"])
            song.sections.append(section)

        return song

    def _load_lines(self, cur: sqlite3.Cursor, section_id: int) -> list[Line]:
        """Carga las líneas de una sección, incluyendo sílabas y acordes."""
        cur.execute(
            "SELECT id, position FROM `lines` WHERE section_id=? ORDER BY position",
            (section_id,),
        )
        lines: list[Line] = []
        for line_row in cur.fetchall():
            line = Line(id=line_row["id"], position=line_row["position"])

            cur.execute(
                "SELECT s.id, s.position, s.text, c.id AS chord_id, c.value AS chord_value "
                "FROM syllables s "
                "LEFT JOIN chords c ON c.syllable_id = s.id "
                "WHERE s.line_id=? ORDER BY s.position",
                (line_row["id"],),
            )
            for syl_row in cur.fetchall():
                chord = (
                    Chord(id=syl_row["chord_id"], value=syl_row["chord_value"])
                    if syl_row["chord_value"] is not None
                    else None
                )
                line.syllables.append(
                    Syllable(
                        id=syl_row["id"],
                        position=syl_row["position"],
                        text=syl_row["text"],
                        chord=chord,
                    )
                )
            lines.append(line)
        return lines

    # Campos por los que se puede filtrar. Whitelist de nombre lógico -> columna
    # SQL real (evita inyección). Para agregar un filtro nuevo, basta una línea.
    _FILTER_COLUMNS = {
        "author": "author",
        "rhythm": "rhythm",
        "key": "`key`",
    }

    def list_songs(
        self, query: str = "", filters: dict[str, str] | None = None
    ) -> list[dict]:
        """
        Devuelve dicts con id, title, author, key, rhythm y favorite.
        Los favoritos aparecen primero; dentro de cada grupo, por título.

        ``query`` filtra por título o autor (búsqueda parcial). ``filters`` es un
        dict {campo: valor} para filtros exactos (ej. {"author": "..."}); solo se
        aceptan los campos de ``_FILTER_COLUMNS``. Todos los criterios se combinan
        con AND.
        """
        where: list[str] = []
        params: list[str] = []

        if query:
            pattern = f"%{query}%"
            where.append("(title LIKE ? OR author LIKE ?)")
            params.extend([pattern, pattern])

        for field, value in (filters or {}).items():
            column = self._FILTER_COLUMNS.get(field)
            if not column or not value:
                continue
            if field == "author" and value == UNKNOWN_AUTHOR:
                where.append("(author IS NULL OR author = '')")   # canciones sin autor
            else:
                where.append(f"{column} = ?")
                params.append(value)

        sql = "SELECT id, title, author, `key`, rhythm, favorite FROM songs"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY favorite DESC, title"      # favoritos primero

        conn = self._connect()
        cur = conn.cursor()
        cur.execute(sql, params)
        return [dict(row) for row in cur.fetchall()]

    def set_favorite(self, song_id: int, favorite: bool) -> None:
        """Marca o desmarca una canción como favorita (salen primero en la lista).

        Deja rastro en ``fav_audit``: hay un bug abierto en el que la marca cambia
        sin que nadie la toque, y no se ha podido reproducir. El registro sirve
        para saber si la escritura vino de la app o no (ver ROADMAP).
        """
        conn = self._connect()
        cur = conn.cursor()
        try:
            cur.execute("UPDATE songs SET favorite=? WHERE id=?",
                        (1 if favorite else 0, song_id))
            cur.execute(
                "INSERT INTO fav_audit (song_id, value) VALUES (?, ?)",
                (song_id, 1 if favorite else 0))
            conn.commit()
        except Exception:
            _log.exception("error al marcar favorito id=%s", song_id)
            conn.rollback()
            raise

    def favorite_audit(self, limit: int = 20) -> list[dict]:
        """Últimas escrituras a ``songs.favorite``, de la más reciente a la más vieja."""
        conn = self._connect()
        cur = conn.cursor()
        cur.execute(
            "SELECT song_id, value, at FROM fav_audit ORDER BY id DESC LIMIT ?", (limit,))
        return [dict(row) for row in cur.fetchall()]

    def distinct_values(self, field: str) -> list[str]:
        """Valores distintos no vacíos de un campo filtrable (para los desplegables)."""
        column = self._FILTER_COLUMNS.get(field)
        if column is None:
            raise ValueError(f"Campo no filtrable: {field}")
        conn = self._connect()
        cur = conn.cursor()
        cur.execute(
            f"SELECT DISTINCT {column} FROM songs "
            f"WHERE {column} IS NOT NULL AND {column} <> '' ORDER BY {column}"
        )
        return [row[0] for row in cur.fetchall()]

    # ------------------------------------------------------------------
    # Autores (derivados de songs.author; el favorito vive en author_favorites)
    # ------------------------------------------------------------------

    def list_authors(self) -> list[dict]:
        """Autores con su número de canciones. Los favoritos aparecen primero.

        Devuelve dicts con name, song_count y favorite. Las canciones sin autor
        se agrupan al final bajo el marcador ``UNKNOWN_AUTHOR`` (name), que la UI
        muestra como «Desconocido».
        """
        conn = self._connect()
        cur = conn.cursor()
        cur.execute("""
            SELECT s.author AS name,
                   COUNT(*) AS song_count,
                   (f.name IS NOT NULL) AS favorite
            FROM songs s
            LEFT JOIN author_favorites f ON f.name = s.author
            WHERE s.author IS NOT NULL AND s.author <> ''
            GROUP BY s.author
            ORDER BY favorite DESC, s.author
        """)
        authors = [dict(row) for row in cur.fetchall()]

        # Grupo «Desconocido»: canciones sin autor, siempre al final.
        cur.execute("SELECT COUNT(*) FROM songs WHERE author IS NULL OR author = ''")
        sin_autor = cur.fetchone()[0]
        if sin_autor:
            authors.append({"name": UNKNOWN_AUTHOR, "song_count": sin_autor,
                            "favorite": 0, "unknown": True})
        return authors

    def set_author_favorite(self, name: str, favorite: bool) -> None:
        """Marca o desmarca un autor como favorito (sale primero en la lista)."""
        conn = self._connect()
        cur = conn.cursor()
        try:
            if favorite:
                cur.execute(
                    "INSERT OR IGNORE INTO author_favorites (name) VALUES (?)", (name,))
            else:
                cur.execute("DELETE FROM author_favorites WHERE name=?", (name,))
            conn.commit()
        except Exception:
            _log.exception("error al marcar autor favorito %r", name)
            conn.rollback()
            raise

    def delete_author(self, name: str) -> int:
        """Elimina un autor y **todas sus canciones**. Devuelve cuántas borró.

        Hace backup antes: es la operación más destructiva de la app.
        """
        self.backup("delete_author")
        conn = self._connect()
        cur = conn.cursor()
        try:
            if name == UNKNOWN_AUTHOR:
                cur.execute("DELETE FROM songs WHERE author IS NULL OR author = ''")
            else:
                cur.execute("DELETE FROM songs WHERE author=?", (name,))
            deleted = cur.rowcount
            cur.execute("DELETE FROM author_favorites WHERE name=?", (name,))
            conn.commit()
            _log.info("autor eliminado: %r (%d canciones)", name, deleted)
            return deleted
        except Exception:
            _log.exception("error al eliminar autor %r", name)
            conn.rollback()
            raise

    def rename_author(self, old: str, new: str) -> None:
        """
        Renombra un autor en todas sus canciones. Si ``new`` coincide con un autor
        existente, ambos quedan fusionados. Si ``new`` queda vacío, las canciones
        quedan sin autor (NULL). La marca de favorito viaja con el nombre.
        """
        new_value = new.strip() or None
        self.backup("rename_author")
        conn = self._connect()
        cur = conn.cursor()
        try:
            cur.execute("UPDATE songs SET author=? WHERE author=?", (new_value, old))
            # La marca sigue al autor; si se queda sin nombre, se descarta.
            cur.execute("SELECT 1 FROM author_favorites WHERE name=?", (old,))
            was_favorite = cur.fetchone() is not None
            cur.execute("DELETE FROM author_favorites WHERE name=?", (old,))
            if was_favorite and new_value:
                cur.execute(
                    "INSERT OR IGNORE INTO author_favorites (name) VALUES (?)", (new_value,))
            conn.commit()
            _log.info("autor renombrado: %r -> %r", old, new_value)
        except Exception:
            _log.exception("error al renombrar autor %r", old)
            conn.rollback()
            raise

    def delete_song(self, song_id: int) -> None:
        """Elimina una canción y todos sus datos relacionados."""
        self.backup("delete_song")
        conn = self._connect()
        cur = conn.cursor()
        try:
            cur.execute("DELETE FROM songs WHERE id=?", (song_id,))
            conn.commit()
            _log.info("canción eliminada: id=%s", song_id)
        except Exception:
            _log.exception("error al eliminar canción id=%s", song_id)
            conn.rollback()
            raise

    # ------------------------------------------------------------------
    # CRUD listas de canciones (setlists)
    # ------------------------------------------------------------------

    def list_setlists(self) -> list[dict]:
        """Devuelve las listas como dicts con id, name y song_count."""
        conn = self._connect()
        cur = conn.cursor()
        cur.execute(
            "SELECT s.id, s.name, COUNT(ss.id) AS song_count "
            "FROM setlists s "
            "LEFT JOIN setlist_songs ss ON ss.setlist_id = s.id "
            "GROUP BY s.id, s.name ORDER BY s.name"
        )
        return [dict(row) for row in cur.fetchall()]

    def create_setlist(self, name: str) -> int:
        """Crea una lista vacía y devuelve su id."""
        conn = self._connect()
        cur = conn.cursor()
        try:
            cur.execute("INSERT INTO setlists (name) VALUES (?)", (name,))
            new_id = cur.lastrowid
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        return new_id  # type: ignore[return-value]

    def save_setlist(self, setlist: Setlist) -> int:
        """
        Inserta o actualiza una lista completa (nombre + canciones ordenadas con
        su tono). Reemplaza todos los items en una sola transacción. Devuelve el id.
        """
        conn = self._connect()
        cur = conn.cursor()
        try:
            if setlist.id is None:
                cur.execute("INSERT INTO setlists (name) VALUES (?)", (setlist.name,))
                setlist.id = cur.lastrowid
            else:
                cur.execute(
                    "UPDATE setlists SET name=?, updated_at=datetime('now') WHERE id=?",
                    (setlist.name, setlist.id),
                )
                cur.execute(
                    "DELETE FROM setlist_songs WHERE setlist_id=?", (setlist.id,)
                )

            for pos, item in enumerate(setlist.items):
                cur.execute(
                    "INSERT INTO setlist_songs "
                    "(setlist_id, song_id, position, transpose) "
                    "VALUES (?, ?, ?, ?)",
                    (setlist.id, item.song_id, pos, item.transpose),
                )
                item.position = pos
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        return setlist.id  # type: ignore[return-value]

    def load_setlist(self, setlist_id: int) -> Setlist:
        """Carga una lista con sus canciones (título y tono de cada una)."""
        conn = self._connect()
        cur = conn.cursor()
        cur.execute("SELECT id, name FROM setlists WHERE id=?", (setlist_id,))
        row = cur.fetchone()
        if row is None:
            raise ValueError(f"No existe la lista con id={setlist_id}")

        setlist = Setlist(id=row["id"], name=row["name"])

        cur.execute(
            "SELECT ss.id, ss.song_id, ss.position, ss.transpose, "
            "       so.title, so.`key`, so.author, so.rhythm "
            "FROM setlist_songs ss "
            "JOIN songs so ON so.id = ss.song_id "
            "WHERE ss.setlist_id=? ORDER BY ss.position",
            (setlist_id,),
        )
        for item_row in cur.fetchall():
            setlist.items.append(
                SetlistItem(
                    id=item_row["id"],
                    song_id=item_row["song_id"],
                    position=item_row["position"],
                    transpose=item_row["transpose"] or 0,
                    title=item_row["title"],
                    key=item_row["key"],
                    author=item_row["author"],
                    rhythm=item_row["rhythm"],
                )
            )
        return setlist

    def delete_setlist(self, setlist_id: int) -> None:
        """Elimina una lista y sus referencias a canciones (las canciones quedan)."""
        self.backup("delete_setlist")
        conn = self._connect()
        cur = conn.cursor()
        try:
            cur.execute("DELETE FROM setlists WHERE id=?", (setlist_id,))
            conn.commit()
            _log.info("lista eliminada: id=%s", setlist_id)
        except Exception:
            _log.exception("error al eliminar lista id=%s", setlist_id)
            conn.rollback()
            raise
