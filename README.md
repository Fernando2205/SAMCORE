# SamCore

Sistema de detección de anomalías en productos: SAM (segmentación
automática, pesos congelados) + PatchCore (banco de memoria) sobre las
categorías de objetos de MVTec AD, expuesto en una aplicación web con
cuentas, historial e inspección de imágenes propias.

- `backend/` — API FastAPI, motor de inferencia (`app/motor/`), artefactos
  por categoría, galería cerrada, ingesta segura de imágenes y almacén de
  informes. SQLite en modo WAL.
- `frontend/` — React + TypeScript (Vite), Tailwind v4, lint con
  neostandard. Se compila a estáticos que sirve la propia API.
- `notebook/` — cuaderno experimental (Colab): segmentación, corridas de
  PatchCore, re-proyección del mapa y exportación de artefactos.
- `resultados/` — métricas por categoría de las corridas cerradas
  (baseline y SAM + ROI, AUROC re-proyectado, registro de cajas,
  calibración y manifiesto).
- `Dockerfile`, `deploy/` — imagen única de despliegue y publicación en un
  Space Docker de Hugging Face con GPU.

## Artefactos que no se versionan

| Ruta | Contenido | Origen |
|---|---|---|
| `backend/artefactos/<categoría>/` | `banco.npz`, `calibracion.json`, `manifiesto.json` | exportación del cuaderno |
| `backend/galeria/<categoría>/<tipo>/*.png` | subconjunto del test de MVTec AD | celda "exportar galería" del cuaderno |
| `backend/pesos/sam_vit_h_4b8939.pth` | checkpoint de SAM ViT-H (2,56 GB) | `python scripts/descargar_pesos.py` |

La API verifica los manifiestos (SHA-256) al arrancar y solo habilita las
categorías cuyos artefactos coinciden; los bancos se cargan sin `pickle`.

## Correr en desarrollo

Backend (puerto 8000). Requiere Python 3.12 o superior y, para el motor
real, una GPU con CUDA (en una GPU de 6 GB el motor usa fp16):

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\pip install --index-url https://download.pytorch.org/whl/cu128 torch==2.11.0 torchvision==0.26.0
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\python scripts\descargar_pesos.py
.\.venv\Scripts\python -m uvicorn app.main:app --port 8000
```

En el primer arranque se crea la cuenta de administrador y su contraseña
queda en `backend/.admin_inicial.txt` (bórralo tras el primer inicio de
sesión), salvo que se definan `SAMCORE_ADMIN_CORREO` y
`SAMCORE_ADMIN_CONTRASENA`. El motor se carga en segundo plano; `/api/salud`
reporta `motor: real` cuando está listo. Sin GPU ni artefactos, o con
`SAMCORE_MOTOR=simulado`, la API responde con el motor simulado.

Frontend (puerto 5173, proxy a `/api`):

```powershell
cd frontend
pnpm install
pnpm run dev
```

## Variables de entorno

| Variable | Valor por defecto | Uso |
|---|---|---|
| `SAMCORE_MOTOR` | `auto` | `real`, `simulado` o `auto` (real si hay artefactos y GPU) |
| `SAMCORE_PRECISION` | fp16 si la GPU tiene menos de 10 GB | `fp16` o `fp32` para SAM |
| `SAMCORE_COLA` | `4` | solicitudes en espera de la GPU antes de responder 503 |
| `SAMCORE_TIEMPO_MAXIMO` | `120` | segundos por inspección antes de cancelarla |
| `SAMCORE_BD`, `SAMCORE_DATOS` | `backend/samcore.db`, `backend/datos` | base de datos e imágenes de las inspecciones |
| `SAMCORE_ARTEFACTOS`, `SAMCORE_GALERIA`, `SAMCORE_PESOS` | carpetas de `backend/` | ubicación de artefactos, galería y pesos |
| `SAMCORE_FRONTEND` | `frontend/dist` | estáticos del frontend servidos por la API |
| `SAMCORE_HTTPS` | `0` | `1` marca la cookie de sesión como `Secure` |

## Verificación

```powershell
cd backend
.\.venv\Scripts\python -m pytest tests            # controles M-01…M-17 y motor
.\.venv\Scripts\python scripts\prueba_motor.py capsule galeria\capsule\good\000.png
.\.venv\Scripts\python scripts\prueba_extremo_a_extremo.py http://127.0.0.1:8000 <correo> <contraseña> foto.png
cd ..\frontend
pnpm run lint
pnpm run build
```

## Despliegue

Ver `deploy/README.md`: Space Docker de Hugging Face con GPU T4, almacenamiento
persistente en `/data` y publicación con `deploy/subir_space.py`.

## Licencias

Código bajo Apache 2.0. SAM (Meta AI) y la implementación de referencia
de PatchCore (Amazon Science) son Apache 2.0; las imágenes de MVTec AD son
de MVTec Software GmbH bajo CC BY-NC-SA 4.0 y la aplicación muestra la
atribución.
