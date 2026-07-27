# Laboratorio de interfaz

Banco de pruebas para **ver cómo queda** una idea de interfaz antes de tocar la app.

```
flet run ui_lab/main.py
```

Arriba hay una barra fina: el ícono de la izquierda elige la maqueta, el de la paleta
cambia el tema, y la flecha oculta la barra para ver la pantalla limpia (una pestañita
la trae de vuelta). El lienzo tiene el tamaño de un teléfono, igual que la app.

## Reglas

1. **No toca tus canciones.** El laboratorio no abre la base de datos; los datos son
   inventados y viven en memoria (`datos.py`). Si una maqueta intentara importar
   `database`, revienta a propósito con un mensaje claro.
2. **Nada de aquí llega solo a la app.** Cuando una maqueta convenza, se porta a mano
   a `views/`. Este directorio no lo importa nadie del proyecto.
3. **Sí usa los widgets y colores de verdad** (`views.widgets`, `theme`): de eso se
   trata, de que lo que ves aquí sea lo que vas a ver en el teléfono.

## Agregar una maqueta

```
cp ui_lab/maquetas/plantilla.py ui_lab/maquetas/mi_idea.py
```

Editá `NOMBRE`, `DESCRIPCION` y `construir(page, db)`; después sumala a la lista
`MAQUETAS` de `ui_lab/maquetas/__init__.py`. Aparece sola en el selector.

## Qué hay

| Maqueta | Qué muestra |
|---|---|
| `actual.py` | La interfaz como está hoy. Es la referencia contra la que comparar. |
| `plantilla.py` | Esqueleto para copiar. |

## Datos falsos disponibles

`db` es una `BaseFalsa` que imita a la base real en lo que las pantallas **leen**:

- `db.list_songs(query, filters)` — canciones con `id, title, author, key, rhythm, favorite`
- `db.list_authors()` — `name, song_count, favorite`
- `db.list_setlists()` — `id, name, song_count`

Las escrituras (`set_favorite`, `delete_song`) se quedan en memoria y se pierden al
cerrar. Por defecto hay 120 canciones; para probar con una biblioteca grande:
`BaseFalsa(2000)` en `main.py`.

## Ojo con el APK

Este directorio queda dentro del proyecto para poder importar `theme` y
`views.widgets`. No se ejecuta desde la app (nadie lo importa), así que no cambia su
comportamiento; solo suma unos KB al APK. Si molesta, se excluye en el empaquetado.
