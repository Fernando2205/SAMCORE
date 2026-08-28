"""Motor de inferencia SIMULADO del MVP.

Reemplaza al pipeline real (SAM + PatchCore) mientras no existan los
artefactos (bancos de memoria, pesos). Es determinista por
(categoria, imagen): la misma imagen produce siempre el mismo resultado,
lo que permite reabrir informes desde el historial sin guardar mapas.

Costura para T6: sustituir `inspeccionar()` por la llamada al
OrquestadorInferencia real manteniendo el mismo contrato de salida.
"""
import hashlib
import random

from . import galeria


def _generador(categoria: str, imagen_id: str) -> random.Random:
    semilla = int.from_bytes(
        hashlib.sha256(f"{categoria}/{imagen_id}".encode("utf-8")).digest()[:8], "big"
    )
    return random.Random(semilla)


def inspeccionar(categoria: str, imagen_id: str) -> dict:
    umbral = galeria.CATEGORIAS[categoria]["umbral"]
    r = _generador(categoria, imagen_id)
    es_defectuosa = not imagen_id.startswith("good/")

    if es_defectuosa:
        puntuacion = round(r.uniform(umbral * 1.05, umbral * 1.45), 3)
    else:
        puntuacion = round(r.uniform(umbral * 0.45, umbral * 0.92), 3)

    estado_roi = "ROI_DEGRADADA" if r.random() < 0.07 else "ROI_OK"
    veredicto = "ANOMALO" if puntuacion > umbral else "NORMAL"

    regiones = []
    if veredicto == "ANOMALO":
        for _ in range(r.randint(1, 2)):
            regiones.append({
                "x": round(r.uniform(0.25, 0.75), 3),
                "y": round(r.uniform(0.25, 0.75), 3),
                "radio": round(r.uniform(0.08, 0.18), 3),
                "intensidad": round(r.uniform(0.6, 1.0), 3),
            })

    t_segmentacion = r.randint(2100, 2600)
    t_deteccion = r.randint(340, 460)
    return {
        "categoria": categoria,
        "imagen_id": imagen_id,
        "puntuacion": puntuacion,
        "umbral": umbral,
        "veredicto": veredicto,
        "estado_roi": estado_roi,
        "regiones": regiones,
        "tiempos_ms": {
            "segmentacion": t_segmentacion,
            "deteccion": t_deteccion,
            "total": t_segmentacion + t_deteccion,
        },
        "motor": "simulado",
    }
