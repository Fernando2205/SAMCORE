import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, mensajeDeError } from '../api'
import type { FilaHistorial } from '../api'

type Filtro = 'todas' | 'anomalas' | 'normales' | 'degradadas' | 'propias'

const FILTROS: { clave: Filtro, nombre: string }[] = [
  { clave: 'todas', nombre: 'Todas' },
  { clave: 'anomalas', nombre: 'Anómalas' },
  { clave: 'normales', nombre: 'Normales' },
  { clave: 'degradadas', nombre: 'ROI degradada' },
  { clave: 'propias', nombre: 'Imágenes propias' }
]

const COLUMNAS = 'grid-cols-[64px_150px_100px_1fr_90px_120px_150px_100px_120px]'

export function PaginaHistorial () {
  const navegar = useNavigate()
  const [filas, setFilas] = useState<FilaHistorial[] | null>(null)
  const [filtro, setFiltro] = useState<Filtro>('todas')
  const [error, setError] = useState<string | null>(null)

  const cargar = () => {
    api<FilaHistorial[]>('/historial').then(setFilas).catch(() => setFilas([]))
  }

  useEffect(cargar, [])

  if (filas === null) {
    return (
      <div className='flex flex-1 items-center justify-center'>
        <div className='h-9 w-9 animate-spin rounded-full border-3 border-papel-4 border-t-marca' />
      </div>
    )
  }

  const visibles = filas.filter(f => {
    if (filtro === 'anomalas') return f.veredicto === 'ANOMALO'
    if (filtro === 'normales') return f.veredicto === 'NORMAL'
    if (filtro === 'degradadas') return f.estado_roi === 'ROI_DEGRADADA'
    if (filtro === 'propias') return f.origen === 'propia'
    return true
  })
  const anomalas = filas.filter(f => f.veredicto === 'ANOMALO').length
  const propias = filas.filter(f => f.origen === 'propia').length

  const borrar = (fila: FilaHistorial, evento: React.MouseEvent) => {
    evento.stopPropagation()
    if (!window.confirm('¿Borrar esta inspección y sus imágenes de tu historial?')) return
    api(`/historial/${fila.id}`, { method: 'DELETE' })
      .then(() => setFilas(actuales => (actuales ?? []).filter(f => f.id !== fila.id)))
      .catch(e => setError(mensajeDeError(e)))
  }

  return (
    <div className='flex flex-1 flex-col px-12 pb-8'>
      <div className='mt-6 flex items-end justify-between'>
        <h1 className='font-serif text-[34px] leading-tight'>Tu historial de inspecciones</h1>
        <span className='font-mono text-[12px] text-texto-2'>
          {filas.length} inspecciones · {anomalas} anómalas · {propias} con imagen propia
        </span>
      </div>

      {error !== null && (
        <p className='mt-4 border border-anomalo/40 bg-anomalo/5 px-4 py-3 text-[13px] text-anomalo-texto'>{error}</p>
      )}

      {filas.length === 0
        ? (
          <div className='mt-10 flex flex-col items-center gap-3 self-center border border-hairline bg-white px-14 py-12 text-center'>
            <h2 className='font-serif text-xl'>Aún no has hecho inspecciones</h2>
            <p className='max-w-sm text-[13px] leading-relaxed text-texto-2'>
              Cuando inspecciones una imagen, quedará registrada aquí con su informe completo: original, ROI,
              mapa de calor, puntuación y veredicto.
            </p>
            <Link to='/' className='mt-1 bg-marca px-5 py-2.5 text-[13px] font-bold tracking-wide text-white'>
              Ir a la galería
            </Link>
          </div>
          )
        : (
          <>
            <div className='mt-4 flex gap-2 text-[13px]'>
              {FILTROS.map(f => (
                <button
                  key={f.clave}
                  onClick={() => setFiltro(f.clave)}
                  className={filtro === f.clave
                    ? 'border border-tinta bg-tinta px-4 py-1.5 font-semibold text-papel'
                    : 'border border-hairline bg-white px-4 py-1.5 text-texto-2 hover:border-tinta'}
                >
                  {f.nombre}
                </button>
              ))}
            </div>

            {visibles.length === 0
              ? (
                <div className='mt-6 flex flex-col items-center gap-3 self-center border border-hairline bg-white px-14 py-10 text-center'>
                  <h2 className='font-serif text-xl'>Ningún registro coincide</h2>
                  <p className='text-[13px] text-texto-2'>No hay inspecciones con el filtro aplicado.</p>
                  <button
                    onClick={() => setFiltro('todas')}
                    className='border border-tinta bg-white px-4 py-2 text-[13px] font-semibold'
                  >
                    Limpiar filtros
                  </button>
                </div>
                )
              : (
                <div className='mt-4 border border-hairline bg-white'>
                  <div className={`grid ${COLUMNAS} items-center gap-3 border-b-2 border-tinta px-5 py-3 font-mono text-[10.5px] uppercase tracking-[1.5px] text-texto-4`}>
                    <span /><span>Fecha</span><span>Categoría</span><span>Imagen</span><span>Origen</span>
                    <span>Veredicto</span><span>Puntuación / Umbral</span><span>ROI</span><span />
                  </div>
                  {visibles.map(f => (
                    <div
                      key={f.id}
                      role='button'
                      tabIndex={0}
                      onClick={() => navegar(`/inspeccion?id=${f.id}`)}
                      onKeyDown={e => { if (e.key === 'Enter') navegar(`/inspeccion?id=${f.id}`) }}
                      className={`grid ${COLUMNAS} cursor-pointer items-center gap-3 border-b border-hairline-2 px-5 py-2.5 text-left text-[13px] last:border-b-0 hover:bg-papel`}
                    >
                      <span className='flex h-12 w-12 items-center justify-center overflow-hidden border border-hairline bg-papel-2'>
                        <img src={`/api/historial/${f.id}/imagen/roi`} alt='' loading='lazy' className='h-full w-full object-cover' />
                      </span>
                      <span className='font-mono text-[12px] text-texto-2'>{f.creada_en}</span>
                      <span className='font-mono text-[12px] text-texto-2'>{f.categoria}</span>
                      <span className='truncate font-mono text-[12px] text-texto-3' title={f.imagen_id}>{f.imagen_id}</span>
                      <span className='font-mono text-[11.5px] text-texto-2'>{f.origen === 'propia' ? 'propia' : 'galería'}</span>
                      {f.veredicto === 'ANOMALO'
                        ? (
                          <span className='flex items-center gap-1.5 text-[12.5px] font-bold text-anomalo-texto'>
                            <span className='h-[7px] w-[7px] rounded-full bg-anomalo' />Anómalo
                          </span>
                          )
                        : (
                          <span className='flex items-center gap-1.5 text-[12.5px] font-bold text-vnormal-texto'>
                            <span className='h-[7px] w-[7px] rounded-full bg-vnormal' />Normal
                          </span>
                          )}
                      <span className='font-mono text-[12.5px]'>
                        {f.puntuacion.toFixed(3)} / {f.umbral.toFixed(3)}
                      </span>
                      {f.estado_roi === 'ROI_DEGRADADA'
                        ? (
                          <span className='flex items-center gap-1.5 text-[12px] text-alerta-texto'>
                            <span className='h-[7px] w-[7px] rounded-full bg-alerta' />Degradada
                          </span>
                          )
                        : (
                          <span className='flex items-center gap-1.5 text-[12px] text-texto-2'>
                            <span className='h-[7px] w-[7px] rounded-full bg-vnormal' />Correcta
                          </span>
                          )}
                      <span className='flex items-center justify-end gap-3'>
                        <span className='text-[12.5px] font-bold text-marca'>Ver</span>
                        <button
                          onClick={e => borrar(f, e)}
                          title='Borrar esta inspección y sus imágenes'
                          className='border border-hairline bg-white px-2 py-0.5 text-[11.5px] text-texto-3 hover:border-anomalo hover:text-anomalo-texto'
                        >
                          Borrar
                        </button>
                      </span>
                    </div>
                  ))}
                </div>
                )}
            <p className='mt-3 text-[12px] text-texto-4'>
              Selecciona una fila para reabrir el informe completo. Borrar una inspección elimina su registro y sus
              imágenes (original propia, ROI y mapa) del servidor.
            </p>
          </>
          )}
    </div>
  )
}
