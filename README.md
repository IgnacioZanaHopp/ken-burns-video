# ken-burns-video

CLI Python que convierte imágenes y un audio en un video con efecto Ken Burns.

[![CI](https://github.com/IgnacioZanaHopp/ken-burns-video/actions/workflows/ci.yml/badge.svg)](https://github.com/IgnacioZanaHopp/ken-burns-video/actions/workflows/ci.yml)
[![Licencia MIT](https://img.shields.io/badge/licencia-MIT-blue.svg)](LICENSE)

![GIF generado desde un render real de seis segundos](docs/demo.gif)

Zoom y paneo lentos, fundidos entre imágenes y duración determinada por la pista
de audio. Exporta MP4 H.264/AAC a **720p o 1080p**, horizontal, sin servicios
externos. Las ilustraciones y el tono de la demo se generan desde cero con
[examples/generate_assets.py](examples/generate_assets.py); no hay fotografías,
música ni material de terceros. [Ver un frame del MP4 real](docs/frame.png).

## Instalación

Requiere **Python 3.11+**, `ffmpeg` y `ffprobe` en el PATH. FFmpeg debe incluir
`libx264`, `zoompan` y `xfade` (se recomienda FFmpeg 6+).

```sh
# macOS
brew install ffmpeg
# Debian/Ubuntu
sudo apt-get install ffmpeg

# Dentro de un clon del repositorio:
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
ken-burns-video --help
```

O usa [uv](https://docs.astral.sh/uv/): `uv sync --frozen` instala también las
herramientas de desarrollo con las versiones de `uv.lock`.
No se ha publicado el paquete en PyPI.

## Uso

```sh
ken-burns-video foto-1.jpg "foto con espacios.png" foto-3.jpg \
  --audio narracion.wav --output historia.mp4 \
  --resolution 1080p --fps 30 --fade 1 --zoom 1.12
```

Las imágenes aparecen en el orden de los argumentos. Se aceptan PNG, JPEG, WebP,
BMP, TIFF y PPM estáticos. La pista puede usar cualquier formato de audio que
lea tu ffmpeg. Si el archivo contiene video, solo se toma su primera pista de
audio. Las rutas se pasan como argumentos separados, sin shell.

| Opción | Predeterminado | Función |
| --- | --- | --- |
| `--audio`, `-a` | obligatorio | Pista de audio |
| `--output`, `-o` | obligatorio | Ruta MP4; su directorio debe existir |
| `--resolution` | `720p` | `720p` (1280×720) o `1080p` (1920×1080) |
| `--fps` | `30` | Entero entre 1 y 60 |
| `--fade` | `1` | Fundido en segundos, redondeado al fotograma más cercano |
| `--zoom` | `1.12` | Factor máximo, mayor que 1 y hasta 1.5 |
| `--dry-run` | desactivado | Inspecciona el audio y muestra el plan JSON, sin render |
| `--overwrite` | desactivado | Reemplaza la salida solo después de un render exitoso |

```sh
# Plan inspeccionable: requiere ffprobe, pero no ejecuta ffmpeg.
ken-burns-video foto-1.jpg foto-2.jpg -a voz.wav -o salida.mp4 --dry-run
# También funciona con una imagen, sin transición entre clips.
ken-burns-video portada.png -a voz.wav -o portada.mp4 --fade 0
```

No reemplaza entradas, ni siquiera con `--overwrite`. La salida se genera en un
temporal en el mismo directorio y se publica al completar; ante un fallo se
limpia el temporal y se conserva el archivo anterior. Sin `--overwrite`, también
se protege una salida creada por otro proceso durante el render.

Los errores de dominio salen con código 1 y un mensaje sin traceback. Typer usa
2 para errores de argumentos. Una ejecución exitosa sale con 0.

## Reproducir la demo

Desde el repositorio y con el entorno activado:

```sh
python examples/generate_assets.py --duration 6
ken-burns-video examples/assets/paisaje-1.png examples/assets/paisaje-2.png \
  examples/assets/paisaje-3.png -a examples/assets/tono.wav \
  -o examples/assets/demo.mp4 --fps 24 --fade 0.5
ffmpeg -ss 1 -i examples/assets/demo.mp4 -frames:v 1 frame.png
```

El video de la demo se verificó con ffprobe: **6,000 segundos, 1280×720,
24 fps, 144 fotogramas, H.264 y AAC**. El GIF es una versión de 480 píxeles a
10 fps del MP4; el frame se extrajo con ffmpeg. Los archivos de trabajo grandes
quedan ignorados en `examples/assets/`.

## Arquitectura y decisiones

- `planner.py`: dataclasses inmutables y construcción del comando, sin procesos
  externos. Reparte fotogramas, alterna zoom/paneo y calcula offsets `xfade`.
- `media.py`: ffprobe con timeout de 30 s. Prefiere duración de la pista de audio;
  usa duración de contenedor como respaldo y rechaza ausencia de audio.
- `render.py`: valida archivos, ejecuta ffmpeg y publica la salida atómicamente.
  Conserva solo los últimos 4.000 bytes del log en el mensaje de error.
- `cli.py`: Typer, validación de opciones, plan JSON y mensajes de salida.

Para N imágenes y F fotogramas de fundido, se distribuyen
`ceil(segundos_audio × fps) + (N − 1) × F` fotogramas entre los clips.
Cada solapamiento recupera F fotogramas. Los clips difieren como máximo en uno;
los offsets y fundidos caen en límites de fotograma. La salida se limita con
`-t` a la duración del audio. La representación de video puede diferir menos de
un fotograma; el contenedor/códec de audio puede añadir un pequeño redondeo.

Cada imagen se escala manteniendo su proporción y se recorta al centro para
llenar el formato horizontal; no se estira. Un lienzo intermedio al doble de
resolución reduce los saltos del paneo. Se normalizan aspecto de píxel, formato
y base temporal antes de `xfade`. El zoom alterna acercamiento y alejamiento,
con paneo horizontal y centrado vertical.

Límites: máximo 100 imágenes y audio de hasta un día. Para varias imágenes el
fundido debe ocupar al menos un fotograma y no solaparse con otra transición
dentro de un clip intermedio; si el audio es corto, reduce `--fade` o usa menos
imágenes. Cada clip necesita al menos dos fotogramas. Los renders 1080p consumen
CPU y memoria; no hay aceleración por GPU ni gestión de rotación EXIF propia.
Usa imágenes orientadas previamente. El render no impone timeout global.

Los filtros siguen la [documentación oficial de ffmpeg](https://ffmpeg.org/ffmpeg-filters.html#zoompan).

## Desarrollo y pruebas

```sh
uv sync --frozen
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest                 # incluye dos renders reales si hay ffmpeg/ffprobe
uv run pytest -m 'not smoke'  # solo unitarias, sin render
uv run pytest -m smoke       # 720p con fundidos y 1080p con una imagen
uv build                     # wheel y sdist en dist/
```

Se ejecutaron **52 pruebas**, incluidas las dos de humo, además de ruff y mypy
estricto. Las unitarias inspeccionan el comando, tiempos, zoom, mapeo de pistas,
validación, errores de ffprobe, CLI y protección de salidas. Las de humo renderizan
medios sintéticos en temporales, decodifican frames para verificar las imágenes y
su mezcla, e inspeccionan resolución, audio, duración y número de fotogramas.
Sin ffmpeg/ffprobe las de humo se marcan como omitidas; CI instala ambas
herramientas y las ejecuta en Python 3.11 y 3.13.

Los badges reflejarán ejecuciones reales cuando se publique el repositorio.

## Roadmap

- Paneos verticales y puntos de enfoque por imagen.
- Barras laterales opcionales para conservar la imagen completa.
- Progreso de render y presets de calidad.

## Cómo se construyó

Se desarrolló con asistencia de IA (Codex). El autor es responsable del diseño,
la revisión y las pruebas; las verificaciones automatizadas y los renders reales
se ejecutaron durante el desarrollo y se pueden reproducir con estos comandos.

## English summary

Python CLI that turns still images and an audio track into a Ken Burns video.  
Frame-based timing, alternating zoom/pan, crossfades and 720p/1080p MP4 output.  
Typed planning core, pytest coverage, real ffmpeg smoke renders and CI.

## Licencia

[MIT](LICENSE) © 2026 Ignacio Zañartu Hoppner.
