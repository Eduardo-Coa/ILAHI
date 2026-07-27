"""Pasar de una canción a otra dentro de su lista (arrastrando o con ‹/›).

La vista de canción hereda el RECORRIDO que la lista tenía en pantalla al abrirla,
igual que ya hacía una setlist. Aquí se prueba de dónde sale ese recorrido
(``SongsScreen.browse_song_ids``) y cómo se ubica una canción dentro de él
(``main.posicion_en_recorrido``), que es lo que decide si hay anterior/siguiente.
"""

from __future__ import annotations

from models.song import Song
from database.db import PINNED_ALBUM
from main import posicion_en_recorrido
from views.song_list_view import SongsScreen
from views.stage_view import StageScreen


def _textos(control, acc=None) -> list[str]:
    """Todos los textos visibles de un árbol de controles."""
    acc = [] if acc is None else acc
    valor = getattr(control, "value", None)
    if isinstance(valor, str) and valor.strip():
        acc.append(valor)
    for atributo in ("controls", "content"):
        hijo = getattr(control, atributo, None)
        if hijo is None:
            continue
        for c in (hijo if isinstance(hijo, list) else [hijo]):
            _textos(c, acc)
    return acc


def _barra(nav_buttons: bool) -> list[str]:
    pantalla = StageScreen(
        None, Song(id=1, title="Himno", key="D"), on_back=lambda: None,
        on_prev=lambda: None, on_next=lambda: None,
        position_label="2/500", nav_buttons=nav_buttons)
    return _textos(pantalla._top_bar())


# -- ‹/› solo dentro de una lista, el contador siempre ------------------------

def test_dentro_de_una_lista_hay_botones_y_contador():
    textos = _barra(nav_buttons=True)
    assert "‹ Anterior" in textos
    assert "Siguiente ›" in textos
    assert "2/500" in textos


def test_fuera_de_una_lista_queda_solo_el_contador():
    """En un álbum/autor/biblioteca se pasa de canción arrastrando: las píldoras
    sobran, pero la posición sigue interesando."""
    textos = _barra(nav_buttons=False)
    assert "2/500" in textos
    assert not [t for t in textos if "Anterior" in t or "Siguiente" in t]


# -- ubicación dentro del recorrido -------------------------------------------

def test_posicion_en_el_medio_tiene_anterior_y_siguiente():
    i, total, etiqueta = posicion_en_recorrido([10, 20, 30], 20)
    assert (i, total, etiqueta) == (1, 3, "2/3")


def test_la_primera_no_tiene_anterior():
    i, _total, etiqueta = posicion_en_recorrido([10, 20, 30], 10)
    assert i == 0                      # sin anterior
    assert etiqueta == "1/3"


def test_la_ultima_no_tiene_siguiente():
    i, total, etiqueta = posicion_en_recorrido([10, 20, 30], 30)
    assert i == total - 1              # sin siguiente
    assert etiqueta == "3/3"


def test_sin_recorrido_no_hay_navegacion():
    """Abrir una canción fuera de una lista no debe ofrecer anterior/siguiente."""
    assert posicion_en_recorrido(None, 10) == (None, 0, "")
    assert posicion_en_recorrido([], 10) == (None, 0, "")


def test_una_cancion_ajena_al_recorrido_no_navega():
    assert posicion_en_recorrido([10, 20], 99) == (None, 0, "")


def test_una_sola_cancion_no_tiene_vecinas():
    i, total, etiqueta = posicion_en_recorrido([10], 10)
    assert (i, total) == (0, 1)        # ni anterior ni siguiente
    assert etiqueta == "1/1"


# -- de dónde sale el recorrido -----------------------------------------------

def _pantalla(db, **kwargs) -> SongsScreen:
    nada = lambda *a, **k: None
    opciones = dict(
        on_open_song=nada, on_open_setlists=nada, on_import=nada,
        on_export_all=nada, on_new_song=nada, on_edit_song=nada,
        on_export_song=nada, on_open_authors=nada, embedded=True,
        external_search=True)
    opciones.update(kwargs)
    return SongsScreen(None, db, **opciones)


def test_el_recorrido_sale_de_la_lista_en_su_orden(db):
    db.save_song(Song(id=None, title="Bravo"))
    db.save_song(Song(id=None, title="Alfa"))
    db.save_song(Song(id=None, title="Charlie"))

    pantalla = _pantalla(db)
    pantalla._refill(update=False)

    titulos = [db.load_song(i).title for i in pantalla.browse_song_ids()]
    assert titulos == ["Alfa", "Bravo", "Charlie"]      # el orden de la lista


def test_el_recorrido_respeta_el_filtro_por_album(db):
    db.save_song(Song(id=None, title="Himno", album=PINNED_ALBUM))
    db.save_song(Song(id=None, title="Suelta", author="Ana Pérez"))

    pantalla = _pantalla(db, filtro=("album", PINNED_ALBUM))
    pantalla._refill(update=False)

    ids = pantalla.browse_song_ids()
    assert [db.load_song(i).title for i in ids] == ["Himno"]


def test_el_recorrido_IGNORA_la_busqueda(db):
    """Buscar sirve para ENCONTRAR la canción; al abrirla se está en el álbum, no en
    el resultado. Así el contador dice «142/628» y no «1/2», y arrastrar lleva a la
    canción que sigue en el álbum, no al otro resultado."""
    db.save_song(Song(id=None, title="Cantad alegres"))
    db.save_song(Song(id=None, title="Da gloria"))
    db.save_song(Song(id=None, title="Cantad con gozo"))

    pantalla = _pantalla(db, query="Cantad")
    pantalla._refill(update=False)

    # La lista EN PANTALLA sí filtra…
    assert len(pantalla._filler._items) == 2
    # …pero el recorrido lleva las tres, en su orden alfabético.
    titulos = [db.load_song(i).title for i in pantalla.browse_song_ids()]
    assert titulos == ["Cantad alegres", "Cantad con gozo", "Da gloria"]


def test_el_recorrido_ignora_la_busqueda_pero_respeta_el_album(db):
    """Buscando DENTRO de un álbum, el recorrido es ese álbum entero (no la
    biblioteca): el contador cuenta sobre el himnario, no sobre todo."""
    db.save_song(Song(id=None, title="Cantad alegres", album=PINNED_ALBUM))
    db.save_song(Song(id=None, title="Da gloria", album=PINNED_ALBUM))
    db.save_song(Song(id=None, title="Cantad suelta", author="Ana Pérez"))

    pantalla = _pantalla(db, filtro=("album", PINNED_ALBUM), query="Cantad")
    pantalla._refill(update=False)

    titulos = [db.load_song(i).title for i in pantalla.browse_song_ids()]
    assert titulos == ["Cantad alegres", "Da gloria"]      # el álbum entero
    assert "Cantad suelta" not in titulos                  # ajena al álbum


def test_la_cancion_abierta_desde_una_busqueda_esta_en_su_recorrido(db):
    """Regresión: en Canciones el cancionero incluido se oculta al navegar, pero SÍ
    aparece al buscar. Si el recorrido lo excluyera, esa canción quedaría fuera de su
    propio recorrido y se perdería el contador."""
    himno = db.save_song(Song(id=None, title="Cantad alegres", album=PINNED_ALBUM))
    db.save_song(Song(id=None, title="Suelta", author="Ana Pérez"))

    pantalla = _pantalla(db, query="Cantad")     # en Canciones, con búsqueda
    pantalla._refill(update=False)

    assert himno in pantalla.browse_song_ids()


def test_el_recorrido_de_favoritos_son_solo_los_favoritos(db):
    a = db.save_song(Song(id=None, title="Alfa"))
    db.save_song(Song(id=None, title="Bravo"))
    db.set_favorite(a, True)

    pantalla = _pantalla(db, tab="favorites")
    pantalla._refill(update=False)

    assert pantalla.browse_song_ids() == [a]
