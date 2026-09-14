"""Motor de inferencia SIMULADO (desarrollo y pruebas automatizadas).

Determinista por (categoria, imagen): la misma entrada produce siempre el
mismo resultado. Respeta el contrato de salida del motor real (mismas
claves, incluidos los derivados `_recorte` y `_mapa_imagen`) para que la
API, el almacen y la interfaz no distingan entre ambos. Se usa solo cuando
`SAMCORE_MOTOR=simulado` o cuando el motor real no esta disponible en modo
`auto`.
"""
import hashlib
import random

import numpy as np
from PIL import Image

from . import galeria
from .motor import reproyeccion, seleccion


def _generador(categoria: str, clave: str) -> random.Random:
    semilla = int.from_bytes(hashlib.sha256(f"{categoria}/{clave}".encode("utf-8")).digest()[:8], "big")
    return random.Random(semilla)


def inspeccionar(imagen: Image.Image, categoria: str, clave: str) -> dict:
    umbral = galeria.umbral_de(categoria)
    r = _generador(categoria, clave)
    es_defectuosa = not clave.startswith("good/")
    if es_defectuosa:
        puntuacion = round(r.uniform(umbral * 1.05, umbral * 1.45), 4)
    else:
        puntuacion = round(r.uniform(umbral * 0.45, umbral * 0.92), 4)
    estado_roi = seleccion.ROI_DEGRADADA if r.random() < 0.07 else seleccion.ROI_OK
    veredicto = "ANOMALO" if puntuacion > umbral else "NORMAL"

    imagen = imagen.convert("RGB")
    ancho, alto = imagen.size
    lado = int(min(ancho, alto) * r.uniform(0.55, 0.95))
    x0 = int((ancho - lado) * r.uniform(0.0, 1.0))
    y0 = int((alto - lado) * r.uniform(0.0, 1.0))
    caja_sam = (x0, y0, x0 + lado - 1, y0 + lado - 1)
    caja_roi = seleccion.expandir_caja(caja_sam, imagen.size)

    yy, xx = np.mgrid[0:alto, 0:ancho]
    cx, cy = (caja_sam[0] + caja_sam[2]) / 2, (caja_sam[1] + caja_sam[3]) / 2
    seg = (((xx - cx) / (lado / 2)) ** 2 + ((yy - cy) / (lado / 2.4)) ** 2) <= 1.0  # elipse dentro de la caja
    mapa = np.zeros((alto, ancho), dtype=np.float32)
    if veredicto == "ANOMALO":
        for _ in range(r.randint(1, 2)):
            cx, cy = r.uniform(0.3, 0.7) * ancho, r.uniform(0.3, 0.7) * alto
            radio = r.uniform(0.08, 0.16) * max(ancho, alto)
            mapa = np.maximum(mapa, puntuacion * np.exp(-((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * radio**2)))
    t_seg, t_det = r.randint(2100, 2600), r.randint(340, 460)
    return {
        "categoria": categoria,
        "puntuacion": puntuacion,
        "umbral": round(umbral, 4),
        "veredicto": veredicto,
        "estado_roi": estado_roi,
        "caja": {"sam": list(caja_sam), "roi": list(caja_roi)},
        "tam": [ancho, alto],
        "mascaras": r.randint(8, 40),
        "regiones": reproyeccion.regiones_de(mapa, umbral),
        "tiempos_ms": {"segmentacion": t_seg, "deteccion": t_det, "reproyeccion": 5, "total": t_seg + t_det + 5},
        "motor": "simulado",
        "_mapa": mapa,
        "_recorte": reproyeccion.recortar(imagen, caja_roi),
        "_mapa_imagen": reproyeccion.mapa_a_imagen(mapa, umbral),
        "_mascara_imagen": reproyeccion.mascara_a_imagen(seg, imagen.size),
    }
