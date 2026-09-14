# Despliegue en Hugging Face (Space Docker con GPU T4)

Una sola imagen contiene la API, el frontend compilado, el motor, los
bancos por categoría y los pesos de SAM (ADR-02). La base de datos y las
imágenes de las inspecciones viven en el almacenamiento persistente del
Space (`/data`).

## Requisitos en la cuenta de Hugging Face

1. Cuenta con método de pago (el hardware T4 small se factura por minuto
   activo) y un token de acceso con permiso de escritura.
2. Crear el Space: SDK **Docker**, hardware **T4 small**, visibilidad
   pública, *sleep time* 15 minutos, y activar **Persistent storage**
   (small) para `/data`.
3. Variables del Space (Settings → Variables and secrets):
   - `SAMCORE_ADMIN_CORREO` = correo del operador.
   - `SAMCORE_ADMIN_CONTRASENA` = contraseña inicial del operador (secreto).

## Contenido del repositorio del Space

El repositorio del Space es distinto del repositorio de código: además del
código lleva los archivos que no se versionan en GitHub.

```
Dockerfile              .dockerignore
README.md               (este archivo con la cabecera YAML de abajo)
backend/app  backend/scripts  backend/requirements.txt
backend/artefactos/<categoria>/{banco.npz,calibracion.json,manifiesto.json}   (LFS)
backend/galeria/<categoria>/<tipo>/*.png                                      (LFS)
frontend/ (fuentes; se compila dentro de la imagen)
```

Cabecera YAML que debe encabezar el `README.md` del Space:

```yaml
---
title: SamCore
emoji: 🔍
colorFrom: gray
colorTo: green
sdk: docker
app_port: 7860
pinned: false
license: apache-2.0
---
```

## Publicar

Con el token en la variable de entorno `HF_TOKEN`:

```powershell
cd backend
.\.venv\Scripts\pip install huggingface_hub
.\.venv\Scripts\python ..\deploy\subir_space.py <usuario>/samcore
```

El script crea el Space si no existe, sube el contenido (con LFS para los
binarios) y deja la construcción en marcha. La primera construcción tarda
entre 20 y 40 minutos (descarga de torch y de los pesos de SAM).

## Verificación tras el despliegue

1. `GET https://<usuario>-samcore.hf.space/api/salud` responde `motor: real`
   y lista las ocho categorías con artefactos.
2. Iniciar sesión con la cuenta del operador, aprobar una cuenta de
   usuario y realizar una inspección de galería y una carga de imagen
   propia.
3. Anotar el p95 de segmentación reportado en Estadísticas (RNF-02).
