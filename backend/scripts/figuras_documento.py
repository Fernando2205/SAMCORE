"""Genera dos figuras para el documento a partir de la galeria, los registros
congelados y los npz del experimento:

  segmentacion_pasos.png   original -> mascara elegida y cajas -> recorte (motor real)
  resultados_visuales.png  por categoria: original, ROI, mapa linea base, mapa ROI
                           re-proyectado (mapas del experimento, escala comun 0-1)

    .venv/Scripts/python scripts/figuras_documento.py <carpeta resultados> <carpeta images>
"""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from app import galeria  # noqa: E402
from app.motor import reproyeccion  # noqa: E402

LADO = 360
MARGEN = 14
ALTO_TITULO = 30


def fuente(tam: int):
    for nombre in ("segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(nombre, tam)
        except OSError:
            continue
    return ImageFont.load_default()


def cuadrar(img: Image.Image, lado: int = LADO) -> Image.Image:
    img = img.convert("RGB")
    img.thumbnail((lado, lado), Image.Resampling.LANCZOS)
    lienzo = Image.new("RGB", (lado, lado), (250, 247, 241))
    lienzo.paste(img, ((lado - img.width) // 2, (lado - img.height) // 2))
    return lienzo


def rejilla(paneles: list[list[tuple[Image.Image, str]]], titulos_fila: list[str] | None = None) -> Image.Image:
    filas, cols = len(paneles), len(paneles[0])
    ancho_fila = 150 if titulos_fila else 0
    ancho = ancho_fila + cols * (LADO + MARGEN) + MARGEN
    alto = filas * (LADO + ALTO_TITULO + MARGEN) + MARGEN
    lienzo = Image.new("RGB", (ancho, alto), "white")
    dib = ImageDraw.Draw(lienzo)
    f_tit, f_fila = fuente(18), fuente(20)
    for i, fila in enumerate(paneles):
        y0 = MARGEN + i * (LADO + ALTO_TITULO + MARGEN)
        if titulos_fila:
            dib.text((MARGEN, y0 + ALTO_TITULO + LADO // 2 - 12), titulos_fila[i], fill="black", font=f_fila)
        for j, (img, titulo) in enumerate(fila):
            x0 = ancho_fila + MARGEN + j * (LADO + MARGEN)
            dib.text((x0, y0 + 4), titulo, fill=(60, 60, 60), font=f_tit)
            lienzo.paste(cuadrar(img), (x0, y0 + ALTO_TITULO))
    return lienzo


def mapa_sobre(img: Image.Image, mapa01: np.ndarray) -> Image.Image:
    rgb = reproyeccion._paleta_jet(np.clip(mapa01, 0, 1))
    alfa = (np.clip(mapa01, 0, 1) * 0.75 * 255).astype(np.uint8)
    capa = Image.fromarray(np.dstack([rgb, alfa]), "RGBA")
    return Image.alpha_composite(img.convert("RGBA"), capa).convert("RGB")


def figura_segmentacion(salida: Path) -> None:
    from app.motor import orquestador

    motor = orquestador.instancia()
    motor.preparar()
    assert motor.listo, motor.error
    paneles = []
    for cat, imagen_id in [("capsule", "crack/000.png"), ("transistor", "bent_lead/000.png"), ("bottle", "broken_large/000.png")]:
        with Image.open(galeria.ruta_imagen(cat, imagen_id)) as img:
            img = img.convert("RGB")
        r = motor.inspeccionar(img, cat)
        con_mascara = Image.alpha_composite(img.convert("RGBA"), r["_mascara_imagen"]).convert("RGB")
        dib = ImageDraw.Draw(con_mascara)
        dib.rectangle(r["caja"]["sam"], outline=(12, 122, 107), width=6)
        dib.rectangle(r["caja"]["roi"], outline=(22, 24, 26), width=6)
        paneles.append([
            (img, "Original"),
            (con_mascara, "Máscara elegida y cajas"),
            (r["_recorte"], f"ROI ({r['caja']['roi'][2] - r['caja']['roi'][0] + 1} px de lado)"),
            (mapa_sobre(img, np.clip(r["_mapa"] / (1.5 * r["umbral"]), 0, 1)), f"Mapa re-proyectado · {r['veredicto']}"),
        ])
    rejilla(paneles, ["capsule", "transistor", "bottle"]).save(salida, optimize=True)
    print("guardada", salida)


def figura_resultados(resultados: Path, salida: Path) -> None:
    paneles, filas = [], []
    for cat, imagen_id in [("screw", "scratch_neck/000.png"), ("hazelnut", "crack/000.png"),
                           ("transistor", "cut_lead/000.png"), ("bottle", "broken_large/000.png")]:
        with Image.open(galeria.ruta_imagen(cat, imagen_id)) as img:
            img = img.convert("RGB")
        ancho, alto = img.size
        base = np.load(resultados / cat / f"anomaly_data_baseline_{cat}.npz", allow_pickle=True)
        roi = np.load(resultados / cat / f"anomaly_data_sam_roi_{cat}.npz", allow_pickle=True)
        clave = lambda p: "/".join(Path(str(p)).parts[-2:])  # noqa: E731
        ib = [clave(p) for p in base["image_paths"]].index(imagen_id)
        ir = [clave(p) for p in roi["image_paths"]].index(imagen_id)
        with open(resultados / cat / f"roi_estado_{cat}.csv", encoding="utf-8") as f:
            caja = next(tuple(int(fila[k]) for k in ("x0", "y0", "x1", "y1")) for fila in csv.DictReader(f)
                        if fila["split"] == "test" and f"{fila['tipo']}/{fila['imagen']}" == imagen_id)
        mapa_base = reproyeccion.reproyectar(base["segmentations"][ib].astype(np.float32), (0, 0, ancho - 1, alto - 1), (alto, ancho))
        mapa_roi = reproyeccion.reproyectar(roi["segmentations"][ir].astype(np.float32), caja, (alto, ancho))
        paneles.append([
            (img, f"Original ({imagen_id.split('/')[0]})"),
            (reproyeccion.recortar(img, caja), "ROI"),
            (mapa_sobre(img, mapa_base), f"Línea base · {float(base['scores'][ib]):.2f}"),
            (mapa_sobre(img, mapa_roi), f"SAM + ROI · {float(roi['scores'][ir]):.2f}"),
        ])
        filas.append(cat)
    rejilla(paneles, filas).save(salida, optimize=True)
    print("guardada", salida)


def main() -> None:
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    resultados, images = Path(sys.argv[1]), Path(sys.argv[2])
    galeria.escanear()
    figura_resultados(resultados, images / "resultados_visuales.png")
    figura_segmentacion(images / "segmentacion_pasos.png")


if __name__ == "__main__":
    main()
