"""Segmentador SAM 1 (ViT-H) en modo de generacion automatica de mascaras.

- Pesos verificados por SHA-256 antes de cargar (M-07); la carga usa
  `weights_only` de torch, que solo admite tensores (sin codigo).
- Precision: fp32 en la GPU del despliegue; fp16 (pesos en media precision
  mas autocast) para la verificacion funcional en una GPU pequena.
- Tope de mascaras consideradas por imagen (M-05).
"""
import hashlib
import logging
import os
import time
from pathlib import Path

import numpy as np
import torch

log = logging.getLogger("samcore")

RUTA_PESOS = Path(os.environ.get("SAMCORE_PESOS", Path(__file__).resolve().parents[2] / "pesos"))
SAM_ARCHIVO = "sam_vit_h_4b8939.pth"
SAM_SHA256 = "a7bf3b02f3ebf1267aba913ff637d9a2d5c33d3173bb679e46d9f338c26f262e"
SAM_URL = "https://dl.fbaipublicfiles.com/segment_anything/sam_vit_h_4b8939.pth"
MAX_MASCARAS = 256


def _sha256(ruta: Path) -> str:
    h = hashlib.sha256()
    with ruta.open("rb") as f:
        for bloque in iter(lambda: f.read(1 << 22), b""):
            h.update(bloque)
    return h.hexdigest()


def ruta_checkpoint() -> Path:
    return RUTA_PESOS / SAM_ARCHIVO


def verificar_checkpoint() -> bool:
    ruta = ruta_checkpoint()
    if not ruta.is_file():
        log.error("evento=sam_pesos_ausentes ruta=%s", ruta)
        return False
    real = _sha256(ruta)
    if real != SAM_SHA256:
        log.error("evento=sam_pesos_invalidos ruta=%s", ruta)
        return False
    return True


class SegmentadorSAM:
    def __init__(self, device: torch.device, precision: str = "fp32") -> None:
        self.device = device
        self.precision = precision
        self._generador = None

    def cargar(self) -> None:
        from segment_anything import SamAutomaticMaskGenerator, sam_model_registry

        if not verificar_checkpoint():
            raise RuntimeError("Pesos de SAM ausentes o con hash invalido")
        t0 = time.perf_counter()
        sam = sam_model_registry["vit_h"](checkpoint=str(ruta_checkpoint()))
        sam.eval()
        if self.precision == "fp16":
            sam.half()
        sam.to(self.device)
        # Parametros por defecto del generador: los mismos del experimento.
        self._generador = SamAutomaticMaskGenerator(sam)
        log.info(
            "evento=sam_listo device=%s precision=%s segundos=%.1f",
            self.device, self.precision, time.perf_counter() - t0,
        )

    @property
    def listo(self) -> bool:
        return self._generador is not None

    def segmentar(self, imagen_rgb: np.ndarray) -> list[dict]:
        """Mascaras candidatas (diccionarios de SAM), a lo sumo MAX_MASCARAS."""
        if self._generador is None:
            raise RuntimeError("SAM no esta cargado")
        usar_autocast = self.device.type == "cuda" and self.precision == "fp16"
        with torch.inference_mode():
            with torch.autocast(device_type="cuda", dtype=torch.float16, enabled=usar_autocast):
                mascaras = self._generador.generate(imagen_rgb)
        if len(mascaras) > MAX_MASCARAS:
            mascaras = sorted(mascaras, key=lambda m: m.get("area", 0), reverse=True)[:MAX_MASCARAS]
        return mascaras
