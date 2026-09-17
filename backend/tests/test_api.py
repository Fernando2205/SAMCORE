"""Suite de verificacion de la API: un caso por control vigente del modelo
de amenazas (M-01 a M-17) mas el contrato funcional de inspeccion,
historial e informe."""
import io
import json
import sqlite3

from PIL import Image, PngImagePlugin

from app import db, ingesta, seguridad
from tests.conftest import crear_usuario


def _png(ancho=200, alto=150, color=(120, 160, 200), metadatos=None) -> bytes:
    imagen = Image.new("RGB", (ancho, alto), color)
    salida = io.BytesIO()
    info = PngImagePlugin.PngInfo()
    for clave, valor in (metadatos or {}).items():
        info.add_text(clave, valor)
    imagen.save(salida, format="PNG", pnginfo=info)
    return salida.getvalue()


def _inspeccionar(cliente, categoria="capsule", imagen="good/000.png"):
    return cliente.post("/api/inspeccionar", json={"categoria": categoria, "imagen_id": imagen})


# ----------------------------------------------------------- contrato base ---
def test_salud_reporta_motor_simulado(servidor):
    r = servidor.get("/api/salud")
    assert r.status_code == 200
    assert r.json()["motor"] == "simulado"
    assert r.headers["x-content-type-options"] == "nosniff"


def test_sin_sesion_no_hay_acceso(servidor):
    for ruta in ["/api/categorias", "/api/historial", "/api/estadisticas", "/api/admin/usuarios"]:
        assert servidor.get(ruta).status_code == 401
    assert _inspeccionar(servidor).status_code == 401


def test_inspeccion_de_galeria_genera_informe_completo(usuario_a):
    r = _inspeccionar(usuario_a)
    assert r.status_code == 200, r.text
    datos = r.json()
    assert datos["veredicto"] in ("ANOMALO", "NORMAL")
    assert datos["estado_roi"] in ("ROI_OK", "ROI_DEGRADADA")
    assert datos["origen"] == "galeria"
    assert set(datos["imagenes"]) == {"original", "roi", "mapa", "mascara"}
    assert set(datos["tiempos_ms"]) >= {"segmentacion", "deteccion", "total"}
    for clase in ("roi", "mapa", "mascara"):
        imagen = usuario_a.get(datos["imagenes"][clase])
        assert imagen.status_code == 200 and imagen.headers["content-type"] == "image/png"
    original = usuario_a.get(datos["imagenes"]["original"])
    assert original.status_code == 200 and original.headers["content-type"] == "image/png"
    informe = usuario_a.get(f"/api/historial/{datos['id']}/informe")
    assert informe.status_code == 200
    assert informe.json()["puntuacion"] == datos["puntuacion"]
    assert informe.json()["veredicto"] == datos["veredicto"]


def test_historial_lista_solo_lo_propio(usuario_a, usuario_b):
    _inspeccionar(usuario_a, imagen="good/001.png")
    ids_a = {f["id"] for f in usuario_a.get("/api/historial").json()}
    ids_b = {f["id"] for f in usuario_b.get("/api/historial").json()}
    assert ids_a and not (ids_a & ids_b)


# -------------------------------------------------- M-03 listas cerradas ---
def test_m03_parametros_fuera_de_lista(usuario_a):
    assert _inspeccionar(usuario_a, categoria="inexistente").status_code == 422
    assert _inspeccionar(usuario_a, imagen="../../etc/passwd").status_code == 422
    assert _inspeccionar(usuario_a, imagen="good/../crack/000.png").status_code == 422
    assert usuario_a.get("/api/galeria/capsule/imagen/..%2F..%2Fapp%2Fmain.py").status_code == 422
    r = usuario_a.post("/api/inspeccionar", content=b"{no es json", headers={"Content-Type": "application/json"})
    assert r.status_code == 422


def test_m03_categoria_sin_banco_en_modo_simulado_lista_cerrada(usuario_a):
    assert usuario_a.get("/api/galeria/metal_nut").json()["imagenes"] == []
    assert _inspeccionar(usuario_a, categoria="metal_nut", imagen="good/000.png").status_code == 422


# ----------------------------------------------- M-01 limitacion de tasa ---
def test_m01_limite_de_inspecciones_por_usuario(admin):
    cliente = crear_usuario(admin, "rafaga@pruebas.local")
    codigos = [_inspeccionar(cliente).status_code for _ in range(seguridad.limitador_inspeccion.maximo + 1)]
    assert codigos[:-1] == [200] * seguridad.limitador_inspeccion.maximo
    assert codigos[-1] == 429
    assert cliente.post("/api/inspeccionar/propia", data={"categoria": "capsule"},
                        files={"archivo": ("a.png", _png(), "image/png")}).status_code == 429


# --------------------------------------------- M-02 errores centralizados ---
def test_m02_error_interno_sin_detalles(admin, monkeypatch):
    from app import inferencia

    def explota(*args, **kwargs):
        raise RuntimeError("detalle interno secreto /ruta/privada")

    cliente = crear_usuario(admin, "error@pruebas.local", relanzar_errores=False)
    monkeypatch.setattr(inferencia, "inspeccionar", explota)
    r = _inspeccionar(cliente)
    assert r.status_code == 500
    cuerpo = r.json()
    assert cuerpo["error"] == "inesperado" and cuerpo["ref"].startswith("ERR-")
    assert "secreto" not in r.text and "Traceback" not in r.text


# ----------------------------------------- M-10 autenticacion robusta ---
def test_m10_contrasena_corta_y_limite_de_intentos(servidor):
    r = servidor.post("/api/auth/registro", json={"correo": "corta@pruebas.local", "contrasena": "abc", "confirmacion": "abc"})
    assert r.status_code == 422
    codigos = [
        servidor.post("/api/auth/login", json={"correo": "nadie@pruebas.local", "contrasena": "incorrecta-123"}).status_code
        for _ in range(seguridad.limitador_login.maximo + 1)
    ]
    assert codigos[:-1] == [401] * seguridad.limitador_login.maximo and codigos[-1] == 429


def test_m10_m13_solo_hash_y_sal_en_la_bd():
    con = db.conectar()
    try:
        fila = con.execute("SELECT * FROM usuarios WHERE correo = 'ana@pruebas.local'").fetchone()
    finally:
        con.close()
    assert fila["hash_contrasena"] != "contrasena-larga-1" and len(fila["sal"]) == 32
    assert set(fila.keys()) <= {"id", "correo", "hash_contrasena", "sal", "rol", "estado", "creado_en", "ultimo_acceso"}


# ----------------------------------------------- M-11 gestion de sesiones ---
def test_m11_cookie_endurecida_y_cierre_de_sesion(admin):
    cliente = crear_usuario(admin, "sesion@pruebas.local")
    cabecera = cliente.cookies.jar
    galleta = next(c for c in cabecera if c.name == seguridad.COOKIE_SESION)
    assert galleta.has_nonstandard_attr("HttpOnly") and galleta.get_nonstandard_attr("SameSite") == "lax"
    assert cliente.get("/api/sesion").status_code == 200
    assert cliente.post("/api/auth/logout").status_code == 200
    assert cliente.get("/api/sesion").status_code == 401


def test_m11_desactivar_cuenta_invalida_su_sesion(admin):
    cliente = crear_usuario(admin, "baja@pruebas.local")
    objetivo = next(u for u in admin.get("/api/admin/usuarios").json() if u["correo"] == "baja@pruebas.local")
    assert admin.post(f"/api/admin/usuarios/{objetivo['id']}/estado", json={"accion": "desactivar"}).status_code == 200
    assert cliente.get("/api/sesion").status_code == 401
    r = cliente.post("/api/auth/login", json={"correo": "baja@pruebas.local", "contrasena": "contrasena-larga-1"})
    assert r.status_code == 403


def test_m11_token_ajeno_no_abre_sesion(servidor):
    servidor.cookies.set(seguridad.COOKIE_SESION, "token-inventado")
    assert servidor.get("/api/sesion").status_code == 401
    servidor.cookies.clear()


# ------------------------------------------------ M-12 anti-IDOR ---
def test_m12_informe_e_imagenes_de_otro_usuario(usuario_a, usuario_b):
    propia = _inspeccionar(usuario_a).json()
    assert usuario_b.get(f"/api/historial/{propia['id']}/informe").status_code == 404
    assert usuario_b.get(f"/api/historial/{propia['id']}/imagen/mapa").status_code == 404
    assert usuario_b.delete(f"/api/historial/{propia['id']}").status_code == 404
    assert usuario_a.get(f"/api/historial/{propia['id']}/informe").status_code == 200


# --------------------------------------------- M-15 rol en el servidor ---
def test_m15_usuario_normal_sin_administracion(usuario_a):
    assert usuario_a.get("/api/admin/usuarios").status_code == 403
    assert usuario_a.post("/api/admin/usuarios/1/estado", json={"accion": "aprobar"}).status_code == 403


def test_m15_ultimo_administrador_no_se_desactiva(admin):
    yo = next(u for u in admin.get("/api/admin/usuarios").json() if u["rol"] == "administrador" and u["estado"] == "activo")
    r = admin.post(f"/api/admin/usuarios/{yo['id']}/estado", json={"accion": "desactivar"})
    assert r.status_code == 409 and r.json()["error"] == "ultimo_admin"


def test_m15_transicion_invalida(admin):
    yo = next(u for u in admin.get("/api/admin/usuarios").json() if u["rol"] == "administrador")
    assert admin.post(f"/api/admin/usuarios/{yo['id']}/estado", json={"accion": "aprobar"}).status_code == 409
    assert admin.post(f"/api/admin/usuarios/{yo['id']}/estado", json={"accion": "volar"}).status_code == 422


# ------------------------------------------- M-16 ingesta segura ---
def _subir(cliente, contenido: bytes, nombre="foto.png", tipo="image/png", categoria="capsule"):
    return cliente.post("/api/inspeccionar/propia", data={"categoria": categoria}, files={"archivo": (nombre, contenido, tipo)})


def test_m16_extension_falsa_y_archivo_no_imagen(usuario_b):
    r = _subir(usuario_b, b"#!/bin/sh\necho hola\n", nombre="script.png")
    assert r.status_code == 422 and r.json()["error"] == "tipo"
    r = _subir(usuario_b, b"GIF89a" + b"\x00" * 100, nombre="animacion.gif", tipo="image/gif")
    assert r.status_code == 422 and r.json()["error"] == "tipo"


def test_m16_imagen_sobredimensionada_en_pixeles(usuario_b):
    r = _subir(usuario_b, _png(6000, 6000))
    assert r.status_code == 422 and r.json()["error"] == "dimensiones"


def test_m16_archivo_demasiado_grande(usuario_b):
    grande = b"\x89PNG\r\n\x1a\n" + b"\x00" * (ingesta.MAX_BYTES + 10)
    r = _subir(usuario_b, grande)
    assert r.status_code == 413


def test_m16_png_truncado(usuario_b):
    r = _subir(usuario_b, _png()[:120])
    assert r.status_code == 422 and r.json()["error"] == "corrupta"


def test_m16_categoria_invalida_en_carga(usuario_b):
    assert _subir(usuario_b, _png(), categoria="../capsule").status_code == 422


# ------------------------------------------ M-17 retencion controlada ---
def test_m17_imagen_propia_recodificada_privada_y_borrable(usuario_a, usuario_b, raiz_temporal):
    r = _subir(usuario_a, _png(metadatos={"Comment": "gps 3.45,-76.53", "Author": "ana"}), nombre="mi foto (1).png")
    assert r.status_code == 200, r.text
    datos = r.json()
    assert datos["origen"] == "propia" and datos["imagen_id"].startswith("propia/")
    carpeta = raiz_temporal / "datos" / "inspecciones" / str(datos["id"])
    assert all((carpeta / f"{n}.png").is_file() for n in ("original", "mapa", "roi", "mascara"))
    with Image.open(carpeta / "original.png") as guardada:
        assert "Comment" not in guardada.info and "Author" not in guardada.info
    assert usuario_a.get(datos["imagenes"]["original"]).status_code == 200
    assert usuario_b.get(datos["imagenes"]["original"]).status_code == 404
    assert usuario_b.get(f"/api/historial/{datos['id']}/informe").status_code == 404
    assert usuario_a.delete(f"/api/historial/{datos['id']}").status_code == 200
    assert not carpeta.exists()
    assert usuario_a.get(f"/api/historial/{datos['id']}/informe").status_code == 404
    assert all(f["id"] != datos["id"] for f in usuario_a.get("/api/historial").json())


def test_m17_imagen_grande_se_reduce(usuario_a):
    r = _subir(usuario_a, _png(2400, 1600))
    assert r.status_code == 200
    assert max(r.json()["tam"]) == ingesta.LADO_MAXIMO


def test_borrado_por_lotes_solo_lo_propio(admin, raiz_temporal):
    usuario_a = crear_usuario(admin, "lotes-a@pruebas.local")
    usuario_b = crear_usuario(admin, "lotes-b@pruebas.local")
    ids_a = [_inspeccionar(usuario_a).json()["id"] for _ in range(3)]
    id_b = _inspeccionar(usuario_b).json()["id"]
    r = usuario_a.post("/api/historial/borrar", json={"ids": ids_a[:2] + [id_b, 999999]})
    assert r.status_code == 200 and sorted(r.json()["borradas"]) == sorted(ids_a[:2])
    restantes = {f["id"] for f in usuario_a.get("/api/historial").json()}
    assert ids_a[2] in restantes and not (set(ids_a[:2]) & restantes)
    assert usuario_b.get(f"/api/historial/{id_b}/informe").status_code == 200
    assert not (raiz_temporal / "datos" / "inspecciones" / str(ids_a[0])).exists()
    assert usuario_a.post("/api/historial/borrar", json={"ids": []}).status_code == 422


def test_metricas_del_experimento(servidor, usuario_a):
    assert servidor.get("/api/metricas").status_code == 401
    datos = usuario_a.get("/api/metricas").json()
    assert len(datos["categorias"]) == 10
    for c in datos["categorias"]:
        assert 0 <= c["imagen"]["roi"] <= 1 and 0 <= c["pixel_reproyectado"]["base"] <= 1
    assert datos["medias"]["imagen"]["base"] >= datos["medias"]["imagen"]["roi"]


def test_m14_respaldo_y_restauracion_de_la_bd(raiz_temporal, monkeypatch):
    respaldo = raiz_temporal / "respaldo" / "samcore.db"
    monkeypatch.setattr(db, "RUTA_RESPALDO", respaldo)
    assert db.respaldar() and respaldo.is_file()
    con = sqlite3.connect(respaldo)
    try:
        assert con.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0] >= 1
    finally:
        con.close()
    # restauracion: sin BD local y con respaldo -> se reconstruye desde el respaldo
    local = raiz_temporal / "restaurada" / "samcore.db"
    monkeypatch.setattr(db, "RUTA_BD", local)
    assert db.restaurar_desde_respaldo() and local.is_file()
    assert not db.restaurar_desde_respaldo()  # ya existe: no se sobrescribe


# ------------------------------------------------ M-14 persistencia ---
def test_m14_bd_en_modo_wal_y_datos_persisten(raiz_temporal):
    con = sqlite3.connect(raiz_temporal / "pruebas.db")
    try:
        assert con.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
        assert con.execute("SELECT COUNT(*) FROM inspecciones").fetchone()[0] > 0
    finally:
        con.close()


# ------------------------------------------------ estadisticas ---
def test_estadisticas_agregadas(usuario_a):
    datos = usuario_a.get("/api/estadisticas").json()
    assert datos["total"] >= 1 and "por_categoria" in datos and "propias" in datos
    assert json.dumps(datos)
    # histograma de puntuacion/umbral: 20 intervalos de 0,1 mas uno abierto; cuenta todas las inspecciones
    assert len(datos["histograma"]) == 21 and datos["histograma"][-1]["hasta"] is None
    assert sum(h["normales"] + h["anomalas"] for h in datos["histograma"]) == datos["total"]
    assert all(h["anomalas"] == 0 for h in datos["histograma"] if h["hasta"] is not None and h["hasta"] <= 1.0)
    assert all(h["normales"] == 0 for h in datos["histograma"] if h["desde"] >= 1.0)
    # desglose y tiempos por etapa por categoria
    fila = datos["por_categoria"][0]
    assert fila["normales"] + fila["anomalas"] == fila["inspecciones"]
    assert fila["seg_p95_ms"] is not None and fila["det_p50_ms"] is not None
    assert datos["seg_p95_ms"] >= datos["det_p95_ms"]
