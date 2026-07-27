"""PLANTILLA para una maqueta nueva. Copiá este archivo con otro nombre y editá.

Pasos:
  1. Copiar a ``ui_lab/maquetas/mi_idea.py``.
  2. Cambiar NOMBRE y DESCRIPCION (salen en el selector del laboratorio).
  3. Escribir ``construir``; devolver el control raíz de la pantalla.
  4. Registrarla en ``ui_lab/maquetas/__init__.py`` (una línea).

Reglas del laboratorio:
  · Datos SIEMPRE de ``db`` (la BaseFalsa) o inventados aquí. Nunca la base real.
  · Se pueden importar los widgets de ``views.widgets`` y los colores de ``theme``:
    de eso se trata, de que se vea igual que la app.
  · Nada de lo que se escriba aquí llega a la app hasta que se porte a mano.
"""

from __future__ import annotations
import flet as ft

import theme
from views.widgets import logo_header

NOMBRE = "Plantilla (copiame)"
DESCRIPCION = "Punto de partida para una idea nueva."


def construir(page: ft.Page, db) -> ft.Control:
    """Arma la maqueta.

    ``page`` es la página de Flet (para ``page.update()`` si algo cambia en el sitio).
    ``db``   es la ``BaseFalsa``: ``db.list_songs()``, ``db.list_authors()``,
             ``db.list_setlists()``.
    """
    canciones = db.list_songs()

    return ft.Column(expand=True, spacing=0, controls=[
        logo_header(),
        ft.Container(
            expand=True, alignment=ft.Alignment.CENTER,
            content=ft.Column(
                tight=True, horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Text("Tu maqueta va acá", size=20,
                            weight=ft.FontWeight.BOLD, color=theme.THEME["text"]),
                    ft.Text(f"hay {len(canciones)} canciones falsas para usar",
                            size=13, color=theme.THEME["text_muted"]),
                ])),
    ])
