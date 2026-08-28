"""API del MVP de SamCore (FastAPI).

Contrato alineado con arquitectura_sistema.md §3.5 mas el delta de
cuentas (D-11): login obligatorio, roles usuario/administrador, historial
por usuario y estadisticas de uso. Motor de inferencia simulado
(ver inferencia.py). Controles presentes en el MVP: listas cerradas
(M-03), errores sin detalles internos (M-02), limitacion de tasa
(M-01 / AM-11), rol verificado en el servidor (M-15), log con atribucion
(M-09), sesiones con hash en BD (AM-12).
"""
import logging
import re
import secrets
import sqlite3
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from . import db, galeria, inferencia, seguridad

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("samcore")


@asynccontextmanager
async def _ciclo_vida(app: FastAPI):
    db.iniciar()
    yield


app = FastAPI(title="SamCore API", version="0.1.0", docs_url=None, redoc_url=None, lifespan=_ciclo_vida)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UsuarioActual = Annotated[sqlite3.Row, Depends(seguridad.usuario_actual)]
_RE_CORREO = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


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


def _ip(request: Request) -> str:
    return request.client.host if request.client else "desconocida"


def _publico(usuario: sqlite3.Row) -> dict:
    return {"correo": usuario["correo"], "rol": usuario["rol"]}


@app.get("/api/salud")
def salud() -> dict:
    from . import artefactos

    con_artefactos = [c for c in galeria.CATEGORIAS if artefactos.disponibles(c)]
    return {
        "estado": "ok",
        "motor": "simulado",
        "categorias_con_artefactos": con_artefactos,
        "gpu": "no aplica (MVP)",
    }


@app.post("/api/auth/registro", status_code=201)
def registro(datos: DatosRegistro, request: Request) -> dict:
    if not seguridad.limitador_registro.permitir(_ip(request)):
        raise HTTPException(429, {"error": "limite", "mensaje": "Demasiadas solicitudes. Espera un momento."})
    correo = datos.correo.strip().lower()
    if not _RE_CORREO.match(correo):
        raise HTTPException(422, {"error": "correo_invalido", "mensaje": "Ingresa un correo válido."})
    if len(datos.contrasena) < 10:
        raise HTTPException(422, {"error": "contrasena_corta", "mensaje": "La contraseña debe tener al menos 10 caracteres."})
    if datos.contrasena != datos.confirmacion:
        raise HTTPException(422, {"error": "no_coinciden", "mensaje": "Las contraseñas no coinciden."})
    sal, hash_c = seguridad.hashear_contrasena(datos.contrasena)
    con = db.conectar()
    try:
        con.execute(
            "INSERT INTO usuarios (correo, hash_contrasena, sal) VALUES (?, ?, ?)",
            (correo, hash_c, sal),
        )
        con.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(409, {"error": "correo_en_uso", "mensaje": "Ese correo ya tiene una solicitud o cuenta."})
    finally:
        con.close()
    log.info("evento=registro correo=%s estado=pendiente", correo)
    return {"mensaje": "Solicitud registrada. Podrás entrar cuando el operador la apruebe."}


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
            log.info("evento=login_fallido correo=%s", correo)
            raise HTTPException(401, {"error": "credenciales", "mensaje": "Correo o contraseña incorrectos."})
        if usuario["estado"] == "pendiente":
            raise HTTPException(403, {"error": "pendiente", "mensaje": "Tu solicitud sigue pendiente de aprobación por el operador."})
        if usuario["estado"] != "activo":
            raise HTTPException(403, {"error": "sin_acceso", "mensaje": "Esta cuenta no tiene acceso a la plataforma. Contacta al operador del sistema."})
        token = seguridad.crear_sesion(con, usuario["id"])
    finally:
        con.close()
    response.set_cookie(
        seguridad.COOKIE_SESION,
        token,
        max_age=seguridad.DURACION_SESION_S,
        httponly=True,
        samesite="lax",
    )
    log.info("evento=login correo=%s rol=%s", correo, usuario["rol"])
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
    response.delete_cookie(seguridad.COOKIE_SESION)
    return {"mensaje": "Sesión cerrada."}


@app.get("/api/sesion")
def sesion(usuario: UsuarioActual) -> dict:
    return _publico(usuario)


@app.get("/api/categorias")
def categorias(usuario: UsuarioActual) -> list[dict]:
    return galeria.listar_categorias()


@app.get("/api/galeria/{categoria}")
def imagenes(categoria: str, usuario: UsuarioActual) -> dict:
    if categoria not in galeria.CATEGORIAS:
        raise HTTPException(422, {"error": "parametros", "mensaje": "Categoría no soportada."})
    return {
        "categoria": categoria,
        "umbral": galeria.CATEGORIAS[categoria]["umbral"],
        "imagenes": galeria.listar_imagenes(categoria),
    }


@app.post("/api/inspeccionar")
def inspeccionar(datos: DatosInspeccion, usuario: UsuarioActual) -> dict:
    if not galeria.es_imagen_valida(datos.categoria, datos.imagen_id):
        raise HTTPException(422, {"error": "parametros", "mensaje": "Categoría o imagen fuera de la galería."})
    if not seguridad.limitador_inspeccion.permitir(str(usuario["id"])):
        raise HTTPException(429, {"error": "limite", "mensaje": "La GPU está atendiendo otras inspecciones. Intenta de nuevo en unos segundos."})
    resultado = inferencia.inspeccionar(datos.categoria, datos.imagen_id)
    con = db.conectar()
    try:
        cur = con.execute(
            "INSERT INTO inspecciones (usuario_id, categoria, imagen_id, puntuacion, umbral, veredicto, estado_roi, duracion_ms) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                usuario["id"], resultado["categoria"], resultado["imagen_id"],
                resultado["puntuacion"], resultado["umbral"], resultado["veredicto"],
                resultado["estado_roi"], resultado["tiempos_ms"]["total"],
            ),
        )
        con.commit()
        resultado["id"] = cur.lastrowid
    finally:
        con.close()
    log.info(
        "evento=inspeccion usuario=%s categoria=%s imagen=%s veredicto=%s roi=%s",
        usuario["correo"], datos.categoria, datos.imagen_id,
        resultado["veredicto"], resultado["estado_roi"],
    )
    return resultado


@app.get("/api/historial")
def historial(usuario: UsuarioActual) -> list[dict]:
    con = db.conectar()
    try:
        filas = con.execute(
            "SELECT id, categoria, imagen_id, puntuacion, umbral, veredicto, estado_roi, duracion_ms, creada_en "
            "FROM inspecciones WHERE usuario_id = ? ORDER BY creada_en DESC, id DESC LIMIT 200",
            (usuario["id"],),
        ).fetchall()
    finally:
        con.close()
    return [dict(f) for f in filas]


def _p95(valores: list[int]) -> int:
    if not valores:
        return 0
    ordenados = sorted(valores)
    indice = min(len(ordenados) - 1, round(0.95 * (len(ordenados) - 1)))
    return ordenados[indice]


@app.get("/api/estadisticas")
def estadisticas(usuario: UsuarioActual) -> dict:
    con = db.conectar()
    try:
        filas = con.execute(
            "SELECT categoria, veredicto, estado_roi, duracion_ms FROM inspecciones"
        ).fetchall()
        usuarios_activos = con.execute(
            "SELECT COUNT(*) FROM usuarios WHERE estado = 'activo'"
        ).fetchone()[0]
    finally:
        con.close()
    total = len(filas)
    anomalas = sum(1 for f in filas if f["veredicto"] == "ANOMALO")
    degradadas = sum(1 for f in filas if f["estado_roi"] == "ROI_DEGRADADA")
    por_categoria = []
    for nombre in galeria.CATEGORIAS:
        propias = [f for f in filas if f["categoria"] == nombre]
        if not propias:
            continue
        por_categoria.append({
            "categoria": nombre,
            "inspecciones": len(propias),
            "pct_anomalas": round(100 * sum(1 for f in propias if f["veredicto"] == "ANOMALO") / len(propias), 1),
            "pct_roi_degradada": round(100 * sum(1 for f in propias if f["estado_roi"] == "ROI_DEGRADADA") / len(propias), 1),
            "p95_ms": _p95([f["duracion_ms"] for f in propias]),
        })
    por_categoria.sort(key=lambda c: -c["inspecciones"])
    return {
        "total": total,
        "anomalas": anomalas,
        "pct_anomalas": round(100 * anomalas / total, 1) if total else 0.0,
        "pct_roi_degradada": round(100 * degradadas / total, 1) if total else 0.0,
        "p95_ms": _p95([f["duracion_ms"] for f in filas]),
        "usuarios_activos": usuarios_activos,
        "por_categoria": por_categoria,
    }


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
        usuario["correo"], objetivo["correo"], datos.accion, hacia,
    )
    return {"id": usuario_id, "estado": hacia}
