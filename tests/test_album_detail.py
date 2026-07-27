"""Vista propia de un álbum/autor y su selector «Elegir existentes».

Lo que se prueba aquí es la lógica, no el dibujo: qué columna agrupa cada tipo,
qué canciones ofrece el selector (nunca las que ya están en el grupo) y que
agregar una la asigne de verdad y la saque de la lista de candidatas.
"""

from __future__ import annotations

from models.song import Song
from database.db import PINNED_ALBUM
from views.album_detail_view import AddToEntryScreen, campo_de, etiqueta_de


def test_campo_y_etiqueta_por_tipo():
    assert campo_de("album") == "album"
    assert campo_de("autor") == "author"
    assert etiqueta_de("album") == "álbum"
    assert etiqueta_de("autor") == "autor"


def _poblar(db) -> None:
    db.save_song(Song(id=None, title="Himno A", album=PINNED_ALBUM))
    db.save_song(Song(id=None, title="Himno B", album=PINNED_ALBUM))
    db.save_song(Song(id=None, title="Suelta", author="Ana Pérez"))
    db.save_song(Song(id=None, title="Otra", author="Beto Ruiz"))


def _candidatas(pantalla: AddToEntryScreen) -> list[str]:
    """Títulos que el selector ofrece ahora mismo."""
    return [s["title"] for s in pantalla._filler._items]


def test_el_selector_no_ofrece_las_que_ya_estan_en_el_album(db):
    _poblar(db)
    pantalla = AddToEntryScreen(db, "album", PINNED_ALBUM, on_back=lambda: None)
    pantalla._refill()

    assert sorted(_candidatas(pantalla)) == ["Otra", "Suelta"]


def test_el_selector_no_ofrece_las_que_ya_son_de_ese_autor(db):
    _poblar(db)
    pantalla = AddToEntryScreen(db, "autor", "Ana Pérez", on_back=lambda: None)
    pantalla._refill()

    assert "Suelta" not in _candidatas(pantalla)
    assert sorted(_candidatas(pantalla)) == ["Himno A", "Himno B", "Otra"]


def test_agregar_asigna_el_album_y_saca_la_fila(db):
    _poblar(db)
    pantalla = AddToEntryScreen(db, "album", PINNED_ALBUM, on_back=lambda: None)
    pantalla._refill()
    suelta = next(s for s in db.list_songs() if s["title"] == "Suelta")

    pantalla._add(suelta)

    assert db.load_song(suelta["id"]).album == PINNED_ALBUM
    assert "Suelta" not in _candidatas(pantalla)      # ya no se vuelve a ofrecer
    assert len(db.list_songs(filters={"album": PINNED_ALBUM})) == 3


def test_agregar_a_un_autor_no_toca_el_album(db):
    """Álbum y autor son independientes: sumar un himno a un autor lo deja en su
    álbum (una canción puede tener los dos)."""
    _poblar(db)
    pantalla = AddToEntryScreen(db, "autor", "Ana Pérez", on_back=lambda: None)
    pantalla._refill()
    himno = next(s for s in db.list_songs() if s["title"] == "Himno A")

    pantalla._add(himno)

    recargada = db.load_song(himno["id"])
    assert recargada.author == "Ana Pérez"
    assert recargada.album == PINNED_ALBUM


def test_el_buscador_del_selector_filtra_sin_perder_la_exclusion(db):
    _poblar(db)
    pantalla = AddToEntryScreen(db, "album", PINNED_ALBUM, on_back=lambda: None)
    pantalla._query = "Himno"
    pantalla._refill()

    # "Himno A"/"Himno B" coinciden con la búsqueda pero YA están en el álbum.
    assert _candidatas(pantalla) == []
