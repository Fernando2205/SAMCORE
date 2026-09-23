"""Compara la caja de la ROI que produce el motor de la aplicacion (SAM + regla
+ caja cuadrada) con la caja congelada del experimento, para TODAS las
imagenes de la galeria. Complementa a validar_contra_experimento.py, que
muestrea por categoria.

    .venv/Scripts/python scripts/validar_cajas_galeria.py <carpeta resultados>
"""
import csv
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

from app import galeria  # noqa: E402
from app.motor import orquestador  # noqa: E402


def iou(a, b) -> float:
    ix0, iy0, ix1, iy1 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, ix1 - ix0 + 1) * max(0, iy1 - iy0 + 1)
    area = lambda c: (c[2] - c[0] + 1) * (c[3] - c[1] + 1)  # noqa: E731
    return inter / (area(a) + area(b) - inter)


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    resultados = Path(sys.argv[1])
    galeria.escanear()
    motor = orquestador.instancia()
    motor.preparar()
    assert motor.listo, motor.error
    print(f"motor listo: {motor.descripcion_gpu()}", flush=True)
    ious, tiempos = [], []
    for cat in motor.categorias():
        cajas = {}
        with open(resultados / cat / f"roi_estado_{cat}.csv", encoding="utf-8") as f:
            for fila in csv.DictReader(f):
                if fila["split"] == "test":
                    cajas[f"{fila['tipo']}/{fila['imagen']}"] = tuple(int(fila[k]) for k in ("x0", "y0", "x1", "y1"))
        for imagen_id in galeria.listar_imagenes(cat):
            if imagen_id not in cajas:
                continue
            with Image.open(galeria.ruta_imagen(cat, imagen_id)) as img:
                img = img.convert("RGB")
            t0 = time.perf_counter()
            r = motor.inspeccionar(img, cat)
            tiempos.append(time.perf_counter() - t0)
            j = iou(tuple(r["caja"]["roi"]), cajas[imagen_id])
            ious.append(j)
            print(f"{cat:<11} {imagen_id:<24} IoU={j:.4f} {r['estado_roi']} {tiempos[-1]:.1f}s", flush=True)
    ious = np.array(ious)
    print(f"\nRESUMEN: n={len(ious)} IoU media={ious.mean():.4f} mín={ious.min():.4f} "
          f"< 0,995: {(ious < 0.995).sum()} · tiempo mediano {np.median(tiempos):.1f}s", flush=True)


if __name__ == "__main__":
    main()
