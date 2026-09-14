import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { api, mensajeDeError, subirImagen } from '../api'
import type { Resultado } from '../api'

const ETAPAS = [
  'Imagen preparada',
  'Segmentación del objeto (SAM)',
  'Selección y recorte de la ROI',
  'Comparación con el banco (PatchCore)',
  'Puntuación y veredicto'
]

interface EstadoNavegacion {
  archivo?: File
  categoria?: string
}

function Figura ({ titulo, nota, children }: { titulo: string, nota: string, children?: React.ReactNode }) {
  return (
    <figure className='flex min-w-0 flex-col'>
      <div className='relative flex h-[300px] items-center justify-center overflow-hidden border border-tinta bg-papel-2'>
        {children}
      </div>
      <figcaption className='mt-2.5 border-t-[3px] border-tinta pt-2 font-mono text-[11px] text-texto-2'>
        {titulo} <span className='font-serif text-[13.5px] italic text-texto-2'>{nota}</span>
      </figcaption>
    </figure>
  )
}

function Esqueleto () {
  return <div className='h-[300px] animate-pulse border border-dashed border-borde-input bg-papel-3' />
}

function Caja ({ caja, tam, discontinua }: { caja: number[], tam: number[], discontinua: boolean }) {
  const [x0, y0, x1, y1] = caja
  const [ancho, alto] = tam
  return (
    <span
      className={`pointer-events-none absolute border-2 border-marca ${discontinua ? 'border-dashed' : ''}`}
      style={{
        left: `${(100 * x0) / ancho}%`,
        top: `${(100 * y0) / alto}%`,
        width: `${(100 * (x1 - x0 + 1)) / ancho}%`,
        height: `${(100 * (y1 - y0 + 1)) / alto}%`
      }}
    />
  )
}

function Segmentacion ({ resultado }: { resultado: Resultado }) {
  const ladoRoi = resultado.caja.roi[2] - resultado.caja.roi[0] + 1
  const ladoImagen = Math.max(resultado.tam[0], resultado.tam[1])
  return (
    <span className='relative inline-block max-h-full max-w-full'>
      <img src={resultado.imagenes.original} alt='' className='max-h-[298px] max-w-full object-contain' />
      <img src={resultado.imagenes.mascara} alt='Máscara elegida por SAM' className='absolute inset-0 h-full w-full object-contain' />
      <Caja caja={resultado.caja.sam} tam={resultado.tam} discontinua={false} />
      {ladoRoi < ladoImagen && <Caja caja={resultado.caja.roi} tam={resultado.tam} discontinua />}
      <img
        src={resultado.imagenes.roi}
        alt='Recorte que analiza PatchCore'
        title='Recorte que analiza PatchCore'
        className='absolute bottom-1 right-1 w-[30%] border border-tinta bg-white shadow'
      />
    </span>
  )
}

export function PaginaInspeccion () {
  const [parametros] = useSearchParams()
  const ubicacion = useLocation()
  const navegar = useNavigate()
  const estadoNavegacion = (ubicacion.state ?? {}) as EstadoNavegacion
  const idInforme = parametros.get('id')
  const archivo = estadoNavegacion.archivo
  const categoria = parametros.get('categoria') ?? estadoNavegacion.categoria ?? ''
  const imagen = parametros.get('imagen') ?? ''
  const numeroGaleria = parametros.get('n')
  const reabriendo = idInforme !== null

  const [etapa, setEtapa] = useState(0)
  const [resultado, setResultado] = useState<Resultado | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [borrando, setBorrando] = useState(false)
  const listoRef = useRef<Resultado | null>(null)

  const vistaPreviaPropia = useMemo(() => (archivo !== undefined ? URL.createObjectURL(archivo) : null), [archivo])
  useEffect(() => () => { if (vistaPreviaPropia !== null) URL.revokeObjectURL(vistaPreviaPropia) }, [vistaPreviaPropia])

  useEffect(() => {
    setEtapa(0)
    setResultado(null)
    setError(null)
    listoRef.current = null

    let solicitud: Promise<Resultado>
    if (idInforme !== null) {
      solicitud = api<Resultado>(`/historial/${idInforme}/informe`)
    } else if (archivo !== undefined) {
      solicitud = subirImagen(categoria, archivo)
    } else if (categoria !== '' && imagen !== '') {
      solicitud = api<Resultado>('/inspeccionar', {
        method: 'POST',
        body: JSON.stringify({ categoria, imagen_id: imagen })
      })
    } else {
      setError('No hay ninguna imagen seleccionada.')
      return
    }

    solicitud
      .then(r => {
        listoRef.current = r
        if (idInforme !== null) {
          setResultado(r)
          setEtapa(ETAPAS.length)
        }
      })
      .catch(e => setError(mensajeDeError(e)))

    if (idInforme !== null) return
    const temporizador = setInterval(() => {
      setEtapa(anterior => {
        if (anterior >= ETAPAS.length) return anterior
        if (anterior === 1 && listoRef.current === null) return anterior
        if (anterior === ETAPAS.length - 1) {
          if (listoRef.current !== null) {
            setResultado(listoRef.current)
            return anterior + 1
          }
          return anterior
        }
        return anterior + 1
      })
    }, 350)
    return () => clearInterval(temporizador)
  }, [idInforme, categoria, imagen, archivo])

  const anomalo = resultado?.veredicto === 'ANOMALO'
  const degradada = resultado?.estado_roi === 'ROI_DEGRADADA'
  const propia = resultado?.origen === 'propia' || (resultado === null && archivo !== undefined)
  const pctBarra = resultado === null ? 0 : Math.min(100, Math.round((resultado.puntuacion / (resultado.umbral / 0.68)) * 100))
  const urlOriginal = resultado?.imagenes.original ?? vistaPreviaPropia ?? (categoria !== '' && imagen !== '' ? `/api/galeria/${categoria}/imagen/${imagen}` : null)
  const tipoReal = resultado?.origen === 'galeria' ? resultado.imagen_id.split('/')[0] : null
  const etiquetaImagen = archivo !== undefined
    ? `${categoria} / ${archivo.name}`
    : resultado?.origen === 'propia'
      ? `${resultado.categoria} / imagen propia`
      : `${resultado?.categoria ?? categoria} / imagen de la galería${numeroGaleria !== null ? ` ${numeroGaleria.padStart(2, '0')}` : ''}`

  const borrar = () => {
    if (resultado === null || !window.confirm('¿Borrar esta inspección y sus imágenes de tu historial?')) return
    setBorrando(true)
    api(`/historial/${resultado.id}`, { method: 'DELETE' })
      .then(() => navegar('/historial'))
      .catch(e => { setError(mensajeDeError(e)); setBorrando(false) })
  }

  return (
    <div className='flex flex-1 flex-col px-12 pb-8'>
      <div className='mt-6 flex items-end justify-between'>
        <div className='flex flex-col gap-1.5'>
          <Link to={reabriendo ? '/historial' : '/'} className='flex items-center gap-2 text-[13px] font-semibold text-marca'>
            ← {reabriendo ? 'Volver al historial' : 'Volver a la galería'}
          </Link>
          <h1 className='font-serif text-[34px] leading-tight'>
            {resultado === null && error === null ? 'Analizando la imagen…' : 'Informe de inspección'}
          </h1>
        </div>
        <div className='text-right font-mono text-[12px] leading-relaxed text-texto-2'>
          {etiquetaImagen}
          {resultado?.creada_en !== undefined && <><br />{resultado.creada_en}</>}
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

      {propia && error === null && (
        <div className='mt-4 flex items-start gap-2.5 border border-marca/40 bg-marca/5 px-4 py-2.5 text-[13px] text-[#2f4a44]'>
          <strong className='shrink-0'>Veredicto orientativo.</strong>
          <span>
            El sistema no verifica que la imagen pertenezca a la categoría elegida ni detecta imágenes fuera de
            distribución. La imagen se guarda re-codificada, sin metadatos, en tu historial, y puedes borrarla
            cuando quieras.
          </span>
        </div>
      )}

      {degradada && (
        <div className='mt-4 flex items-center gap-2.5 border border-alerta/40 bg-alerta/5 px-4 py-2.5 text-[13px] text-alerta-texto'>
          <strong>ROI degradada:</strong>
          <span>
            ninguna máscara superó los filtros de la regla de selección y el análisis se realizó sobre la máscara
            de mayor área. Interpreta la localización con cautela.
          </span>
        </div>
      )}

      {error === null && (
        <div className='mt-5 flex flex-1 items-start gap-9'>
          <div className='grid min-w-0 flex-1 grid-cols-3 gap-5'>
            <Figura titulo='Fig. 1 — Original.' nota={propia ? 'Imagen propia, re-codificada.' : 'Imagen de prueba tal como está en el dataset.'}>
              {urlOriginal !== null && <img src={urlOriginal} alt='Original' className='max-h-full max-w-full object-contain' />}
            </Figura>
            {resultado === null
              ? (
                <>
                  <Esqueleto />
                  <Esqueleto />
                </>
                )
              : (
                <>
                  <Figura
                    titulo='Fig. 2 — Segmentación.'
                    nota={degradada
                      ? 'Máscara de respaldo (mayor área) y recorte que analiza PatchCore.'
                      : `Máscara elegida por SAM, su caja y la caja cuadrada con margen (${resultado.caja.roi[2] - resultado.caja.roi[0] + 1} px). Recuadro: recorte que analiza PatchCore.`}
                  >
                    <Segmentacion resultado={resultado} />
                  </Figura>
                  <Figura titulo='Fig. 3 — Mapa de calor.' nota={anomalo ? 'Re-proyectado a coordenadas de la imagen original.' : 'Sin regiones que se acerquen al umbral.'}>
                    <span className='relative inline-block max-h-full max-w-full'>
                      <img src={resultado.imagenes.original} alt='' className='max-h-[298px] max-w-full object-contain' />
                      <img src={resultado.imagenes.mapa} alt='Mapa de anomalías' className='absolute inset-0 h-full w-full object-contain' />
                    </span>
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
                    La segmentación con SAM tarda alrededor de 10 segundos por imagen en la GPU del servicio.
                    Si el servicio estaba suspendido por inactividad, el primer análisis puede tardar entre 1 y 3
                    minutos mientras arranca.
                  </p>
                </div>
                )
              : (
                <>
                  <section>
                    <span className='font-mono text-[11px] uppercase tracking-[2px] text-texto-4'>
                      01 — Veredicto{propia ? ' (orientativo)' : ''}
                    </span>
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
                      {' '}{resultado.mascaras} máscaras candidatas.
                    </p>
                  </section>

                  <section className='border-t border-hairline pt-4'>
                    <span className='font-mono text-[11px] uppercase tracking-[2px] text-texto-4'>03 — Origen de la imagen</span>
                    {propia
                      ? (
                        <>
                          <p className='mt-2 text-[12.5px] leading-relaxed text-texto-2'>
                            Imagen propia · guardada re-codificada y sin metadatos · en tu historial · borrable.
                          </p>
                          <button
                            onClick={borrar}
                            disabled={borrando}
                            className='mt-3 border border-anomalo/50 bg-white px-3.5 py-1.5 text-[12.5px] font-semibold text-anomalo-texto hover:bg-anomalo/5 disabled:opacity-50'
                          >
                            {borrando ? 'Borrando…' : 'Borrar del historial'}
                          </button>
                        </>
                        )
                      : (
                        <p className='mt-2 text-[12.5px] leading-relaxed text-texto-2'>
                          Galería de prueba de MVTec AD (CC BY-NC-SA 4.0). Tipo real en el dataset:{' '}
                          <strong className={tipoReal === 'good' ? 'text-vnormal-texto' : 'text-anomalo-texto'}>
                            {tipoReal === 'good' ? 'sin defecto' : tipoReal}
                          </strong>
                          {tipoReal !== null && (
                            <> · {(tipoReal === 'good') === (resultado.veredicto === 'NORMAL') ? 'el veredicto coincide' : 'el veredicto no coincide'}</>
                          )}
                        </p>
                        )}
                  </section>

                  <section className='border-t border-hairline pt-4'>
                    <span className='font-mono text-[11px] uppercase tracking-[2px] text-texto-4'>04 — Tiempos de inferencia</span>
                    <div className='mt-3 flex justify-between text-[13px] text-texto-2'>
                      <span>Segmentación</span>
                      <span className='font-mono'>{resultado.tiempos_ms.segmentacion.toLocaleString('es-CO')} ms</span>
                    </div>
                    <div className='mt-1.5 flex justify-between text-[13px] text-texto-2'>
                      <span>Detección</span>
                      <span className='font-mono'>{resultado.tiempos_ms.deteccion.toLocaleString('es-CO')} ms</span>
                    </div>
                    <div className='mt-1.5 flex justify-between text-[13px] text-texto-2'>
                      <span>Re-proyección</span>
                      <span className='font-mono'>{resultado.tiempos_ms.reproyeccion.toLocaleString('es-CO')} ms</span>
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
