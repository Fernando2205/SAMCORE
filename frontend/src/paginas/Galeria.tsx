import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import type { Categoria, Galeria } from '../api'

function Miniatura ({ imagenId, onClick }: { imagenId: string, onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className='group flex flex-col overflow-hidden border border-hairline bg-white text-left hover:border-marca'
    >
      <span className='flex h-[140px] items-center justify-center bg-papel-2'>
        <svg width='44' height='44' viewBox='0 0 24 24' fill='none' aria-hidden='true'>
          <rect x='3' y='5' width='18' height='14' rx='1' stroke='#a49c8d' strokeWidth='1.6' />
          <circle cx='9' cy='10' r='1.7' stroke='#a49c8d' strokeWidth='1.6' />
          <path d='M4 17 L9.5 12.5 L13.5 16 L16.5 13.5 L20 16.5' stroke='#a49c8d' strokeWidth='1.6' strokeLinejoin='round' />
        </svg>
      </span>
      <span className='border-t border-hairline-2 px-3 py-2 font-mono text-[11px] text-texto-3 group-hover:text-tinta'>
        {imagenId}
      </span>
    </button>
  )
}

export function PaginaGaleria () {
  const navegar = useNavigate()
  const [categorias, setCategorias] = useState<Categoria[]>([])
  const [galeria, setGaleria] = useState<Galeria | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api<Categoria[]>('/categorias')
      .then(lista => {
        setCategorias(lista)
        if (lista.length > 0) elegir(lista[0].nombre)
      })
      .catch(() => setError('No fue posible cargar la galería.'))
  }, [])

  const elegir = (nombre: string) => {
    setGaleria(null)
    api<Galeria>(`/galeria/${nombre}`)
      .then(setGaleria)
      .catch(() => setError('No fue posible cargar la galería.'))
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
          Galería cerrada: se analizan únicamente las imágenes de prueba de las 10 categorías de
          objetos de MVTec AD con banco de memoria preparado. No es posible cargar archivos propios.
        </span>
      </div>

      <div className='mt-6'>
        <span className='font-mono text-[11px] uppercase tracking-[2px] text-texto-4'>Categoría</span>
        <div className='mt-2.5 flex flex-wrap gap-2 font-mono text-[13px]'>
          {categorias.map(c => {
            const activa = galeria?.categoria === c.nombre
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
            <span className='text-[12.5px] text-texto-3'>Selecciona una imagen para inspeccionarla</span>
          </div>
          <div className='mt-3 grid grid-cols-6 gap-4'>
            {galeria.imagenes.map(imagen => (
              <Miniatura
                key={imagen}
                imagenId={imagen}
                onClick={() => navegar(`/inspeccion?categoria=${galeria.categoria}&imagen=${encodeURIComponent(imagen)}`)}
              />
            ))}
          </div>
          <p className='mt-3 font-mono text-[11px] text-texto-4'>
            {galeria.imagenes.length} imágenes de prueba · miniaturas de referencia (marcador de posición) ·
            umbral p99: {galeria.umbral.toFixed(3)}
          </p>
        </>
      )}
    </div>
  )
}
