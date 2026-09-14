"""Detector PatchCore: caracteristicas WideResNet-50 (capas 2 y 3) y
puntuacion por vecino mas cercano contra el banco de memoria.

Reproduce paso a paso la ruta de inferencia de la implementacion de
referencia (amazon-science/patchcore-inspection, licencia Apache 2.0) con la
que se prepararon los bancos: mismas transformaciones de entrada, misma
agregacion de parches (3x3, stride 1), misma reduccion a 1024 dimensiones,
distancia L2 al cuadrado (como el indice plano de FAISS) con k = 1,
puntuacion de imagen = maximo sobre los parches, y mapa 28x28 interpolado a
224x224 con suavizado gaussiano sigma = 4.
"""
import logging
from dataclasses import dataclass

import numpy as np
import torch
import torch.nn.functional as F
import torchvision
from PIL import Image
from scipy import ndimage
from torchvision import transforms

log = logging.getLogger("samcore")

# Los bancos y los umbrales se calcularon en fp32 exacto; en GPU Ampere o
# posteriores torch usa TF32 por defecto en convoluciones, lo que desplaza las
# puntuaciones respecto de la calibracion. Se desactiva para reproducirla.
torch.backends.cudnn.allow_tf32 = False
torch.backends.cuda.matmul.allow_tf32 = False

RESIZE = 256
IMAGESIZE = 224
PATCHSIZE = 3
DIM_PREPROCESO = 1024
DIM_OBJETIVO = 1024
SIGMA_SUAVIZADO = 4
MEDIA_IMAGENET = [0.485, 0.456, 0.406]
STD_IMAGENET = [0.229, 0.224, 0.225]

TRANSFORMACION = transforms.Compose([
    transforms.Resize(RESIZE),
    transforms.CenterCrop(IMAGESIZE),
    transforms.ToTensor(),
    transforms.Normalize(mean=MEDIA_IMAGENET, std=STD_IMAGENET),
])


def _patchify(x: torch.Tensor) -> tuple[torch.Tensor, tuple[int, int]]:
    """(B, C, H, W) -> (B, H*W, C, 3, 3) con relleno 1 y stride 1."""
    relleno = (PATCHSIZE - 1) // 2
    desplegado = F.unfold(x, kernel_size=PATCHSIZE, stride=1, padding=relleno)
    n_h, n_w = x.shape[-2], x.shape[-1]
    desplegado = desplegado.reshape(x.shape[0], x.shape[1], PATCHSIZE, PATCHSIZE, -1)
    return desplegado.permute(0, 4, 1, 2, 3), (n_h, n_w)


@dataclass
class BancoMemoria:
    """Banco de parches normales de una categoria (M, 1024) y su umbral."""

    categoria: str
    tensores: torch.Tensor
    umbral: float

    @torch.inference_mode()
    def consultar_knn(self, parches: torch.Tensor, k: int = 1) -> torch.Tensor:
        """Distancia L2 al cuadrado al vecino mas cercano de cada parche
        (k = 1, como el indice plano de FAISS de la referencia)."""
        if k != 1:
            raise ValueError("el sistema opera con un unico vecino (k = 1)")
        q = parches.to(self.tensores.device, torch.float32)
        b = self.tensores
        d2 = (q * q).sum(1, keepdim=True) + (b * b).sum(1)[None, :] - 2.0 * (q @ b.T)
        return d2.min(dim=1).values.clamp_min_(0.0)


class DetectorPatchCore:
    def __init__(self, device: torch.device) -> None:
        self.device = device
        pesos = torchvision.models.Wide_ResNet50_2_Weights.IMAGENET1K_V1
        red = torchvision.models.wide_resnet50_2(weights=pesos).to(device)
        self._red = red
        # La implementacion de referencia mide las dimensiones de las
        # caracteristicas con un paso hacia adelante de un tensor de unos en
        # modo entrenamiento, lo que actualiza una vez las estadisticas de
        # BatchNorm (momento 0,1). Los bancos y umbrales se prepararon con esa
        # red, asi que se reproduce el mismo paso antes de pasar a evaluacion.
        red.train()
        with torch.no_grad():
            self._capas(torch.ones(1, 3, IMAGESIZE, IMAGESIZE, device=device))
        red.eval()
        log.info("evento=patchcore_listo device=%s", device)

    @torch.inference_mode()
    def _capas(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        r = self._red
        x = r.maxpool(r.relu(r.bn1(r.conv1(x))))
        x = r.layer1(x)
        c2 = r.layer2(x)
        c3 = r.layer3(c2)
        return c2, c3

    @torch.inference_mode()
    def incrustar(self, imagen: Image.Image) -> torch.Tensor:
        """Caracteristicas por parche (784, 1024) de un recorte ROI (PIL RGB)."""
        x = TRANSFORMACION(imagen).unsqueeze(0).to(self.device)
        capas = list(self._capas(x))
        parches = [_patchify(c) for c in capas]
        formas = [p[1] for p in parches]
        feats = [p[0] for p in parches]
        ref_h, ref_w = formas[0]
        for i in range(1, len(feats)):
            f = feats[i]
            ph, pw = formas[i]
            f = f.reshape(f.shape[0], ph, pw, *f.shape[2:])
            f = f.permute(0, -3, -2, -1, 1, 2)
            forma_base = f.shape
            f = f.reshape(-1, *f.shape[-2:])
            f = F.interpolate(f.unsqueeze(1), size=(ref_h, ref_w), mode="bilinear", align_corners=False)
            f = f.squeeze(1)
            f = f.reshape(*forma_base[:-2], ref_h, ref_w)
            f = f.permute(0, -2, -1, 1, 2, 3)
            feats[i] = f.reshape(len(f), -1, *f.shape[-3:])
        feats = [f.reshape(-1, *f.shape[-3:]) for f in feats]
        # Preprocesamiento: cada capa a DIM_PREPROCESO por parche
        reducidas = []
        for f in feats:
            f = f.reshape(len(f), 1, -1)
            reducidas.append(F.adaptive_avg_pool1d(f, DIM_PREPROCESO).squeeze(1))
        apiladas = torch.stack(reducidas, dim=1)
        # Agregacion: (N, capas, DIM) -> (N, DIM_OBJETIVO)
        apiladas = apiladas.reshape(len(apiladas), 1, -1)
        agregadas = F.adaptive_avg_pool1d(apiladas, DIM_OBJETIVO)
        return agregadas.reshape(len(agregadas), -1)

    @torch.inference_mode()
    def puntuar(self, caracteristicas: torch.Tensor, banco: BancoMemoria | torch.Tensor) -> tuple[float, np.ndarray]:
        """Puntuacion de imagen (maximo por parche) y mapa 224x224."""
        if not isinstance(banco, BancoMemoria):
            banco = BancoMemoria("", banco.to(self.device, torch.float32), 0.0)
        d_min = banco.consultar_knn(caracteristicas)
        puntuacion = float(d_min.max().item())
        lado = int(round(len(d_min) ** 0.5))
        mapa = d_min.reshape(1, 1, lado, lado)
        mapa = F.interpolate(mapa, size=(IMAGESIZE, IMAGESIZE), mode="bilinear", align_corners=False)
        mapa = mapa.squeeze().cpu().numpy().astype(np.float32)
        mapa = ndimage.gaussian_filter(mapa, sigma=SIGMA_SUAVIZADO).astype(np.float32)
        return puntuacion, mapa

    def evaluar(self, recorte: Image.Image, banco: BancoMemoria) -> tuple[float, np.ndarray]:
        """ROI (PIL RGB) -> (puntuacion de imagen, mapa 224x224)."""
        return self.puntuar(self.incrustar(recorte), banco)
