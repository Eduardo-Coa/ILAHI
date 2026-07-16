"""Preferencias de la app: JSON en la carpeta de datos (como en el escritorio).

Un único ``preferences.json`` en ``data_dir()`` guarda pares clave→valor (p. ej.
``{"theme": "noche"}``). En Android esa carpeta es el almacenamiento por-app de
Flet (``FLET_APP_STORAGE_DATA``), que sobrevive a actualizar el APK.

Lectura tolerante: si el archivo no existe o está corrupto se devuelven los
valores por defecto — las preferencias nunca impiden arrancar. Los tests pasan
una ruta temporal propia para no tocar las preferencias reales.
"""

from __future__ import annotations
import json
from pathlib import Path
from typing import Any

from database.config import data_dir

PREFS_FILENAME = "preferences.json"


def _prefs_path(path: Path | None = None) -> Path:
    """Ruta del archivo de preferencias (la real, o la que pasen los tests)."""
    return path if path is not None else data_dir() / PREFS_FILENAME


def load_prefs(path: Path | None = None) -> dict:
    """Lee todas las preferencias; ``{}`` si no hay archivo o no es JSON válido."""
    try:
        data = json.loads(_prefs_path(path).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def get_pref(key: str, default: Any = None, path: Path | None = None) -> Any:
    """Una preferencia puntual (o ``default`` si no está guardada)."""
    return load_prefs(path).get(key, default)


def set_pref(key: str, value: Any, path: Path | None = None) -> None:
    """Guarda una preferencia (crea la carpeta y el archivo si hace falta)."""
    p = _prefs_path(path)
    prefs = load_prefs(path)
    prefs[key] = value
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(prefs, ensure_ascii=False, indent=2), encoding="utf-8")
