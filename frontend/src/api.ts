export interface Sesion {
  correo: string
  rol: 'usuario' | 'administrador'
}

export type EstadoMotor = 'real' | 'simulado' | 'cargando' | 'sin_banco' | 'error' | 'sin_iniciar'

export interface Salud {
  estado: string
  motor: EstadoMotor | string
  categorias_con_artefactos: string[]
  gpu: string
  carga_propia: boolean
}

export interface Categoria {
  nombre: string
  umbral: number
  imagenes: number
  motor: EstadoMotor
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
  pico: number
}

export interface Resultado {
  id: number
  categoria: string
  imagen_id: string
  origen: 'galeria' | 'propia'
  puntuacion: number
  umbral: number
  veredicto: 'ANOMALO' | 'NORMAL'
  estado_roi: 'ROI_OK' | 'ROI_DEGRADADA'
  caja: { sam: number[], roi: number[] }
  tam: number[]
  mascaras: number
  regiones: Region[]
  tiempos_ms: { segmentacion: number, deteccion: number, reproyeccion: number, total: number }
  motor: string
  imagenes: { original: string, roi: string, mapa: string, mascara: string }
  creada_en?: string
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
  origen: 'galeria' | 'propia'
  motor: string
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
  propias: number
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

async function procesar<T> (respuesta: Response): Promise<T> {
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

export async function api<T> (ruta: string, opciones: RequestInit = {}): Promise<T> {
  const respuesta = await fetch(`/api${ruta}`, {
    credentials: 'same-origin',
    headers: opciones.body ? { 'Content-Type': 'application/json' } : undefined,
    ...opciones
  })
  return await procesar<T>(respuesta)
}

export async function subirImagen (categoria: string, archivo: File): Promise<Resultado> {
  const formulario = new FormData()
  formulario.append('categoria', categoria)
  formulario.append('archivo', archivo, archivo.name)
  const respuesta = await fetch('/api/inspeccionar/propia', {
    method: 'POST',
    credentials: 'same-origin',
    body: formulario
  })
  return await procesar<Resultado>(respuesta)
}

export function mensajeDeError (e: unknown): string {
  return e instanceof ErrorApi ? e.message : 'No fue posible conectar con el servidor.'
}
