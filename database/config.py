"""Configuración de la base de datos SQLite de HymnChords (versión móvil / Flet).

Igual que en el escritorio, la base es un único archivo SQLite. Lo único que cambia
respecto a la app de escritorio es DÓNDE vive ese archivo según la plataforma:

- En el dispositivo (APK empaquetado con Flet), Flet expone una carpeta privada y
  escribible por-app en la variable de entorno ``FLET_APP_STORAGE_DATA``. Es la
  fuente de verdad en Android/iOS.
  VERIFICADO en el emulador: la variable existe y apunta a
  ``/data/user/0/<paquete>/app_flutter``, que sobrevive a reinstalar el APK
  (probado marcando un favorito y actualizando la app encima).
- En desarrollo de escritorio (``flet run``), se usa ``APPDATA`` (Windows) o el home.
  Se usa un nombre de carpeta propio ("HymnChordsMobile") para NO compartir la base
  con la app de escritorio original (que usa "HymnChords"): así el desarrollo nunca
  toca la biblioteca real del usuario.

La API pública (``DBConfig``, ``data_dir``, ``load_config``, ``DB_FILENAME``) es la
misma que en el escritorio, para que ``database/db.py`` y los tests funcionen sin
cambios.
"""

from __future__ import annotations
import os
from dataclasses import dataclass
from pathlib import Path

# Carpeta propia de la versión móvil, separada de la del escritorio ("HymnChords").
APP_DIR_NAME = "HymnChordsMobile"
DB_FILENAME = "hymnchords.db"


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

    Si no se indica ``path``, se usa ``<carpeta de datos>/hymnchords.db``. Los
    tests pasan una ruta temporal propia para no tocar nunca la base real.
    """
    if path is None:
        path = data_dir() / DB_FILENAME
    return DBConfig(path=path)
