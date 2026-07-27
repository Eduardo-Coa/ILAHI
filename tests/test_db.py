"""Pruebas de la capa de base de datos (contra la base de pruebas aislada)."""

from __future__ import annotations

from models.song import Song, Section, Line, Syllable, Chord
from models.setlist import Setlist, SetlistItem
from database.db import UNKNOWN_AUTHOR, PINNED_ALBUM


def _sample_song() -> Song:
    song = Song(id=None, title="Canción de prueba", author="Autor", key="C")
    section = Section(id=None, position=0, type="verse", label="Estrofa 1")
    line = Line(id=None, position=0)
    line.syllables = [
        Syllable(id=None, position=0, text="Glo", chord=Chord(id=None, value="C")),
        Syllable(id=None, position=1, text="ria"),
        Syllable(id=None, position=2, text="a", chord=Chord(id=None, value="G")),
    ]
    section.lines.append(line)
    song.sections.append(section)
    return song


def test_save_assigns_id(db):
    sid = db.save_song(_sample_song())
    assert isinstance(sid, int) and sid > 0


def test_save_and_load_preserves_content(db):
    sid = db.save_song(_sample_song())
    loaded = db.load_song(sid)

    assert loaded.title == "Canción de prueba"
    assert loaded.author == "Autor"
    assert loaded.key == "C"

    syllables = loaded.sections[0].lines[0].syllables
    assert [s.text for s in syllables] == ["Glo", "ria", "a"]
    assert syllables[0].chord.value == "C"
    assert syllables[1].chord is None
    assert syllables[2].chord.value == "G"


def test_save_and_load_preserves_album(db):
    song = _sample_song()
    song.album = "Himnario Adventista"
    sid = db.save_song(song)
    assert db.load_song(sid).album == "Himnario Adventista"


def test_album_defaults_to_none(db):
    sid = db.save_song(_sample_song())
    assert db.load_song(sid).album is None


def test_list_songs(db):
    db.save_song(_sample_song())
    songs = db.list_songs()
    assert len(songs) == 1
    assert songs[0]["title"] == "Canción de prueba"


def test_search_filter(db):
    db.save_song(_sample_song())
    assert len(db.list_songs("prueba")) == 1
    assert len(db.list_songs("inexistente")) == 0


def test_delete_song(db):
    sid = db.save_song(_sample_song())
    db.delete_song(sid)
    assert db.list_songs() == []


def test_exclude_album_oculta_esas_canciones(db):
    db.save_song(Song(id=None, title="A", album="Himnario Adventista"))
    db.save_song(Song(id=None, title="B", album="Himnario Adventista"))
    db.save_song(Song(id=None, title="C", author="Otro"))

    resultado = db.list_songs(exclude_album="Himnario Adventista")
    assert [s["title"] for s in resultado] == ["C"]
    # sin exclude_album, vuelven a aparecer las tres
    assert len(db.list_songs()) == 3


def test_exclude_album_no_afecta_otros_albumes(db):
    db.save_song(Song(id=None, title="A", album="Himnario Adventista"))
    db.save_song(Song(id=None, title="B", album="Cancionero Juvenil"))

    resultado = db.list_songs(exclude_album="Himnario Adventista")
    assert [s["title"] for s in resultado] == ["B"]


def _song(title, author=None, key=None):
    return Song(id=None, title=title, author=author, key=key)


def test_filter_by_author(db):
    db.save_song(_song("Sublime Gracia", author="Himnario Adventista"))
    db.save_song(_song("Cuán Grande", author="Himnario Adventista"))
    db.save_song(_song("Otra", author="Otro Autor"))

    result = db.list_songs(filters={"author": "Himnario Adventista"})
    assert len(result) == 2
    titles = {r["title"] for r in result}
    assert titles == {"Sublime Gracia", "Cuán Grande"}


def test_filter_combines_with_search(db):
    db.save_song(_song("Sublime Gracia", author="Himnario Adventista"))
    db.save_song(_song("Cuán Grande", author="Himnario Adventista"))

    result = db.list_songs(query="sublime", filters={"author": "Himnario Adventista"})
    assert len(result) == 1
    assert result[0]["title"] == "Sublime Gracia"


def test_distinct_values_authors(db):
    db.save_song(_song("A", author="Autor Uno"))
    db.save_song(_song("B", author="Autor Dos"))
    db.save_song(_song("C", author="Autor Uno"))
    db.save_song(_song("D", author=None))  # sin autor: no aparece

    assert db.distinct_values("author") == ["Autor Dos", "Autor Uno"]


def test_distinct_values_campo_invalido(db):
    import pytest
    with pytest.raises(ValueError):
        db.distinct_values("title")  # no está en _FILTER_COLUMNS


def test_rename_author_propaga_a_todas(db):
    db.save_song(_song("A", author="Hinnario Aventista"))
    db.save_song(_song("B", author="Hinnario Aventista"))
    db.save_song(_song("C", author="Otro"))

    db.rename_author("Hinnario Aventista", "Himnario Adventista")

    assert db.distinct_values("author") == ["Himnario Adventista", "Otro"]
    assert len(db.list_songs(filters={"author": "Himnario Adventista"})) == 2


def test_rename_author_fusiona(db):
    db.save_song(_song("A", author="Himnario Adventista"))
    db.save_song(_song("B", author="Hinnario Aventista"))  # errata

    db.rename_author("Hinnario Aventista", "Himnario Adventista")

    # Quedan fusionados bajo un solo autor
    assert db.distinct_values("author") == ["Himnario Adventista"]
    assert len(db.list_songs(filters={"author": "Himnario Adventista"})) == 2


def test_autor_se_normaliza_con_trim(db):
    sid = db.save_song(_song("A", author="  Himnario Adventista  "))
    loaded = db.load_song(sid)
    assert loaded.author == "Himnario Adventista"


def test_update_existing_song(db):
    song = _sample_song()
    sid = db.save_song(song)

    song.title = "Título actualizado"
    db.save_song(song)

    loaded = db.load_song(sid)
    assert loaded.title == "Título actualizado"
    # No se duplicó: sigue habiendo una sola canción
    assert len(db.list_songs()) == 1


def test_list_albumes_y_autores_mezcla_y_ordena(db):
    # Himnario Adventista: álbum SIN autor por canción (como la migración real).
    db.save_song(Song(id=None, title="A", album="Himnario Adventista"))
    db.save_song(Song(id=None, title="B", album="Himnario Adventista"))
    # Otro álbum, con autor propio por canción (álbum y autor no son excluyentes).
    db.save_song(Song(id=None, title="C", album="Cancionero Juvenil", author="Ana Pérez"))
    db.save_song(Song(id=None, title="D", author="Ana Pérez"))       # solo autor
    db.save_song(Song(id=None, title="E", author=None))              # sin autor ni álbum

    entradas = db.list_albumes_y_autores()
    resumen = [(e["tipo"], e["name"], e["song_count"]) for e in entradas]
    assert resumen == [
        ("album", "Himnario Adventista", 2),   # fijado primero
        ("album", "Cancionero Juvenil", 1),    # álbumes antes que autores
        ("autor", "Ana Pérez", 2),             # D y también C (tiene álbum y autor)
        ("autor", UNKNOWN_AUTHOR, 1),          # solo E: A y B ya están en su álbum
    ]


def test_set_album_favorite(db):
    db.save_song(Song(id=None, title="A", album="Himnario Adventista"))
    db.set_album_favorite("Himnario Adventista", True)
    entradas = db.list_albumes_y_autores()
    assert entradas[0]["favorite"] == 1

    db.set_album_favorite("Himnario Adventista", False)
    entradas = db.list_albumes_y_autores()
    assert entradas[0]["favorite"] == 0


def test_rename_album_propaga_y_conserva_favorito(db):
    db.save_song(Song(id=None, title="A", album="Hinnario Aventista"))
    db.save_song(Song(id=None, title="B", album="Hinnario Aventista"))
    db.set_album_favorite("Hinnario Aventista", True)

    db.rename_album("Hinnario Aventista", "Himnario Adventista")

    assert db.distinct_values("album") == ["Himnario Adventista"]
    assert len(db.list_songs(filters={"album": "Himnario Adventista"})) == 2
    entradas = db.list_albumes_y_autores()
    assert entradas[0]["name"] == "Himnario Adventista"
    assert entradas[0]["favorite"] == 1


def test_delete_album_borra_sus_canciones(db):
    db.save_song(Song(id=None, title="A", album="Himnario Adventista"))
    db.save_song(Song(id=None, title="B", album="Himnario Adventista"))
    db.save_song(Song(id=None, title="C", author="Otro"))

    deleted = db.delete_album("Himnario Adventista")

    assert deleted == 2
    assert len(db.list_songs()) == 1
    assert db.list_songs()[0]["title"] == "C"


def test_set_song_group_asigna_album_y_autor(db):
    sid = db.save_song(Song(id=None, title="Suelta"))

    db.set_song_group(sid, "album", PINNED_ALBUM)
    db.set_song_group(sid, "author", "Ana Pérez")

    cargada = db.load_song(sid)
    assert cargada.album == PINNED_ALBUM
    assert cargada.author == "Ana Pérez"


def test_set_song_group_vacio_deja_el_campo_en_null(db):
    sid = db.save_song(Song(id=None, title="A", album=PINNED_ALBUM))
    db.set_song_group(sid, "album", "   ")
    assert db.load_song(sid).album is None


def test_set_song_group_rechaza_campos_no_agrupables(db):
    import pytest
    sid = db.save_song(Song(id=None, title="A"))
    with pytest.raises(ValueError):
        db.set_song_group(sid, "title", "Otro título")


def test_la_lista_trae_el_album_de_cada_cancion(db):
    """Dentro de una lista, una canción del cancionero incluido (sin autor, con
    álbum) tiene que poder mostrarse por su álbum en vez de «Desconocido»."""
    sid = db.save_song(Song(id=None, title="Himno", album=PINNED_ALBUM))
    otro = db.save_song(Song(id=None, title="Suelta", author="Ana Pérez"))
    setlist = Setlist(id=None, name="Culto", items=[
        SetlistItem(id=None, song_id=sid, position=0),
        SetlistItem(id=None, song_id=otro, position=1),
    ])
    lid = db.save_setlist(setlist)

    items = db.load_setlist(lid).items
    assert items[0].author is None and items[0].album == PINNED_ALBUM
    assert items[1].author == "Ana Pérez" and items[1].album is None


def test_migra_himnario_de_author_a_album_al_iniciar(db):
    """Simula una base "vieja" (como la del teléfono, nunca tocada por el script
    manual): canciones con ``author = PINNED_ALBUM`` y sin álbum. Al arrancar de
    nuevo (``init_schema``, lo que hace la app en cada apertura), se migran solas."""
    db.save_song(Song(id=None, title="A", author=PINNED_ALBUM))
    db.save_song(Song(id=None, title="B", author=PINNED_ALBUM))
    db.save_song(Song(id=None, title="C", author="Otro"))

    db.init_schema()      # simula el siguiente arranque de la app

    por_titulo = {r["title"]: db.load_song(r["id"]) for r in db.list_songs()}
    assert por_titulo["A"].author is None
    assert por_titulo["A"].album == PINNED_ALBUM
    assert por_titulo["B"].author is None
    assert por_titulo["B"].album == PINNED_ALBUM
    assert por_titulo["C"].author == "Otro"
    assert por_titulo["C"].album is None


def test_migracion_de_himnario_es_idempotente(db):
    db.save_song(Song(id=None, title="A", author=PINNED_ALBUM))
    db.init_schema()
    db.init_schema()      # correr de nuevo no debe romper ni duplicar nada

    assert len(db.list_songs()) == 1
    loaded = db.load_song(db.list_songs()[0]["id"])
    assert loaded.album == PINNED_ALBUM
    assert loaded.author is None


def test_migracion_no_toca_canciones_que_ya_tienen_album(db):
    db.save_song(Song(id=None, title="A", author=PINNED_ALBUM, album="Otro álbum"))
    db.init_schema()

    loaded = db.load_song(db.list_songs()[0]["id"])
    assert loaded.author == PINNED_ALBUM     # no se tocó: ya tenía álbum propio
    assert loaded.album == "Otro álbum"
