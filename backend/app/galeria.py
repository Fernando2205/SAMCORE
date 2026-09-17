"""Galeria cerrada (ADR-08): listas cerradas de categorias e imagenes.

Las imagenes viven en `backend/galeria/<categoria>/<tipo>/<archivo>.png`
(subconjunto del conjunto de prueba de MVTec AD, ver README de la carpeta).
Al arrancar se construye el mapa identificador -> ruta; todo parametro del
cliente se valida contra ese mapa y ninguna ruta se construye con texto del
cliente (M-03).
"""
import os
import random
from pathlib import Path

CATEGORIAS_MVTEC = (
    "bottle", "cable", "capsule", "hazelnut", "metal_nut",
    "pill", "screw", "toothbrush", "transistor", "zipper",
)

# Solo para el motor simulado (desarrollo y pruebas): umbrales ilustrativos.
UMBRALES_ILUSTRATIVOS = {
    "bottle": 2.772, "cable": 3.512, "capsule": 1.925, "hazelnut": 4.334, "metal_nut": 3.845,
    "pill": 2.911, "screw": 2.055, "toothbrush": 1.910, "transistor": 3.232, "zipper": 1.314,
}

RUTA_GALERIA = Path(os.environ.get("SAMCORE_GALERIA", Path(__file__).resolve().parent.parent / "galeria"))
_EXTENSIONES = {".png", ".jpg", ".jpeg"}

_mapa: dict[str, dict[str, Path]] = {}


def escanear() -> None:
    """Construye el mapa cerrado id -> ruta a partir de la carpeta."""
    _mapa.clear()
    for categoria in CATEGORIAS_MVTEC:
        carpeta = RUTA_GALERIA / categoria
        entradas: dict[str, Path] = {}
        if carpeta.is_dir():
            for tipo_dir in sorted(p for p in carpeta.iterdir() if p.is_dir()):
                for archivo in sorted(p for p in tipo_dir.iterdir() if p.suffix.lower() in _EXTENSIONES):
                    entradas[f"{tipo_dir.name}/{archivo.name}"] = archivo
        # Orden mezclado pero estable por categoria: la galeria no revela el
        # tipo de cada imagen ni agrupa las normales al principio.
        ids = list(entradas)
        random.Random(f"samcore-galeria-{categoria}").shuffle(ids)
        _mapa[categoria] = {i: entradas[i] for i in ids}


def umbral_de(categoria: str) -> float:
    """Umbral calibrado real si hay artefactos validos; si no, el ilustrativo."""
    from . import artefactos

    calibrado = artefactos.umbral_calibrado(categoria)
    return calibrado if calibrado is not None else UMBRALES_ILUSTRATIVOS[categoria]


def listar_categorias() -> list[dict]:
    from . import artefactos

    return [
        {
            "nombre": nombre,
            "umbral": umbral_de(nombre),
            "imagenes": len(listar_imagenes(nombre)),
            **artefactos.estado_categoria(nombre),
        }
        for nombre in CATEGORIAS_MVTEC
    ]


def listar_imagenes(categoria: str) -> list[str]:
    return list(_mapa.get(categoria, {}).keys())


def ruta_imagen(categoria: str, imagen_id: str) -> Path | None:
    return _mapa.get(categoria, {}).get(imagen_id)


LADO_MINIATURA = 320
RUTA_MINIATURAS = Path(os.environ.get("SAMCORE_MINIATURAS", Path(__file__).resolve().parent.parent / "datos" / "miniaturas"))


def ruta_miniatura(categoria: str, imagen_id: str) -> Path | None:
    """Miniatura JPEG de la imagen de galeria (se genera una vez y se guarda).
    El nombre de archivo se deriva del identificador validado, nunca del
    texto del cliente."""
    from PIL import Image

    original = ruta_imagen(categoria, imagen_id)
    if original is None:
        return None
    tipo, nombre = imagen_id.split("/", 1)
    destino = RUTA_MINIATURAS / categoria / f"{tipo}__{Path(nombre).stem}.jpg"
    if not destino.is_file():
        destino.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(original) as img:
            img = img.convert("RGB")
            img.thumbnail((LADO_MINIATURA, LADO_MINIATURA), Image.Resampling.LANCZOS)
            img.save(destino, format="JPEG", quality=82, optimize=True)
    return destino


def es_categoria_valida(categoria: str) -> bool:
    return categoria in CATEGORIAS_MVTEC


def es_imagen_valida(categoria: str, imagen_id: str) -> bool:
    return ruta_imagen(categoria, imagen_id) is not None
