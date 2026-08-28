import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api'
import type { FilaHistorial } from '../api'

type Filtro = 'todas' | 'anomalas' | 'normales' | 'degradadas'

const FILTROS: { clave: Filtro, nombre: string }[] = [
  { clave: 'todas', nombre: 'Todas' },
  { clave: 'anomalas', nombre: 'Anómalas' },
  { clave: 'normales', nombre: 'Normales' },
  { clave: 'degradadas', nombre: 'ROI degradada' }
]

export function PaginaHistorial () {
  const navegar = useNavigate()
  const [filas, setFilas] = useState<FilaHistorial[] | null>(null)
  const [filtro, setFiltro] = useState<Filtro>('todas')

  useEffect(() => {
    api<FilaHistorial[]>('/historial').then(setFilas).catch(() => setFilas([]))
  }, [])

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
    return true
  })
  const anomalas = filas.filter(f => f.veredicto === 'ANOMALO').length
  const degradadas = filas.filter(f => f.estado_roi === 'ROI_DEGRADADA').length

  return (
    <div className='flex flex-1 flex-col px-12 pb-8'>
      <div className='mt-6 flex items-end justify-between'>
        <h1 className='font-serif text-[34px] leading-tight'>Tu historial de inspecciones</h1>
        <span className='font-mono text-[12px] text-texto-2'>
          {filas.length} inspecciones · {anomalas} anómalas · {degradadas} con ROI degradada
        </span>
      </div>

      {filas.length === 0
        ? (
          <div className='mt-10 flex flex-col items-center gap-3 self-center border border-hairline bg-white px-14 py-12 text-center'>
            <h2 className='font-serif text-xl'>Aún no has hecho inspecciones</h2>
            <p className='max-w-sm text-[13px] leading-relaxed text-texto-2'>
              Cuando inspecciones una imagen, quedará registrada aquí con su categoría, puntuación y veredicto.
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
                  <div className='grid grid-cols-[150px_110px_1fr_120px_170px_110px_60px] gap-3 border-b-2 border-tinta px-5 py-3 font-mono text-[10.5px] uppercase tracking-[1.5px] text-texto-4'>
                    <span>Fecha</span><span>Categoría</span><span>Imagen</span><span>Veredicto</span>
                    <span>Puntuación / Umbral</span><span>ROI</span><span />
                  </div>
                  {visibles.map(f => (
                    <button
                      key={f.id}
                      onClick={() => navegar(`/inspeccion?categoria=${f.categoria}&imagen=${encodeURIComponent(f.imagen_id)}`)}
                      className='grid w-full grid-cols-[150px_110px_1fr_120px_170px_110px_60px] items-center gap-3 border-b border-hairline-2 px-5 py-3 text-left text-[13px] last:border-b-0 hover:bg-papel'
                    >
                      <span className='font-mono text-[12px] text-texto-2'>{f.creada_en}</span>
                      <span className='font-mono text-[12px] text-texto-2'>{f.categoria}</span>
                      <span className='font-mono text-[12px] text-texto-3'>{f.imagen_id}</span>
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
                      <span className='text-[12.5px] font-bold text-marca'>Ver</span>
                    </button>
                  ))}
                </div>
                )}
            <p className='mt-3 text-[12px] text-texto-4'>
              Selecciona una fila para reabrir el informe completo de esa inspección
              (el motor simulado es determinista: la misma imagen produce el mismo resultado).
            </p>
          </>
          )}
    </div>
  )
}
