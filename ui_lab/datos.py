"""Datos FALSOS para el laboratorio de interfaz.

Todo lo de aquí es inventado y vive en memoria. El laboratorio NO abre la base de
datos real ni toca tus canciones: esa es la regla del banco de pruebas (ver README).
Las estructuras imitan exactamente lo que devuelve ``database.db.Database`` para que
las maquetas puedan usar los widgets de verdad sin adaptaciones.
"""

from __future__ import annotations

# Álbum que viene incluido en la app: va SIEMPRE primero en la lista de álbumes.
ALBUM_FIJADO = "Himnario Adventista"

# Cada canción: id, title, album, author, key, rhythm, favorite.
# Un ÁLBUM agrupa canciones de varios autores (p. ej. «Himnario Adventista» reúne a
# Lutero, Heber, Newton…). Una canción puede tener álbum, autor, o los dos.
_TITULOS = [
    ("Castillo Fuerte es Nuestro Dios", ALBUM_FIJADO, "Martín Lutero", "C", "4/4"),
    ("Cristo me Ama", ALBUM_FIJADO, "Anna B. Warner", "C", "4/4"),
    ("A Cristo Coronad", ALBUM_FIJADO, "Matthew Bridges", "D", "4/4"),
    ("Santo, Santo, Santo", ALBUM_FIJADO, "Reginald Heber", "D", "4/4"),
    ("Sublime Gracia", ALBUM_FIJADO, "John Newton", "G", "3/4"),
    ("Roca de la Eternidad", ALBUM_FIJADO, "Augustus Toplady", "A", "4/4"),
    ("Firmes y Adelante", ALBUM_FIJADO, "Sabine Baring-Gould", "E", "4/4"),
    ("Al Mundo Paz", ALBUM_FIJADO, "Isaac Watts", "D", "2/4"),
    ("Noche de Paz", ALBUM_FIJADO, "Franz Gruber", "Bb", "3/4"),
    ("Cuán Grande es Él", ALBUM_FIJADO, "Carl Boberg", "G", "4/4"),
    ("En Mi Caminar", "Canciones Adventistas", "Grupo Vocal Eben-Ezer", "D", "3/4"),
    ("Cuán Bello es el Señor", "Canciones Adventistas", "Anónimo", "A", "4/4"),
    ("Alabaré a Mi Señor", "Canciones Adventistas", "Anónimo", "G", "4/4"),
    ("Dios de lo Alto", "Canciones Adventistas", "Coral Adventista", "Bb", "4/4"),
    ("Tan Bueno es Dios", "Alabanzas de Júbilo", "Coral Adventista", "F", "4/4"),
    ("Grande, Señor, es tu Misericordia", "Alabanzas de Júbilo", "Anónimo", "C", "3/4"),
    # Sin álbum: canciones sueltas, solo con autor.
    ("De Tal Manera Amó", "", "Marcos Witt", "F", "3/4"),
    ("¡Oh Amor de Dios!", "", "Frederick Lehman", "C", "3/4"),
    ("Señor Jesús, el Día ya se Fue", "", "Marcos Witt", "D", "4/4"),
    ("Nuestro Sol se Pone Ya", "", "Anónimo", "F", "6/4"),
]


def canciones(n: int = 120) -> list[dict]:
    """``n`` canciones falsas, numeradas como un himnario. Una de cada siete es
    favorita."""
    filas = []
    for i in range(n):
        titulo, album, autor, tono, ritmo = _TITULOS[i % len(_TITULOS)]
        filas.append({
            "id": i + 1,
            "title": f"{i + 1:03d} - {titulo}",
            "album": album,
            "author": autor,
            "key": tono,
            "rhythm": ritmo,
            "favorite": 1 if i % 7 == 0 else 0,
        })
    return filas


def albumes_y_autores(songs: list[dict] | None = None) -> list[dict]:
    """Lo que muestra la pestaña «Álbumes»: álbumes Y autores en una sola lista.

    Cada entrada trae ``tipo`` ("album" o "autor"), que es lo que decide el ícono
    (disco o persona). ``ALBUM_FIJADO`` va siempre primero por ser la biblioteca que
    viene incluida en la app; el resto va alfabético, álbumes antes que autores.
    """
    songs = songs if songs is not None else canciones()
    conteo: dict[tuple[str, str], int] = {}
    for s in songs:
        if s.get("album"):
            conteo[("album", s["album"])] = conteo.get(("album", s["album"]), 0) + 1
        if s.get("author"):
            conteo[("autor", s["author"])] = conteo.get(("autor", s["author"]), 0) + 1

    entradas = [{"name": nombre, "tipo": tipo, "song_count": n, "favorite": 0}
                for (tipo, nombre), n in conteo.items()]
    # Fijado primero; después álbumes; dentro de cada grupo, alfabético.
    entradas.sort(key=lambda e: (e["name"] != ALBUM_FIJADO,
                                 e["tipo"] != "album",
                                 e["name"].lower()))
    return entradas


def autores(songs: list[dict] | None = None) -> list[dict]:
    """Solo los autores (sin álbumes), como el ``list_authors()`` de hoy."""
    return [e for e in albumes_y_autores(songs) if e["tipo"] == "autor"]


def listas(n: int = 8) -> list[dict]:
    """Listas (setlists) falsas, como ``list_setlists()``: id, name, song_count."""
    nombres = ["Culto de Adoración", "Escuela Sabática", "Vigilia de Oración",
               "Santa Cena", "Bautismos", "Jóvenes", "Navidad", "Ensayo"]
    return [{"id": i + 1, "name": nombres[i % len(nombres)],
             "song_count": 4 + (i * 3) % 11} for i in range(n)]


class BaseFalsa:
    """Imita la parte de ``Database`` que LEEN las pantallas, con datos inventados.

    Sirve para montar pantallas reales dentro del laboratorio y verlas tal cual son.
    Las escrituras se quedan en memoria y se pierden al cerrar: aquí no hay archivo
    ni canciones de verdad que estropear.
    """

    def __init__(self, n_canciones: int = 120) -> None:
        self._songs = canciones(n_canciones)
        self._setlists = listas()

    # -- lectura (lo que usan las vistas) --
    def list_songs(self, query: str = "", filters: dict | None = None,
                   exclude_album: str | None = None) -> list[dict]:
        filas = self._songs
        for campo in ("author", "album"):
            if filters and filters.get(campo):
                filas = [s for s in filas if s.get(campo) == filters[campo]]
        if exclude_album:
            filas = [s for s in filas if s.get("album") != exclude_album]
        if query:
            q = query.lower()
            filas = [s for s in filas
                     if q in s["title"].lower() or q in (s["author"] or "").lower()]
        return [dict(s) for s in filas]

    def set_campo(self, song_id: int, campo: str, valor: str) -> None:
        """Asigna álbum o autor a una canción (lo que hará el ＋ del detalle)."""
        for s in self._songs:
            if s["id"] == song_id:
                s[campo] = valor

    def list_authors(self) -> list[dict]:
        """Solo autores (lo que devuelve hoy la app)."""
        return autores(self._songs)

    def list_albumes_y_autores(self) -> list[dict]:
        """Álbumes + autores en una lista, con ``tipo`` y el fijado primero."""
        return albumes_y_autores(self._songs)

    def list_setlists(self) -> list[dict]:
        return [dict(s) for s in self._setlists]

    def distinct_values(self, field: str) -> list[str]:
        return sorted({s[field] for s in self._songs if s.get(field)})

    # -- escritura (solo en memoria, para que los botones respondan) --
    def set_favorite(self, song_id: int, favorite: bool) -> None:
        for s in self._songs:
            if s["id"] == song_id:
                s["favorite"] = 1 if favorite else 0

    def delete_song(self, song_id: int) -> None:
        self._songs = [s for s in self._songs if s["id"] != song_id]

    def save_song(self, song) -> int:
        """Guardado falso: asigna un id y recuerda lo básico en memoria (el lab no
        persiste). Devuelve el id, como la base real, para que los flujos que guardan
        (p. ej. Nueva canción) no revienten."""
        new_id = max((s["id"] for s in self._songs), default=0) + 1
        self._songs.append({
            "id": new_id,
            "title": getattr(song, "title", "") or "",
            "author": getattr(song, "author", None),
            "album": getattr(song, "album", None),
            "key": getattr(song, "key", None),
            "rhythm": getattr(song, "rhythm", None),
            "favorite": 0,
        })
        return new_id
