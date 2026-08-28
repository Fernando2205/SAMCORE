"""Descubrimiento y verificacion de artefactos reales por categoria.

Contrato con el notebook (especificacion de AGENTS.md §5, D-08 — sin
pickle en la ruta de carga):

    backend/artefactos/<categoria>/
        manifiesto.json      metadatos + SHA-256 de cada archivo
        banco.npz            banco de memoria PatchCore (coreset 10 %)
        calibracion.json     umbral calibrado + percentil + split usado

`manifiesto.json` esperado:
    {
      "categoria": "capsule",
      "version": "1",
      "archivos": {"banco.npz": "<sha256>", "calibracion.json": "<sha256>"}
    }

El motor real se conecta en T6; mientras tanto este modulo solo informa
que categorias ya tienen artefactos validos, y la API lo expone para que
el frontend muestre "motor real" o "simulado" por categoria.
"""
import hashlib
import json
import logging
from pathlib import Path

log = logging.getLogger("samcore")

RUTA_ARTEFACTOS = Path(__file__).resolve().parent.parent / "artefactos"

_cache: dict[str, bool] = {}


def _sha256(ruta: Path) -> str:
    h = hashlib.sha256()
    with ruta.open("rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def disponibles(categoria: str) -> bool:
    """True si la categoria tiene artefactos completos y con hash valido (M-07)."""
    if categoria in _cache:
        return _cache[categoria]
    carpeta = RUTA_ARTEFACTOS / categoria
    manifiesto = carpeta / "manifiesto.json"
    valido = False
    if manifiesto.is_file():
        try:
            datos = json.loads(manifiesto.read_text(encoding="utf-8"))
            archivos: dict[str, str] = datos["archivos"]
            valido = datos.get("categoria") == categoria and all(
                (carpeta / nombre).is_file() and _sha256(carpeta / nombre) == esperado
                for nombre, esperado in archivos.items()
            )
            if not valido:
                log.warning("evento=artefactos_invalidos categoria=%s", categoria)
        except (KeyError, ValueError, OSError):
            log.warning("evento=manifiesto_ilegible categoria=%s", categoria)
    _cache[categoria] = valido
    return valido


def motor_para(categoria: str) -> str:
    """"real" cuando hay artefactos validos y el motor real este integrado (T6)."""
    # Integracion del motor real pendiente (T6): aunque existan artefactos
    # validos, la inferencia sigue simulada; el estado se reporta aparte.
    return "simulado"


def estado_categoria(categoria: str) -> dict:
    return {"motor": motor_para(categoria), "artefactos": disponibles(categoria)}
