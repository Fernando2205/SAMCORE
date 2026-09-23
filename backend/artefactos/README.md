# Artefactos del modelo por categoría

El backend busca aquí los artefactos del pipeline real (SAM + PatchCore).
Cuando una categoría tiene su carpeta completa y con hashes válidos,
`/api/salud` la lista en `categorias_con_artefactos` y el motor real la
atiende; una categoría cuyo manifiesto no coincide queda deshabilitada
(422 al inspeccionarla) y el evento se registra en el log.

## Estructura esperada (por categoría)

```
backend/artefactos/capsule/
├── manifiesto.json     metadatos + SHA-256 de cada archivo
├── banco.npz           banco de memoria PatchCore tras coreset
└── calibracion.json    umbral calibrado + configuración congelada
```

`manifiesto.json`:

```json
{
  "categoria": "capsule",
  "version": "1",
  "archivos": {
    "banco.npz": "<sha256 hex>",
    "calibracion.json": "<sha256 hex>"
  }
}
```

`banco.npz` (`np.savez_compressed`; se carga con `allow_pickle=False`,
nunca con pickle):

- `banco`: float32 `[N, D]` — parches del coreset (capas layer2+layer3
  de WideResNet-50-2).

`calibracion.json`:

```json
{
  "categoria": "capsule",
  "umbral": 1.924665,
  "percentil": 99,
  "n_validacion": 32,
  "n_preparacion": 187,
  "n_parches": 14660,
  "dim_parche": 1024,
  "capas": ["layer2", "layer3"],
  "tam_entrada": [224, 224],
  "resize": 256,
  "coreset_pct": 10,
  "regla_seleccion": {
    "area_min_pct": 3, "area_max_pct": 95, "rho": 0.35,
    "pesos": { "iou": 0.6, "estabilidad": 0.4, "relleno": 0.25, "borde": -0.15 }
  },
  "semilla": 0,
  "torchvision": "0.26.0+cu128"
}
```

El umbral es el percentil 99 de las puntuaciones de `n_validacion`
imágenes normales apartadas del entrenamiento antes de construir el banco
(el banco usa las `n_preparacion` restantes).

Los pesos de SAM (ViT-H) no forman parte de estos artefactos: se
descargan del checkpoint oficial y se verifican por SHA-256 al construir
la imagen de despliegue (`scripts/descargar_pesos.py`).

La verificación de hashes (`app/artefactos.py`) corre al arrancar la API
para todas las carpetas presentes; los bancos se cargan con
`allow_pickle=False`.
