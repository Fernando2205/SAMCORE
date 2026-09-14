# Pesos de SAM

La aplicación espera aquí el checkpoint de SAM 1 (ViT-H):

```
backend/pesos/sam_vit_h_4b8939.pth
```

Fuente: `https://dl.fbaipublicfiles.com/segment_anything/sam_vit_h_4b8939.pth`
(2,56 GB). El motor verifica su SHA-256 antes de cargarlo (M-07):

```
a7bf3b02f3ebf1267aba913ff637d9a2d5c33d3173bb679e46d9f338c26f262e
```

El archivo no se versiona; la imagen de despliegue lo descarga y verifica
al construirse. Los pesos de WideResNet-50 (PatchCore) los descarga
torchvision en el primer arranque a su caché habitual.
