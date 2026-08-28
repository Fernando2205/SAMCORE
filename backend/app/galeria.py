"""Galeria cerrada (ADR-08): listas cerradas de categorias e imagenes.

Todo parametro de entrada se valida contra estas listas (M-03); no hay
carga de archivos ni rutas construidas con texto del cliente. Los ids
imitan la estructura de MVTec AD; en el MVP son marcadores de posicion y
el servidor aun no sirve las imagenes reales (costura pendiente para T6).
Los umbrales por categoria son ilustrativos salvo capsule (3.417, valor
del diseno); los reales saldran del calibrador (ADR-07).
"""

CATEGORIAS: dict[str, dict] = {
    "bottle": {"umbral": 3.664, "defectos": ["broken_large", "broken_small", "contamination"]},
    "cable": {"umbral": 3.512, "defectos": ["bent_wire", "cable_swap", "cut_outer_insulation", "missing_cable"]},
    "capsule": {"umbral": 3.417, "defectos": ["crack", "faulty_imprint", "poke", "scratch", "squeeze"]},
    "hazelnut": {"umbral": 3.290, "defectos": ["crack", "cut", "hole", "print"]},
    "metal_nut": {"umbral": 3.845, "defectos": ["bent", "color", "flip", "scratch"]},
    "pill": {"umbral": 3.201, "defectos": ["color", "contamination", "crack", "faulty_imprint", "scratch"]},
    "screw": {"umbral": 3.105, "defectos": ["manipulated_front", "scratch_head", "scratch_neck", "thread_side", "thread_top"]},
    "toothbrush": {"umbral": 3.038, "defectos": ["defective"]},
    "transistor": {"umbral": 3.577, "defectos": ["bent_lead", "cut_lead", "damaged_case", "misplaced"]},
    "zipper": {"umbral": 3.882, "defectos": ["broken_teeth", "fabric_border", "rough", "split_teeth"]},
}

_IMAGENES_POR_TIPO = 2
_IMAGENES_BUENAS = 6


def listar_categorias() -> list[dict]:
    from . import artefactos

    return [
        {
            "nombre": nombre,
            "umbral": datos["umbral"],
            "imagenes": len(listar_imagenes(nombre)),
            **artefactos.estado_categoria(nombre),
        }
        for nombre, datos in CATEGORIAS.items()
    ]


def listar_imagenes(categoria: str) -> list[str]:
    datos = CATEGORIAS[categoria]
    ids = [f"good/{i:03d}.png" for i in range(_IMAGENES_BUENAS)]
    for defecto in datos["defectos"]:
        ids.extend(f"{defecto}/{i:03d}.png" for i in range(_IMAGENES_POR_TIPO))
    return ids


def es_imagen_valida(categoria: str, imagen_id: str) -> bool:
    return categoria in CATEGORIAS and imagen_id in listar_imagenes(categoria)
