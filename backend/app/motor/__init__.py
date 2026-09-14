"""Motor de inferencia real: SAM (segmentacion) + PatchCore (deteccion).

Modulos:
- seleccion: regla de seleccion de mascara (ADR-04) y caja cuadrada (ADR-10).
- segmentador: carga de SAM ViT-H y generacion automatica de mascaras.
- patchcore: extraccion de caracteristicas WideResNet-50 y puntuacion contra
  el banco de memoria (misma ruta de calculo que la implementacion de
  referencia usada en el experimento).
- reproyeccion: mapa de anomalias en coordenadas de la imagen original.
- orquestador: pipeline completo, con concurrencia acotada y topes por etapa.
"""
