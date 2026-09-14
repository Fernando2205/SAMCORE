"""Almacen de informes e imagenes por inspeccion (retencion controlada, M-17).

    backend/datos/inspecciones/<id>/
        informe.json    resultado completo (sin arreglos)
        roi.png         recorte de la ROI
        mapa.png        mapa de anomalias re-proyectado (RGBA)
        mascara.png     mascara elegida por SAM sobre la imagen original (RGBA)
        original.png    solo para imagenes propias (version re-codificada)

Las rutas se derivan del identificador numerico de la inspeccion, nunca de
texto del cliente. Borrar una inspeccion elimina la carpeta completa.
"""
import json
import os
import shutil
from pathlib import Path

from PIL import Image

RUTA_DATOS = Path(os.environ.get("SAMCORE_DATOS", Path(__file__).resolve().parent.parent / "datos"))
CLASES = ("original", "roi", "mapa", "mascara")


def carpeta(inspeccion_id: int) -> Path:
    return RUTA_DATOS / "inspecciones" / str(int(inspeccion_id))


def _publico(resultado: dict) -> dict:
    return {k: v for k, v in resultado.items() if not k.startswith("_")}


def guardar(inspeccion_id: int, resultado: dict, original: Image.Image | None = None) -> None:
    destino = carpeta(inspeccion_id)
    destino.mkdir(parents=True, exist_ok=True)
    if original is not None:
        original.save(destino / "original.png", format="PNG", optimize=True)
    recorte = resultado.get("_recorte")
    if recorte is not None:
        recorte.save(destino / "roi.png", format="PNG", optimize=True)
    mapa = resultado.get("_mapa_imagen")
    if mapa is not None:
        mapa.save(destino / "mapa.png", format="PNG", optimize=True)
    mascara = resultado.get("_mascara_imagen")
    if mascara is not None:
        mascara.save(destino / "mascara.png", format="PNG", optimize=True)
    (destino / "informe.json").write_text(
        json.dumps(_publico(resultado), ensure_ascii=False), encoding="utf-8"
    )


def cargar_informe(inspeccion_id: int) -> dict | None:
    ruta = carpeta(inspeccion_id) / "informe.json"
    if not ruta.is_file():
        return None
    try:
        return json.loads(ruta.read_text(encoding="utf-8"))
    except ValueError:
        return None


def ruta_derivado(inspeccion_id: int, clase: str) -> Path | None:
    if clase not in CLASES:
        return None
    ruta = carpeta(inspeccion_id) / f"{clase}.png"
    return ruta if ruta.is_file() else None


def borrar(inspeccion_id: int) -> None:
    shutil.rmtree(carpeta(inspeccion_id), ignore_errors=True)
