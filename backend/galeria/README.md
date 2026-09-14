# Galería cerrada

Subconjunto del conjunto de prueba de MVTec AD que la aplicación ofrece
para inspeccionar (ADR-08). Estructura esperada:

```
backend/galeria/<categoria>/<tipo>/<archivo>.png
```

Por ejemplo `backend/galeria/capsule/good/000.png` o
`backend/galeria/transistor/bent_lead/001.png`. La API construye al
arrancar la lista cerrada de identificadores (`<tipo>/<archivo>`) a partir
de esta carpeta; no existe otra forma de referirse a una imagen.

Las imágenes no se versionan en este repositorio (licencia CC BY-NC-SA
4.0 de MVTec Software GmbH; la aplicación muestra la atribución). Se
exportan desde el cuaderno experimental con la celda de "exportar galería"
(6 imágenes normales y 2 por tipo de defecto para cada categoría con
banco) y se copian aquí o a la imagen de despliegue.
