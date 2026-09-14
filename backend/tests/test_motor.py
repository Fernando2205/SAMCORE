"""Pruebas unitarias del motor: regla de seleccion, caja cuadrada,
re-proyeccion, ingesta y verificacion de artefactos (M-06/M-07)."""
import hashlib
import io
import json

import numpy as np
import pytest
from PIL import Image

from app import artefactos, ingesta
from app.motor import reproyeccion, seleccion


def _mascara(w, h, x0, y0, x1, y1, iou=0.9, estabilidad=0.95):
    seg = np.zeros((h, w), dtype=bool)
    seg[y0:y1 + 1, x0:x1 + 1] = True
    return {"segmentation": seg, "area": int(seg.sum()), "predicted_iou": iou, "stability_score": estabilidad}


def test_regla_filtra_por_area_y_elige_la_mejor():
    w, h = 200, 200
    pequena = _mascara(w, h, 10, 10, 15, 15)             # < 3 % del area
    completa = _mascara(w, h, 0, 0, 199, 199)            # > 95 % del area
    objeto = _mascara(w, h, 40, 40, 150, 150, iou=0.92)  # ~31 %, cerca de rho
    caja, seg, meta, estado = seleccion.seleccionar([pequena, completa, objeto], (w, h))
    assert estado == seleccion.ROI_OK and caja == (40, 40, 150, 150)


def test_regla_degrada_si_nada_pasa_el_filtro():
    w, h = 200, 200
    caja, seg, meta, estado = seleccion.seleccionar([_mascara(w, h, 0, 0, 5, 5), _mascara(w, h, 0, 0, 199, 199)], (w, h))
    assert estado == seleccion.ROI_DEGRADADA and caja == (0, 0, 199, 199)
    assert seleccion.seleccionar([], (w, h))[3] == seleccion.ROI_DEGRADADA


def test_caja_cuadrada_con_margen_y_recorte_al_lienzo():
    caja = seleccion.expandir_caja((100, 150, 299, 249), (1024, 1024))
    x0, y0, x1, y1 = caja
    assert x1 - x0 == y1 - y0
    assert x1 - x0 + 1 == round(200 * 256 / 224)
    assert 0 <= x0 and x1 < 1024 and 0 <= y0 and y1 < 1024
    completa = seleccion.expandir_caja((10, 20, 900, 1000), (1024, 1024))
    assert completa == (0, 0, 1023, 1023)


def test_reproyeccion_coloca_el_mapa_en_la_caja():
    mapa = np.ones((224, 224), dtype=np.float32)
    caja = (100, 100, 355, 355)  # lado 256 -> Resize(256) exacto, borde de 16 px a cero
    completo = reproyeccion.reproyectar(mapa, caja, (600, 800))
    assert completo.shape == (600, 800)
    assert completo[:100].max() == 0 and completo[:, :100].max() == 0 and completo[356:].max() == 0
    assert completo[228, 228] == pytest.approx(1.0, abs=1e-3)
    assert completo[102, 102] == pytest.approx(0.0, abs=1e-3)


def test_derivados_visuales():
    mapa = np.zeros((120, 160), dtype=np.float32)
    mapa[40:60, 70:90] = 5.0
    imagen = reproyeccion.mapa_a_imagen(mapa, umbral=2.0)
    assert imagen.mode == "RGBA" and imagen.size == (160, 120)
    assert imagen.getpixel((80, 50))[3] > 0 and imagen.getpixel((5, 5))[3] == 0
    regiones = reproyeccion.regiones_de(mapa, umbral=2.0)
    assert len(regiones) == 1 and 0.4 < regiones[0]["x"] < 0.6 and 0.35 < regiones[0]["y"] < 0.5
    seg = np.zeros((120, 160), dtype=bool)
    seg[30:90, 40:120] = True
    mascara = reproyeccion.mascara_a_imagen(seg, (160, 120))
    assert mascara.size == (160, 120)
    assert mascara.getpixel((80, 60))[3] == 90 and mascara.getpixel((40, 60))[3] == 255 and mascara.getpixel((5, 5))[3] == 0
    assert reproyeccion.mascara_a_imagen(None, (160, 120)).getpixel((80, 60))[3] == 0


def _png_bytes(w, h, formato="PNG"):
    salida = io.BytesIO()
    Image.new("RGB", (w, h), (10, 20, 30)).save(salida, format=formato)
    return salida.getvalue()


def test_ingesta_acepta_png_y_jpeg_y_reduce():
    imagen = ingesta.ingerir(_png_bytes(3000, 1500))
    assert imagen.size == (1024, 512) and imagen.mode == "RGB" and not imagen.info
    assert ingesta.ingerir(_png_bytes(300, 200, "JPEG")).size == (300, 200)


def test_ingesta_rechaza():
    with pytest.raises(ingesta.ImagenRechazada) as exc:
        ingesta.ingerir(b"BM" + b"\x00" * 200)
    assert exc.value.codigo == "tipo"
    with pytest.raises(ingesta.ImagenRechazada) as exc:
        ingesta.ingerir(_png_bytes(20, 20))
    assert exc.value.codigo == "dimensiones"
    with pytest.raises(ingesta.ImagenRechazada):
        ingesta.ingerir(_png_bytes(200, 200)[:50])


def test_artefactos_manifiesto_y_hash(tmp_path, monkeypatch):
    monkeypatch.setattr(artefactos, "RUTA_ARTEFACTOS", tmp_path)
    artefactos._cache.clear()
    carpeta = tmp_path / "capsule"
    carpeta.mkdir()
    np.savez_compressed(carpeta / "banco.npz", banco=np.zeros((10, 1024), dtype=np.float32))
    (carpeta / "calibracion.json").write_text(json.dumps({"umbral": 1.5}), encoding="utf-8")
    hashes = {n: hashlib.sha256((carpeta / n).read_bytes()).hexdigest() for n in ("banco.npz", "calibracion.json")}
    (carpeta / "manifiesto.json").write_text(json.dumps({"categoria": "capsule", "version": "1", "archivos": hashes}), encoding="utf-8")
    assert artefactos.disponibles("capsule") and artefactos.umbral_calibrado("capsule") == 1.5
    assert artefactos.cargar_banco("capsule").shape == (10, 1024)
    # un byte alterado en el banco -> la categoria se deshabilita
    datos = bytearray((carpeta / "banco.npz").read_bytes())
    datos[-1] ^= 0xFF
    (carpeta / "banco.npz").write_bytes(bytes(datos))
    artefactos._cache.clear()
    assert not artefactos.disponibles("capsule")
    with pytest.raises(RuntimeError):
        artefactos.cargar_banco("capsule")
    # sin manifiesto -> no disponible
    (carpeta / "manifiesto.json").unlink()
    artefactos._cache.clear()
    assert not artefactos.disponibles("capsule")
