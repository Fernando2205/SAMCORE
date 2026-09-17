"""Publica el sistema en un Space Docker de Hugging Face.

    HF_TOKEN=<token> python deploy/subir_space.py <usuario>/<space>

Sube el codigo, los artefactos por categoria y la galeria (binarios por LFS).
Los pesos de SAM no se suben: la imagen los descarga y verifica al construirse.
"""
import os
import sys
from pathlib import Path

from huggingface_hub import HfApi

RAIZ = Path(__file__).resolve().parents[1]
CABECERA = """---
title: SamCore
emoji: 🔍
colorFrom: gray
colorTo: green
sdk: docker
app_port: 7860
pinned: false
license: apache-2.0
---

"""
IGNORAR = [
    "**/.venv/**", "**/node_modules/**", "**/__pycache__/**", "**/*.pyc",
    "backend/samcore.db*", "backend/.admin_inicial.txt", "backend/datos/**",
    "backend/pesos/*.pth", "backend/pesos/torch/**", "backend/tests/**",
    "backend/galeria/*/muestra/**", "frontend/dist/**", "USB_template/**",
    "viejo/**", "Template actualizado/**", ".git/**", "deploy/**", ".env",
]


def main() -> None:
    if len(sys.argv) != 2 or "/" not in sys.argv[1]:
        sys.exit(__doc__)
    token = os.environ.get("HF_TOKEN")
    if not token:
        sys.exit("Falta HF_TOKEN en el entorno")
    repo = sys.argv[1]
    api = HfApi(token=token)
    api.create_repo(repo, repo_type="space", space_sdk="docker", exist_ok=True)
    api.upload_folder(
        folder_path=str(RAIZ), repo_id=repo, repo_type="space",
        ignore_patterns=IGNORAR + ["README.md"], commit_message="despliegue de SamCore",
    )
    # El README del Space lleva la cabecera YAML que configura el Space; se
    # sube al final para que la carpeta no lo pise con el README de GitHub.
    readme = CABECERA + (RAIZ / "README.md").read_text(encoding="utf-8")
    api.upload_file(
        path_or_fileobj=readme.encode("utf-8"), path_in_repo="README.md", repo_id=repo, repo_type="space",
        commit_message="configuración del Space",
    )
    print(f"publicado: https://huggingface.co/spaces/{repo}")


if __name__ == "__main__":
    main()
