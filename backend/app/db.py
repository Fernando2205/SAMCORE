"""Base de datos SQLite del MVP.

Elección provisional (D-15): SQLite basta para el MVP local; el despliegue
en el Space necesitará almacenamiento persistente o una BD externa
(pendiente de decidir, ver modelo_amenazas.md AM-15).
"""
import logging
import os
import secrets
import sqlite3
from pathlib import Path

log = logging.getLogger("samcore")

RUTA_BD = Path(os.environ.get("SAMCORE_BD", Path(__file__).resolve().parent.parent / "samcore.db"))
RUTA_CREDENCIAL_INICIAL = RUTA_BD.parent / ".admin_inicial.txt"

ESQUEMA = """
CREATE TABLE IF NOT EXISTS usuarios (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  correo TEXT NOT NULL UNIQUE,
  hash_contrasena TEXT NOT NULL,
  sal TEXT NOT NULL,
  rol TEXT NOT NULL DEFAULT 'usuario',
  estado TEXT NOT NULL DEFAULT 'pendiente',
  creado_en TEXT NOT NULL DEFAULT (datetime('now')),
  ultimo_acceso TEXT
);
CREATE TABLE IF NOT EXISTS sesiones (
  token_hash TEXT PRIMARY KEY,
  usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
  creada_en TEXT NOT NULL DEFAULT (datetime('now')),
  expira_en TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS inspecciones (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
  categoria TEXT NOT NULL,
  imagen_id TEXT NOT NULL,
  puntuacion REAL NOT NULL,
  umbral REAL NOT NULL,
  veredicto TEXT NOT NULL,
  estado_roi TEXT NOT NULL,
  duracion_ms INTEGER NOT NULL,
  creada_en TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_inspecciones_usuario ON inspecciones(usuario_id, creada_en);
"""


def conectar() -> sqlite3.Connection:
    con = sqlite3.connect(RUTA_BD)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def iniciar() -> None:
    from . import seguridad

    con = conectar()
    try:
        con.executescript(ESQUEMA)
        hay_admin = con.execute(
            "SELECT 1 FROM usuarios WHERE rol = 'administrador' LIMIT 1"
        ).fetchone()
        if not hay_admin:
            correo = os.environ.get("SAMCORE_ADMIN_CORREO", "admin@samcore.local")
            contrasena = os.environ.get("SAMCORE_ADMIN_CONTRASENA") or secrets.token_urlsafe(9)
            sal, hash_c = seguridad.hashear_contrasena(contrasena)
            con.execute(
                "INSERT INTO usuarios (correo, hash_contrasena, sal, rol, estado) "
                "VALUES (?, ?, ?, 'administrador', 'activo')",
                (correo, hash_c, sal),
            )
            con.commit()
            RUTA_CREDENCIAL_INICIAL.write_text(
                "Cuenta de administrador inicial de SamCore (solo desarrollo).\n"
                f"Correo: {correo}\nContrasena: {contrasena}\n"
                "Borra este archivo despues del primer inicio de sesion.\n",
                encoding="utf-8",
            )
            log.info("evento=bootstrap_admin correo=%s credencial=%s", correo, RUTA_CREDENCIAL_INICIAL)
        con.commit()
    finally:
        con.close()
