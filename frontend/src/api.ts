export interface Sesion {
  correo: string
  rol: 'usuario' | 'administrador'
}

export interface Categoria {
  nombre: string
  umbral: number
  imagenes: number
  motor: string
  artefactos: boolean
}

export interface Galeria {
  categoria: string
  umbral: number
  imagenes: string[]
}

export interface Region {
  x: number
  y: number
  radio: number
  intensidad: number
}

export interface Resultado {
  id: number
  categoria: string
  imagen_id: string
  puntuacion: number
  umbral: number
  veredicto: 'ANOMALO' | 'NORMAL'
  estado_roi: 'ROI_OK' | 'ROI_DEGRADADA'
  regiones: Region[]
  tiempos_ms: { segmentacion: number, deteccion: number, total: number }
  motor: string
}

export interface FilaHistorial {
  id: number
  categoria: string
  imagen_id: string
  puntuacion: number
  umbral: number
  veredicto: 'ANOMALO' | 'NORMAL'
  estado_roi: 'ROI_OK' | 'ROI_DEGRADADA'
  duracion_ms: number
  creada_en: string
}

export interface EstadisticaCategoria {
  categoria: string
  inspecciones: number
  pct_anomalas: number
  pct_roi_degradada: number
  p95_ms: number
}

export interface Estadisticas {
  total: number
  anomalas: number
  pct_anomalas: number
  pct_roi_degradada: number
  p95_ms: number
  usuarios_activos: number
  por_categoria: EstadisticaCategoria[]
}

export interface UsuarioAdmin {
  id: number
  correo: string
  rol: string
  estado: 'pendiente' | 'activo' | 'desactivado' | 'rechazado'
  creado_en: string
  ultimo_acceso: string | null
  inspecciones: number
}

export class ErrorApi extends Error {
  codigo: string
  estado: number

  constructor (estado: number, codigo: string, mensaje: string) {
    super(mensaje)
    this.estado = estado
    this.codigo = codigo
  }
}

export async function api<T> (ruta: string, opciones: RequestInit = {}): Promise<T> {
  const respuesta = await fetch(`/api${ruta}`, {
    credentials: 'same-origin',
    headers: opciones.body ? { 'Content-Type': 'application/json' } : undefined,
    ...opciones
  })
  const cuerpo = await respuesta.json().catch(() => ({}))
  if (!respuesta.ok) {
    throw new ErrorApi(
      respuesta.status,
      typeof cuerpo.error === 'string' ? cuerpo.error : 'inesperado',
      typeof cuerpo.mensaje === 'string' ? cuerpo.mensaje : 'No fue posible completar la operación.'
    )
  }
  return cuerpo as T
}
