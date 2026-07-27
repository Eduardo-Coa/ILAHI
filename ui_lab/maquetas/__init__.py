"""Registro de maquetas del laboratorio.

Para agregar una: crear el módulo (copiando ``plantilla.py``) y sumarlo a ``MAQUETAS``.
El orden de esta lista es el orden del selector.
"""

from __future__ import annotations

from ui_lab.maquetas import (acordes_centrados, actual, album_detalle, albumes,
                             boton_guardar_flotante, campos_metadatos, plantilla)

# Cada módulo debe exponer NOMBRE, DESCRIPCION y construir(page, db).
MAQUETAS = [
    album_detalle,
    albumes,
    actual,
    acordes_centrados,
    campos_metadatos,
    boton_guardar_flotante,
    plantilla,
]
