"""Orquestador de inferencia: imagen -> SAM -> regla de seleccion -> caja
cuadrada -> PatchCore -> re-proyeccion. Concurrencia acotada a la GPU (M-01),
tope de tiempo por etapa (M-05) y bancos cargados sin pickle (M-06).
"""
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturoAgotado

import numpy as np
import torch
from PIL import Image

from .. import artefactos
from . import reproyeccion, seleccion
from .patchcore import DetectorPatchCore
from .segmentador import SegmentadorSAM

log = logging.getLogger("samcore")

COLA_MAXIMA = int(os.environ.get("SAMCORE_COLA", "4"))
TIEMPO_MAXIMO_S = float(os.environ.get("SAMCORE_TIEMPO_MAXIMO", "120"))


class ColaLlena(Exception):
    pass


class TiempoAgotado(Exception):
    pass


def _elegir_dispositivo_y_precision() -> tuple[torch.device, str]:
    if not torch.cuda.is_available():
        return torch.device("cpu"), "fp32"
    precision = os.environ.get("SAMCORE_PRECISION")
    if precision not in ("fp16", "fp32"):
        memoria_gb = torch.cuda.get_device_properties(0).total_memory / 2**30
        precision = "fp16" if memoria_gb < 10 else "fp32"
    return torch.device("cuda"), precision


class Orquestador:
    def __init__(self) -> None:
        self.device, self.precision = _elegir_dispositivo_y_precision()
        self.estado = "sin_iniciar"  # sin_iniciar | cargando | listo | error
        self.error: str | None = None
        self._sam: SegmentadorSAM | None = None
        self._detector: DetectorPatchCore | None = None
        self._bancos: dict[str, torch.Tensor] = {}
        self._umbrales: dict[str, float] = {}
        self._gpu = threading.Lock()
        self._en_cola = 0
        self._cola_lock = threading.Lock()
        self._ejecutor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="gpu")

    # ---- carga -----------------------------------------------------------
    def preparar_en_segundo_plano(self) -> None:
        hilo = threading.Thread(target=self.preparar, name="carga-motor", daemon=True)
        hilo.start()

    def preparar(self) -> None:
        self.estado = "cargando"
        try:
            t0 = time.perf_counter()
            for categoria in artefactos.categorias_con_artefactos():
                banco = artefactos.cargar_banco(categoria)
                self._bancos[categoria] = torch.from_numpy(banco)
                self._umbrales[categoria] = float(artefactos.calibracion(categoria)["umbral"])
            self._detector = DetectorPatchCore(self.device)
            self._sam = SegmentadorSAM(self.device, self.precision)
            self._sam.cargar()
            self.estado = "listo"
            log.info(
                "evento=motor_listo categorias=%d device=%s precision=%s segundos=%.1f",
                len(self._bancos), self.device, self.precision, time.perf_counter() - t0,
            )
        except Exception as exc:  # noqa: BLE001 - se reporta por estado, no se propaga
            self.estado = "error"
            self.error = type(exc).__name__
            log.error("evento=motor_error tipo=%s detalle=%s", type(exc).__name__, exc)

    @property
    def listo(self) -> bool:
        return self.estado == "listo"

    def categorias(self) -> list[str]:
        return sorted(self._bancos)

    def soporta(self, categoria: str) -> bool:
        return self.listo and categoria in self._bancos

    def descripcion_gpu(self) -> str:
        if self.device.type != "cuda":
            return "cpu"
        return f"{torch.cuda.get_device_name(0)} ({self.precision})"

    # ---- inferencia -------------------------------------------------------
    def inspeccionar(self, imagen: Image.Image, categoria: str) -> dict:
        """Ejecuta el pipeline con concurrencia acotada. Lanza ColaLlena o
        TiempoAgotado; el resultado incluye arreglos e imagenes derivadas."""
        if not self.soporta(categoria):
            raise RuntimeError(f"Categoria sin banco: {categoria}")
        with self._cola_lock:
            if self._en_cola >= COLA_MAXIMA:
                raise ColaLlena()
            self._en_cola += 1
        try:
            futuro = self._ejecutor.submit(self._pipeline, imagen, categoria)
            try:
                return futuro.result(timeout=TIEMPO_MAXIMO_S)
            except FuturoAgotado:
                log.warning("evento=tiempo_agotado categoria=%s", categoria)
                raise TiempoAgotado() from None
        finally:
            with self._cola_lock:
                self._en_cola -= 1

    def _pipeline(self, imagen: Image.Image, categoria: str) -> dict:
        imagen = imagen.convert("RGB")
        ancho, alto = imagen.size
        arreglo = np.asarray(imagen)

        t0 = time.perf_counter()
        mascaras = self._sam.segmentar(arreglo)
        caja_sam, _seg, _meta, estado = seleccion.seleccionar(mascaras, imagen.size)
        if caja_sam is None:
            caja_sam = seleccion.caja_completa(imagen.size)
        caja_roi = seleccion.expandir_caja(caja_sam, imagen.size)
        recorte = reproyeccion.recortar(imagen, caja_roi)
        t1 = time.perf_counter()

        caracteristicas = self._detector.incrustar(recorte)
        puntuacion, mapa224 = self._detector.puntuar(caracteristicas, self._bancos[categoria])
        t2 = time.perf_counter()

        umbral = self._umbrales[categoria]
        mapa = reproyeccion.reproyectar(mapa224, caja_roi, (alto, ancho))
        veredicto = "ANOMALO" if puntuacion > umbral else "NORMAL"
        t3 = time.perf_counter()

        return {
            "categoria": categoria,
            "puntuacion": round(puntuacion, 4),
            "umbral": round(umbral, 4),
            "veredicto": veredicto,
            "estado_roi": estado,
            "caja": {"sam": list(caja_sam), "roi": list(caja_roi)},
            "tam": [ancho, alto],
            "mascaras": len(mascaras),
            "regiones": reproyeccion.regiones_de(mapa, umbral),
            "tiempos_ms": {
                "segmentacion": int((t1 - t0) * 1000),
                "deteccion": int((t2 - t1) * 1000),
                "reproyeccion": int((t3 - t2) * 1000),
                "total": int((t3 - t0) * 1000),
            },
            "motor": "real",
            "_mapa": mapa,
            "_recorte": recorte,
            "_mapa_imagen": reproyeccion.mapa_a_imagen(mapa, umbral),
        }


_instancia: Orquestador | None = None


def instancia() -> Orquestador:
    global _instancia
    if _instancia is None:
        _instancia = Orquestador()
    return _instancia
