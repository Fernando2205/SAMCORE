"""Consolida las metricas del experimento (AUROC por categoria, linea base y
SAM + ROI) en un JSON que la aplicacion sirve en /api/metricas.

    .venv/Scripts/python scripts/exportar_metricas.py <carpeta resultados> [salida.json]

Lee results_baseline_<cat>.csv, results_sam_roi_<cat>.csv,
auroc_reproyectado_<cat>.csv y roi_estado_<cat>.csv de cada categoria.
"""
import csv
import json
import statistics
import sys
from datetime import date
from pathlib import Path


def _fila(ruta: Path) -> list[float]:
    return [float(v) for v in ruta.read_text(encoding="utf-8").splitlines()[1].split(",")[1:4]]


def consolidar(resultados: Path) -> dict:
    categorias = []
    for carpeta in sorted(p for p in resultados.iterdir() if p.is_dir()):
        cat = carpeta.name
        base, roi = carpeta / f"results_baseline_{cat}.csv", carpeta / f"results_sam_roi_{cat}.csv"
        rep, registro = carpeta / f"auroc_reproyectado_{cat}.csv", carpeta / f"roi_estado_{cat}.csv"
        if not all(r.is_file() for r in (base, roi, rep, registro)):
            continue
        b, r = _fila(base), _fila(roi)
        rep_b, rep_r = [float(v) for v in rep.read_text(encoding="utf-8").splitlines()[1].split(",")[1:3]]
        filas = list(csv.DictReader(registro.open(encoding="utf-8")))
        test = [f for f in filas if f["split"] == "test"]
        lados = sorted(int(f["x1"]) - int(f["x0"]) + 1 for f in test)
        lado_imagen = max(max(int(f["x1"]) + 1, int(f["y1"]) + 1) for f in filas)
        categorias.append({
            "categoria": cat,
            "n_entrenamiento": len(filas) - len(test),
            "n_prueba": len(test),
            "imagen": {"base": round(b[0], 4), "roi": round(r[0], 4)},
            "pixel_todas": {"base": round(b[1], 4), "roi": round(r[1], 4)},
            "pixel_anomalas": {"base": round(b[2], 4), "roi": round(r[2], 4)},
            "pixel_reproyectado": {"base": round(rep_b, 4), "roi": round(rep_r, 4)},
            "zoom": round(lado_imagen / lados[len(lados) // 2], 2),
            "roi_degradada": sum(1 for f in filas if f["estado"] == "ROI_DEGRADADA"),
        })
    claves = ["imagen", "pixel_todas", "pixel_anomalas", "pixel_reproyectado"]
    medias = {k: {rama: round(statistics.fmean(c[k][rama] for c in categorias), 4) for rama in ("base", "roi")} for k in claves}
    return {
        "fecha": date.today().isoformat(),
        "protocolo": "PatchCore (WideResNet-50-2, capas 2 y 3, coreset 10 %, k = 1) sobre imagen completa (base) "
                     "y sobre la ROI de SAM con caja cuadrada (roi); píxel re-proyectado = mapa devuelto a "
                     "coordenadas originales contra la máscara de referencia completa.",
        "categorias": categorias,
        "medias": medias,
    }


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    salida = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(__file__).resolve().parents[1] / "app" / "metricas_experimento.json"
    datos = consolidar(Path(sys.argv[1]))
    salida.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(datos['categorias'])} categorías -> {salida}")


if __name__ == "__main__":
    main()
