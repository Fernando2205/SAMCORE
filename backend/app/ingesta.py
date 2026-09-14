"""Ingesta segura de imagenes subidas por el usuario (M-16).

Orden de las comprobaciones, del mas barato al mas caro:
1. tamano en bytes (el endpoint corta la lectura al superar el tope);
2. tipo real por numeros magicos (PNG o JPEG), no por extension ni cabecera;
3. decodificacion con tope de pixeles (bomba de descompresion);
4. dimensiones minimas y maximas;
5. re-codificacion a una imagen nueva sin metadatos (EXIF, ICC, texto),
   reducida a un lado maximo. Solo esa version entra al pipeline y al
   almacenamiento (M-17).
"""
from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_BYTES = 8 * 1024 * 1024
MAX_PIXELES = 25_000_000
LADO_MAXIMO = 1024
LADO_MINIMO = 64

_MAGIA_PNG = b"\x89PNG\r\n\x1a\n"
_MAGIA_JPEG = b"\xff\xd8\xff"


class ImagenRechazada(Exception):
    def __init__(self, codigo: str, mensaje: str) -> None:
        super().__init__(mensaje)
        self.codigo = codigo
        self.mensaje = mensaje


def tipo_por_magia(datos: bytes) -> str | None:
    if datos.startswith(_MAGIA_PNG):
        return "png"
    if datos.startswith(_MAGIA_JPEG):
        return "jpeg"
    return None


def ingerir(datos: bytes) -> Image.Image:
    """Devuelve una imagen RGB nueva, sin metadatos, lista para el pipeline."""
    if len(datos) > MAX_BYTES:
        raise ImagenRechazada("tamano", "La imagen supera el tamaño máximo de 8 MB.")
    tipo = tipo_por_magia(datos)
    if tipo is None:
        raise ImagenRechazada("tipo", "Solo se aceptan imágenes JPG o PNG.")
    Image.MAX_IMAGE_PIXELS = MAX_PIXELES
    try:
        with Image.open(BytesIO(datos)) as prueba:
            if prueba.format not in ("PNG", "JPEG"):
                raise ImagenRechazada("tipo", "Solo se aceptan imágenes JPG o PNG.")
            prueba.verify()
        with Image.open(BytesIO(datos)) as imagen:
            ancho, alto = imagen.size
            if ancho * alto > MAX_PIXELES:
                raise ImagenRechazada("dimensiones", "La imagen tiene demasiados píxeles.")
            if min(ancho, alto) < LADO_MINIMO:
                raise ImagenRechazada("dimensiones", "La imagen es demasiado pequeña (mínimo 64 píxeles por lado).")
            # La orientacion EXIF (fotos de celular) se aplica a los pixeles
            # antes de descartar los metadatos; si no, la imagen queda girada.
            orientada = ImageOps.exif_transpose(imagen)
            limpia = (orientada if orientada is not None else imagen).convert("RGB")
    except Image.DecompressionBombError:
        raise ImagenRechazada("dimensiones", "La imagen tiene demasiados píxeles.") from None
    except (UnidentifiedImageError, OSError, ValueError):
        raise ImagenRechazada("corrupta", "No fue posible leer la imagen.") from None
    if max(limpia.size) > LADO_MAXIMO:
        limpia.thumbnail((LADO_MAXIMO, LADO_MAXIMO), Image.Resampling.LANCZOS)
    # Copia nueva: sin el diccionario `info` (EXIF, ICC, texto) de la original.
    salida = Image.new("RGB", limpia.size)
    salida.paste(limpia)
    return salida
