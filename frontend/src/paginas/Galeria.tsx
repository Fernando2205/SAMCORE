import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import type { Categoria, Galeria } from '../api'

function Miniatura ({ categoria, imagenId, numero, onClick }: { categoria: string, imagenId: string, numero: number, onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className='group flex flex-col overflow-hidden border border-hairline bg-white text-left hover:border-marca'
    >
      <span className='flex h-[140px] items-center justify-center overflow-hidden bg-papel-2'>
        <img
          src={`/api/galeria/${categoria}/imagen/${imagenId}`}
          alt={`${categoria} ${imagenId}`}
          loading='lazy'
          className='h-full w-full object-cover'
        />
      </span>
      <span className='border-t border-hairline-2 px-3 py-2 text-center font-mono text-[11px] text-texto-3 group-hover:text-tinta'>
        {String(numero).padStart(2, '0')}
      </span>
    </button>
  )
}

export function PaginaGaleria () {
  const navegar = useNavigate()
  const [categorias, setCategorias] = useState<Categoria[]>([])
  const [galeria, setGaleria] = useState<Galeria | null>(null)
  const [error, setError] = useState<string | null>(null)
  const entradaArchivo = useRef<HTMLInputElement | null>(null)

  useEffect(() => {
    api<Categoria[]>('/categorias')
      .then(lista => {
        setCategorias(lista)
        const primera = lista.find(c => c.artefactos) ?? lista[0]
        if (primera !== undefined) elegir(primera.nombre)
      })
      .catch(() => setError('No fue posible cargar la galería.'))
  }, [])

  const elegir = (nombre: string) => {
    setGaleria(null)
    api<Galeria>(`/galeria/${nombre}`)
      .then(setGaleria)
      .catch(() => setError('No fue posible cargar la galería.'))
  }

  const categoriaActual = categorias.find(c => c.nombre === galeria?.categoria)
  const soportadas = categorias.filter(c => c.artefactos)

  const alElegirArchivo = (evento: React.ChangeEvent<HTMLInputElement>) => {
    const archivo = evento.target.files?.[0]
    evento.target.value = ''
    if (archivo === undefined || galeria === null) return
    navegar('/inspeccion', { state: { archivo, categoria: galeria.categoria } })
  }

  return (
    <div className='flex flex-1 flex-col px-12 pb-8'>
      <div className='mt-5 flex items-center gap-2.5 border border-marca/35 bg-marca/5 px-4 py-2.5 text-[13px] text-[#2f4a44]'>
        <svg width='16' height='16' viewBox='0 0 24 24' fill='none' className='shrink-0' aria-hidden='true'>
          <circle cx='12' cy='12' r='10' stroke='#0c7a6b' strokeWidth='2' />
          <line x1='12' y1='11' x2='12' y2='17' stroke='#0c7a6b' strokeWidth='2' strokeLinecap='round' />
          <circle cx='12' cy='7.5' r='1.4' fill='#0c7a6b' />
        </svg>
        <span>
          Modo principal: galería de prueba de las {soportadas.length} categorías de objetos de MVTec AD con banco
          de memoria preparado. También puedes subir una imagen propia de una categoría soportada: su veredicto
          es orientativo y queda en tu historial.
        </span>
      </div>

      <div className='mt-6'>
        <span className='font-mono text-[11px] uppercase tracking-[2px] text-texto-4'>Categoría</span>
        <div className='mt-2.5 flex flex-wrap gap-2 font-mono text-[13px]'>
          {categorias.map(c => {
            const activa = galeria?.categoria === c.nombre
            if (!c.artefactos) {
              return (
                <span
                  key={c.nombre}
                  title='Sin banco de memoria: la regla de selección no produce una región estable en esta categoría'
                  className='cursor-not-allowed border border-dashed border-hairline px-4 py-1.5 text-texto-4 line-through'
                >
                  {c.nombre}
                </span>
              )
            }
            return (
              <button
                key={c.nombre}
                onClick={() => elegir(c.nombre)}
                className={activa
                  ? 'border border-tinta bg-tinta px-4 py-1.5 font-semibold text-papel'
                  : 'border border-hairline bg-white px-4 py-1.5 text-texto-2 hover:border-tinta'}
              >
                {c.nombre}
              </button>
            )
          })}
        </div>
      </div>

      {error !== null && (
        <p className='mt-6 border border-anomalo/40 bg-anomalo/5 px-4 py-3 text-[13px] text-anomalo-texto'>{error}</p>
      )}

      {galeria !== null && (
        <>
          <div className='mt-6 flex items-baseline justify-between'>
            <h1 className='font-serif text-2xl'>Galería de prueba — {galeria.categoria}</h1>
            <span className='text-[12.5px] text-texto-3'>Selecciona una imagen para inspeccionarla. La galería no indica cuáles tienen defectos.</span>
          </div>
          {galeria.imagenes.length === 0
            ? (
              <p className='mt-3 border border-dashed border-borde-input px-4 py-6 text-center text-[13px] text-texto-3'>
                Esta categoría aún no tiene imágenes de galería cargadas en el servidor.
              </p>
              )
            : (
              <div className='mt-3 grid grid-cols-6 gap-4'>
                {galeria.imagenes.map((imagen, i) => (
                  <Miniatura
                    key={imagen}
                    categoria={galeria.categoria}
                    imagenId={imagen}
                    numero={i + 1}
                    onClick={() => navegar(`/inspeccion?categoria=${galeria.categoria}&imagen=${encodeURIComponent(imagen)}&n=${i + 1}`)}
                  />
                ))}
              </div>
              )}
          <p className='mt-3 font-mono text-[11px] text-texto-4'>
            {galeria.imagenes.length} imágenes de prueba · umbral p99: {galeria.umbral.toFixed(3)} ·
            motor: {categoriaActual?.motor ?? '—'}
          </p>

          <div className='mt-8 flex items-center justify-between gap-6 border-2 border-dashed border-tinta bg-white px-6 py-5'>
            <div className='flex flex-col gap-1'>
              <span className='font-mono text-[11px] uppercase tracking-[2px] text-texto-4'>Imagen propia · {galeria.categoria}</span>
              <span className='text-[13.5px] text-texto-2'>
                Sube una foto de un producto de esta categoría. Veredicto orientativo: el sistema no detecta
                imágenes fuera de las categorías soportadas.
              </span>
              <span className='font-mono text-[11px] text-texto-4'>
                JPG o PNG · máximo 8 MB · solo categorías soportadas · se guarda en tu historial (borrable)
              </span>
            </div>
            <input
              ref={entradaArchivo}
              type='file'
              accept='image/png,image/jpeg'
              className='hidden'
              onChange={alElegirArchivo}
            />
            <button
              onClick={() => entradaArchivo.current?.click()}
              className='shrink-0 bg-tinta px-5 py-2.5 text-[12.5px] font-bold tracking-[2px] text-papel hover:bg-marca'
            >
              ELEGIR ARCHIVO
            </button>
          </div>
        </>
      )}
    </div>
  )
}
