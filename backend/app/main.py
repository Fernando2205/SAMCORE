"""API de SamCore (FastAPI).

Contrato de arquitectura_sistema.md §3.5 con cuentas (D-11), carga de imagen
propia (D-17) y retencion controlada del informe (D-20). Controles:
listas cerradas (M-03), errores sin detalles internos (M-02), limitacion de
tasa y cola acotada a la GPU (M-01), topes por etapa (M-05), artefactos sin
pickle y verificados por manifiesto (M-06/M-07), log con atribucion (M-09),
autenticacion y sesiones (M-10/M-11), historial filtrado por sesion (M-12),
rol verificado en servidor (M-15), ingesta segura (M-16) y retencion
controlada (M-17).
"""
import json
import logging
import os
import re
import secrets
import sqlite3
from contextlib import asynccontextmanager
from io import BytesIO
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image
from pydantic import BaseModel

from . import almacen, artefactos, db, galeria, inferencia, ingesta, seguridad

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("samcore")

MODO_MOTOR = os.environ.get("SAMCORE_MOTOR", "auto")  # auto | real | simulado
COOKIE_SEGURA = os.environ.get("SAMCORE_HTTPS", "0") == "1"
RUTA_FRONTEND = Path(os.environ.get("SAMCORE_FRONTEND", Path(__file__).resolve().parents[2] / "frontend" / "dist"))


@asynccontextmanager
async def _ciclo_vida(app: FastAPI):
    db.iniciar()
    db.iniciar_respaldo_periodico()
    galeria.escanear()
    if MODO_MOTOR != "simulado" and artefactos.categorias_con_artefactos():
        from .motor import orquestador

        orquestador.instancia().preparar_en_segundo_plano()
    yield
    db.respaldar()


app = FastAPI(title="SamCore API", version="1.0.0", docs_url=None, redoc_url=None, lifespan=_ciclo_vida)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def _cabeceras_seguridad(request: Request, call_next):
    respuesta = await call_next(request)
    respuesta.headers["X-Content-Type-Options"] = "nosniff"
    # Contra el secuestro de clics: solo el propio origen y huggingface.co
    # (la pestaña App del Space muestra la aplicación en un marco embebido)
    # pueden enmarcar la aplicación; cualquier otro sitio queda bloqueado.
    respuesta.headers["Content-Security-Policy"] = "frame-ancestors 'self' https://huggingface.co"
    respuesta.headers["Referrer-Policy"] = "same-origin"
    if request.url.path.startswith("/api") and "image/" not in respuesta.headers.get("content-type", ""):
        respuesta.headers["Cache-Control"] = "no-store"
    return respuesta


UsuarioActual = Annotated[sqlite3.Row, Depends(seguridad.usuario_actual)]
_RE_CORREO = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_RE_NOMBRE_ARCHIVO = re.compile(r"[^A-Za-z0-9._-]+")


@app.exception_handler(HTTPException)
async def _error_http(request: Request, exc: HTTPException) -> JSONResponse:
    cuerpo = exc.detail if isinstance(exc.detail, dict) else {"error": "http", "mensaje": str(exc.detail)}
    return JSONResponse(status_code=exc.status_code, content=cuerpo)


@app.exception_handler(Exception)
async def _error_inesperado(request: Request, exc: Exception) -> JSONResponse:
    ref = secrets.token_hex(2).upper()
    log.error("evento=error_inesperado ref=%s ruta=%s tipo=%s", ref, request.url.path, type(exc).__name__)
    return JSONResponse(
        status_code=500,
        content={"error": "inesperado", "mensaje": "No fue posible completar la operación.", "ref": f"ERR-{ref}"},
    )


class DatosRegistro(BaseModel):
    correo: str
    contrasena: str
    confirmacion: str


class DatosLogin(BaseModel):
    correo: str
    contrasena: str


class DatosInspeccion(BaseModel):
    categoria: str
    imagen_id: str


class DatosEstadoUsuario(BaseModel):
    accion: str


class DatosBorrado(BaseModel):
    ids: list[int]


def _ip(request: Request) -> str:
    return request.client.host if request.client else "desconocida"


def _publico(usuario: sqlite3.Row) -> dict:
    return {"correo": usuario["correo"], "rol": usuario["rol"]}


# ---------------------------------------------------------------- salud ---
@app.get("/api/salud")
def salud() -> dict:
    con_artefactos = artefactos.categorias_con_artefactos()
    motor, gpu = "simulado", "no aplica"
    if MODO_MOTOR != "simulado" and con_artefactos:
        from .motor import orquestador

        instancia = orquestador.instancia()
        motor = "real" if instancia.listo else instancia.estado
        gpu = instancia.descripcion_gpu()
    return {
        "estado": "ok",
        "motor": motor,
        "categorias_con_artefactos": con_artefactos,
        "gpu": gpu,
        "carga_propia": True,
    }


# --------------------------------------------------------------- cuentas ---
@app.post("/api/auth/registro", status_code=201)
def registro(datos: DatosRegistro, request: Request) -> dict:
    if not seguridad.limitador_registro.permitir(_ip(request)):
        raise HTTPException(429, {"error": "limite", "mensaje": "Demasiadas solicitudes. Espera un momento."})
    correo = datos.correo.strip().lower()
    if not _RE_CORREO.match(correo) or len(correo) > 254:
        raise HTTPException(422, {"error": "correo_invalido", "mensaje": "Ingresa un correo válido."})
    if len(datos.contrasena) < 10 or len(datos.contrasena) > 200:
        raise HTTPException(422, {"error": "contrasena_corta", "mensaje": "La contraseña debe tener al menos 10 caracteres."})
    if datos.contrasena != datos.confirmacion:
        raise HTTPException(422, {"error": "no_coinciden", "mensaje": "Las contraseñas no coinciden."})
    sal, hash_c = seguridad.hashear_contrasena(datos.contrasena)
    con = db.conectar()
    try:
        con.execute("INSERT INTO usuarios (correo, hash_contrasena, sal) VALUES (?, ?, ?)", (correo, hash_c, sal))
        con.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(409, {"error": "correo_en_uso", "mensaje": "Ese correo ya tiene una solicitud o cuenta."})
    finally:
        con.close()
    log.info("evento=registro usuario=%s estado=pendiente", _anonimo(correo))
    return {"mensaje": "Solicitud registrada. Podrás entrar cuando el operador la apruebe."}


def _anonimo(correo: str) -> str:
    """Identificador estable sin exponer el correo en el log (M-09)."""
    import hashlib

    return hashlib.sha256(correo.encode("utf-8")).hexdigest()[:10]


@app.post("/api/auth/login")
def login(datos: DatosLogin, request: Request, response: Response) -> dict:
    correo = datos.correo.strip().lower()
    if not seguridad.limitador_login.permitir(f"{correo}|{_ip(request)}"):
        raise HTTPException(429, {"error": "limite", "mensaje": "Se superó el límite de intentos. Espera un minuto e intenta de nuevo."})
    con = db.conectar()
    try:
        usuario = con.execute("SELECT * FROM usuarios WHERE correo = ?", (correo,)).fetchone()
        credenciales_ok = usuario is not None and seguridad.verificar_contrasena(
            datos.contrasena, usuario["sal"], usuario["hash_contrasena"]
        )
        if not credenciales_ok:
            log.info("evento=login_fallido usuario=%s", _anonimo(correo))
            raise HTTPException(401, {"error": "credenciales", "mensaje": "Correo o contraseña incorrectos."})
        if usuario["estado"] == "pendiente":
            raise HTTPException(403, {"error": "pendiente", "mensaje": "Tu solicitud sigue pendiente de aprobación por el operador."})
        if usuario["estado"] != "activo":
            raise HTTPException(403, {"error": "sin_acceso", "mensaje": "Esta cuenta no tiene acceso a la plataforma. Contacta al operador del sistema."})
        token = seguridad.crear_sesion(con, usuario["id"])
    finally:
        con.close()
    response.set_cookie(
        seguridad.COOKIE_SESION, token, max_age=seguridad.DURACION_SESION_S,
        httponly=True, samesite="lax", secure=COOKIE_SEGURA, path="/",
    )
    log.info("evento=login usuario=%s rol=%s", _anonimo(correo), usuario["rol"])
    return _publico(usuario)


@app.post("/api/auth/logout")
def logout(request: Request, response: Response) -> dict:
    token = request.cookies.get(seguridad.COOKIE_SESION)
    if token:
        con = db.conectar()
        try:
            seguridad.borrar_sesion(con, token)
        finally:
            con.close()
    response.delete_cookie(seguridad.COOKIE_SESION, path="/")
    return {"mensaje": "Sesión cerrada."}


@app.get("/api/sesion")
def sesion(usuario: UsuarioActual) -> dict:
    return _publico(usuario)


# --------------------------------------------------------------- galeria ---
@app.get("/api/categorias")
def categorias(usuario: UsuarioActual) -> list[dict]:
    return galeria.listar_categorias()


def _validar_categoria(categoria: str) -> None:
    if not galeria.es_categoria_valida(categoria):
        raise HTTPException(422, {"error": "parametros", "mensaje": "Categoría no soportada."})


@app.get("/api/galeria/{categoria}")
def imagenes(categoria: str, usuario: UsuarioActual) -> dict:
    _validar_categoria(categoria)
    return {"categoria": categoria, "umbral": galeria.umbral_de(categoria), "imagenes": galeria.listar_imagenes(categoria)}


@app.get("/api/galeria/{categoria}/imagen/{imagen_id:path}")
def imagen_galeria(categoria: str, imagen_id: str, usuario: UsuarioActual) -> FileResponse:
    ruta = galeria.ruta_imagen(categoria, imagen_id) if galeria.es_categoria_valida(categoria) else None
    if ruta is None:
        raise HTTPException(422, {"error": "parametros", "mensaje": "Categoría o imagen fuera de la galería."})
    return FileResponse(ruta, media_type="image/png", headers={"Cache-Control": "private, max-age=86400"})


# ------------------------------------------------------------- inferencia ---
def _ejecutar_motor(imagen: Image.Image, categoria: str, clave: str) -> dict:
    if MODO_MOTOR != "simulado":
        from .motor import orquestador

        motor = orquestador.instancia()
        if motor.soporta(categoria):
            try:
                return motor.inspeccionar(imagen, categoria)
            except orquestador.ColaLlena:
                raise HTTPException(503, {"error": "ocupado", "mensaje": "La GPU está atendiendo otras inspecciones. Intenta de nuevo en unos segundos."})
            except orquestador.TiempoAgotado:
                raise HTTPException(503, {"error": "tiempo", "mensaje": "La inspección tardó más de lo permitido y se canceló. Intenta con otra imagen."})
        if artefactos.disponibles(categoria) and motor.estado in ("sin_iniciar", "cargando"):
            raise HTTPException(503, {"error": "motor_cargando", "mensaje": "El motor de inferencia está arrancando. Intenta de nuevo en un minuto."})
        if MODO_MOTOR == "real":
            raise HTTPException(503, {"error": "motor", "mensaje": "El motor de inferencia no está disponible para esta categoría."})
    return inferencia.inspeccionar(imagen, categoria, clave)


def _exigir_banco(categoria: str) -> None:
    if MODO_MOTOR != "simulado" and not artefactos.disponibles(categoria):
        raise HTTPException(422, {"error": "sin_banco", "mensaje": "Esta categoría no tiene banco de memoria preparado."})


def _limitar_inspeccion(usuario: sqlite3.Row) -> None:
    if not seguridad.limitador_inspeccion.permitir(str(usuario["id"])):
        raise HTTPException(429, {"error": "limite", "mensaje": "Has alcanzado el límite de inspecciones por minuto. Espera un momento."})


def _registrar(usuario: sqlite3.Row, resultado: dict, imagen_id: str, origen: str, original: Image.Image | None) -> dict:
    con = db.conectar()
    try:
        tiempos = resultado["tiempos_ms"]
        cur = con.execute(
            "INSERT INTO inspecciones (usuario_id, categoria, imagen_id, puntuacion, umbral, veredicto, estado_roi, duracion_ms, "
            "origen, motor, segmentacion_ms, deteccion_ms) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                usuario["id"], resultado["categoria"], imagen_id, resultado["puntuacion"], resultado["umbral"],
                resultado["veredicto"], resultado["estado_roi"], tiempos["total"], origen, resultado["motor"],
                tiempos.get("segmentacion"), tiempos.get("deteccion"),
            ),
        )
        con.commit()
        inspeccion_id = int(cur.lastrowid)
    finally:
        con.close()
    resultado = dict(resultado)
    resultado.update({"id": inspeccion_id, "imagen_id": imagen_id, "origen": origen})
    almacen.guardar(inspeccion_id, resultado, original)
    log.info(
        "evento=inspeccion usuario=%s id=%s categoria=%s origen=%s veredicto=%s roi=%s motor=%s total_ms=%s",
        _anonimo(usuario["correo"]), inspeccion_id, resultado["categoria"], origen,
        resultado["veredicto"], resultado["estado_roi"], resultado["motor"], resultado["tiempos_ms"]["total"],
    )
    return _respuesta(resultado)


def _respuesta(informe: dict) -> dict:
    """Informe publico con las URL de sus imagenes."""
    publico = {k: v for k, v in informe.items() if not k.startswith("_")}
    inspeccion_id, categoria = publico["id"], publico["categoria"]
    if publico.get("origen") == "propia":
        original = f"/api/historial/{inspeccion_id}/imagen/original"
    else:
        original = f"/api/galeria/{categoria}/imagen/{publico['imagen_id']}"
    publico["imagenes"] = {
        "original": original,
        "roi": f"/api/historial/{inspeccion_id}/imagen/roi",
        "mapa": f"/api/historial/{inspeccion_id}/imagen/mapa",
        "mascara": f"/api/historial/{inspeccion_id}/imagen/mascara",
    }
    return publico


@app.post("/api/inspeccionar")
def inspeccionar(datos: DatosInspeccion, usuario: UsuarioActual) -> dict:
    ruta = galeria.ruta_imagen(datos.categoria, datos.imagen_id) if galeria.es_categoria_valida(datos.categoria) else None
    if ruta is None:
        raise HTTPException(422, {"error": "parametros", "mensaje": "Categoría o imagen fuera de la galería."})
    _exigir_banco(datos.categoria)
    _limitar_inspeccion(usuario)
    with Image.open(ruta) as imagen:
        imagen = imagen.convert("RGB")
    resultado = _ejecutar_motor(imagen, datos.categoria, datos.imagen_id)
    return _registrar(usuario, resultado, datos.imagen_id, "galeria", None)


@app.post("/api/inspeccionar/propia")
async def inspeccionar_propia(
    request: Request,
    usuario: UsuarioActual,
    categoria: Annotated[str, Form()],
    archivo: Annotated[UploadFile, File()],
) -> dict:
    _validar_categoria(categoria)
    _exigir_banco(categoria)
    declarado = request.headers.get("content-length")
    if declarado and declarado.isdigit() and int(declarado) > ingesta.MAX_BYTES + 4096:
        raise HTTPException(413, {"error": "tamano", "mensaje": "La imagen supera el tamaño máximo de 8 MB."})
    _limitar_inspeccion(usuario)
    datos = bytearray()
    while True:
        trozo = await archivo.read(1 << 20)
        if not trozo:
            break
        datos.extend(trozo)
        if len(datos) > ingesta.MAX_BYTES:
            raise HTTPException(413, {"error": "tamano", "mensaje": "La imagen supera el tamaño máximo de 8 MB."})
    try:
        imagen = await run_in_threadpool(ingesta.ingerir, bytes(datos))
    except ingesta.ImagenRechazada as exc:
        raise HTTPException(422, {"error": exc.codigo, "mensaje": exc.mensaje})
    nombre = _RE_NOMBRE_ARCHIVO.sub("_", (archivo.filename or "imagen"))[:60] or "imagen"
    clave = f"propia/{nombre}"
    resultado = await run_in_threadpool(_ejecutar_motor, imagen, categoria, clave)
    return await run_in_threadpool(_registrar, usuario, resultado, clave, "propia", imagen)


# -------------------------------------------------------------- historial ---
def _fila_propia(con: sqlite3.Connection, inspeccion_id: int, usuario: sqlite3.Row) -> sqlite3.Row:
    fila = con.execute(
        "SELECT * FROM inspecciones WHERE id = ? AND usuario_id = ?", (inspeccion_id, usuario["id"])
    ).fetchone()
    if fila is None:
        raise HTTPException(404, {"error": "no_encontrada", "mensaje": "Esa inspección no existe en tu historial."})
    return fila


@app.get("/api/historial")
def historial(usuario: UsuarioActual) -> list[dict]:
    con = db.conectar()
    try:
        filas = con.execute(
            "SELECT id, categoria, imagen_id, puntuacion, umbral, veredicto, estado_roi, duracion_ms, creada_en, origen, motor "
            "FROM inspecciones WHERE usuario_id = ? ORDER BY creada_en DESC, id DESC LIMIT 200",
            (usuario["id"],),
        ).fetchall()
    finally:
        con.close()
    return [dict(f) for f in filas]


@app.get("/api/historial/{inspeccion_id}/informe")
def informe(inspeccion_id: int, usuario: UsuarioActual) -> dict:
    con = db.conectar()
    try:
        fila = _fila_propia(con, inspeccion_id, usuario)
    finally:
        con.close()
    datos = almacen.cargar_informe(inspeccion_id)
    if datos is None:
        raise HTTPException(404, {"error": "sin_informe", "mensaje": "El informe de esa inspección ya no está disponible."})
    datos.update({"id": fila["id"], "imagen_id": fila["imagen_id"], "origen": fila["origen"], "creada_en": fila["creada_en"]})
    return _respuesta(datos)


@app.get("/api/historial/{inspeccion_id}/imagen/{clase}")
def imagen_informe(inspeccion_id: int, clase: str, usuario: UsuarioActual) -> FileResponse:
    if clase not in almacen.CLASES:
        raise HTTPException(422, {"error": "parametros", "mensaje": "Imagen no reconocida."})
    con = db.conectar()
    try:
        _fila_propia(con, inspeccion_id, usuario)
    finally:
        con.close()
    ruta = almacen.ruta_derivado(inspeccion_id, clase)
    if ruta is None:
        raise HTTPException(404, {"error": "sin_imagen", "mensaje": "Esa imagen ya no está disponible."})
    return FileResponse(ruta, media_type="image/png", headers={"Cache-Control": "private, max-age=3600"})


@app.post("/api/historial/borrar")
def borrar_inspecciones(datos: DatosBorrado, usuario: UsuarioActual) -> dict:
    """Borrado por lotes: solo las inspecciones de la sesion; los demas
    identificadores se ignoran sin revelar si existen (M-12)."""
    ids = sorted({int(i) for i in datos.ids})[:200]
    if not ids:
        raise HTTPException(422, {"error": "parametros", "mensaje": "No hay inspecciones seleccionadas."})
    marcadores = ",".join("?" * len(ids))
    con = db.conectar()
    try:
        propias = [
            f["id"] for f in con.execute(
                f"SELECT id FROM inspecciones WHERE usuario_id = ? AND id IN ({marcadores})", (usuario["id"], *ids)
            ).fetchall()
        ]
        if propias:
            con.execute(
                f"DELETE FROM inspecciones WHERE usuario_id = ? AND id IN ({','.join('?' * len(propias))})",
                (usuario["id"], *propias),
            )
            con.commit()
    finally:
        con.close()
    for inspeccion_id in propias:
        almacen.borrar(inspeccion_id)
    log.info("evento=inspecciones_borradas usuario=%s cantidad=%s", _anonimo(usuario["correo"]), len(propias))
    return {"borradas": propias}


@app.delete("/api/historial/{inspeccion_id}")
def borrar_inspeccion(inspeccion_id: int, usuario: UsuarioActual) -> dict:
    con = db.conectar()
    try:
        _fila_propia(con, inspeccion_id, usuario)
        con.execute("DELETE FROM inspecciones WHERE id = ? AND usuario_id = ?", (inspeccion_id, usuario["id"]))
        con.commit()
    finally:
        con.close()
    almacen.borrar(inspeccion_id)
    log.info("evento=inspeccion_borrada usuario=%s id=%s", _anonimo(usuario["correo"]), inspeccion_id)
    return {"id": inspeccion_id, "borrada": True}


# ------------------------------------------------------------ estadisticas ---
def _percentil(valores: list[int], p: float) -> int | None:
    limpios = sorted(v for v in valores if v is not None)
    if not limpios:
        return None
    return int(limpios[min(len(limpios) - 1, round(p * (len(limpios) - 1)))])


def _p95(valores: list[int]) -> int:
    return _percentil(valores, 0.95) or 0


_HISTOGRAMA_ANCHO = 0.1
_HISTOGRAMA_TOPE = 2.0


def _histograma(filas) -> list[dict]:
    """Razon puntuacion/umbral en intervalos de 0,1 hasta 2,0 y un ultimo
    intervalo abierto; cada intervalo cuenta normales y anomalas."""
    n = int(round(_HISTOGRAMA_TOPE / _HISTOGRAMA_ANCHO))
    intervalos = [{"desde": round(i * _HISTOGRAMA_ANCHO, 2), "hasta": round((i + 1) * _HISTOGRAMA_ANCHO, 2),
                   "normales": 0, "anomalas": 0} for i in range(n)]
    intervalos.append({"desde": _HISTOGRAMA_TOPE, "hasta": None, "normales": 0, "anomalas": 0})
    for f in filas:
        if not f["umbral"]:
            continue
        razon = f["puntuacion"] / f["umbral"]
        indice = min(n, max(0, int(razon / _HISTOGRAMA_ANCHO)))
        intervalos[indice]["anomalas" if f["veredicto"] == "ANOMALO" else "normales"] += 1
    return intervalos


@app.get("/api/estadisticas")
def estadisticas(usuario: UsuarioActual) -> dict:
    con = db.conectar()
    try:
        filas = con.execute(
            "SELECT categoria, veredicto, estado_roi, duracion_ms, origen, puntuacion, umbral, segmentacion_ms, deteccion_ms "
            "FROM inspecciones"
        ).fetchall()
        usuarios_activos = con.execute("SELECT COUNT(*) FROM usuarios WHERE estado = 'activo'").fetchone()[0]
    finally:
        con.close()
    total = len(filas)
    anomalas = sum(1 for f in filas if f["veredicto"] == "ANOMALO")
    degradadas = sum(1 for f in filas if f["estado_roi"] == "ROI_DEGRADADA")
    por_categoria = []
    for nombre in galeria.CATEGORIAS_MVTEC:
        propias = [f for f in filas if f["categoria"] == nombre]
        if not propias:
            continue
        n_anomalas = sum(1 for f in propias if f["veredicto"] == "ANOMALO")
        n_degradadas = sum(1 for f in propias if f["estado_roi"] == "ROI_DEGRADADA")
        por_categoria.append({
            "categoria": nombre,
            "inspecciones": len(propias),
            "normales": len(propias) - n_anomalas,
            "anomalas": n_anomalas,
            "degradadas": n_degradadas,
            "pct_anomalas": round(100 * n_anomalas / len(propias), 1),
            "pct_roi_degradada": round(100 * n_degradadas / len(propias), 1),
            "p95_ms": _p95([f["duracion_ms"] for f in propias]),
            "seg_p50_ms": _percentil([f["segmentacion_ms"] for f in propias], 0.5),
            "seg_p95_ms": _percentil([f["segmentacion_ms"] for f in propias], 0.95),
            "det_p50_ms": _percentil([f["deteccion_ms"] for f in propias], 0.5),
            "det_p95_ms": _percentil([f["deteccion_ms"] for f in propias], 0.95),
        })
    por_categoria.sort(key=lambda c: -c["inspecciones"])
    return {
        "total": total,
        "anomalas": anomalas,
        "propias": sum(1 for f in filas if f["origen"] == "propia"),
        "pct_anomalas": round(100 * anomalas / total, 1) if total else 0.0,
        "pct_roi_degradada": round(100 * degradadas / total, 1) if total else 0.0,
        "p95_ms": _p95([f["duracion_ms"] for f in filas]),
        "seg_p95_ms": _percentil([f["segmentacion_ms"] for f in filas], 0.95),
        "det_p95_ms": _percentil([f["deteccion_ms"] for f in filas], 0.95),
        "usuarios_activos": usuarios_activos,
        "histograma": _histograma(filas),
        "por_categoria": por_categoria,
    }


_RUTA_METRICAS = Path(__file__).resolve().parent / "metricas_experimento.json"


@app.get("/api/metricas")
def metricas(usuario: UsuarioActual) -> dict:
    """Metricas de evaluacion del experimento (AUROC por categoria), salida
    del modo por lotes; se consolidan fuera de linea desde los resultados."""
    if not _RUTA_METRICAS.is_file():
        raise HTTPException(404, {"error": "sin_metricas", "mensaje": "Las métricas del experimento no están disponibles."})
    return json.loads(_RUTA_METRICAS.read_text(encoding="utf-8"))


# --------------------------------------------------------- administracion ---
@app.get("/api/admin/usuarios")
def admin_usuarios(usuario: UsuarioActual) -> list[dict]:
    seguridad.requiere_admin(usuario)
    con = db.conectar()
    try:
        filas = con.execute(
            "SELECT u.id, u.correo, u.rol, u.estado, u.creado_en, u.ultimo_acceso, "
            "       (SELECT COUNT(*) FROM inspecciones i WHERE i.usuario_id = u.id) AS inspecciones "
            "FROM usuarios u ORDER BY CASE u.estado WHEN 'pendiente' THEN 0 ELSE 1 END, u.creado_en"
        ).fetchall()
    finally:
        con.close()
    return [dict(f) for f in filas]


_TRANSICIONES = {
    "aprobar": ("pendiente", "activo"),
    "rechazar": ("pendiente", "rechazado"),
    "desactivar": ("activo", "desactivado"),
    "reactivar": ("desactivado", "activo"),
}


@app.post("/api/admin/usuarios/{usuario_id}/estado")
def admin_cambiar_estado(usuario_id: int, datos: DatosEstadoUsuario, usuario: UsuarioActual) -> dict:
    seguridad.requiere_admin(usuario)
    if datos.accion not in _TRANSICIONES:
        raise HTTPException(422, {"error": "parametros", "mensaje": "Acción no soportada."})
    desde, hacia = _TRANSICIONES[datos.accion]
    con = db.conectar()
    try:
        objetivo = con.execute("SELECT * FROM usuarios WHERE id = ?", (usuario_id,)).fetchone()
        if objetivo is None or objetivo["estado"] != desde:
            raise HTTPException(409, {"error": "estado", "mensaje": "La cuenta ya no está en ese estado; recarga la tabla."})
        if datos.accion == "desactivar" and objetivo["rol"] == "administrador":
            admins_activos = con.execute(
                "SELECT COUNT(*) FROM usuarios WHERE rol = 'administrador' AND estado = 'activo'"
            ).fetchone()[0]
            if admins_activos <= 1:
                raise HTTPException(409, {"error": "ultimo_admin", "mensaje": "No es posible desactivar la última cuenta de administrador."})
        con.execute("UPDATE usuarios SET estado = ? WHERE id = ?", (hacia, usuario_id))
        if hacia != "activo":
            con.execute("DELETE FROM sesiones WHERE usuario_id = ?", (usuario_id,))
        con.commit()
    finally:
        con.close()
    log.info(
        "evento=admin_estado admin=%s objetivo=%s accion=%s nuevo_estado=%s",
        _anonimo(usuario["correo"]), _anonimo(objetivo["correo"]), datos.accion, hacia,
    )
    return {"id": usuario_id, "estado": hacia}


# ---------------------------------------------------------------- frontend ---
if RUTA_FRONTEND.is_dir():
    app.mount("/assets", StaticFiles(directory=RUTA_FRONTEND / "assets"), name="assets")

    @app.get("/{ruta:path}", include_in_schema=False)
    def _spa(ruta: str) -> FileResponse:
        if ruta.startswith("api/"):
            raise HTTPException(404, {"error": "no_encontrado", "mensaje": "Recurso no encontrado."})
        candidato = (RUTA_FRONTEND / ruta).resolve()
        if ruta and candidato.is_file() and RUTA_FRONTEND.resolve() in candidato.parents:
            return FileResponse(candidato)
        return FileResponse(RUTA_FRONTEND / "index.html")
