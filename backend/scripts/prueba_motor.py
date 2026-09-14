"""Prueba de humo del motor real: carga SAM + PatchCore + bancos y ejecuta el
pipeline sobre una o varias imagenes.

    .venv/Scripts/python scripts/prueba_motor.py capsule galeria/capsule/good/000.png [...]
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import torch  # noqa: E402
from PIL import Image  # noqa: E402

from app.motor import orquestador  # noqa: E402


def main() -> None:
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    categoria, rutas = sys.argv[1], sys.argv[2:]
    motor = orquestador.instancia()
    t0 = time.perf_counter()
    motor.preparar()
    print(f"motor: estado={motor.estado} error={motor.error} device={motor.device} precision={motor.precision} "
          f"categorias={motor.categorias()} carga={time.perf_counter() - t0:.1f}s")
    if motor.estado != "listo":
        sys.exit(1)
    for ruta in rutas:
        with Image.open(ruta) as img:
            img = img.convert("RGB")
        r = motor.inspeccionar(img, categoria)
        print(
            f"{Path(ruta).name}: {r['veredicto']} puntuacion={r['puntuacion']:.4f} umbral={r['umbral']:.4f} "
            f"roi={r['estado_roi']} caja_sam={r['caja']['sam']} caja_roi={r['caja']['roi']} "
            f"mascaras={r['mascaras']} tiempos={r['tiempos_ms']} regiones={len(r['regiones'])}"
        )
    if torch.cuda.is_available():
        print(f"VRAM pico: {torch.cuda.max_memory_allocated() / 2**30:.2f} GiB")


if __name__ == "__main__":
    main()
