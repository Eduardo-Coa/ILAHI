r"""Utilidad de DESARROLLO: re-siembra la BD que usa ``flet run`` con los datos de
``sample_data`` (canciones + lista), en el sitio donde Flet la guarda en escritorio
(``storage/data/``).

Funciona aunque flet esté abierto (SQLite permite escritura concurrente): borra lo
existente y vuelve a insertar. Tras correrlo, en la app: '‹ Volver' y reabre (o
reinicia flet) para ver los datos nuevos.

Uso:  .\.venv\Scripts\python.exe tools\reseed_dev.py
"""

from __future__ import annotations
import sys
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ))

from database.config import DBConfig
from database.db import Database
from sample_data import sample_songs, sample_setlist
from utils.song_text import line_to_chord_lyric

# En escritorio, `flet run` define FLET_APP_STORAGE_DATA -> <proyecto>/storage/data.
DB_PATH = PROJ / "storage" / "data" / "ilahi.db"


def main() -> None:
    db = Database(DBConfig(path=DB_PATH))
    db.init_schema()
    for sl in db.list_setlists():        # borra listas viejas
        db.delete_setlist(sl["id"])
    for s in db.list_songs():            # borra canciones (cascade a secciones/…)
        db.delete_song(s["id"])
    for song in sample_songs():          # re-siembra canciones
        db.save_song(song)
    song_ids = [s["id"] for s in db.list_songs()]
    db.save_setlist(sample_setlist(song_ids))   # re-siembra lista

    rows = db.list_songs()
    first_line = db.load_song(rows[0]["id"]).sections[0].lines[0]
    setlists = db.list_setlists()
    db.close()
    print(f"Re-sembrado en: {DB_PATH}")
    print("Canciones:", [r["title"] for r in rows])
    print("Listas:", [(s["name"], s["song_count"]) for s in setlists])
    print("Primera linea:", repr(line_to_chord_lyric(first_line)[1]))


if __name__ == "__main__":
    main()
