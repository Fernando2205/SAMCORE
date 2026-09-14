"""Comprueba que la reimplementacion de PatchCore de la aplicacion produce
exactamente las mismas caracteristicas, puntuaciones y mapas que el codigo
de referencia (amazon-science/patchcore-inspection) con el mismo banco.

    .venv/Scripts/python scripts/validar_contra_referencia.py <carpeta src/patchcore de la referencia> <categoria> <imagen> [...]

El unico componente sustituido en la referencia es el indice FAISS (no
instalable aqui): se usa la misma busqueda exacta por distancia L2 al
cuadrado, que es lo que devuelve IndexFlatL2.
"""
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
import torch  # noqa: E402
import torchvision  # noqa: E402
from PIL import Image  # noqa: E402

from app import artefactos  # noqa: E402
from app.motor.patchcore import TRANSFORMACION, DetectorPatchCore  # noqa: E402


class BusquedaExacta:
    """Sustituto de FaissNN con la misma semantica (L2 al cuadrado, exacto)."""

    def __init__(self, *args, **kwargs) -> None:
        self.indice = None

    def fit(self, features: np.ndarray) -> None:
        self.indice = torch.from_numpy(np.ascontiguousarray(features)).float()

    def run(self, k: int, query: np.ndarray, index_features=None):
        b = self.indice if index_features is None else torch.from_numpy(index_features).float()
        q = torch.from_numpy(np.ascontiguousarray(query)).float()
        d2 = (q * q).sum(1, keepdim=True) + (b * b).sum(1)[None, :] - 2.0 * (q @ b.T)
        d, i = d2.topk(k, dim=1, largest=False)
        return d.clamp_min(0).numpy(), i.numpy()


def cargar_referencia(ruta_src: Path):
    faiss_falso = types.ModuleType("faiss")
    faiss_falso.omp_set_num_threads = lambda n: None
    sys.modules["faiss"] = faiss_falso
    sys.modules["timm"] = types.ModuleType("timm")
    sys.modules["tqdm"] = types.ModuleType("tqdm")  # solo lo usan fit/predict por lotes
    sys.path.insert(0, str(ruta_src.parent))
    import patchcore.common  # noqa: E402
    import patchcore.patchcore  # noqa: E402
    import patchcore.sampler  # noqa: E402

    patchcore.common.FaissNN = BusquedaExacta
    return patchcore


def main() -> None:
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    ruta_src, categoria, rutas = Path(sys.argv[1]), sys.argv[2], sys.argv[3:]
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    pc = cargar_referencia(ruta_src)

    backbone = torchvision.models.wide_resnet50_2(weights=torchvision.models.Wide_ResNet50_2_Weights.IMAGENET1K_V1)
    backbone.name, backbone.seed = "wideresnet50", 0
    referencia = pc.patchcore.PatchCore(device)
    referencia.load(
        backbone=backbone, layers_to_extract_from=["layer2", "layer3"], device=device,
        input_shape=(3, 224, 224), pretrain_embed_dimension=1024, target_embed_dimension=1024,
        patchsize=3, featuresampler=pc.sampler.IdentitySampler(), anomaly_score_num_nn=1,
        nn_method=BusquedaExacta(),
    )
    banco_np = artefactos.cargar_banco(categoria)
    referencia.anomaly_scorer.fit(detection_features=[banco_np])

    propio = DetectorPatchCore(device)
    banco = artefactos.GestorArtefactos.cargar_banco(categoria, device)

    for ruta in rutas:
        with Image.open(ruta) as img:
            img = img.convert("RGB")
        x = TRANSFORMACION(img).unsqueeze(0)
        feats_ref = np.asarray(referencia._embed(x.to(device)))
        feats_app = propio.incrustar(img).cpu().numpy()
        puntos_ref, mapas_ref = referencia._predict(x)
        puntuacion_app, mapa_app = propio.puntuar(propio.incrustar(img), banco)
        print(
            f"{Path(ruta).name}: características |Δ| máx={np.abs(feats_ref - feats_app).max():.2e} · "
            f"puntuación ref={float(puntos_ref[0]):.6f} app={puntuacion_app:.6f} "
            f"(|Δ|={abs(float(puntos_ref[0]) - puntuacion_app):.2e}) · mapa |Δ| máx={np.abs(mapas_ref[0] - mapa_app).max():.2e}"
        )


if __name__ == "__main__":
    main()
