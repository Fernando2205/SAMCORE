"""Galeria cerrada (ADR-08): listas cerradas de categorias e imagenes.

Las imagenes viven en `backend/galeria/<categoria>/<tipo>/<archivo>.png`
(subconjunto del conjunto de prueba de MVTec AD, ver README de la carpeta).
Al arrancar se construye el mapa identificador -> ruta; todo parametro del
cliente se valida contra ese mapa y ninguna ruta se construye con texto del
cliente (M-03).
"""
import os
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
        _mapa[categoria] = entradas


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


def es_categoria_valida(categoria: str) -> bool:
    return categoria in CATEGORIAS_MVTEC


def es_imagen_valida(categoria: str, imagen_id: str) -> bool:
    return ruta_imagen(categoria, imagen_id) is not None
