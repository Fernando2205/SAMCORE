"""Valida el motor de la aplicacion contra las puntuaciones del experimento.

Para cada imagen de la galeria (imagenes de prueba de MVTec AD) compara:
  (a) la puntuacion de PatchCore de la aplicacion, recortando con la caja
      congelada del experimento, contra la puntuacion guardada en
      anomaly_data_sam_roi_<categoria>.npz  -> fidelidad de la reimplementacion;
  (b) en una muestra por categoria, el pipeline completo (SAM de la
      aplicacion + regla + PatchCore) contra la caja y la puntuacion del
      experimento -> consistencia de la segmentacion.

    .venv/Scripts/python scripts/validar_contra_experimento.py <carpeta resultados> [imagenes por categoria para (b)]
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
from app.motor.reproyeccion import recortar  # noqa: E402


def iou(a, b) -> float:
    ix0, iy0, ix1, iy1 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, ix1 - ix0 + 1) * max(0, iy1 - iy0 + 1)
    area = lambda c: (c[2] - c[0] + 1) * (c[3] - c[1] + 1)  # noqa: E731
    return inter / (area(a) + area(b) - inter)


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    resultados = Path(sys.argv[1])
    por_categoria = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    galeria.escanear()
    motor = orquestador.instancia()
    motor.preparar()
    assert motor.listo, motor.error
    print(f"motor listo: {motor.descripcion_gpu()} · categorias {motor.categorias()}\n")

    difs_a, difs_b, ious = [], [], []
    for cat in motor.categorias():
        npz = np.load(resultados / cat / f"anomaly_data_sam_roi_{cat}.npz", allow_pickle=True)
        ref = {"/".join(Path(str(p)).parts[-2:]): float(s) for p, s in zip(npz["image_paths"], npz["scores"])}
        cajas = {}
        with open(resultados / cat / f"roi_estado_{cat}.csv", encoding="utf-8") as f:
            for fila in csv.DictReader(f):
                if fila["split"] == "test":
                    cajas[f"{fila['tipo']}/{fila['imagen']}"] = tuple(int(fila[k]) for k in ("x0", "y0", "x1", "y1"))
        ids = galeria.listar_imagenes(cat)
        banco = motor._bancos[cat]
        # El CLI de PatchCore guarda las puntuaciones normalizadas min-max sobre
        # todo el conjunto de prueba: exp = (cruda - min) / (max - min). Si la
        # reimplementacion es fiel, las puntuaciones crudas de la aplicacion
        # caen sobre una recta exacta frente a las del experimento.
        crudas, normalizadas = [], []
        for imagen_id in ids:
            if imagen_id not in ref or imagen_id not in cajas:
                continue
            with Image.open(galeria.ruta_imagen(cat, imagen_id)) as img:
                img = img.convert("RGB")
            puntuacion, _ = motor._detector.evaluar(recortar(img, cajas[imagen_id]), banco)
            crudas.append(puntuacion)
            normalizadas.append(ref[imagen_id])
        x, y = np.array(normalizadas), np.array(crudas)
        b, a = np.polyfit(x, y, 1)
        residuo = y - (a + b * x)
        r2 = 1 - (residuo**2).sum() / ((y - y.mean())**2).sum()
        orden_ok = np.array_equal(np.argsort(x), np.argsort(y))
        difs_a.append((r2, np.abs(residuo).max() / (y.max() - y.min())))
        print(f"(a) {cat:<11} n={len(y):>3}  R²={r2:.6f}  residuo máx={np.abs(residuo).max():.4f} "
              f"({100 * np.abs(residuo).max() / (y.max() - y.min()):.2f} % del rango)  mismo orden={orden_ok}  "
              f"crudas [{y.min():.3f}, {y.max():.3f}] umbral {banco.umbral:.3f}")

        candidatos = [i for i in ids if i in ref and i in cajas]
        muestra = ([i for i in candidatos if i.startswith("good/")][:1] +
                   [i for i in candidatos if not i.startswith("good/")][:max(0, por_categoria - 1)]) if por_categoria else []
        for imagen_id in muestra:
            with Image.open(galeria.ruta_imagen(cat, imagen_id)) as img:
                img = img.convert("RGB")
            t0 = time.perf_counter()
            r = motor.inspeccionar(img, cat)
            j = iou(tuple(r["caja"]["roi"]), cajas[imagen_id])
            esperada = a + b * ref[imagen_id]  # puntuacion cruda que implica el experimento
            difs_b.append(abs(r["puntuacion"] - esperada))
            ious.append(j)
            print(f"    (b) {imagen_id:<24} app={r['puntuacion']:.4f} experimento≈{esperada:.4f} "
                  f"IoU caja={j:.3f} roi={r['estado_roi']} {r['veredicto']} {time.perf_counter() - t0:.1f}s")

    r2s = [d[0] for d in difs_a]
    print(f"\nRESUMEN (a) PatchCore con la caja del experimento: {len(r2s)} categorías, "
          f"R² mín={min(r2s):.6f}, residuo máx={100 * max(d[1] for d in difs_a):.2f} % del rango")
    print(f"RESUMEN (b) pipeline completo (SAM de la aplicación): n={len(difs_b)} "
          f"|Δ puntuación| media={np.mean(difs_b):.4f} máx={np.max(difs_b):.4f} · "
          f"IoU caja media={np.mean(ious):.3f} mín={np.min(ious):.3f}")


if __name__ == "__main__":
    main()
