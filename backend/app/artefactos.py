"""Artefactos por categoria: descubrimiento, verificacion y carga.

Contrato con el cuaderno experimental (D-08, sin pickle en la ruta de carga):

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

Una categoria sin manifiesto valido no se habilita (M-07). El banco se carga
con `allow_pickle=False` y se valida su forma y tipo (M-06).
"""
import hashlib
import json
import logging
import os
from pathlib import Path

import numpy as np

log = logging.getLogger("samcore")

RUTA_ARTEFACTOS = Path(os.environ.get("SAMCORE_ARTEFACTOS", Path(__file__).resolve().parent.parent / "artefactos"))

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
            valido = (
                datos.get("categoria") == categoria
                and {"banco.npz", "calibracion.json"} <= set(archivos)
                and all(
                    (carpeta / nombre).is_file() and _sha256(carpeta / nombre) == esperado
                    for nombre, esperado in archivos.items()
                )
            )
            if not valido:
                log.warning("evento=artefactos_invalidos categoria=%s", categoria)
        except (KeyError, TypeError, ValueError, OSError):
            log.warning("evento=manifiesto_ilegible categoria=%s", categoria)
    _cache[categoria] = valido
    return valido


def categorias_con_artefactos() -> list[str]:
    if not RUTA_ARTEFACTOS.is_dir():
        return []
    return sorted(p.name for p in RUTA_ARTEFACTOS.iterdir() if p.is_dir() and disponibles(p.name))


def calibracion(categoria: str) -> dict | None:
    if not disponibles(categoria):
        return None
    try:
        return json.loads((RUTA_ARTEFACTOS / categoria / "calibracion.json").read_text(encoding="utf-8"))
    except (ValueError, OSError):
        log.warning("evento=calibracion_ilegible categoria=%s", categoria)
        return None


def umbral_calibrado(categoria: str) -> float | None:
    datos = calibracion(categoria)
    try:
        return float(datos["umbral"]) if datos else None
    except (KeyError, TypeError, ValueError):
        return None


def cargar_banco(categoria: str) -> np.ndarray:
    """Banco (M, D) float32, cargado sin pickle (M-06)."""
    if not disponibles(categoria):
        raise RuntimeError(f"Artefactos invalidos para {categoria}")
    with np.load(RUTA_ARTEFACTOS / categoria / "banco.npz", allow_pickle=False) as datos:
        banco = datos["banco"]
    if banco.ndim != 2 or banco.dtype != np.float32:
        raise RuntimeError(f"Banco con forma o tipo inesperados: {banco.shape} {banco.dtype}")
    return np.ascontiguousarray(banco)


class GestorArtefactos:
    """Verificacion por manifiesto y carga de bancos y pesos (M-06/M-07)."""

    @staticmethod
    def verificar_sha256(ruta: Path, esperado: str) -> bool:
        return ruta.is_file() and _sha256(ruta) == esperado

    @staticmethod
    def categorias() -> list[str]:
        return categorias_con_artefactos()

    @staticmethod
    def cargar_banco(categoria: str, device=None):
        import torch

        from .motor.patchcore import BancoMemoria

        tensores = torch.from_numpy(cargar_banco(categoria))
        if device is not None:
            tensores = tensores.to(device)
        umbral = umbral_calibrado(categoria)
        if umbral is None:
            raise RuntimeError(f"Calibracion ilegible para {categoria}")
        return BancoMemoria(categoria, tensores, umbral)

    @staticmethod
    def verificar_pesos_sam() -> bool:
        from .motor.segmentador import verificar_checkpoint

        return verificar_checkpoint()


def motor_para(categoria: str) -> str:
    """'real' | 'cargando' | 'simulado' | 'sin_banco' segun el estado del motor."""
    modo = os.environ.get("SAMCORE_MOTOR", "auto")
    if modo == "simulado":
        return "simulado"
    if not disponibles(categoria):
        return "sin_banco"
    from .motor import orquestador

    motor = orquestador.instancia()
    if motor.soporta(categoria):
        return "real"
    if motor.estado in ("sin_iniciar", "cargando"):
        return "cargando"
    return "simulado" if modo == "auto" else "error"


def estado_categoria(categoria: str) -> dict:
    return {"motor": motor_para(categoria), "artefactos": disponibles(categoria)}
