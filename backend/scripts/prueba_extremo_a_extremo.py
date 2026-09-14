"""Prueba de extremo a extremo contra un servidor en marcha (motor real):
salud, sesion, galeria, inspeccion de galeria, carga de imagen propia,
informe, imagenes derivadas y borrado.

    .venv/Scripts/python scripts/prueba_extremo_a_extremo.py http://127.0.0.1:8000 correo contrasena [imagen_propia.png]
"""
import sys
import time
from pathlib import Path

import httpx


def main() -> None:
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    base, correo, contrasena = sys.argv[1:4]
    propia = Path(sys.argv[4]) if len(sys.argv) > 4 else None
    c = httpx.Client(base_url=base, timeout=300)

    for _ in range(60):
        salud = c.get("/api/salud").json()
        if salud["motor"] == "real":
            break
        print("esperando motor:", salud["motor"])
        time.sleep(5)
    print("salud:", salud)
    assert salud["motor"] == "real", "el motor real no quedo listo"

    r = c.post("/api/auth/login", json={"correo": correo, "contrasena": contrasena})
    assert r.status_code == 200, r.text
    print("sesion:", r.json())

    categorias = c.get("/api/categorias").json()
    con_galeria = [x for x in categorias if x["artefactos"] and x["imagenes"] > 0]
    print("categorias con banco y galeria:", [(x["nombre"], x["imagenes"], x["motor"]) for x in con_galeria])
    assert con_galeria, "sin categorias listas"
    cat = con_galeria[0]["nombre"]
    galeria = c.get(f"/api/galeria/{cat}").json()
    imagen_id = galeria["imagenes"][0]

    t0 = time.perf_counter()
    r = c.post("/api/inspeccionar", json={"categoria": cat, "imagen_id": imagen_id})
    assert r.status_code == 200, r.text
    res = r.json()
    print(f"inspeccion galeria {cat}/{imagen_id}: {res['veredicto']} {res['puntuacion']} / {res['umbral']} "
          f"roi={res['estado_roi']} tiempos={res['tiempos_ms']} motor={res['motor']} ({time.perf_counter() - t0:.1f}s)")
    for clase, url in res["imagenes"].items():
        img = c.get(url)
        assert img.status_code == 200 and img.headers["content-type"] == "image/png", (clase, img.status_code)
        print(f"  imagen {clase}: {len(img.content)} bytes")
    informe = c.get(f"/api/historial/{res['id']}/informe").json()
    assert informe["puntuacion"] == res["puntuacion"]

    if propia is not None:
        with propia.open("rb") as f:
            r = c.post("/api/inspeccionar/propia", data={"categoria": cat}, files={"archivo": (propia.name, f, "image/png")})
        assert r.status_code == 200, r.text
        p = r.json()
        print(f"imagen propia: {p['veredicto']} {p['puntuacion']} / {p['umbral']} origen={p['origen']} tam={p['tam']} tiempos={p['tiempos_ms']}")
        assert c.get(p["imagenes"]["original"]).status_code == 200
        assert c.delete(f"/api/historial/{p['id']}").status_code == 200
        assert c.get(f"/api/historial/{p['id']}/informe").status_code == 404
        print("  borrada del historial: ok")

    r = c.post("/api/inspeccionar", json={"categoria": cat, "imagen_id": "../../x.png"})
    assert r.status_code == 422
    print("historial:", len(c.get("/api/historial").json()), "filas · estadisticas:", c.get("/api/estadisticas").json()["p95_ms"], "ms p95")
    print("EXTREMO A EXTREMO OK")


if __name__ == "__main__":
    main()
