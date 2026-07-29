# ROADMAP — Ilahi Mobile (Flet → Android)

Port de la app de escritorio Ilahi a un APK de Android usando **Flet**
(Python + Flutter). Doc vivo: se marca el avance por fase.

## Decisiones tomadas

- **Framework:** Flet (Python + Flutter). Reutiliza toda la lógica Python y sus
  tests; UI nueva. `flet build apk` corre nativo en Windows (sin WSL/Docker).
- **Alcance v1 (MVP completo):** ver + tocar en vivo, setlists, importar/exportar
  `.ilahi`, y edición en el teléfono.
- **Protección del escritorio:** todo vive en `HymnChords apk` (repo aparte). La
  lógica se **copia** (vendoriza), no se comparte. Cero cambios en la app original.
- **Datos aislados en desarrollo:** la app móvil usa la carpeta `IlahiMobile`
  (no `Ilahi`), para nunca tocar la base real del escritorio.
- **Renombrado a Ilahi (2026-07-29):** cambian el formato (`ilahi-song` /
  `ilahi-bundle`), la extensión (`.ilahi`) y los nombres de base, log y respaldos
  (`ilahi.db`, `ilahi.log`, `ilahi-*.db`), con lectura de los viejos. **NO cambia
  `[project] name = "hymnchords"`** en `pyproject.toml`: de ahí sale el id de
  paquete de Android (`com.eduardocoa.hymnchords`), y tocarlo instalaría una app
  nueva al lado, dejando inaccesible la biblioteca del teléfono. El nombre visible
  bajo el ícono ya es "Ilahi" (`product`). Por lo mismo el APK sigue saliendo como
  `hymnchords.apk`, y la extensión de las copias completas sigue siendo `.hymnbak`.

## Estrategia

Desarrollar toda la app corriendo en **escritorio** (`flet run`, solo requiere
`pip install flet`) y traer el toolchain de Android (Flutter + Android SDK) solo
al final, para empaquetar el APK.

## Fases

### Fase 1 — Andamiaje + core reutilizado  ✅ COMPLETA
- [x] Crear proyecto en `HymnChords apk` + venv propio.
- [x] Copiar `models/`, `utils/` (syllabifier, song_text, song_io, lyrics_parser),
      `database/db.py` y los tests de lógica.
- [x] Adaptar `database/config.py` (rama `FLET_APP_STORAGE_DATA` + carpeta propia).
- [x] Stub Flet (`main.py`) con el tema oscuro.
- [x] Incluido `utils/logging_setup.py` (lo requiere `test_db_backup`; también da
      logging a la app móvil).
- [x] `pip install flet` (**0.85.3**, instala y corre en Python 3.14) + `pytest`
      **verde: 117 tests**.

### Fase 2 — Datos + arranque  ✅ COMPLETA
- [x] `theme.py` (THEME portado 1:1) + bootstrap: `init_schema` en carpeta aislada.
- [x] `sample_data.py`: siembra 2 canciones de ejemplo desechables si la BD está vacía.
- [x] `build_song_list()` muestra las canciones leídas de SQLite (validado headless:
      round-trip de 2 canciones, 25 sílabas, acordes OK).
- **Nota Flet 0.85:** los helpers de layout son classmethods PascalCase
  (`ft.Padding.only/.symmetric`, `ft.Margin.symmetric`), **no** `ft.padding.*`.

### Fase 3 — Ver + tocar en vivo (corazón del MVP)  ✅ COMPLETA
- [x] Lista de canciones tocable (`views/song_list_view.py`). Buscador: **pendiente**
      (rápido: `db.list_songs(query=...)` + un `ft.TextField`).
- [x] Vista escenario (`views/stage_view.py`): acordes sobre la letra, monoespaciado
      (reusa `display_song` + `line_to_chord_lyric`).
- [x] Transposición instantánea (offset global + modulación por bloque, no destructiva).
- [x] **Cambiar el tono en la vista de canción se GUARDA** como el nuevo tono (círculo).
      El panel de tono llama a `on_persist_key(song, delta)` → `transpose_song` + `save_song`
      (transpone los acordes y actualiza `key`, sin tocar las modulaciones por bloque, que
      son relativas). En una **lista** (setlist) el cambio sigue siendo visual (no se pasa
      `on_persist_key`), porque ahí el tono es propio de la lista. «Restablecer» del panel
      pasa a «Al tono original» cuando persiste y hay `original_key`.
- [x] **Tono original** (`songs.original_key`, columna nueva + migración): el tono real de la
      canción, distinto del **círculo** (`key`) con que se toca — p. ej. original La♭, círculo
      Sol, capo 1. Se edita en «Nueva canción» y «Editar letra» (campo junto a «Tono
      círculo») y se muestra en la vista de canción («Original: Ab») junto a autor/ritmo/capo.
      `song_io` lo serializa (opcional; archivos viejos → None).
- [x] Tamaño de fuente (A−/A+) y scroll vertical. El **modo escenario entra en negro puro**
      (`_STAGE_BG`) y restaura el fondo del tema al salir; se quitó el botón "Fondo".
- [x] Navegación lista ↔ escenario.
- [x] **Modo escenario** (`PresentScreen`): vista limpia (solo la canción) + tamaño de
      fuente + **autoscroll** (play/pausa + slider de velocidad; `run_task` + `scroll_to`).
- [x] **Autoscroll reescrito.** Antes llevaba un contador propio de posición, que no sabía
      dónde estaba el scroll de verdad ni dónde terminaba la canción. De ahí cuatro fallos:
      demasiado rápido, reanudar en el punto viejo tras subir con el dedo, temblar al llegar
      al final, y saltar al final ignorando la velocidad en el segundo pase.
      Ahora se guía por `ListView.on_scroll` (`OnScrollEvent.pixels` y `.max_scroll_extent`):
      - la velocidad del slider es en **píxeles por segundo** (4–90), no por tick, así el
        mínimo es de verdad lento y no depende de la cadencia del bucle;
      - `pixels` solo se sincroniza **en pausa** (mientras toca llega a mitad de la animación
        y frenaría el avance); `max_scroll_extent` se lee siempre;
      - al llegar al final, o si la canción cabe en pantalla, se detiene y el ícono vuelve a ▶;
      - si `scroll_to` falla, se detiene también: el ícono no puede quedarse en ⏸ mintiendo.
- [x] **Controles rediseñados.** Vista de canción: flecha ← arriba a la izquierda, título
      **centrado**, y cuatro botones flotantes: **Tono** (badge con la clave; abre un cuadro
      − · tono · + con el desfase y Restablecer), **Aa** (cuadro «Tamaño del texto»),
      **✎ Editar** y **▶** (escenario). Se quitaron de la barra superior «Transponer»,
      «Fuente», «Editar» y «Exportar» (exportar vive en el menú ⋮ de la lista).
      Escenario: título centrado + panel fijo (radio 24) con **velocidad**
      (play/pausa · 🚶 slider 🏃) y **tamaño** (Aa · A− · nº · A+ · ↺), separador y **✕**
      centrada. Tamaño por defecto `SIZE_STAGE = 14` en ambas.
      Las dos filas del panel usan **casillas laterales de ancho fijo** (`_SLOT_WIDTH`) y el
      mismo `spacing`: así el grupo A−/nº/A+ queda centrado bajo el slider y el ↺ cae justo
      bajo el ícono de correr. El ↺ es `ROTATE_LEFT` (la flecha de `REFRESH` invertida:
      apunta hacia atrás = «volver al tamaño base»).
      Trampas encontradas en el dispositivo:
      - el glifo **▶ se pinta como emoji naranja** en Android → usar `ft.Icons.PLAY_ARROW`;
      - al alternar play/pausa hay que **reemplazar el `content`** del contenedor (mutar la
        propiedad del ícono no siempre repinta, igual que `TextButton.text`);
      - los círculos A−/A+ necesitan un `bgcolor` que contraste con el panel que los contiene
        (`surface` sobre `surface2` y viceversa) o se vuelven invisibles;
      - una `Column` con `tight=True` **no se centra** con `horizontal_alignment`: el centrado
        lo hace el `Container` padre con `alignment=Alignment.CENTER`.
      El panel del escenario es fijo (va en la `Column`, no flota sobre la letra) y el
      `ListView` lleva 28 px de hueco inferior para que la última línea nunca quede tapada.
- [x] **Vista de canción reorganizada**: el ✎ **Editar** pasó a la esquina superior derecha
      (mismo `square_button` que el editor de acordes; hace de par simétrico del ← y mantiene
      el título centrado). Los botones flotantes ya no son una fila centrada abajo sino una
      **columna vertical a la derecha**, en orden descendente: **Tono · Fuente (Aa) · Escenario (▶)**.
      El hueco inferior del `ListView` subió a 228 px (3 botones × 60 + 2 × 12 + margen) para
      que la letra no quede tapada al hacer scroll.
- Render por **columnas por sílaba** (acorde encima; alineación por *layout*, NO por
  fuente monoespaciada — la `"monospace"` de Flet driftea en líneas largas). Bonus:
  *wrap* por palabra, así las líneas largas no se recortan en pantalla angosta.
- Aprendizaje: en dev, `flet run` guarda la BD en `storage/data/` (no en APPDATA);
  para re-sembrar sin cerrar flet, usar `tools/reseed_dev.py`.

### Fase 4 — Setlists  ✅ COMPLETA (ver/tocar + crear/editar)
- [x] Listar/abrir setlists (`views/setlist_view.py`), detalle ordenado con tono por lista.
- [x] Navegación anterior/siguiente en vivo (el escenario abre con el tono propio de la lista).
- [x] Buscador de canciones (venía pendiente de Fase 3): `SongsScreen` filtra por título/autor.
- [x] **Fase 4b** — crear lista, renombrar, agregar/quitar canciones, tono por canción (−/+),
      eliminar (confirmación). Autosave en cada cambio.
- [x] **Selector mejorado**: buscador + filtro por artista (`ft.Dropdown` + `distinct_values`).
- [x] **Reordenar arrastrando** (`ft.ReorderableListView` / `on_reorder`) en lugar de ▲▼.
- Validado headless: filtro/buscador, reorder, y crear/renombrar/quitar persisten en SQLite.

### Fase 5 — Importar / Exportar `.ilahi`  ✅ COMPLETA (escritorio + Android)
- [x] Importar (canción suelta o cancionero) con FilePicker → `load_songs` → `save_song`.
- [x] Exportar todo como cancionero (`export_bundle`) y exportar canción desde el escenario.
- [x] FilePicker de Flet 0.85 (servicio async: `await pick_files/save_file`) + estado en UI.
- [x] **Android**: import y **export** verificados en emulador (picker nativo; el archivo
      exportado se relee sin pérdida: título, autor, tono, ritmo y los 14 acordes).
- **Clave de `save_file` en Flet 0.85:** en móvil/web **exige `src_bytes`** (el sistema
  escribe el archivo vía SAF) y sin él lanza `ValueError`; en escritorio solo devuelve la
  ruta y el archivo lo escribe la app. De ahí `song_to_bytes` / `bundle_to_bytes` en
  `utils/song_io.py` y la rama `page.platform.is_mobile()` en `main.py:save_bytes`.
- Validado headless: round-trip canción y bundle, import a BD, acordes preservados, y
  que los bytes serializados son **idénticos** a lo que escribe `export_song/export_bundle`.

### Fase 6 — Edición táctil  ✅ (6a: crear + asignar acordes)
- [x] **Crear canción** (`NewSongScreen`): metadatos + pegar letra → `parse_lyrics`
      (silabifica) → guardar → editor. Rediseñada con el lenguaje de la app: flecha ← que
      cancela, título centrado, campos redondeados del tema y botón **«Guardar»** en píldora
      (antes «Procesar letra», misma función). Los helpers `_themed_field` y `_pill_button`
      se comparten con «Editar letra».
- [x] **Asignar acordes** (`EditSongScreen`): rejilla de sílabas tocables; editor inferior
      con campo + **sugerencias diatónicas** (`chords_for_key`). El acorde se actualiza en el
      sitio (ágil, sin repintar toda la rejilla). Accesos: ＋ Nueva y ✎ Editar (escenario).
- [x] **Editor rediseñado**: encabezado con los mismos botones que la vista de canción
      (← y ✎, 44 px cada uno) y el título centrado, sin autor/ritmo/capo. El editor pasó a ser
      un **panel flotante** (radio 20, `surface2`) con caja del acorde, **Aplicar** / **Quitar**,
      las **casillas de paso** y las sugerencias como chips, resaltando el acorde puesto.
      Las piezas comunes (botón cuadrado, botón redondo, título centrado, panel flotante)
      viven en `views/widgets.py` para que las dos pantallas no se desincronicen.
      Composición: caja + acciones en dos columnas del mismo ancho, etiquetas con línea
      separadora, y **10 sugerencias en 2 filas de 5**, todas de 62×38 (cabe «D#m»/«G#m7»).
      `models/key_chords.py` ahora devuelve **10** por tono: se dejaron fuera el `iii`
      (mayor) y el `v` natural (menor), los grados que menos se usan. El **disminuido se
      mantiene**; lo que falte se escribe a mano.
      **Trampa:** un `Container` sin `width` dentro de un `Row` se estira a todo el ancho;
      las píldoras necesitan ancho explícito.
- [x] **Editar letra** con el mismo lenguaje: título centrado, **flecha ← que cancela**
      (vuelve sin guardar), caja de texto redondeada con los colores del tema y botón
      «Guardar cambios» en píldora. Sin `FilledButton` azul de Material. Ahora edita también
      **autor, ritmo y capo** (además de la letra); `merge_lyrics` conserva los acordes de
      las líneas sin cambios y los metadatos se sobrescriben al guardar.
- [x] **Grupo «Desconocido»** en la lista de autores: las canciones sin autor se agrupan al
      final (marcador `UNKNOWN_AUTHOR`, se muestra «Desconocido»). Filtrarlo lista esas
      canciones; su ⋮ solo ofrece Exportar y Eliminar (no es un autor real: sin favorito ni
      renombrar). `list_songs(filters={"author": UNKNOWN_AUTHOR})` → `author IS NULL OR ''`.
- [x] Volver desde el **editor de acordes** lleva a la **vista de canción**, no al inicio
      (`on_back=lambda: go_stage(song_id)`).
- [x] Autosave en cada cambio (`save_song` update = borra+reinserta, sin duplicar).
- [x] **Eliminar canción** desde la lista (confirmación en línea) + **editar la letra**
      (`EditLyricsScreen` → `merge_lyrics`, conserva acordes de las líneas que no cambian).
- [x] Agregar/quitar **casilla de acorde** (izq/der) en el editor, para acordes de paso;
      en el escenario, una casilla con acorde y sin letra muestra un **guión** (estilo
      "coro-nad"). Verificado en emulador.
- [x] **Modulación por sección**: control −/+ en cada encabezado (desde la 2ª; la 1ª define
      el tono base), persistido en `sections.transpose` (no destructivo). El editor muestra
      los acordes **como suenan** en cada sección, las **sugerencias siguen el tono de la
      sección**, y al elegir un acorde se guarda **destransponido** al tono base — así
      `display_song` lo reproduce igual en el escenario. Round-trip validado.
- [x] **Pantalla de inicio rediseñada** (tarjetas): ★/♪ **favorito** funcional (columna
      `songs.favorite` + migración ligera; los favoritos se ordenan primero), autor, ritmo,
      **badge de tono** y menú **⋮** (Editar / Exportar / Marcar favorito / Eliminar).
      Íconos Material de Flet (los glifos Unicode exóticos salen ▯ en Android).
      Verificado en emulador: el ★ persiste tras cerrar la app y tras reinstalar el APK.
- [x] **Barra inferior** (Biblioteca · Favoritos · Listas · Ajustes), `Row` propio en vez de
      `ft.NavigationBar` (el mockup no lleva la «píldora» de Material y así los colores salen
      del THEME). Esquinas superiores redondeadas: ojo, el borde debe ser **uniforme**
      (`Border.all`), Flutter no acepta `borderRadius` con un borde de un solo lado.
      Favoritos filtra la misma lista; Listas navega a las setlists (por eso se quitó el
      enlace «Listas ▸» del encabezado). **Ajustes es un marcador de posición**: muestra
      «próximamente», su vista está pendiente de definir.
- [x] **`key` estable en cada tarjeta** (`song-<id>`) y en cada pestaña. Sin `key`, Flet
      reconcilia los hijos por posición y, al cambiar el largo de la lista (Biblioteca 4 →
      Favoritos 1), puede reutilizar controles de otra canción. Es buena práctica con o sin
      bug (ya se usaba en el `ReorderableListView`).
- [x] **Buscador rediseñado**: píldora con lupa y embudo de filtros. El `suffix` de
      `ft.TextField` **no se pinta en Android**, así que la píldora es un `Container` propio
      con `Row`[Icon, TextField sin bordes, IconButton]. Busca solo por **título y autor**
      (por decisión del usuario; el hint no promete tono).
- [x] **Barra inferior compartida** (`views/bottom_bar.py`), también en la vista de Listas.
- [x] **Botón ＋ flotante** (FAB, esquina inferior derecha sobre la barra) que abre un cuadro
      de esquinas redondeadas (`AlertDialog` + `RoundedRectangleBorder`) con: Nueva canción /
      Importar… / Exportar biblioteca. Sustituye la fila de botones que había arriba.
      En Flet 0.85 los diálogos se abren con `page.show_dialog(dlg)` y se cierran con
      `page.pop_dialog()` (**no existe** `page.open()`).
- [x] **Autores** (`views/author_list_view.py`), desde el embudo → «Filtrar por autor».
      Misma tarjeta que las canciones: ícono de perfil (dorado si es favorito) · nombre ·
      badge con el nº de canciones · menú ⋮ (Editar nombre / Exportar / Favorito / Eliminar).
      Tocar un autor filtra la biblioteca y muestra un chip para quitar el filtro.
      - `author_favorites` (tabla nueva): el autor no es una entidad, es un campo de `songs`,
        así que la marca vive aparte por nombre. `rename_author` se la lleva consigo.
      - **Eliminar un autor borra sus canciones** (decisión del usuario). Pide confirmación
        diciendo cuántas y hace `backup()` antes.
      - Exportar reusa `bundle_to_bytes` (mismo cancionero que la app de escritorio).
- [ ] 🐛 **ABIERTO — `songs.favorite` cambia solo (4 veces: se perdió y también apareció).**
      Sonda temporal en el emulador (única vía: `print()` de Python **no llega a logcat** y
      la app de release no permite `run-as`) confirmó que el cambio es **en la BD**
      (`fav=[(1,0),…]` con `favcol=True`), no de pintado. **Descartados** como causa:
      reiniciar la app, instalar un APK nuevo encima (el favorito sobrevivió), la migración
      `_migrate_song_favorite`, `save_song` (su UPDATE no toca la columna), el arranque
      (`bootstrap_db`) y los backups (solo crean copias, nunca restauran). Tampoco lo
      reproducen: el ciclo Biblioteca↔Favoritos↔Listas, ni ir a Autores y volver, ni abrir
      y cancelar el diálogo de renombrar. Las veces que ocurrió, el emulador llevaba
      **minutos u horas inactivo** con la app abierta antes de reinstalar.
      **Instrumentado:** ahora `set_favorite` deja rastro en la tabla `fav_audit`
      (song_id, value, at) y `db.favorite_audit()` la lee. Si el ⭐ vuelve a cambiar solo,
      esa tabla dice si la escritura salió de la app (habrá fila) o no (no habrá ninguna),
      que es justo la bifurcación que falta resolver. Pendiente: mostrarla en Ajustes.
- La BD en Android vive en `FLET_APP_STORAGE_DATA` = `/data/user/0/<paquete>/app_flutter`
  y **sobrevive a actualizar el APK** (verificado marcando un favorito y reinstalando).
- [x] **Sección «Introducción»**: toda canción nueva empieza con una intro (tipo `intro`,
      label «Introducción»): **2 líneas de 5 casillas** de acorde vacías. En la vista de
      canción y en el editor se muestran como **guiones monoespaciados**; sobre la casilla
      que tenga acorde aparece el acorde encima. En el editor las casillas son tocables
      (no se colapsan aunque estén vacías). No se edita desde «Editar letra» (se omite del
      texto y `merge_lyrics` la conserva con sus acordes). Núcleo en `lyrics_parser`
      (`make_intro_section`/`prepend_intro`); render en `stage_view._intro_line_block` y
      `edit_view._intro_cell`. Las **líneas de solo acordes** (casillas que `parse_lyrics`
      antepone a cada sección) **solo se muestran en la intro**: en estrofa/coro/etc. se
      omiten al renderizar (vista de canción y editor), corrigiendo la fila apretada de
      acordes que aparecía bajo cada título de sección. Se hizo a nivel de render (no del
      parser) para no romper los tests ni el pegado tipo Cifra Club.
- [x] **Sección «Interludio»**: escribir `[Inter]`, `[Interludio]`, `INTER` o `INTERLUDIO`
      crea una sección de casillas idéntica a la intro (tipo `intro`, label «Interludio»,
      2×5 guiones). A diferencia de la Introducción prependida, el interludio **sí** aparece
      en «Editar letra» como `[Interludio]`, así se mueve/quita y su posición se conserva;
      `merge_lyrics` recupera sus acordes alineando las casillas por índice (separando antes
      la Introducción prependida para que la alineación cuadre). Etiquetas de intro/interludio
      canónicas («Introducción»/«Interludio»).
- [x] **Botones «Insertar sección»** bajo la caja de letra en «Nueva canción» y «Editar letra»:
      Estrofa · Coro · Puente · Interludio · Final. Insertan `[Nombre]` al final del texto
      (más fácil que escribirlo a mano). «Introducción» no está: se antepone sola.
- [ ] **Fase 6b** (refino restante): unir/dividir sílabas.
- Validado headless: crear→procesar→guardar; editar→sílaba→acorde→persiste; la migración
  de `favorite` no pierde datos y `save_song` conserva la marca.

### Fase 7 — Empaque APK  🚧 (APK corre en emulador; falta pulir)
- [x] Instalar Flutter (3.44.5) + Android SDK + emulador (Pixel 7 x86_64). Flet usa su
      propio Flutter (3.41.7) al compilar; el que instalamos dejó SDK + licencias OK.
- [x] `flet build apk` → `build\apk\hymnchords.apk` (66 MB). Requisitos Windows:
      **Developer Mode** (symlinks para plugins) + `pyproject.toml` con org/product.
- [x] **Corre en el emulador y `sqlite3` FUNCIONA on-device** (siembra + lee las 2
      canciones desde SQLite) → **riesgo #1 RESUELTO**. 🎯
- [x] Cosmético (verificado en emulador): **SafeArea** (la barra de estado ya no tapa la
      barra superior) + glifos **↓/↑** en Importar/Exportar (antes salían ▯).
- [x] **Import en Android FUNCIONA** 🎯: el file-picker nativo abre, el `.hymnchords` es
      seleccionable, da ruta usable, y `load_songs`+`save_song` importan (caveat Fase 5 resuelto).
- [x] **Export en Android FUNCIONA** 🎯: diálogo nativo de guardado con nombre sugerido →
      escribe en `/sdcard/Download/` (requiere `src_bytes`, ver Fase 5).
- [x] Verificado en emulador: inicio (tarjetas + favorito + menú ⋮), vista escenario
      (acordes alineados), modo escenario, importar y exportar.
- [x] **Corre en teléfono real** (HONOR Magic5 Lite, `com.eduardocoa.hymnchords`), con la
      biblioteca de verdad: 630 canciones, 2 listas y los favoritos.
- [x] **Rename a Ilahi verificado on-device (29 jul 2026)**: `adb install -r` sobre la
      versión vieja → `migrate_legacy_db_files()` renombró `hymnchords.db` (+ `-wal`/`-shm`)
      a `ilahi.db` sin perder nada (630 canciones antes y después, contrastado con un
      `.hymnbak` exportado justo antes). El picker nativo **sí deja seleccionar `.ilahi`**
      (el caveat de extensión no registrada no aplica) y también los `.hymnchords` viejos;
      se importaron ambos y luego se borraron las copias de prueba.
- [x] **Empaquetado limpio (29 jul 2026)**: Flet solo excluye `build/` por defecto, así
      que el APK se llevaba dentro `.venv/` (49,6 MB), `storage/` con la base de
      desarrollo y todos los respaldos (58,7 MB) y `.git/` (8 MB) — 116 de los 120 MB
      del payload, y la biblioteca de canciones viajaba dentro del archivo. Se añadió
      `[tool.flet.app] exclude` en `pyproject.toml`: payload **120 MB → 1,58 MB** y APK
      **116,6 MB → 67,5 MB**. Verificado que los 35 archivos que la app necesita siguen
      dentro y que arranca con la biblioteca intacta. `assets/` NO se excluye (ícono,
      logo y clicks del metrónomo se leen en runtime).
- [ ] Falta: edición (teclado) y setlists (drag) en el emulador.
      Quitar la traza `[present] error scroll_to`.

## Spikes de riesgo (validar temprano)

1. ~~`sqlite3` en el dispositivo (#1)~~ **RESUELTO** ✅: el Python móvil de Flet (3.12)
   trae `sqlite3`; el APK siembra y lee la BD on-device sin problema (probado en emulador).
2. **Rendimiento de grilla densa** en edición (~400 controles + re-render). Si
   sufre, editar por línea/sección en vez de la grilla completa.
3. ~~Fuente monoespaciada en Android~~ **RESUELTO**: alineación por *layout* (columnas
   por sílaba); no se necesita fuente monoespaciada ni bundlearla.

## Fuera de alcance (por ahora)

Exportar a PDF (fpdf2 pesa en Android; se hace en el escritorio), sincronización /
nube, exportar setlists completas. Igual que en la app de escritorio.
