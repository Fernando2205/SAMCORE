"""Re-proyeccion del mapa de anomalias a coordenadas de la imagen original
(protocolo EA-02) y derivados visuales (recorte ROI y mapa coloreado).
"""
import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image

from .patchcore import IMAGESIZE, RESIZE


def reproyectar(mapa: np.ndarray, caja, tam_original: tuple[int, int]) -> np.ndarray:
    """Invierte CenterCrop(224) o Resize(256) y coloca el mapa en la imagen
    completa (fuera de la caja queda 0). tam_original = (alto, ancho)."""
    alto, ancho = tam_original
    x0, y0, x1, y1 = caja
    bw, bh = x1 - x0 + 1, y1 - y0 + 1
    if bw <= bh:
        rw, rh = RESIZE, int(round(RESIZE * bh / bw))
    else:
        rh, rw = RESIZE, int(round(RESIZE * bw / bh))
    rw, rh = max(rw, IMAGESIZE), max(rh, IMAGESIZE)
    lienzo = np.zeros((rh, rw), dtype=np.float32)
    oy, ox = (rh - IMAGESIZE) // 2, (rw - IMAGESIZE) // 2
    lienzo[oy:oy + IMAGESIZE, ox:ox + IMAGESIZE] = mapa
    t = torch.from_numpy(lienzo)[None, None]
    mapa_caja = F.interpolate(t, size=(bh, bw), mode="bilinear", align_corners=False)[0, 0].numpy()
    completo = np.zeros((alto, ancho), dtype=np.float32)
    completo[y0:y1 + 1, x0:x1 + 1] = mapa_caja
    return completo


def recortar(imagen: Image.Image, caja) -> Image.Image:
    x0, y0, x1, y1 = caja
    return imagen.crop((x0, y0, x1 + 1, y1 + 1))


def _paleta_jet(valores: np.ndarray) -> np.ndarray:
    """Mapa de color tipo jet para valores en [0, 1] -> (..., 3) uint8."""
    v = np.clip(valores, 0.0, 1.0)
    r = np.clip(1.5 - np.abs(4.0 * v - 3.0), 0.0, 1.0)
    g = np.clip(1.5 - np.abs(4.0 * v - 2.0), 0.0, 1.0)
    b = np.clip(1.5 - np.abs(4.0 * v - 1.0), 0.0, 1.0)
    return (np.stack([r, g, b], axis=-1) * 255).astype(np.uint8)


def mapa_a_imagen(mapa: np.ndarray, umbral: float) -> Image.Image:
    """Superposicion RGBA: color por intensidad relativa al umbral y
    transparencia creciente con la puntuacion (0 = transparente)."""
    escala = max(umbral * 1.5, 1e-6)
    v = np.clip(mapa / escala, 0.0, 1.0).astype(np.float32)
    rgb = _paleta_jet(v)
    alfa = (np.clip(v * 1.6, 0.0, 0.85) * 255).astype(np.uint8)
    rgba = np.dstack([rgb, alfa])
    return Image.fromarray(rgba, mode="RGBA")


def regiones_de(mapa: np.ndarray, umbral: float, maximo: int = 3) -> list[dict]:
    """Regiones donde el mapa supera el umbral, como circulos normalizados
    (x, y, radio en fraccion de la imagen; intensidad = pico / umbral)."""
    from scipy import ndimage

    alto, ancho = mapa.shape
    etiquetas, n = ndimage.label(mapa > umbral)
    regiones = []
    for i in range(1, n + 1):
        ys, xs = np.where(etiquetas == i)
        if len(xs) == 0:
            continue
        pico = float(mapa[ys, xs].max())
        radio = float(np.sqrt(len(xs) / np.pi)) / max(alto, ancho)
        regiones.append({
            "x": round(float(xs.mean()) / ancho, 4),
            "y": round(float(ys.mean()) / alto, 4),
            "radio": round(max(radio, 0.02), 4),
            "intensidad": round(min(pico / umbral, 2.0) / 2.0, 3),
            "pico": round(pico, 4),
        })
    regiones.sort(key=lambda r: -r["pico"])
    return regiones[:maximo]


class ReProyectorMapa:
    """Devuelve el mapa de la ROI a coordenadas de la imagen original y
    produce los derivados visuales del informe."""

    reproyectar = staticmethod(reproyectar)
    recortar = staticmethod(recortar)
    a_imagen = staticmethod(mapa_a_imagen)
    regiones = staticmethod(regiones_de)
