import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import type { Estadisticas, EstadisticaCategoria, IntervaloHistograma, MetricasExperimento, ParMetrica } from '../api'

// Colores validados (contraste y visión de color): veredicto = estado,
// etapas = identidad. El texto nunca lleva el color del dato.
const COLOR_NORMAL = '#1e9e6a'
const COLOR_ANOMALO = '#d84a38'
const COLOR_SEGMENTACION = '#0f9683'
const COLOR_DETECCION = '#b07c1f'
const COLOR_REJILLA = '#e8e1d3'
const COLOR_TINTA = '#16181a'

const fmt = (n: number, dec = 0) => n.toLocaleString('es-CO', { maximumFractionDigits: dec, minimumFractionDigits: dec })
const fmtMs = (ms: number | null) => (ms === null ? '—' : ms >= 1000 ? `${fmt(ms / 1000, 1)} s` : `${fmt(ms)} ms`)

const retraso = (ms: number): React.CSSProperties => ({ '--retraso': `${ms}ms` } as React.CSSProperties)

/** True la primera vez que el elemento entra en pantalla; las animaciones esperan a ese momento. */
function useEnVista<T extends HTMLElement> (): [React.RefObject<T | null>, boolean] {
  const ref = useRef<T | null>(null)
  const [visto, setVisto] = useState(false)
  useEffect(() => {
    const el = ref.current
    if (el === null || visto) return
    if (typeof IntersectionObserver === 'undefined') {
      setVisto(true)
      return
    }
    const observador = new IntersectionObserver(entradas => {
      if (entradas.some(e => e.isIntersecting)) {
        setVisto(true)
        observador.disconnect()
      }
    }, { threshold: 0.15 })
    observador.observe(el)
    return () => observador.disconnect()
  }, [visto])
  return [ref, visto]
}

/** Cuenta de 0 al valor con una curva suave; sin animación si el sistema pide menos movimiento. */
function useContador (valor: number, duracion = 900): number {
  const [actual, setActual] = useState(0)
  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      setActual(valor)
      return
    }
    const inicio = performance.now()
    let marco = 0
    const paso = (t: number) => {
      const p = Math.min(1, (t - inicio) / duracion)
      setActual(valor * (1 - Math.pow(1 - p, 3)))
      if (p < 1) marco = requestAnimationFrame(paso)
    }
    marco = requestAnimationFrame(paso)
    return () => cancelAnimationFrame(marco)
  }, [valor, duracion])
  return actual
}

interface Aviso {
  x: number
  y: number
  titulo: string
  lineas: string[]
}

function Tooltip ({ aviso }: { aviso: Aviso | null }) {
  if (aviso === null) return null
  return (
    <div
      className='pointer-events-none absolute z-10 border border-tinta bg-white px-3 py-2 shadow-sm'
      style={{ left: aviso.x + 12, top: aviso.y + 12 }}
    >
      <div className='font-mono text-[11px] text-texto-3'>{aviso.titulo}</div>
      {aviso.lineas.map(l => <div key={l} className='text-[13px] font-semibold text-tinta'>{l}</div>)}
    </div>
  )
}

function Leyenda ({ items }: { items: { color: string, nombre: string, hueco?: boolean }[] }) {
  return (
    <div className='mt-3 flex flex-wrap gap-x-5 gap-y-1 font-mono text-[11px] text-texto-2'>
      {items.map(i => (
        <span key={i.nombre} className='flex items-center gap-1.5'>
          <span
            className='inline-block h-[9px] w-[9px] rounded-full'
            style={i.hueco === true ? { border: `2px solid ${i.color}`, background: 'white' } : { background: i.color }}
          />
          {i.nombre}
        </span>
      ))}
    </div>
  )
}

function usarAviso () {
  const [aviso, setAviso] = useState<Aviso | null>(null)
  const mostrar = (e: React.PointerEvent | React.FocusEvent, titulo: string, lineas: string[]) => {
    const tarjeta = (e.currentTarget as Element).closest('[data-tarjeta]') as HTMLElement | null
    const caja = tarjeta?.getBoundingClientRect()
    const cx = 'clientX' in e ? e.clientX : (e.currentTarget as Element).getBoundingClientRect().left
    const cy = 'clientY' in e ? e.clientY : (e.currentTarget as Element).getBoundingClientRect().top
    setAviso({ x: cx - (caja?.left ?? 0), y: cy - (caja?.top ?? 0), titulo, lineas })
  }
  return { aviso, mostrar, ocultar: () => setAviso(null) }
}

function ticks (maximo: number, n = 4): number[] {
  if (maximo <= 0) return [0]
  const bruto = maximo / n
  const potencia = Math.pow(10, Math.floor(Math.log10(bruto)))
  const paso = [1, 2, 5, 10].map(m => m * potencia).find(p => p >= bruto) ?? potencia
  const salida: number[] = []
  for (let v = 0; v <= maximo + paso * 0.001; v += paso) salida.push(Math.round(v * 1000) / 1000)
  return salida
}

// ---------------------------------------------------------------- histograma
function Histograma ({ intervalos }: { intervalos: IntervaloHistograma[] }) {
  const { aviso, mostrar, ocultar } = usarAviso()
  const ancho = 640; const alto = 210
  const izq = 36; const der = 12; const arriba = 18; const abajo = 34
  const areaW = ancho - izq - der; const areaH = alto - arriba - abajo
  const maximo = Math.max(1, ...intervalos.map(i => i.normales + i.anomalas))
  const marcas = ticks(maximo)
  const techo = marcas[marcas.length - 1]
  const anchoBarra = areaW / intervalos.length
  const y = (v: number) => arriba + areaH - (v / techo) * areaH
  const xUmbral = izq + (1.0 / 0.1) * anchoBarra
  const etiquetaIntervalo = (i: IntervaloHistograma) => (i.hasta === null ? `≥ ${fmt(i.desde, 1)}` : `${fmt(i.desde, 1)} a ${fmt(i.hasta, 1)}`)

  return (
    <div className='relative' data-tarjeta>
      <svg viewBox={`0 0 ${ancho} ${alto}`} className='w-full' role='img' aria-label='Histograma de la puntuación relativa al umbral'>
        {marcas.map(m => (
          <g key={m}>
            <line x1={izq} x2={ancho - der} y1={y(m)} y2={y(m)} stroke={COLOR_REJILLA} strokeWidth={1} />
            <text x={izq - 6} y={y(m) + 3} textAnchor='end' className='fill-texto-4' fontSize={10} fontFamily='IBM Plex Mono, monospace'>{fmt(m)}</text>
          </g>
        ))}
        {intervalos.map((i, k) => {
          const total = i.normales + i.anomalas
          const x0 = izq + k * anchoBarra + 1
          const w = Math.max(1, anchoBarra - 2)
          const color = i.desde >= 1.0 ? COLOR_ANOMALO : COLOR_NORMAL
          const h = Math.max(0, y(0) - y(total))
          return (
            <g
              key={k}
              tabIndex={0}
              onPointerMove={e => mostrar(e, `Puntuación / umbral ${etiquetaIntervalo(i)}`, [`${fmt(total)} inspecciones`])}
              onFocus={e => mostrar(e, `Puntuación / umbral ${etiquetaIntervalo(i)}`, [`${fmt(total)} inspecciones`])}
              onPointerLeave={ocultar}
              onBlur={ocultar}
            >
              <rect x={x0} y={arriba} width={w} height={areaH} fill='transparent' />
              {total > 0 && (
                <rect className='anim-crecer-y' style={retraso(k * 18)} x={x0} y={y(total)} width={w} height={h} fill={color} rx={Math.min(4, w / 2)} ry={Math.min(4, w / 2)} />
              )}
              {total > 0 && h > 6 && <rect className='anim-crecer-y' style={retraso(k * 18)} x={x0} y={y(0) - Math.min(4, h)} width={w} height={Math.min(4, h)} fill={color} />}
            </g>
          )
        })}
        <line x1={xUmbral} x2={xUmbral} y1={arriba - 6} y2={y(0)} stroke={COLOR_TINTA} strokeWidth={1.5} />
        <text x={xUmbral + 5} y={arriba + 2} className='fill-texto-2' fontSize={10} fontFamily='IBM Plex Mono, monospace'>umbral</text>
        <line x1={izq} x2={ancho - der} y1={y(0)} y2={y(0)} stroke={COLOR_REJILLA} strokeWidth={1} />
        {[0, 0.5, 1.0, 1.5, 2.0].map(v => (
          <text key={v} x={izq + (v / 0.1) * anchoBarra} y={alto - abajo + 14} textAnchor='middle' className='fill-texto-4' fontSize={10} fontFamily='IBM Plex Mono, monospace'>
            {fmt(v, 1)}
          </text>
        ))}
        <text x={ancho - der} y={alto - abajo + 14} textAnchor='end' className='fill-texto-4' fontSize={10} fontFamily='IBM Plex Mono, monospace'>≥ 2,0</text>
        <text x={izq + areaW / 2} y={alto - 4} textAnchor='middle' className='fill-texto-3' fontSize={10.5} fontFamily='IBM Plex Mono, monospace'>
          puntuación de la inspección dividida por el umbral de su categoría
        </text>
      </svg>
      <Leyenda items={[{ color: COLOR_NORMAL, nombre: 'Normal (por debajo del umbral)' }, { color: COLOR_ANOMALO, nombre: 'Anómalo (por encima)' }]} />
      <Tooltip aviso={aviso} />
    </div>
  )
}

// --------------------------------------------------- barras apiladas por categoría
function BarrasCategoria ({ filas }: { filas: EstadisticaCategoria[] }) {
  const { aviso, mostrar, ocultar } = usarAviso()
  const maximo = Math.max(1, ...filas.map(f => f.inspecciones))
  return (
    <div className='relative' data-tarjeta>
      <div className='flex flex-col gap-2'>
        {filas.map((f, i) => {
          const total = f.inspecciones
          const pctN = (f.normales / maximo) * 100
          const pctA = (f.anomalas / maximo) * 100
          const lineas = [`${fmt(f.normales)} normales · ${fmt(f.anomalas)} anómalas`, `${fmt(f.pct_roi_degradada, 1)} % con ROI degradada`]
          return (
            <div
              key={f.categoria}
              tabIndex={0}
              className='flex items-center gap-3 outline-none focus-visible:bg-papel'
              onPointerMove={e => mostrar(e, f.categoria, lineas)}
              onFocus={e => mostrar(e, f.categoria, lineas)}
              onPointerLeave={ocultar}
              onBlur={ocultar}
            >
              <span className='w-[88px] text-right font-mono text-[12px] text-texto-2'>{f.categoria}</span>
              <span className='flex h-4 flex-1 items-center gap-[2px]'>
                {f.normales > 0 && (
                  <span
                    className='anim-crecer-x h-[14px]'
                    style={{ width: `${pctN}%`, background: COLOR_NORMAL, borderRadius: f.anomalas === 0 ? '0 4px 4px 0' : 0, ...retraso(i * 40) }}
                  />
                )}
                {f.anomalas > 0 && (
                  <span className='anim-crecer-x h-[14px]' style={{ width: `${pctA}%`, background: COLOR_ANOMALO, borderRadius: '0 4px 4px 0', ...retraso(i * 40 + 120) }} />
                )}
                <span className='anim-aparecer ml-1.5 font-mono text-[12px] text-texto-2' style={retraso(i * 40 + 400)}>{fmt(total)}</span>
              </span>
              <span className='w-[92px] text-right font-mono text-[11px] text-texto-4'>
                {f.degradadas > 0 ? `${fmt(f.pct_roi_degradada, 1)} % deg.` : ''}
              </span>
            </div>
          )
        })}
      </div>
      <Leyenda items={[{ color: COLOR_NORMAL, nombre: 'Normales' }, { color: COLOR_ANOMALO, nombre: 'Anómalas' }]} />
      <Tooltip aviso={aviso} />
    </div>
  )
}

// ------------------------------------------------------ tiempos por etapa (p50 a p95)
function PanelTiempos ({ titulo, color, filas, p50, p95, unidad }: {
  titulo: string
  color: string
  filas: EstadisticaCategoria[]
  p50: (f: EstadisticaCategoria) => number | null
  p95: (f: EstadisticaCategoria) => number | null
  unidad: 'ms' | 's'
}) {
  const { aviso, mostrar, ocultar } = usarAviso()
  const conDatos = filas.filter(f => p50(f) !== null && p95(f) !== null)
  const escala = unidad === 's' ? 1000 : 1
  const maximo = Math.max(1, ...conDatos.map(f => (p95(f) ?? 0) / escala))
  const marcas = ticks(maximo, 3)
  const techo = marcas[marcas.length - 1]
  const ancho = 320; const filaH = 24; const izq = 8; const der = 16; const arriba = 6
  const alto = arriba + conDatos.length * filaH + 22
  const x = (v: number) => izq + (v / techo) * (ancho - izq - der)

  return (
    <div className='relative flex-1' data-tarjeta>
      <h3 className='font-mono text-[11px] uppercase tracking-[2px] text-texto-4'>{titulo}</h3>
      {conDatos.length === 0
        ? <p className='mt-2 text-[12px] text-texto-4'>Sin tiempos por etapa registrados todavía.</p>
        : (
          <div className='mt-2 flex gap-2'>
            <div className='flex flex-col' style={{ paddingTop: arriba }}>
              {conDatos.map(f => (
                <span key={f.categoria} className='flex items-center font-mono text-[12px] text-texto-2' style={{ height: filaH }}>{f.categoria}</span>
              ))}
            </div>
            <svg viewBox={`0 0 ${ancho} ${alto}`} className='w-full' role='img' aria-label={titulo}>
              {marcas.map(m => (
                <g key={m}>
                  <line x1={x(m)} x2={x(m)} y1={arriba} y2={arriba + conDatos.length * filaH} stroke={COLOR_REJILLA} strokeWidth={1} />
                  <text x={x(m)} y={alto - 6} textAnchor='middle' className='fill-texto-4' fontSize={10} fontFamily='IBM Plex Mono, monospace'>
                    {fmt(m, unidad === 's' ? 1 : 0)} {unidad}
                  </text>
                </g>
              ))}
              {conDatos.map((f, i) => {
                const cy = arriba + i * filaH + filaH / 2
                const a = (p50(f) ?? 0) / escala; const b = (p95(f) ?? 0) / escala
                const lineas = [`p50 ${fmtMs(p50(f))}`, `p95 ${fmtMs(p95(f))}`]
                return (
                  <g
                    key={f.categoria}
                    tabIndex={0}
                    onPointerMove={e => mostrar(e, `${f.categoria} · ${titulo.toLowerCase()}`, lineas)}
                    onFocus={e => mostrar(e, `${f.categoria} · ${titulo.toLowerCase()}`, lineas)}
                    onPointerLeave={ocultar}
                    onBlur={ocultar}
                  >
                    <rect x={0} y={cy - filaH / 2} width={ancho} height={filaH} fill='transparent' />
                    <line className='anim-crecer-x' style={retraso(i * 50)} x1={x(a)} x2={x(b)} y1={cy} y2={cy} stroke={color} strokeWidth={2} strokeLinecap='round' />
                    <circle className='anim-aparecer' style={retraso(i * 50 + 450)} cx={x(b)} cy={cy} r={5} fill='white' stroke={color} strokeWidth={2} />
                    <circle className='anim-aparecer' style={retraso(i * 50)} cx={x(a)} cy={cy} r={5} fill={color} stroke='white' strokeWidth={2} />
                  </g>
                )
              })}
            </svg>
          </div>
          )}
      <Leyenda items={[{ color, nombre: 'p50' }, { color, nombre: 'p95', hueco: true }]} />
      <Tooltip aviso={aviso} />
    </div>
  )
}

// --------------------------------------------- métricas del experimento (AUROC)
function Par ({ par }: { par: ParMetrica }) {
  const cae = par.base - par.roi >= 0.02
  return (
    <>
      <span className='text-right'>{fmt(par.base, 3)}</span>
      <span className={`text-right ${cae ? 'text-anomalo-texto' : ''}`}>{fmt(par.roi, 3)}</span>
    </>
  )
}

const DEFINICIONES: { clave: string, nombre: string, texto: string }[] = [
  {
    clave: 'imagen',
    nombre: 'AUROC imagen',
    texto: 'Cada imagen de prueba aporta una puntuación y una etiqueta (normal o defectuosa). Mide si la puntuación separa ambas clases con cualquier umbral; 1,000 es separación perfecta y 0,500 equivale al azar.'
  },
  {
    clave: 'pixel_todas',
    nombre: 'Píxel, todas',
    texto: 'Cada píxel del mapa de anomalías aporta su valor y su etiqueta en la máscara de referencia, sobre todas las imágenes de prueba. Se calcula dentro del recorte que recibe cada rama, así que penaliza defectos no localizados y falsas alarmas sobre piezas sanas, pero ignora lo que la ROI dejó fuera.'
  },
  {
    clave: 'pixel_anomalas',
    nombre: 'Píxel, anómalas',
    texto: 'Igual que la anterior pero solo sobre las imágenes que contienen algún defecto: mide la calidad de la localización dentro de una pieza defectuosa, sin el efecto de las piezas normales. También se calcula dentro del recorte.'
  },
  {
    clave: 'pixel_reproyectado',
    nombre: 'Píxel, re-proyectado',
    texto: 'El mapa se devuelve a las coordenadas de la imagen original y se evalúa contra la máscara completa; todo lo que la ROI dejó fuera recibe puntuación cero. Es la única variante que compara la línea base y la ROI sobre los mismos píxeles y la métrica primaria del experimento.'
  }
]

function TablaMetricas ({ datos }: { datos: MetricasExperimento }) {
  const columnas = 'grid-cols-[1.1fr_0.6fr_0.6fr_0.6fr_0.6fr_0.6fr_0.6fr_0.6fr_0.6fr_0.5fr]'
  const cabecera = 'font-mono text-[10px] uppercase tracking-[1px] text-texto-4'
  const def = (clave: string) => DEFINICIONES.find(d => d.clave === clave)?.texto
  return (
    <div className='overflow-x-auto'>
      <div className={`grid ${columnas} gap-2 border-b border-hairline pb-1 ${cabecera}`}>
        <span />
        <span className='col-span-2 cursor-help text-center underline decoration-dotted underline-offset-2' title={def('imagen')}>AUROC imagen</span>
        <span className='col-span-2 cursor-help text-center underline decoration-dotted underline-offset-2' title={def('pixel_todas')}>Píxel, todas</span>
        <span className='col-span-2 cursor-help text-center underline decoration-dotted underline-offset-2' title={def('pixel_anomalas')}>Píxel, anómalas</span>
        <span className='col-span-2 cursor-help text-center underline decoration-dotted underline-offset-2' title={def('pixel_reproyectado')}>Píxel, re-proyectado</span>
        <span className='cursor-help text-right underline decoration-dotted underline-offset-2' title='Lado de la imagen dividido por el lado mediano de la ROI cuadrada en el conjunto de prueba. 1,00 significa que la ROI es la imagen completa.'>Zoom</span>
      </div>
      <div className={`grid ${columnas} gap-2 border-b-2 border-tinta py-1.5 ${cabecera}`}>
        <span>Categoría</span>
        {['Base', 'ROI', 'Base', 'ROI', 'Base', 'ROI', 'Base', 'ROI'].map((t, i) => <span key={i} className='text-right'>{t}</span>)}
        <span />
      </div>
      {datos.categorias.map(c => (
        <div key={c.categoria} className={`grid ${columnas} gap-2 border-b border-hairline-2 py-1.5 font-mono text-[12px] text-texto-2`} style={{ fontVariantNumeric: 'tabular-nums' }}>
          <span>{c.categoria}</span>
          <Par par={c.imagen} /><Par par={c.pixel_todas} /><Par par={c.pixel_anomalas} /><Par par={c.pixel_reproyectado} />
          <span className='text-right'>{fmt(c.zoom, 2)}</span>
        </div>
      ))}
      <div className={`grid ${columnas} gap-2 py-2 font-mono text-[12px] font-semibold text-tinta`} style={{ fontVariantNumeric: 'tabular-nums' }}>
        <span>Media</span>
        <Par par={datos.medias.imagen} /><Par par={datos.medias.pixel_todas} /><Par par={datos.medias.pixel_anomalas} /><Par par={datos.medias.pixel_reproyectado} />
        <span />
      </div>
    </div>
  )
}

/** Panel plegable controlado: el contenido se vuelve a montar en cada apertura
 * (la animación de entrada se repite) y se desvanece antes de cerrarse. */
function Desplegable ({ titulo, children }: { titulo: string, children: React.ReactNode }) {
  const [abierto, setAbierto] = useState(false)
  const [cerrando, setCerrando] = useState(false)
  const [apertura, setApertura] = useState(0)
  const alternar = () => {
    if (abierto) {
      setCerrando(true)
      window.setTimeout(() => { setAbierto(false); setCerrando(false) }, 220)
    } else {
      setApertura(a => a + 1)
      setAbierto(true)
    }
  }
  return (
    <div className='mt-3 border border-hairline bg-papel px-4 py-3'>
      <button
        type='button'
        aria-expanded={abierto}
        onClick={alternar}
        className='flex w-full cursor-pointer items-center gap-2 text-left text-[13px] font-semibold text-tinta'
      >
        <span
          className='inline-block text-[11px] text-marca transition-transform duration-200'
          style={{ transform: abierto && !cerrando ? 'rotate(90deg)' : 'none' }}
        >
          ▶
        </span>
        {titulo}
      </button>
      {abierto && (
        <div key={apertura} className={cerrando ? 'anim-desvanecer' : ''}>
          {children}
        </div>
      )}
    </div>
  )
}

// ------------------------------------------------------------------- página
function Kpi ({ rotulo, valor, formato, detalle, orden = 0 }: {
  rotulo: string
  valor: number | null
  formato: (n: number) => string
  detalle?: string
  orden?: number
}) {
  const animado = useContador(valor ?? 0)
  return (
    <div className='anim-aparecer border border-hairline bg-white px-5 py-4' style={retraso(orden * 80)}>
      <span className='font-mono text-[10.5px] uppercase tracking-[2px] text-texto-4'>{rotulo}</span>
      <div className='mt-2 flex items-baseline gap-2.5'>
        <span className='text-[36px] font-semibold leading-none' style={{ fontVariantNumeric: 'tabular-nums' }}>
          {valor === null ? '—' : formato(animado)}
        </span>
        {detalle !== undefined && <span className='font-mono text-[13px] text-texto-2'>{detalle}</span>}
      </div>
    </div>
  )
}

function Tarjeta ({ titulo, nota, children, ancha, orden = 0 }: { titulo: string, nota: string, children: React.ReactNode, ancha?: boolean, orden?: number }) {
  const [ref, visto] = useEnVista<HTMLElement>()
  return (
    <section
      ref={ref}
      className={`anim-aparecer mt-4 flex flex-col border border-hairline bg-white px-6 py-5 ${ancha === true ? 'flex-[1.4]' : 'flex-1'} ${visto ? '' : 'anim-espera'}`}
      style={retraso(100 + orden * 90)}
    >
      <h2 className='font-serif text-[19px]'>{titulo}</h2>
      <p className='mt-0.5 text-[12px] text-texto-3'>{nota}</p>
      <div className='mt-3.5'>{children}</div>
    </section>
  )
}

export function PaginaEstadisticas () {
  const [datos, setDatos] = useState<Estadisticas | null>(null)
  const [metricas, setMetricas] = useState<MetricasExperimento | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    api<Estadisticas>('/estadisticas').then(setDatos).catch(() => setError(true))
    api<MetricasExperimento>('/metricas').then(setMetricas).catch(() => setMetricas(null))
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

  return (
    <div className='flex flex-1 flex-col px-12 pb-8'>
      <div className='mt-6 flex items-end justify-between'>
        <div>
          <h1 className='font-serif text-[34px] leading-tight'>Estadísticas de uso</h1>
          <p className='mt-1 text-[12.5px] text-texto-3'>
            Métricas globales y anónimas de la plataforma, calculadas del registro de inspecciones de todas las cuentas.
          </p>
        </div>
        <span className='font-mono text-[12px] text-texto-2'>{datos.usuarios_activos} cuentas activas</span>
      </div>

      {datos.total === 0
        ? (
          <div className='mt-10 flex flex-col items-center gap-3 self-center border border-hairline bg-white px-14 py-12 text-center'>
            <h2 className='font-serif text-xl'>Aún no hay actividad registrada</h2>
            <p className='max-w-sm text-[13px] leading-relaxed text-texto-2'>
              Las estadísticas se calculan con las inspecciones de todas las cuentas. Vuelve cuando la plataforma tenga uso.
            </p>
          </div>
          )
        : (
          <>
            <div className='mt-5 grid grid-cols-4 gap-4'>
              <Kpi rotulo='Inspecciones' valor={datos.total} formato={n => fmt(Math.round(n))} detalle={`${fmt(datos.propias)} con imagen propia`} orden={0} />
              <Kpi rotulo='Veredictos anómalos' valor={datos.anomalas} formato={n => fmt(Math.round(n))} detalle={`${fmt(datos.pct_anomalas, 1)} %`} orden={1} />
              <Kpi rotulo='Tasa de ROI degradada' valor={datos.pct_roi_degradada} formato={n => `${fmt(n, 1)} %`} orden={2} />
              <Kpi rotulo='Segmentación p95' valor={datos.seg_p95_ms} formato={n => fmtMs(Math.round(n))} detalle={`detección p95 ${fmtMs(datos.det_p95_ms)}`} orden={3} />
            </div>

            <div className='mt-4 flex items-stretch gap-4'>
              <Tarjeta
                ancha
                orden={2}
                titulo='Puntuación frente al umbral'
                nota='Cuántas inspecciones caen a cada distancia del umbral de su categoría. Las cercanas a 1,0 son los casos límite.'
              >
                <Histograma intervalos={datos.histograma} />
              </Tarjeta>
              <Tarjeta orden={3} titulo='Inspecciones por categoría' nota='Volumen y veredictos; a la derecha, la proporción con ROI degradada.'>
                <BarrasCategoria filas={datos.por_categoria} />
              </Tarjeta>
            </div>

            <div className='mt-4 flex items-stretch gap-4'>
              <Tarjeta ancha orden={4} titulo='Tiempo por etapa y categoría' nota='Mediana y percentil 95 por inspección, medidos en la GPU del servicio. Escalas independientes por etapa.'>
                <div className='flex gap-8'>
                  <PanelTiempos titulo='Segmentación (SAM)' color={COLOR_SEGMENTACION} filas={datos.por_categoria} p50={f => f.seg_p50_ms} p95={f => f.seg_p95_ms} unidad='s' />
                  <PanelTiempos titulo='Detección (PatchCore)' color={COLOR_DETECCION} filas={datos.por_categoria} p50={f => f.det_p50_ms} p95={f => f.det_p95_ms} unidad='ms' />
                </div>
              </Tarjeta>
              <Tarjeta orden={5} titulo='Detalle por categoría' nota='Los mismos datos de los gráficos, en tabla.'>
                <div className='grid grid-cols-[1.2fr_0.7fr_0.8fr_0.8fr_0.9fr_0.9fr] gap-2 border-b-2 border-tinta pb-2 font-mono text-[10px] uppercase tracking-[1px] text-texto-4'>
                  <span>Categoría</span>
                  <span className='text-right'>Insp.</span>
                  <span className='text-right'>% anóm.</span>
                  <span className='text-right'>ROI deg.</span>
                  <span className='text-right'>Seg. p95</span>
                  <span className='text-right'>Det. p95</span>
                </div>
                {datos.por_categoria.map(c => (
                  <div key={c.categoria} className='grid grid-cols-[1.2fr_0.7fr_0.8fr_0.8fr_0.9fr_0.9fr] gap-2 border-b border-hairline-2 py-1.5 font-mono text-[12px] text-texto-2 last:border-b-0'>
                    <span>{c.categoria}</span>
                    <span className='text-right'>{fmt(c.inspecciones)}</span>
                    <span className='text-right'>{fmt(c.pct_anomalas, 1)}</span>
                    <span className='text-right'>{fmt(c.pct_roi_degradada, 1)}</span>
                    <span className='text-right'>{fmtMs(c.seg_p95_ms)}</span>
                    <span className='text-right'>{fmtMs(c.det_p95_ms)}</span>
                  </div>
                ))}
              </Tarjeta>
            </div>
          </>
          )}
      {metricas !== null && (
        <Tarjeta
          orden={6}
          titulo='Evaluación del experimento'
          nota={`AUROC por categoría sobre el conjunto de prueba de MVTec AD con anotaciones de referencia, salida del modo por lotes (${metricas.fecha}). ${metricas.protocolo}`}
        >
          <div className='mt-4'>
            <TablaMetricas datos={metricas} />
            <p className='mt-3 text-[12px] leading-relaxed text-texto-3'>
              Base: PatchCore sobre la imagen completa. ROI: PatchCore sobre la región segmentada por SAM. En rojo, las
              caídas de dos centésimas o más respecto de la base. Pasa el cursor por el nombre de cada métrica para ver su
              definición, o despliega la guía. Estas métricas no se calculan con el uso de la plataforma: requieren las
              máscaras de referencia del conjunto de datos.
            </p>
            <Desplegable titulo='Cómo leer las cuatro métricas'>
              <dl className='mt-3 grid grid-cols-[170px_1fr] gap-x-4 gap-y-2.5 text-[12.5px] leading-relaxed'>
                {[...DEFINICIONES, {
                  clave: 'diferencia',
                  nombre: 'Por qué difieren',
                  texto: 'Las dos variantes dentro del recorte solo ven lo que la ROI contiene, así que pueden verse bien aunque la ROI haya dejado el defecto fuera. La re-proyectada devuelve el mapa a la imagen original y cuenta esa exclusión como puntuación cero; por eso es la que baja en transistor, bottle, cable y metal_nut.'
                }].map((d, i) => (
                  <div key={d.clave} className='contents'>
                    <dt className='anim-aparecer font-mono text-[11.5px] uppercase tracking-[1px] text-texto-2' style={retraso(i * 90)}>{d.nombre}</dt>
                    <dd className='anim-aparecer text-texto-2' style={retraso(i * 90 + 40)}>{d.texto}</dd>
                  </div>
                ))}
              </dl>
            </Desplegable>
          </div>
        </Tarjeta>
      )}
    </div>
  )
}
