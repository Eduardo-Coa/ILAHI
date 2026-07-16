# HymnChords Mobile

Port a Android (teléfono) de la app de escritorio **HymnChords**, construido con
[Flet](https://flet.dev) (Python + Flutter). Reutiliza intacta la lógica de la
versión de escritorio (silabificador, transpositor, parser de acordes, base de
datos SQLite) y reescribe solo la interfaz para pantalla táctil.

> La app de escritorio original vive en una carpeta aparte y **no se modifica**.
> Aquí la lógica está *copiada* (vendorizada), no compartida.

## Desarrollo

```powershell
# 1) Activar el entorno del proyecto
.\.venv\Scripts\Activate.ps1

# 2) Instalar dependencias
pip install -r requirements.txt -r requirements-dev.txt

# 3) Correr la app en el escritorio (iteración rápida, sin Android SDK)
flet run main.py

# 4) Correr las pruebas de la lógica reutilizada
pytest
```

## Empaquetar a APK (más adelante)

Requiere el SDK de Flutter + Android SDK instalados (ver ROADMAP.md, Fase 7):

```powershell
flet build apk
```

## Estructura

```
models/      lógica de datos (dataclasses) — copiada del escritorio
utils/       silabificador, parser, import/export, texto — copiado
database/    db.py (SQLite) + config.py (adaptado a almacenamiento móvil)
tests/       pruebas de la lógica (pytest) — copiadas
main.py      punto de entrada Flet
ROADMAP.md   plan por fases y estado
```
