import { useEffect, useState } from 'react'
import { NavLink, Navigate, Outlet, useNavigate } from 'react-router-dom'
import { api } from '../api'
import { useSesion } from '../auth'
import { Sello, Wordmark } from './Sello'

interface Salud {
  estado: string
  motor: string
}

function Pestana ({ a, children }: { a: string, children: string }) {
  return (
    <NavLink
      to={a}
      className={({ isActive }) =>
        isActive
          ? 'border-b-2 border-marca pb-1 font-medium text-tinta'
          : 'pb-1 font-medium text-texto-3 hover:text-tinta'}
    >
      {children}
    </NavLink>
  )
}

export function Marco () {
  const { sesion, cargando, salir } = useSesion()
  const navegar = useNavigate()
  const [salud, setSalud] = useState<Salud | null>(null)

  useEffect(() => {
    api<Salud>('/salud').then(setSalud).catch(() => setSalud(null))
  }, [])

  if (cargando) {
    return (
      <div className='flex h-screen items-center justify-center'>
        <div className='h-9 w-9 animate-spin rounded-full border-3 border-papel-4 border-t-marca' />
      </div>
    )
  }
  if (sesion === null) return <Navigate to='/login' replace />

  const cerrarSesion = () => {
    salir().finally(() => navegar('/login'))
  }

  return (
    <div className='flex min-h-screen flex-col'>
      <header className='flex h-[66px] shrink-0 items-center justify-between border-b border-tinta px-12'>
        <div className='flex items-center gap-3'>
          <Sello tamano={32} />
          <div className='flex items-baseline gap-3'>
            <Wordmark />
            <span className='text-[11.5px] uppercase tracking-[1.5px] text-texto-4'>
              Detección de anomalías en productos
            </span>
          </div>
        </div>
        <div className='flex items-center gap-6'>
          <nav className='flex items-center gap-6 text-[13.5px]'>
            <Pestana a='/'>Inspección</Pestana>
            <Pestana a='/historial'>Historial</Pestana>
            <Pestana a='/estadisticas'>Estadísticas</Pestana>
            {sesion.rol === 'administrador' && <Pestana a='/admin'>Administración</Pestana>}
          </nav>
          <span className='flex items-center gap-2 rounded-full border border-hairline bg-white px-3.5 py-1.5 font-mono text-[11.5px] text-texto-2'>
            <span className={`h-[7px] w-[7px] rounded-full ${salud ? 'bg-vnormal' : 'bg-anomalo'}`} />
            {salud ? `motor ${salud.motor}` : 'sin conexión'}
          </span>
          <span className='font-mono text-[11.5px] text-texto-3'>{sesion.correo}</span>
          <button
            onClick={cerrarSesion}
            className='border border-hairline bg-white px-3 py-1.5 text-xs font-semibold text-texto-2 hover:border-tinta hover:text-tinta'
          >
            Salir
          </button>
        </div>
      </header>

      <main className='flex flex-1 flex-col'>
        <Outlet />
      </main>

      <footer className='mt-auto flex items-center justify-between border-t border-tinta px-12 py-3.5 font-mono text-[10.5px] text-texto-4'>
        <span>Trabajo de grado · Ingeniería de Sistemas · Universidad de San Buenaventura Cali</span>
        <span>Imágenes: MVTec Anomaly Detection Dataset © MVTec Software GmbH · CC BY-NC-SA 4.0</span>
      </footer>
    </div>
  )
}
