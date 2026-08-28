import { useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api, ErrorApi } from '../api'
import type { Resultado } from '../api'

const ETAPAS = [
  'Imagen preparada',
  'Segmentación del objeto (SAM)',
  'Selección y recorte de la ROI',
  'Comparación con el banco (PatchCore)',
  'Puntuación y veredicto'
]

function Figura ({ titulo, nota, children }: { titulo: string, nota: string, children?: React.ReactNode }) {
  return (
    <figure className='flex flex-col'>
      <div className='relative flex h-[300px] items-center justify-center overflow-hidden border border-tinta bg-papel-2'>
        {children}
      </div>
      <figcaption className='mt-2.5 border-t-[3px] border-tinta pt-2 font-mono text-[11px] text-texto-2'>
        {titulo} <span className='font-serif text-[13.5px] italic text-texto-2'>{nota}</span>
      </figcaption>
    </figure>
  )
}

function MarcadorImagen ({ imagenId }: { imagenId: string }) {
  return (
    <span className='flex flex-col items-center gap-2 font-mono text-[12px] text-texto-4'>
      <svg width='54' height='54' viewBox='0 0 24 24' fill='none' aria-hidden='true'>
        <rect x='3' y='5' width='18' height='14' rx='1' stroke='#a49c8d' strokeWidth='1.4' />
        <circle cx='9' cy='10' r='1.7' stroke='#a49c8d' strokeWidth='1.4' />
        <path d='M4 17 L9.5 12.5 L13.5 16 L16.5 13.5 L20 16.5' stroke='#a49c8d' strokeWidth='1.4' strokeLinejoin='round' />
      </svg>
      {imagenId}
      <span className='text-[10px]'>marcador de posición</span>
    </span>
  )
}

export function PaginaInspeccion () {
  const [parametros] = useSearchParams()
  const categoria = parametros.get('categoria') ?? ''
  const imagen = parametros.get('imagen') ?? ''
  const [etapa, setEtapa] = useState(0)
  const [resultado, setResultado] = useState<Resultado | null>(null)
  const [error, setError] = useState<string | null>(null)
  const listoRef = useRef<Resultado | null>(null)

  useEffect(() => {
    setEtapa(0)
    setResultado(null)
    setError(null)
    listoRef.current = null

    api<Resultado>('/inspeccionar', {
      method: 'POST',
      body: JSON.stringify({ categoria, imagen_id: imagen })
    })
      .then(r => { listoRef.current = r })
      .catch(e => setError(e instanceof ErrorApi ? e.message : 'No fue posible conectar con el servidor.'))

    const temporizador = setInterval(() => {
      setEtapa(anterior => {
        if (anterior >= ETAPAS.length) return anterior
        if (anterior === ETAPAS.length - 1) {
          if (listoRef.current !== null) {
            setResultado(listoRef.current)
            return anterior + 1
          }
          return anterior
        }
        return anterior + 1
      })
    }, 450)
    return () => clearInterval(temporizador)
  }, [categoria, imagen])

  const anomalo = resultado?.veredicto === 'ANOMALO'
  const degradada = resultado?.estado_roi === 'ROI_DEGRADADA'
  const pctBarra = resultado === null ? 0 : Math.min(100, Math.round((resultado.puntuacion / (resultado.umbral / 0.68)) * 100))

  return (
    <div className='flex flex-1 flex-col px-12 pb-8'>
      <div className='mt-6 flex items-end justify-between'>
        <div className='flex flex-col gap-1.5'>
          <Link to='/' className='flex items-center gap-2 text-[13px] font-semibold text-marca'>
            ← Volver a la galería
          </Link>
          <h1 className='font-serif text-[34px] leading-tight'>
            {resultado === null && error === null ? 'Analizando la imagen…' : 'Informe de inspección'}
          </h1>
        </div>
        <div className='text-right font-mono text-[12px] leading-relaxed text-texto-2'>
          {categoria} / {imagen}
        </div>
      </div>

      {error !== null && (
        <div className='mt-6 flex max-w-xl flex-col gap-3 border border-anomalo/40 bg-anomalo/5 px-5 py-4'>
          <span className='text-[13.5px] text-anomalo-texto'>{error}</span>
          <Link to='/' className='self-start border border-tinta bg-white px-4 py-2 text-[13px] font-semibold'>
            Volver a la galería
          </Link>
        </div>
      )}

      {degradada && (
        <div className='mt-4 flex items-center gap-2.5 border border-alerta/40 bg-alerta/5 px-4 py-2.5 text-[13px] text-alerta-texto'>
          <strong>ROI degradada:</strong>
          <span>
            no se encontró una máscara confiable del objeto y el análisis se realizó sobre la imagen
            casi completa. Interpreta la localización con cautela.
          </span>
        </div>
      )}

      {error === null && (
        <div className='mt-5 flex flex-1 items-start gap-9'>
          <div className='grid flex-1 grid-cols-3 gap-5'>
            <Figura titulo='Fig. 1 — Original.' nota='Imagen de prueba tal como está en el dataset.'>
              <MarcadorImagen imagenId={imagen} />
            </Figura>
            {resultado === null
              ? (
                <>
                  <div className='h-[300px] animate-pulse border border-dashed border-borde-input bg-papel-3' />
                  <div className='h-[300px] animate-pulse border border-dashed border-borde-input bg-papel-3' />
                </>
                )
              : (
                <>
                  <Figura titulo='Fig. 2 — ROI.' nota={degradada ? 'Recorte de respaldo: abarca casi toda la imagen.' : 'Segmentada por SAM, recorte por caja.'}>
                    <span
                      className={`absolute border-2 border-dashed ${degradada ? 'inset-2 border-alerta/65' : 'inset-8 border-marca/65'}`}
                    />
                    <MarcadorImagen imagenId={imagen} />
                  </Figura>
                  <Figura titulo='Fig. 3 — Mapa de calor.' nota={anomalo ? 'En coordenadas de la imagen original.' : 'Sin regiones que se acerquen al umbral.'}>
                    <MarcadorImagen imagenId={imagen} />
                    {resultado.regiones.map((r, i) => (
                      <span
                        key={i}
                        className='pointer-events-none absolute rounded-full'
                        style={{
                          left: `${(r.x - r.radio) * 100}%`,
                          top: `${(r.y - r.radio) * 100}%`,
                          width: `${r.radio * 2 * 100}%`,
                          height: `${r.radio * 2 * 100}%`,
                          background: `radial-gradient(closest-side, rgba(216,74,56,${0.75 * r.intensidad}), rgba(216,150,40,${0.4 * r.intensidad}) 55%, transparent 75%)`
                        }}
                      />
                    ))}
                    {!anomalo && (
                      <span className='pointer-events-none absolute inset-0' style={{ background: 'rgba(72,108,220,0.08)' }} />
                    )}
                  </Figura>
                </>
                )}
          </div>

          <aside className='flex w-[330px] shrink-0 flex-col gap-5 border-l border-hairline pl-8'>
            {resultado === null
              ? (
                <div>
                  <span className='font-mono text-[11px] uppercase tracking-[2px] text-texto-4'>Progreso del pipeline</span>
                  <ul className='mt-3 flex flex-col'>
                    {ETAPAS.map((nombre, i) => {
                      const hecha = i < etapa
                      const activa = i === etapa
                      return (
                        <li key={nombre} className='flex items-center gap-2.5 py-2 text-[13px]'>
                          {hecha && (
                            <svg width='17' height='17' viewBox='0 0 24 24' fill='none' aria-hidden='true'>
                              <circle cx='12' cy='12' r='9.5' stroke='#1e9e6a' strokeWidth='2' />
                              <path d='M7.5 12.5 L10.8 15.5 L16.5 9' stroke='#1e9e6a' strokeWidth='2' strokeLinecap='round' strokeLinejoin='round' />
                            </svg>
                          )}
                          {activa && <span className='h-[15px] w-[15px] animate-spin rounded-full border-[2.5px] border-papel-4 border-t-marca' />}
                          {!hecha && !activa && <span className='h-[15px] w-[15px] rounded-full border-2 border-borde-input' />}
                          <span className={activa ? 'font-semibold text-tinta' : hecha ? 'text-texto-2' : 'text-texto-4'}>
                            {nombre}
                          </span>
                        </li>
                      )
                    })}
                  </ul>
                  <p className='mt-4 border-t border-hairline pt-3.5 text-[12px] leading-relaxed text-texto-3'>
                    Si el servicio estaba suspendido por inactividad, el primer análisis puede tardar
                    entre 1 y 3 minutos mientras arranca.
                  </p>
                </div>
                )
              : (
                <>
                  <section>
                    <span className='font-mono text-[11px] uppercase tracking-[2px] text-texto-4'>01 — Veredicto</span>
                    <div
                      className={`mt-3.5 inline-block -rotate-2 border-[2.5px] px-5 py-2.5 text-[17px] font-bold tracking-[3px] ${anomalo ? 'border-anomalo bg-anomalo/5 text-anomalo-texto' : 'border-vnormal bg-vnormal/5 text-vnormal-texto'}`}
                    >
                      {anomalo ? 'ANÓMALO' : 'NORMAL'}
                    </div>
                    <div className='mt-4 flex items-baseline gap-3.5'>
                      <span className='font-serif text-[58px] leading-none'>{resultado.puntuacion.toFixed(3)}</span>
                      <span className='font-mono text-[12px] leading-snug text-texto-2'>
                        puntuación<br />umbral {resultado.umbral.toFixed(3)}
                      </span>
                    </div>
                    <div className='relative mt-4 h-1.5 bg-papel-4'>
                      <span
                        className='absolute inset-y-0 left-0'
                        style={{
                          width: `${pctBarra}%`,
                          background: anomalo
                            ? 'linear-gradient(90deg, #0c7a6b, #d89628 58%, #d84a38)'
                            : 'linear-gradient(90deg, #0c7a6b, #3a9c88)'
                        }}
                      />
                      <span className='absolute -top-[5px] left-[68%] h-4 w-0.5 bg-tinta' />
                    </div>
                    <div className='mt-1 mr-[24%] text-right font-mono text-[10px] text-texto-4'>umbral</div>
                    <p className='mt-2.5 text-[12.5px] leading-relaxed text-texto-2'>
                      {anomalo
                        ? 'La puntuación supera el umbral calibrado con imágenes normales de validación.'
                        : 'La puntuación queda por debajo del umbral calibrado con imágenes normales de validación.'}
                    </p>
                  </section>

                  <section className='border-t border-hairline pt-4'>
                    <span className='font-mono text-[11px] uppercase tracking-[2px] text-texto-4'>02 — Estado de la ROI</span>
                    {degradada
                      ? (
                        <div className='mt-3 inline-flex items-center gap-2 border border-alerta/45 bg-alerta/10 px-3.5 py-1.5 text-[13px] font-bold text-alerta-texto'>
                          ROI DEGRADADA
                        </div>
                        )
                      : (
                        <div className='mt-3 flex items-center gap-2 text-[14px] font-semibold'>
                          <span className='h-2 w-2 rounded-full bg-vnormal' /> ROI correcta
                        </div>
                        )}
                    <p className='mt-2 text-[12.5px] leading-relaxed text-texto-2'>
                      {degradada
                        ? 'Ninguna máscara superó los filtros de selección; se usó la de mayor área.'
                        : 'La máscara del objeto superó los filtros de la regla de selección.'}
                    </p>
                  </section>

                  <section className='border-t border-hairline pt-4'>
                    <span className='font-mono text-[11px] uppercase tracking-[2px] text-texto-4'>03 — Tiempos de inferencia</span>
                    <div className='mt-3 flex justify-between text-[13px] text-texto-2'>
                      <span>Segmentación</span>
                      <span className='font-mono'>{resultado.tiempos_ms.segmentacion.toLocaleString('es-CO')} ms</span>
                    </div>
                    <div className='mt-1.5 flex justify-between text-[13px] text-texto-2'>
                      <span>Detección</span>
                      <span className='font-mono'>{resultado.tiempos_ms.deteccion.toLocaleString('es-CO')} ms</span>
                    </div>
                    <div className='mt-2.5 flex justify-between border-t border-hairline pt-2.5 text-[13px] font-bold'>
                      <span>Total</span>
                      <span className='font-mono'>{resultado.tiempos_ms.total.toLocaleString('es-CO')} ms</span>
                    </div>
                    <p className='mt-3 font-mono text-[10.5px] text-texto-4'>motor: {resultado.motor}</p>
                  </section>
                </>
                )}
          </aside>
        </div>
      )}
    </div>
  )
}
