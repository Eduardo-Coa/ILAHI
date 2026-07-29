"""Configuración de la base de datos SQLite de Ilahi (versión móvil / Flet).

Igual que en el escritorio, la base es un único archivo SQLite. Lo único que cambia
respecto a la app de escritorio es DÓNDE vive ese archivo según la plataforma:

- En el dispositivo (APK empaquetado con Flet), Flet expone una carpeta privada y
  escribible por-app en la variable de entorno ``FLET_APP_STORAGE_DATA``. Es la
  fuente de verdad en Android/iOS.
  VERIFICADO en el emulador: la variable existe y apunta a
  ``/data/user/0/<paquete>/app_flutter``, que sobrevive a reinstalar el APK
  (probado marcando un favorito y actualizando la app encima).
- En desarrollo de escritorio (``flet run``), se usa ``APPDATA`` (Windows) o el home.
  Se usa un nombre de carpeta propio ("IlahiMobile") para NO compartir la base
  con la app de escritorio original (que usa "Ilahi"): así el desarrollo nunca
  toca la biblioteca real del usuario.

La API pública (``DBConfig``, ``data_dir``, ``load_config``, ``DB_FILENAME``) es la
misma que en el escritorio, para que ``database/db.py`` y los tests funcionen sin
cambios.
"""

from __future__ import annotations
import logging
import os
from dataclasses import dataclass
from pathlib import Path

# Carpeta propia de la versión móvil, separada de la del escritorio ("Ilahi").
APP_DIR_NAME = "IlahiMobile"
DB_FILENAME = "ilahi.db"

# Prefijo de las copias automáticas que guarda ``database/db.py``.
BACKUP_PREFIX = "ilahi-"

# Nombres heredados de cuando la app se llamaba HymnChords. Solo se usan para
# migrar una única vez los archivos que ya existen en la carpeta de datos.
LEGACY_DB_FILENAME = "hymnchords.db"
_LEGACY_FILE_RENAMES = {
    LEGACY_DB_FILENAME: DB_FILENAME,
    "hymnchords.log": "ilahi.log",
}
_LEGACY_BACKUP_PREFIX = "hymnchords-"

# Archivos que SQLite mantiene junto a la base en modo WAL. Se renombran con ella
# o se pierde lo que aún no esté volcado al archivo principal.
_SQLITE_SIDECARS = ("-wal", "-shm")

_log = logging.getLogger("ilahi.config")


@dataclass
class DBConfig:
    """Ubicación del archivo SQLite de la aplicación."""

    path: Path


def data_dir() -> Path:
    """Carpeta de datos donde vive la base (y futuras preferencias)."""
    # 1) Flet: almacenamiento persistente por-app (Android / app empaquetada).
    flet_storage = os.environ.get("FLET_APP_STORAGE_DATA")
    if flet_storage:
        return Path(flet_storage)
    # 2) Desarrollo de escritorio: carpeta de datos del usuario, aislada de la app
    #    de escritorio original gracias al APP_DIR_NAME propio.
    appdata = os.environ.get("APPDATA")  # Windows
    if appdata:
        return Path(appdata) / APP_DIR_NAME
    # macOS / Linux: carpeta oculta en el home
    return Path.home() / f".{APP_DIR_NAME.lower()}"


def load_config(path: Path | None = None) -> DBConfig:
    """
    Devuelve la configuración con la ruta al archivo SQLite.

    Si no se indica ``path``, se usa ``<carpeta de datos>/ilahi.db``. Los
    tests pasan una ruta temporal propia para no tocar nunca la base real.
    """
    if path is None:
        path = data_dir() / DB_FILENAME
    return DBConfig(path=path)


def migrate_legacy_db_files(directory: Path | None = None) -> bool:
    """Renombra en sitio los archivos heredados de HymnChords (``hymnchords*`` →
    ``ilahi*``). Devuelve True si se renombró la base.

    A diferencia del escritorio, aquí NO se mueve ninguna carpeta: en Android la
    ruta la fija Flet (``FLET_APP_STORAGE_DATA``) y no cambia al renombrar la app.
    Lo único que cambia es el nombre del archivo, así que sin esta migración la app
    abriría una base vacía y volvería a sembrar las canciones de ejemplo.

    **Debe llamarse antes de abrir la BD y antes de configurar el logging**: no se
    puede renombrar un archivo que ya está abierto. Es idempotente y nunca pisa un
    archivo con el nombre nuevo; cualquier fallo de E/S se registra sin abortar.
    """
    folder = directory if directory is not None else data_dir()
    if not folder.is_dir():
        return False

    migrated = False
    try:
        for old_name, new_name in _LEGACY_FILE_RENAMES.items():
            source = folder / old_name
            if not source.exists() or (folder / new_name).exists():
                continue
            if old_name == LEGACY_DB_FILENAME:
                _rename_with_sidecars(source, folder / new_name)
                migrated = True
            else:
                source.rename(folder / new_name)
        _rename_legacy_backups(folder / "backups")
    except OSError:
        _log.exception("no se pudieron renombrar los archivos heredados en %s", folder)
        return False

    if migrated:
        _log.info("base de datos migrada: %s -> %s en %s",
                  LEGACY_DB_FILENAME, DB_FILENAME, folder)
    return migrated


def _rename_with_sidecars(source: Path, target: Path) -> None:
    """Renombra la base junto con sus archivos ``-wal`` y ``-shm``.

    SQLite asocia los sidecars por nombre: si se renombra solo la base, el WAL
    huérfano se queda con los últimos cambios y se pierden.
    """
    source.rename(target)
    for suffix in _SQLITE_SIDECARS:
        sidecar = source.with_name(source.name + suffix)
        destino = target.with_name(target.name + suffix)
        if sidecar.exists() and not destino.exists():
            sidecar.rename(destino)


def _rename_legacy_backups(backups: Path) -> None:
    """Re-prefija las copias automáticas viejas (``hymnchords-*.db``)."""
    if not backups.is_dir():
        return
    for backup in backups.glob(f"{_LEGACY_BACKUP_PREFIX}*.db"):
        target = backups / (BACKUP_PREFIX + backup.name[len(_LEGACY_BACKUP_PREFIX):])
        if not target.exists():
            backup.rename(target)
