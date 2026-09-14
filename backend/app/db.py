"""Base de datos SQLite de la aplicacion (ADR-09): modo WAL sobre el
almacenamiento persistente, escrituras transaccionales, claves foraneas.
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
  creada_en TEXT NOT NULL DEFAULT (datetime('now')),
  origen TEXT NOT NULL DEFAULT 'galeria',
  motor TEXT NOT NULL DEFAULT 'simulado',
  segmentacion_ms INTEGER,
  deteccion_ms INTEGER
);
CREATE INDEX IF NOT EXISTS idx_inspecciones_usuario ON inspecciones(usuario_id, creada_en);
"""

# Columnas agregadas despues de la primera version del esquema
_COLUMNAS_NUEVAS = {
    "inspecciones": {
        "origen": "TEXT NOT NULL DEFAULT 'galeria'",
        "motor": "TEXT NOT NULL DEFAULT 'simulado'",
        "segmentacion_ms": "INTEGER",
        "deteccion_ms": "INTEGER",
    },
}


def conectar() -> sqlite3.Connection:
    con = sqlite3.connect(RUTA_BD, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def _migrar(con: sqlite3.Connection) -> None:
    for tabla, columnas in _COLUMNAS_NUEVAS.items():
        existentes = {fila["name"] for fila in con.execute(f"PRAGMA table_info({tabla})")}
        for nombre, definicion in columnas.items():
            if nombre not in existentes:
                con.execute(f"ALTER TABLE {tabla} ADD COLUMN {nombre} {definicion}")


def iniciar() -> None:
    from . import seguridad

    RUTA_BD.parent.mkdir(parents=True, exist_ok=True)
    con = conectar()
    try:
        con.execute("PRAGMA journal_mode = WAL")
        con.executescript(ESQUEMA)
        _migrar(con)
        hay_admin = con.execute("SELECT 1 FROM usuarios WHERE rol = 'administrador' LIMIT 1").fetchone()
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
            if not os.environ.get("SAMCORE_ADMIN_CONTRASENA"):
                RUTA_CREDENCIAL_INICIAL.write_text(
                    "Cuenta de administrador inicial de SamCore (solo desarrollo).\n"
                    f"Correo: {correo}\nContrasena: {contrasena}\n"
                    "Borra este archivo despues del primer inicio de sesion.\n",
                    encoding="utf-8",
                )
            log.info("evento=bootstrap_admin correo=%s", correo)
        con.commit()
    finally:
        con.close()
