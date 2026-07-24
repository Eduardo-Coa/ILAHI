"""Alineación de acordes por sílaba en la vista de canción/escenario.

Cada sílaba es su propia caja CENTRADA (acorde arriba, letra abajo); entre dos
sílabas de la misma palabra se agrega un guion de unión solo cuando el acorde de
alguna de las dos la ensancha más allá de su propia letra (y ninguna es una
casilla vacía). Ver ``views/stage_view.py::_word_col``.
"""

from models.song import Syllable, Chord
from views.stage_view import _word_col, _es_solo_puntuacion, _mover_sueltos_tras_puntuacion

_SIZE = 20
_CHORD_SIZE = 16


def _word(*pairs):
    return [Syllable(id=None, position=i, text=t,
                     chord=Chord(id=None, value=c) if c else None)
            for i, (t, c) in enumerate(pairs)]


def _celdas(word_syllables):
    return _word_col(word_syllables, _SIZE, _CHORD_SIZE).controls


def _valores(celda):
    """(texto_acorde, texto_letra) de una caja [acorde / letra]."""
    return celda.controls[0].value, celda.controls[1].value


def test_acorde_ancho_agrega_un_guion_de_union():
    celdas = _celdas(_word(("par", "G#m7"), ("tir", "C#7")))
    assert len(celdas) == 3       # par | guion | tir
    assert _valores(celdas[0]) == ("G#m7", "par")
    assert celdas[1].controls[1].value == "-"
    assert _valores(celdas[2]) == ("C#7", "tir")


def test_acorde_mediano_sin_guion_si_no_hace_falta():
    celdas = _celdas(_word(("par", "Bm7"), ("tir", "E7")))
    assert len(celdas) == 2       # ninguno de los dos acordes ensancha su sílaba
    assert _valores(celdas[0]) == ("Bm7", "par")
    assert _valores(celdas[1]) == ("E7", "tir")


def test_acordes_cortos_sin_guion():
    celdas = _celdas(_word(("par", "A"), ("tir", "E")))
    assert len(celdas) == 2
    assert _valores(celdas[0]) == ("A", "par")
    assert _valores(celdas[1]) == ("E", "tir")


def test_acorde_solo_en_primera_silaba_sin_ensanchar_no_agrega_guion():
    celdas = _celdas(_word(("ho", "C"), ("la", None)))
    assert len(celdas) == 2
    assert _valores(celdas[0]) == ("C", "ho")
    assert _valores(celdas[1]) == (" ", "la")


def test_acorde_muy_ancho_agrega_guion():
    celdas = _celdas(_word(("cie", "Cmaj7"), ("lo", "G")))
    assert len(celdas) == 3
    assert _valores(celdas[0]) == ("Cmaj7", "cie")
    assert celdas[1].controls[1].value == "-"
    assert _valores(celdas[2]) == ("G", "lo")


def test_tres_silabas_cada_acorde_centrado_sobre_la_suya():
    celdas = _celdas(_word(("ca", "G#m7"), ("mi", "C#7"), ("no", "F#")))
    cajas = [c for c in celdas if c.controls[1].value != "-"]
    assert [_valores(c) for c in cajas] == [("G#m7", "ca"), ("C#7", "mi"), ("F#", "no")]


def test_casilla_sin_letra_queda_en_blanco_no_con_guion():
    celdas = _celdas(_word(("", "A")))
    assert len(celdas) == 1
    assert _valores(celdas[0]) == ("A", " ")


def test_casilla_a_mitad_de_palabra_no_agrega_guion_conector():
    """«pujante» + un D7 suelto al final: la casilla no lleva ni guion propio ni
    conector con «te», aunque «D7» sea más ancho que la sílaba vacía."""
    celdas = _celdas(_word(("pu", None), ("jan", "Em"), ("te", "C6"), ("", "D7")))
    assert len(celdas) == 4       # sin conectores de por medio
    assert _valores(celdas[3]) == ("D7", " ")


def test_es_solo_puntuacion():
    assert _es_solo_puntuacion(_word((": ", None))[0])
    assert _es_solo_puntuacion(_word(('".', None))[0])
    assert not _es_solo_puntuacion(_word(("te", None))[0])


def test_mover_sueltos_tras_puntuacion_corre_el_acorde_despues_de_los_dos_puntos():
    syls = _word(("te", "C6"), ("", "D7"), (": ", None), ('"', None), ("Tu ", "G"))
    reordenados = _mover_sueltos_tras_puntuacion(syls)
    textos_con_acorde = [(s.text, s.chord.value if s.chord else None) for s in reordenados]
    assert textos_con_acorde == [
        ("te", "C6"), (": ", None), ("", "D7"), ('"', None), ("Tu ", "G"),
    ]


def test_mover_sueltos_no_toca_nada_si_no_hay_puntuacion_despues():
    syls = _word(("par", "G#m7"), ("tir", "C#7"))
    assert _mover_sueltos_tras_puntuacion(syls) == syls
