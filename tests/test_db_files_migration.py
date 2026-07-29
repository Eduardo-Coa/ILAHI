"""Pruebas del renombrado en sitio de los archivos heredados (hymnchords* -> ilahi*).

En el móvil la carpeta de datos NO cambia (en Android la fija Flet): lo que se
migra son los nombres de los archivos dentro de ella. Todas las pruebas usan
carpetas temporales explícitas: nunca tocan la carpeta de datos real.
"""

from __future__ import annotations

from database.config import migrate_legacy_db_files


def _carpeta_vieja(tmp_path, con_wal: bool = True, con_respaldos: bool = True):
    """Crea una carpeta de datos al estilo HymnChords con contenido de ejemplo."""
    (tmp_path / "hymnchords.db").write_text("base", encoding="utf-8")
    (tmp_path / "hymnchords.log").write_text("log", encoding="utf-8")
    (tmp_path / "preferences.json").write_text('{"theme": "noche"}', encoding="utf-8")
    if con_wal:
        (tmp_path / "hymnchords.db-wal").write_text("wal", encoding="utf-8")
        (tmp_path / "hymnchords.db-shm").write_text("shm", encoding="utf-8")
    if con_respaldos:
        backups = tmp_path / "backups"
        backups.mkdir()
        (backups / "hymnchords-20260722-172655.db").write_text("r1", encoding="utf-8")
        (backups / "hymnchords-20260723-144559.db").write_text("r2", encoding="utf-8")
    return tmp_path


def test_renombra_base_y_log(tmp_path):
    _carpeta_vieja(tmp_path)

    assert migrate_legacy_db_files(tmp_path) is True
    assert (tmp_path / "ilahi.db").read_text(encoding="utf-8") == "base"
    assert (tmp_path / "ilahi.log").exists()
    assert not (tmp_path / "hymnchords.db").exists()
    assert not (tmp_path / "hymnchords.log").exists()


def test_renombra_los_sidecars_wal_y_shm(tmp_path):
    """El WAL guarda cambios aún no volcados: si no viaja con la base, se pierden."""
    _carpeta_vieja(tmp_path)
    migrate_legacy_db_files(tmp_path)

    assert (tmp_path / "ilahi.db-wal").read_text(encoding="utf-8") == "wal"
    assert (tmp_path / "ilahi.db-shm").exists()
    assert not (tmp_path / "hymnchords.db-wal").exists()
    assert not (tmp_path / "hymnchords.db-shm").exists()


def test_no_toca_las_preferencias(tmp_path):
    _carpeta_vieja(tmp_path)
    migrate_legacy_db_files(tmp_path)
    assert (tmp_path / "preferences.json").read_text(encoding="utf-8") == \
        '{"theme": "noche"}'


def test_renombra_los_respaldos_con_prefijo_nuevo(tmp_path):
    _carpeta_vieja(tmp_path)
    migrate_legacy_db_files(tmp_path)

    respaldos = sorted(p.name for p in (tmp_path / "backups").glob("*.db"))
    assert respaldos == ["ilahi-20260722-172655.db", "ilahi-20260723-144559.db"]


def test_no_pisa_una_base_nueva_existente(tmp_path):
    """Si ya hay una ilahi.db, la vieja se queda donde está: nada se sobrescribe."""
    _carpeta_vieja(tmp_path)
    (tmp_path / "ilahi.db").write_text("base nueva", encoding="utf-8")

    assert migrate_legacy_db_files(tmp_path) is False
    assert (tmp_path / "ilahi.db").read_text(encoding="utf-8") == "base nueva"
    assert (tmp_path / "hymnchords.db").exists()


def test_sin_archivos_viejos_no_hace_nada(tmp_path):
    (tmp_path / "ilahi.db").write_text("base", encoding="utf-8")
    assert migrate_legacy_db_files(tmp_path) is False


def test_carpeta_inexistente_no_revienta(tmp_path):
    assert migrate_legacy_db_files(tmp_path / "no_existe") is False


def test_es_idempotente(tmp_path):
    """Llamarla dos veces no rompe ni vuelve a renombrar nada."""
    _carpeta_vieja(tmp_path)

    assert migrate_legacy_db_files(tmp_path) is True
    assert migrate_legacy_db_files(tmp_path) is False
    assert (tmp_path / "ilahi.db").exists()


def test_migra_carpeta_sin_wal_ni_respaldos(tmp_path):
    _carpeta_vieja(tmp_path, con_wal=False, con_respaldos=False)
    assert migrate_legacy_db_files(tmp_path) is True
    assert (tmp_path / "ilahi.db").exists()
    assert not (tmp_path / "ilahi.db-wal").exists()


def test_base_migrada_sigue_siendo_usable(tmp_path):
    """Round-trip real: se crea una BD con el nombre viejo, se migra y se lee."""
    from database.config import DBConfig
    from database.db import Database
    from models.song import Song

    vieja = Database(DBConfig(path=tmp_path / "hymnchords.db"))
    vieja.init_schema()
    vieja.save_song(Song(id=None, title="Himno de prueba"))
    vieja.close()

    assert migrate_legacy_db_files(tmp_path) is True

    nueva = Database(DBConfig(path=tmp_path / "ilahi.db"))
    nueva.init_schema()
    assert [r["title"] for r in nueva.list_songs()] == ["Himno de prueba"]
    nueva.close()
