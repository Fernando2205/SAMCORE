"""Descarga el checkpoint de SAM (ViT-H) y verifica su SHA-256 (M-07).

    python scripts/descargar_pesos.py [carpeta_destino]

Sale con codigo distinto de cero si el hash no coincide.
"""
import hashlib
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.motor.segmentador import RUTA_PESOS, SAM_ARCHIVO, SAM_SHA256, SAM_URL  # noqa: E402


def sha256(ruta: Path) -> str:
    h = hashlib.sha256()
    with ruta.open("rb") as f:
        for bloque in iter(lambda: f.read(1 << 22), b""):
            h.update(bloque)
    return h.hexdigest()


def main() -> None:
    destino = Path(sys.argv[1]) if len(sys.argv) > 1 else RUTA_PESOS
    destino.mkdir(parents=True, exist_ok=True)
    ruta = destino / SAM_ARCHIVO
    if ruta.is_file() and sha256(ruta) == SAM_SHA256:
        print(f"ya presente y verificado: {ruta}")
        return
    print(f"descargando {SAM_URL} -> {ruta}")
    urllib.request.urlretrieve(SAM_URL, ruta)
    real = sha256(ruta)
    if real != SAM_SHA256:
        ruta.unlink(missing_ok=True)
        sys.exit(f"hash invalido: {real}")
    print("descargado y verificado")


if __name__ == "__main__":
    main()
