import { useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { ErrorApi } from '../api'
import { useSesion } from '../auth'
import { Sello, Wordmark } from '../componentes/Sello'

type TonoAviso = 'rojo' | 'ambar'

const TONOS: Record<TonoAviso, string> = {
  rojo: 'border-anomalo/40 bg-anomalo/5 text-anomalo-texto',
  ambar: 'border-alerta/40 bg-alerta/5 text-alerta-texto'
}

export function PaginaLogin () {
  const { sesion, cargando, entrar } = useSesion()
  const navegar = useNavigate()
  const [correo, setCorreo] = useState('')
  const [contrasena, setContrasena] = useState('')
  const [aviso, setAviso] = useState<{ tono: TonoAviso, texto: string } | null>(null)
  const [enviando, setEnviando] = useState(false)

  if (!cargando && sesion !== null) return <Navigate to='/' replace />

  const enviar = async (evento: React.FormEvent) => {
    evento.preventDefault()
    setAviso(null)
    setEnviando(true)
    try {
      await entrar(correo, contrasena)
      navegar('/')
    } catch (e) {
      if (e instanceof ErrorApi) {
        const tono: TonoAviso = e.codigo === 'pendiente' || e.codigo === 'limite' ? 'ambar' : 'rojo'
        setAviso({ tono, texto: e.message })
      } else {
        setAviso({ tono: 'rojo', texto: 'No fue posible conectar con el servidor.' })
      }
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div className='flex min-h-screen flex-col'>
      <header className='flex h-[66px] items-center border-b border-tinta px-12'>
        <div className='flex items-center gap-3'>
          <Sello tamano={32} />
          <div className='flex items-baseline gap-3'>
            <Wordmark />
            <span className='text-[11.5px] uppercase tracking-[1.5px] text-texto-4'>
              Detección de anomalías en productos
            </span>
          </div>
        </div>
      </header>

      <main className='flex flex-1 items-center justify-center px-6 py-10'>
        <form
          onSubmit={enviar}
          className='flex w-[430px] flex-col gap-4 border-[1.5px] border-tinta bg-white p-10 shadow-[8px_8px_0_rgba(22,24,26,0.08)]'
        >
          <div className='flex flex-col items-center gap-3'>
            <Sello tamano={58} />
            <h1 className='font-serif text-[28px]'>Bienvenido a <span className='text-marca'>Sam</span>Core</h1>
            <p className='text-center text-[13px] text-texto-2'>Inicia sesión para usar la plataforma.</p>
          </div>

          {aviso !== null && (
            <p className={`border px-3.5 py-3 text-[12.5px] leading-relaxed ${TONOS[aviso.tono]}`}>
              {aviso.texto}
            </p>
          )}

          <label className='flex flex-col gap-1.5'>
            <span className='font-mono text-[10.5px] uppercase tracking-[2px] text-texto-4'>Correo</span>
            <input
              type='email'
              required
              value={correo}
              onChange={e => setCorreo(e.target.value)}
              placeholder='nombre@correo.com'
              className='h-11 border border-borde-input bg-papel px-3.5 text-sm outline-none focus:border-marca'
            />
          </label>
          <label className='flex flex-col gap-1.5'>
            <span className='font-mono text-[10.5px] uppercase tracking-[2px] text-texto-4'>Contraseña</span>
            <input
              type='password'
              required
              value={contrasena}
              onChange={e => setContrasena(e.target.value)}
              className='h-11 border border-borde-input bg-papel px-3.5 text-sm outline-none focus:border-marca'
            />
          </label>

          <button
            type='submit'
            disabled={enviando}
            className='h-12 bg-marca text-sm font-bold tracking-wide text-white disabled:opacity-60'
          >
            {enviando ? 'ENTRANDO…' : 'ENTRAR'}
          </button>

          <p className='text-center text-[13px] text-texto-2'>
            ¿No tienes cuenta? <Link to='/solicitar-acceso' className='font-bold text-marca'>Solicitar acceso</Link>
          </p>

          <p className='border-t border-hairline pt-3.5 text-center text-[11.5px] leading-relaxed text-texto-4'>
            El acceso lo administra el operador del sistema: las cuentas nuevas requieren aprobación.
            Toda la actividad queda asociada a tu cuenta; solo guardamos tu correo y tu historial de inspecciones.
          </p>
        </form>
      </main>

      <footer className='flex items-center justify-between border-t border-tinta px-12 py-3.5 font-mono text-[10.5px] text-texto-4'>
        <span>Trabajo de grado · Ingeniería de Sistemas · Universidad de San Buenaventura Cali</span>
        <span>Imágenes: MVTec AD © MVTec Software GmbH · CC BY-NC-SA 4.0</span>
      </footer>
    </div>
  )
}
