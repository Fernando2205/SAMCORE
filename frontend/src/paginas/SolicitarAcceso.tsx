import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api, ErrorApi } from '../api'
import { Sello, Wordmark } from '../componentes/Sello'

export function PaginaSolicitarAcceso () {
  const [correo, setCorreo] = useState('')
  const [contrasena, setContrasena] = useState('')
  const [confirmacion, setConfirmacion] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [enviada, setEnviada] = useState(false)
  const [enviando, setEnviando] = useState(false)

  const enviar = async (evento: React.FormEvent) => {
    evento.preventDefault()
    setError(null)
    if (contrasena.length < 10) {
      setError('La contraseña debe tener al menos 10 caracteres.')
      return
    }
    if (contrasena !== confirmacion) {
      setError('Las contraseñas no coinciden.')
      return
    }
    setEnviando(true)
    try {
      await api('/auth/registro', {
        method: 'POST',
        body: JSON.stringify({ correo, contrasena, confirmacion })
      })
      setEnviada(true)
    } catch (e) {
      setError(e instanceof ErrorApi ? e.message : 'No fue posible conectar con el servidor.')
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
        {enviada
          ? (
            <div className='flex w-[430px] flex-col items-center gap-4 border-[1.5px] border-tinta bg-white p-10 text-center shadow-[8px_8px_0_rgba(22,24,26,0.08)]'>
              <svg width='40' height='40' viewBox='0 0 24 24' fill='none' aria-hidden='true'>
                <circle cx='12' cy='12' r='9.5' stroke='#1e9e6a' strokeWidth='2' />
                <path d='M7.5 12.5 L10.8 15.5 L16.5 9' stroke='#1e9e6a' strokeWidth='2' strokeLinecap='round' strokeLinejoin='round' />
              </svg>
              <h1 className='font-serif text-[26px]'>Solicitud registrada</h1>
              <p className='text-[13px] leading-relaxed text-texto-2'>
                Podrás entrar cuando el operador la apruebe. No se envían correos:
                intenta iniciar sesión más tarde.
              </p>
              <Link to='/login' className='mt-2 bg-marca px-6 py-3 text-sm font-bold tracking-wide text-white'>
                VOLVER AL INICIO DE SESIÓN
              </Link>
            </div>
            )
          : (
            <form
              onSubmit={enviar}
              className='flex w-[430px] flex-col gap-4 border-[1.5px] border-tinta bg-white p-9 shadow-[8px_8px_0_rgba(22,24,26,0.08)]'
            >
              <div className='flex flex-col items-center gap-2.5'>
                <Sello tamano={52} />
                <h1 className='font-serif text-[28px]'>Solicitar acceso</h1>
                <p className='text-center text-[13px] text-texto-2'>
                  Crea tu cuenta; el operador debe aprobarla antes de que puedas entrar.
                </p>
              </div>

              {error !== null && (
                <p className='border border-anomalo/40 bg-anomalo/5 px-3.5 py-3 text-[12.5px] leading-relaxed text-anomalo-texto'>
                  {error}
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
                <span className='text-[11px] text-texto-4'>
                  Mínimo 10 caracteres. No hay recuperación de contraseña: guárdala bien.
                </span>
              </label>
              <label className='flex flex-col gap-1.5'>
                <span className='font-mono text-[10.5px] uppercase tracking-[2px] text-texto-4'>Confirmar contraseña</span>
                <input
                  type='password'
                  required
                  value={confirmacion}
                  onChange={e => setConfirmacion(e.target.value)}
                  className='h-11 border border-borde-input bg-papel px-3.5 text-sm outline-none focus:border-marca'
                />
              </label>

              <button
                type='submit'
                disabled={enviando}
                className='h-12 bg-marca text-sm font-bold tracking-wide text-white disabled:opacity-60'
              >
                {enviando ? 'ENVIANDO…' : 'ENVIAR SOLICITUD'}
              </button>

              <p className='text-center text-[13px] text-texto-2'>
                ¿Ya tienes cuenta? <Link to='/login' className='font-bold text-marca'>Inicia sesión</Link>
              </p>

              <p className='border-t border-hairline pt-3 text-center text-[11.5px] leading-relaxed text-texto-4'>
                No se envían correos de confirmación: tu solicitud queda en estado pendiente y podrás
                entrar cuando el operador la apruebe. Solo guardamos tu correo y tu historial de inspecciones.
              </p>
            </form>
            )}
      </main>

      <footer className='flex items-center justify-between border-t border-tinta px-12 py-3.5 font-mono text-[10.5px] text-texto-4'>
        <span>Trabajo de grado · Ingeniería de Sistemas · Universidad de San Buenaventura Cali</span>
        <span>Imágenes: MVTec AD © MVTec Software GmbH · CC BY-NC-SA 4.0</span>
      </footer>
    </div>
  )
}
