# flet_template — plantilla de build propia

Copia de la plantilla oficial de `flet build` (**flet-build-template v0.85.3**) con **un
solo cambio** respecto al original: el *boot screen* va en negro.

## Por qué existe

Mientras arranca el motor de Python (1–3 s tras el splash), Flet muestra una pantalla
(`BlankScreen`) con el gris por defecto de Material. Como los temas de Ilahi son oscuros,
ese destello gris se nota. El único modo de cambiarlo es una plantilla de build propia:
`pyproject.toml` la apunta con `[tool.flet.template] url = "flet_template/build"`.

## El cambio (único)

`build/{{cookiecutter.out_dir}}/lib/main.dart`, en `class BlankScreen`:

```dart
return const Scaffold(
  backgroundColor: Color(0xFF000000),   // <-- agregado: negro en vez del gris default
  body: SizedBox.shrink(),
);
```

## Cómo re-sincronizar al subir la versión de Flet

Si se cambia la versión de `flet` en `pyproject.toml`, hay que rehacer esta copia:

1. Compilar una vez sin la plantilla propia (comentar `[tool.flet.template]`) para que
   Flet descargue la plantilla nueva a `~/.flet/cache/build-template/v<versión>/flet-build-template.zip`.
2. Reemplazar `flet_template/` extrayendo ese zip.
3. Volver a aplicar el cambio del `BlankScreen` de arriba.
4. Descomentar `[tool.flet.template]` y compilar.

Si Flet cambia la estructura del `BlankScreen`, adaptar el cambio al nuevo código.
