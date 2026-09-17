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

# Respaldo de la base de datos (M-14). En el despliegue la BD vive en el disco
# local del contenedor (SQLite necesita bloqueos que los almacenamientos
# remotos montados no siempre ofrecen) y se copia al almacenamiento
# persistente cada pocos minutos; al arrancar, si no hay BD local, se
# restaura desde ese respaldo.
RUTA_RESPALDO = Path(os.environ["SAMCORE_BD_RESPALDO"]) if os.environ.get("SAMCORE_BD_RESPALDO") else None
INTERVALO_RESPALDO_S = int(os.environ.get("SAMCORE_RESPALDO_CADA", "300"))

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


def restaurar_desde_respaldo() -> bool:
    """Si no existe la BD local pero sí el respaldo, lo copia. True si restauró."""
    if RUTA_RESPALDO is None or RUTA_BD.exists() or not RUTA_RESPALDO.is_file():
        return False
    RUTA_BD.parent.mkdir(parents=True, exist_ok=True)
    origen = sqlite3.connect(RUTA_RESPALDO)
    try:
        destino = sqlite3.connect(RUTA_BD)
        try:
            origen.backup(destino)
        finally:
            destino.close()
    finally:
        origen.close()
    log.info("evento=bd_restaurada desde=%s", RUTA_RESPALDO)
    return True


def respaldar() -> bool:
    """Copia consistente de la BD al respaldo (API de backup de SQLite)."""
    if RUTA_RESPALDO is None or not RUTA_BD.exists():
        return False
    try:
        RUTA_RESPALDO.parent.mkdir(parents=True, exist_ok=True)
        temporal = RUTA_RESPALDO.with_name(RUTA_RESPALDO.name + ".tmp")
        origen = sqlite3.connect(RUTA_BD)
        try:
            destino = sqlite3.connect(temporal)
            try:
                origen.backup(destino)
            finally:
                destino.close()
        finally:
            origen.close()
        os.replace(temporal, RUTA_RESPALDO)
        return True
    except (sqlite3.Error, OSError) as exc:
        log.warning("evento=bd_respaldo_fallido tipo=%s", type(exc).__name__)
        return False


def iniciar_respaldo_periodico() -> None:
    """Hilo en segundo plano que respalda cada INTERVALO_RESPALDO_S segundos."""
    import threading
    import time

    if RUTA_RESPALDO is None:
        return

    def ciclo() -> None:
        while True:
            time.sleep(INTERVALO_RESPALDO_S)
            respaldar()

    threading.Thread(target=ciclo, name="respaldo-bd", daemon=True).start()
    log.info("evento=respaldo_programado cada_s=%s destino=%s", INTERVALO_RESPALDO_S, RUTA_RESPALDO)


def iniciar() -> None:
    from . import seguridad

    RUTA_BD.parent.mkdir(parents=True, exist_ok=True)
    restaurar_desde_respaldo()
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
