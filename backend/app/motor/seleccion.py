"""Regla de seleccion de mascara (ADR-04) y caja cuadrada con margen (ADR-10).

Copia fiel de las funciones del cuaderno experimental (misma formula, mismos
parametros fijados a priori). No se modifica: los bancos de memoria se
prepararon con esta regla y cualquier cambio invalida la calibracion.
"""
from dataclasses import dataclass

import numpy as np

AREA_MIN_RATIO = 0.03
AREA_MAX_RATIO = 0.95
RHO_OBJETIVO = 0.35
PESO_IOU = 0.60
PESO_ESTABILIDAD = 0.40
PESO_RELLENO = 0.25
PESO_BORDE = 0.15
MARGEN_CENTERCROP = 256 / 224

ROI_OK = "ROI_OK"
ROI_DEGRADADA = "ROI_DEGRADADA"

Caja = tuple[int, int, int, int]  # x0, y0, x1, y1 (inclusivos)


def caja_de_mascara(seg: np.ndarray) -> Caja | None:
    ys, xs = np.where(seg)
    if len(xs) == 0:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())


def puntuar_mascara(mascara: dict, tam_imagen: tuple[int, int]):
    """Devuelve (puntaje, caja, seg, mascara) o None si no pasa el filtro de area."""
    w, h = tam_imagen
    seg = mascara.get("segmentation")
    if seg is None:
        return None
    area = float(mascara.get("area", float(np.sum(seg))))
    ratio = area / float(w * h)
    if ratio < AREA_MIN_RATIO or ratio > AREA_MAX_RATIO:
        return None
    caja = caja_de_mascara(seg)
    if caja is None:
        return None
    x0, y0, x1, y1 = caja
    area_caja = max((x1 - x0 + 1) * (y1 - y0 + 1), 1)
    relleno = area / area_caja
    toca_borde = int(x0 <= 1) + int(y0 <= 1) + int(x1 >= w - 2) + int(y1 >= h - 2)
    puntaje = (
        PESO_IOU * float(mascara.get("predicted_iou", 0.0))
        + PESO_ESTABILIDAD * float(mascara.get("stability_score", 0.0))
        + PESO_RELLENO * relleno
        - PESO_BORDE * toca_borde
        - abs(ratio - RHO_OBJETIVO)
    )
    return puntaje, caja, seg, mascara


def seleccionar(mascaras: list[dict], tam_imagen: tuple[int, int]):
    """Devuelve (caja, seg, meta, estado) con estado ROI_OK o ROI_DEGRADADA."""
    if not mascaras:
        return None, None, None, ROI_DEGRADADA
    puntuadas = []
    for m in mascaras:
        item = puntuar_mascara(m, tam_imagen)
        if item is not None:
            puntuadas.append(item)
    if puntuadas:
        puntuadas.sort(key=lambda t: t[0], reverse=True)
        _, caja, seg, meta = puntuadas[0]
        return caja, seg, meta, ROI_OK
    # Respaldo: ninguna mascara paso los filtros -> la de mayor area (degradada)
    mejor = max(mascaras, key=lambda m: float(m.get("area", 0)))
    seg = mejor.get("segmentation")
    caja = caja_de_mascara(seg) if seg is not None else None
    return caja, seg, mejor, ROI_DEGRADADA


def caja_completa(tam_imagen: tuple[int, int]) -> Caja:
    w, h = tam_imagen
    return 0, 0, w - 1, h - 1


def expandir_caja(caja: Caja, tam_imagen: tuple[int, int], margen: float = MARGEN_CENTERCROP) -> Caja:
    """Caja cuadrada con margen 256/224 centrada en la caja cruda (ADR-10)."""
    w, h = tam_imagen
    x0, y0, x1, y1 = caja
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    lado = int(round(max(x1 - x0 + 1, y1 - y0 + 1) * margen))
    lado = min(lado, w, h)
    x0n = max(0, min(int(round(cx - lado / 2)), w - lado))
    y0n = max(0, min(int(round(cy - lado / 2)), h - lado))
    return x0n, y0n, x0n + lado - 1, y0n + lado - 1


@dataclass(frozen=True)
class PesosPuntuacion:
    """Parametros de la regla, fijados a priori (ADR-04); no se modifican."""
    iou_pred: float = PESO_IOU
    estabilidad: float = PESO_ESTABILIDAD
    compacidad: float = PESO_RELLENO
    bordes: float = -PESO_BORDE
    rho_objetivo: float = RHO_OBJETIVO
    area_min: float = AREA_MIN_RATIO
    area_max: float = AREA_MAX_RATIO


class SelectorMascara:
    """Selector de la mascara del objeto: regla ADR-04 + caja cuadrada ADR-10."""

    def __init__(self) -> None:
        self.pesos = PesosPuntuacion()

    def seleccionar(self, mascaras: list[dict], tam_imagen: tuple[int, int]):
        return seleccionar(mascaras, tam_imagen)

    def caja_definitiva(self, caja: Caja | None, tam_imagen: tuple[int, int]) -> Caja:
        """Caja cuadrada con margen; si no hubo mascara, sobre la imagen completa."""
        return expandir_caja(caja if caja is not None else caja_completa(tam_imagen), tam_imagen)
