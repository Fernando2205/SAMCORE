# Artefactos del modelo por categoría

El backend busca aquí los artefactos del pipeline real (SAM + PatchCore).
Cuando una categoría tiene su carpeta completa y con hashes válidos,
`/api/salud` y `/api/categorias` la reportan con `artefactos: true`.
Mientras el motor real no esté integrado, la inferencia es simulada
aunque existan artefactos.

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
  "umbral": 3.417,
  "percentil": 99,
  "n_validacion": 0,
  "dim_parche": 0,
  "capas": ["layer2", "layer3"],
  "tam_entrada": [0, 0],
  "coreset_pct": 10,
  "regla_seleccion": { "area_min_pct": 3, "area_max_pct": 95, "rho": 0.35 },
  "semilla": 0,
  "torchvision": "x.y.z"
}
```

Los pesos de SAM (ViT-H) no forman parte de estos artefactos: se
descargan del checkpoint oficial y se verifican por SHA-256 en el
despliegue.

La integración del motor real reemplaza únicamente a `app/inferencia.py`
manteniendo el mismo contrato de salida; la verificación de hashes
(`app/artefactos.py`) corre sola al primer uso de cada categoría.
