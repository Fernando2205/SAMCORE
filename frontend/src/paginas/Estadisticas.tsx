import { useEffect, useState } from 'react'
import { api } from '../api'
import type { Estadisticas } from '../api'

function Kpi ({ rotulo, valor, detalle }: { rotulo: string, valor: string, detalle?: string }) {
  return (
    <div className='border border-hairline bg-white px-5 py-4'>
      <span className='font-mono text-[10.5px] uppercase tracking-[2px] text-texto-4'>{rotulo}</span>
      <div className='mt-2 flex items-baseline gap-2.5'>
        <span className='font-serif text-[38px] leading-none'>{valor}</span>
        {detalle !== undefined && <span className='font-mono text-[13px] text-texto-2'>{detalle}</span>}
      </div>
    </div>
  )
}

export function PaginaEstadisticas () {
  const [datos, setDatos] = useState<Estadisticas | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    api<Estadisticas>('/estadisticas').then(setDatos).catch(() => setError(true))
  }, [])

  if (error) {
    return <p className='m-12 border border-anomalo/40 bg-anomalo/5 px-4 py-3 text-[13px] text-anomalo-texto'>No fue posible cargar las estadísticas.</p>
  }
  if (datos === null) {
    return (
      <div className='flex flex-1 items-center justify-center'>
        <div className='h-9 w-9 animate-spin rounded-full border-3 border-papel-4 border-t-marca' />
      </div>
    )
  }

  const maximo = Math.max(1, ...datos.por_categoria.map(c => c.inspecciones))

  return (
    <div className='flex flex-1 flex-col px-12 pb-8'>
      <div className='mt-6 flex items-end justify-between'>
        <div>
          <h1 className='font-serif text-[34px] leading-tight'>Estadísticas de uso</h1>
          <p className='mt-1 text-[12.5px] text-texto-3'>
            Métricas globales y anónimas de la plataforma, calculadas del registro de inspecciones.
          </p>
        </div>
        <span className='font-mono text-[12px] text-texto-2'>{datos.usuarios_activos} cuentas activas</span>
      </div>

      {datos.total === 0
        ? (
          <div className='mt-10 flex flex-col items-center gap-3 self-center border border-hairline bg-white px-14 py-12 text-center'>
            <h2 className='font-serif text-xl'>Aún no hay actividad registrada</h2>
            <p className='max-w-sm text-[13px] leading-relaxed text-texto-2'>
              Las estadísticas se calculan con las inspecciones de todas las cuentas.
              Vuelve cuando la plataforma tenga uso.
            </p>
          </div>
          )
        : (
          <>
            <div className='mt-5 grid grid-cols-4 gap-4'>
              <Kpi rotulo='Inspecciones' valor={datos.total.toLocaleString('es-CO')} />
              <Kpi rotulo='Veredictos anómalos' valor={String(datos.anomalas)} detalle={`${datos.pct_anomalas} %`} />
              <Kpi rotulo='Tasa de ROI degradada' valor={`${datos.pct_roi_degradada} %`} />
              <Kpi rotulo='Tiempo total p95' valor={`${datos.p95_ms.toLocaleString('es-CO')} ms`} />
            </div>

            <div className='mt-4 flex flex-1 items-stretch gap-4'>
              <div className='flex flex-[1.35] flex-col border border-hairline bg-white px-6 py-5'>
                <h2 className='font-serif text-[19px]'>Inspecciones por categoría</h2>
                <div className='mt-3.5 flex flex-col gap-2'>
                  {datos.por_categoria.map(c => (
                    <div key={c.categoria} className='flex items-center gap-3'>
                      <span className='w-[88px] text-right font-mono text-[12px] text-texto-2'>{c.categoria}</span>
                      <span className='flex-1 bg-papel-3'>
                        <span
                          className='block h-[13px] bg-marca'
                          style={{ width: `${Math.round((c.inspecciones / maximo) * 100)}%` }}
                        />
                      </span>
                      <span className='w-10 font-mono text-[12px] text-texto-2'>{c.inspecciones}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div className='flex flex-1 flex-col border border-hairline bg-white px-6 py-5'>
                <h2 className='font-serif text-[19px]'>Detalle por categoría</h2>
                <div className='mt-3 grid grid-cols-[1.3fr_1fr_1fr_1fr_1fr] gap-2 border-b-2 border-tinta pb-2 font-mono text-[10px] uppercase tracking-[1.2px] text-texto-4'>
                  <span>Categoría</span>
                  <span className='text-right'>Insp.</span>
                  <span className='text-right'>% anóm.</span>
                  <span className='text-right'>ROI deg.</span>
                  <span className='text-right'>p95 ms</span>
                </div>
                {datos.por_categoria.map(c => (
                  <div
                    key={c.categoria}
                    className='grid grid-cols-[1.3fr_1fr_1fr_1fr_1fr] gap-2 border-b border-hairline-2 py-1.5 font-mono text-[12px] text-texto-2 last:border-b-0'
                  >
                    <span>{c.categoria}</span>
                    <span className='text-right'>{c.inspecciones}</span>
                    <span className='text-right'>{c.pct_anomalas}</span>
                    <span className='text-right'>{c.pct_roi_degradada}</span>
                    <span className='text-right'>{c.p95_ms.toLocaleString('es-CO')}</span>
                  </div>
                ))}
              </div>
            </div>
          </>
          )}
    </div>
  )
}
