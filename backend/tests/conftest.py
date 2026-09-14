"""Entorno aislado para las pruebas: base de datos, datos y galeria en una
carpeta temporal; motor simulado; credenciales de administrador conocidas."""
import os
import sys
import tempfile
from pathlib import Path

import pytest
from PIL import Image

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

_TMP = Path(tempfile.mkdtemp(prefix="samcore-pruebas-"))
os.environ.update({
    "SAMCORE_MOTOR": "simulado",
    "SAMCORE_BD": str(_TMP / "pruebas.db"),
    "SAMCORE_DATOS": str(_TMP / "datos"),
    "SAMCORE_GALERIA": str(_TMP / "galeria"),
    "SAMCORE_ARTEFACTOS": str(_TMP / "artefactos"),
    "SAMCORE_FRONTEND": str(_TMP / "sin_frontend"),
    "SAMCORE_ADMIN_CORREO": "operador@pruebas.local",
    "SAMCORE_ADMIN_CONTRASENA": "clave-de-pruebas-123",
})

CATEGORIAS_GALERIA = {"capsule": ["good", "crack"], "transistor": ["good", "bent_lead"]}


def _crear_galeria() -> None:
    for categoria, tipos in CATEGORIAS_GALERIA.items():
        for tipo in tipos:
            carpeta = _TMP / "galeria" / categoria / tipo
            carpeta.mkdir(parents=True, exist_ok=True)
            for i in range(2):
                Image.new("RGB", (128, 96), (200 - 40 * i, 180, 160)).save(carpeta / f"{i:03d}.png")


_crear_galeria()

from fastapi.testclient import TestClient  # noqa: E402

from app import seguridad  # noqa: E402
from app.main import app  # noqa: E402

# Las pruebas crean muchas cuentas desde la misma IP: el limite de registro
# (3 por 5 minutos) se relaja; los demas limites se prueban con su valor real.
seguridad.limitador_registro.maximo = 1000


@pytest.fixture(scope="session")
def raiz_temporal() -> Path:
    return _TMP


@pytest.fixture(scope="session")
def servidor():
    with TestClient(app) as cliente:
        yield cliente


def _cliente_nuevo(relanzar_errores: bool = True) -> TestClient:
    return TestClient(app, raise_server_exceptions=relanzar_errores)


@pytest.fixture(scope="session")
def admin(servidor) -> TestClient:
    cliente = _cliente_nuevo()
    r = cliente.post("/api/auth/login", json={"correo": "operador@pruebas.local", "contrasena": "clave-de-pruebas-123"})
    assert r.status_code == 200, r.text
    return cliente


def crear_usuario(admin: TestClient, correo: str, contrasena: str = "contrasena-larga-1",
                  relanzar_errores: bool = True) -> TestClient:
    cliente = _cliente_nuevo(relanzar_errores)
    r = cliente.post("/api/auth/registro", json={"correo": correo, "contrasena": contrasena, "confirmacion": contrasena})
    assert r.status_code == 201, r.text
    usuarios = admin.get("/api/admin/usuarios").json()
    objetivo = next(u for u in usuarios if u["correo"] == correo)
    r = admin.post(f"/api/admin/usuarios/{objetivo['id']}/estado", json={"accion": "aprobar"})
    assert r.status_code == 200, r.text
    r = cliente.post("/api/auth/login", json={"correo": correo, "contrasena": contrasena})
    assert r.status_code == 200, r.text
    return cliente


@pytest.fixture(scope="session")
def usuario_a(admin) -> TestClient:
    return crear_usuario(admin, "ana@pruebas.local")


@pytest.fixture(scope="session")
def usuario_b(admin) -> TestClient:
    return crear_usuario(admin, "beto@pruebas.local")
