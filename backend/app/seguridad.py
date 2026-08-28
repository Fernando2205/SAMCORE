"""Contrasenas, sesiones y limitacion de tasa.

- Contrasenas: PBKDF2-HMAC-SHA256 (stdlib) con sal por usuario. El
  mecanismo definitivo (argon2/bcrypt) se decide al fijar el stack de
  despliegue; la interfaz de estas funciones no cambia.
- Sesiones: token aleatorio en cookie HttpOnly; en BD solo se guarda su
  SHA-256 (robar la BD no da sesiones, AM-12).
- Limitacion de tasa: ventanas deslizantes en memoria (AM-11 login,
  M-01 inspecciones). Suficiente para un solo proceso.
"""
import hashlib
import secrets
import sqlite3
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

COOKIE_SESION = "samcore_sesion"
DURACION_SESION_S = 12 * 3600
ITERACIONES_PBKDF2 = 210_000


def hashear_contrasena(contrasena: str, sal_hex: str | None = None) -> tuple[str, str]:
    sal = bytes.fromhex(sal_hex) if sal_hex else secrets.token_bytes(16)
    h = hashlib.pbkdf2_hmac("sha256", contrasena.encode("utf-8"), sal, ITERACIONES_PBKDF2)
    return sal.hex(), h.hex()


def verificar_contrasena(contrasena: str, sal_hex: str, hash_hex: str) -> bool:
    _, calculado = hashear_contrasena(contrasena, sal_hex)
    return secrets.compare_digest(calculado, hash_hex)


def crear_sesion(con: sqlite3.Connection, usuario_id: int) -> str:
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode("ascii")).hexdigest()
    con.execute(
        "INSERT INTO sesiones (token_hash, usuario_id, expira_en) "
        "VALUES (?, ?, datetime('now', ?))",
        (token_hash, usuario_id, f"+{DURACION_SESION_S} seconds"),
    )
    con.execute(
        "UPDATE usuarios SET ultimo_acceso = datetime('now') WHERE id = ?", (usuario_id,)
    )
    con.commit()
    return token


def borrar_sesion(con: sqlite3.Connection, token: str) -> None:
    token_hash = hashlib.sha256(token.encode("ascii")).hexdigest()
    con.execute("DELETE FROM sesiones WHERE token_hash = ?", (token_hash,))
    con.commit()


def usuario_por_token(con: sqlite3.Connection, token: str) -> sqlite3.Row | None:
    token_hash = hashlib.sha256(token.encode("ascii")).hexdigest()
    return con.execute(
        "SELECT u.* FROM sesiones s JOIN usuarios u ON u.id = s.usuario_id "
        "WHERE s.token_hash = ? AND s.expira_en > datetime('now') AND u.estado = 'activo'",
        (token_hash,),
    ).fetchone()


def usuario_actual(request: Request) -> sqlite3.Row:
    """Dependencia FastAPI: exige sesion valida (login obligatorio, D-11)."""
    from . import db

    token = request.cookies.get(COOKIE_SESION)
    if not token:
        raise HTTPException(401, {"error": "sin_sesion", "mensaje": "Inicia sesión para continuar."})
    con = db.conectar()
    try:
        usuario = usuario_por_token(con, token)
    finally:
        con.close()
    if usuario is None:
        raise HTTPException(401, {"error": "sesion_expirada", "mensaje": "Tu sesión expiró. Vuelve a iniciar sesión."})
    return usuario


def requiere_admin(usuario: sqlite3.Row) -> None:
    """El rol se verifica en el servidor en cada accion (M-15)."""
    if usuario["rol"] != "administrador":
        raise HTTPException(403, {"error": "sin_permiso", "mensaje": "No tienes permiso para ver esta sección."})


class Limitador:
    """Ventana deslizante en memoria por clave."""

    def __init__(self, maximo: int, ventana_s: float) -> None:
        self.maximo = maximo
        self.ventana_s = ventana_s
        self._eventos: dict[str, deque[float]] = defaultdict(deque)

    def permitir(self, clave: str) -> bool:
        ahora = time.monotonic()
        cola = self._eventos[clave]
        while cola and ahora - cola[0] > self.ventana_s:
            cola.popleft()
        if len(cola) >= self.maximo:
            return False
        cola.append(ahora)
        return True


limitador_login = Limitador(maximo=5, ventana_s=60)
limitador_inspeccion = Limitador(maximo=6, ventana_s=60)
limitador_registro = Limitador(maximo=3, ventana_s=300)
