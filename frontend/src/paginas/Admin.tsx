import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, ErrorApi } from '../api'
import type { UsuarioAdmin } from '../api'
import { useSesion } from '../auth'

type Accion = 'aprobar' | 'rechazar' | 'desactivar' | 'reactivar'
type Filtro = 'todos' | 'pendiente' | 'activo' | 'desactivado'

interface Confirmacion {
  usuario: UsuarioAdmin
  accion: 'rechazar' | 'desactivar'
}

const TEXTO_CONFIRMACION = {
  rechazar: {
    titulo: '¿Rechazar esta solicitud?',
    cuerpo: 'No podrá iniciar sesión. Si fue un error, la persona puede enviar una nueva solicitud.',
    boton: 'Rechazar'
  },
  desactivar: {
    titulo: '¿Desactivar esta cuenta?',
    cuerpo: 'Perderá el acceso de inmediato y su sesión se cerrará. Su historial se conserva y puedes reactivarla cuando quieras.',
    boton: 'Desactivar'
  }
} as const

function InsigniaEstado ({ estado }: { estado: UsuarioAdmin['estado'] }) {
  if (estado === 'pendiente') {
    return <span className='flex items-center gap-1.5 text-[12px] font-semibold text-alerta-texto'><span className='h-[7px] w-[7px] rounded-full bg-alerta' />Pendiente</span>
  }
  if (estado === 'activo') {
    return <span className='flex items-center gap-1.5 text-[12px] text-texto-2'><span className='h-[7px] w-[7px] rounded-full bg-vnormal' />Activo</span>
  }
  if (estado === 'rechazado') {
    return <span className='flex items-center gap-1.5 text-[12px] text-anomalo-texto'><span className='h-[7px] w-[7px] rounded-full bg-anomalo' />Rechazado</span>
  }
  return <span className='flex items-center gap-1.5 text-[12px] text-texto-4'><span className='h-[7px] w-[7px] rounded-full bg-[#a39d8f]' />Desactivado</span>
}

export function PaginaAdmin () {
  const { sesion } = useSesion()
  const [usuarios, setUsuarios] = useState<UsuarioAdmin[]>([])
  const [filtro, setFiltro] = useState<Filtro>('todos')
  const [confirmacion, setConfirmacion] = useState<Confirmacion | null>(null)
  const [aviso, setAviso] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const cargar = () => {
    api<UsuarioAdmin[]>('/admin/usuarios').then(setUsuarios).catch(e => {
      setError(e instanceof ErrorApi ? e.message : 'No fue posible cargar las cuentas.')
    })
  }

  useEffect(() => {
    if (sesion?.rol === 'administrador') cargar()
  }, [sesion])

  if (sesion !== null && sesion.rol !== 'administrador') {
    return (
      <div className='flex flex-1 flex-col items-center justify-center gap-3 text-center'>
        <svg width='36' height='36' viewBox='0 0 24 24' fill='none' aria-hidden='true'>
          <path d='M12 3 L20 6 V11 C20 16 16.5 19.8 12 21 C7.5 19.8 4 16 4 11 V6 Z' stroke='#d84a38' strokeWidth='2' strokeLinejoin='round' />
          <line x1='9' y1='9' x2='15' y2='15' stroke='#d84a38' strokeWidth='2' strokeLinecap='round' />
          <line x1='15' y1='9' x2='9' y2='15' stroke='#d84a38' strokeWidth='2' strokeLinecap='round' />
        </svg>
        <h1 className='font-serif text-2xl'>No tienes permiso para ver esta sección</h1>
        <p className='text-[13px] text-texto-2'>Esta área es solo para el operador del sistema.</p>
        <Link to='/' className='mt-1 border border-tinta bg-white px-5 py-2 text-[13px] font-semibold'>Volver a la galería</Link>
        <span className='font-mono text-[11px] text-texto-4'>HTTP 403</span>
      </div>
    )
  }

  const ejecutar = async (usuario: UsuarioAdmin, accion: Accion) => {
    setError(null)
    try {
      await api(`/admin/usuarios/${usuario.id}/estado`, {
        method: 'POST',
        body: JSON.stringify({ accion })
      })
      const textos: Record<Accion, string> = {
        aprobar: `Cuenta aprobada — ${usuario.correo} ya puede entrar.`,
        rechazar: `Solicitud rechazada — ${usuario.correo}`,
        desactivar: `Cuenta desactivada — ${usuario.correo}`,
        reactivar: `Cuenta reactivada — ${usuario.correo}`
      }
      setAviso(textos[accion])
      setTimeout(() => setAviso(null), 4000)
      cargar()
    } catch (e) {
      setError(e instanceof ErrorApi ? e.message : 'No fue posible completar la acción.')
    } finally {
      setConfirmacion(null)
    }
  }

  const visibles = usuarios.filter(u => filtro === 'todos' || u.estado === filtro)
  const pendientes = usuarios.filter(u => u.estado === 'pendiente').length
  const activos = usuarios.filter(u => u.estado === 'activo').length
  const desactivados = usuarios.filter(u => u.estado === 'desactivado').length

  const BotonSecundario = ({ texto, alPulsar }: { texto: string, alPulsar: () => void }) => (
    <button onClick={alPulsar} className='border border-tinta bg-white px-3.5 py-1.5 text-[12px] font-semibold hover:bg-papel'>
      {texto}
    </button>
  )

  return (
    <div className='flex flex-1 flex-col px-12 pb-8'>
      <div className='mt-6 flex items-end justify-between'>
        <h1 className='font-serif text-[34px] leading-tight'>Administración de acceso</h1>
        <span className='font-mono text-[12px] text-texto-2'>
          {activos} activos · {pendientes} pendientes · {desactivados} desactivados
        </span>
      </div>

      {error !== null && (
        <p className='mt-4 border border-anomalo/40 bg-anomalo/5 px-4 py-3 text-[13px] text-anomalo-texto'>{error}</p>
      )}

      <div className='mt-4 flex gap-2 text-[13px]'>
        {([
          ['todos', 'Todos'],
          ['pendiente', pendientes > 0 ? `Pendientes · ${pendientes}` : 'Pendientes'],
          ['activo', 'Activos'],
          ['desactivado', 'Desactivados']
        ] as [Filtro, string][]).map(([clave, nombre]) => (
          <button
            key={clave}
            onClick={() => setFiltro(clave)}
            className={filtro === clave
              ? 'border border-tinta bg-tinta px-4 py-1.5 font-semibold text-papel'
              : clave === 'pendiente' && pendientes > 0
                ? 'border border-alerta/50 bg-white px-4 py-1.5 font-semibold text-alerta-texto'
                : 'border border-hairline bg-white px-4 py-1.5 text-texto-2 hover:border-tinta'}
          >
            {nombre}
          </button>
        ))}
      </div>

      <div className='mt-4 border border-hairline bg-white'>
        <div className='grid grid-cols-[1.6fr_130px_130px_150px_110px_220px] gap-3 border-b-2 border-tinta px-5 py-3 font-mono text-[10.5px] uppercase tracking-[1.5px] text-texto-4'>
          <span>Correo</span><span>Rol</span><span>Estado</span><span>Último acceso</span>
          <span>Inspecciones</span><span>Acciones</span>
        </div>
        {visibles.length === 0 && (
          <div className='flex flex-col items-center gap-2 px-6 py-10 text-center'>
            <span className='text-[13px] text-texto-2'>Sin cuentas en este estado.</span>
          </div>
        )}
        {visibles.map(u => (
          <div
            key={u.id}
            className={`grid grid-cols-[1.6fr_130px_130px_150px_110px_220px] items-center gap-3 border-b border-hairline-2 px-5 py-3 text-[13px] last:border-b-0 ${u.estado === 'pendiente' ? 'bg-alerta/5' : ''}`}
          >
            <span className='font-mono text-[12.5px]'>{u.correo}</span>
            {u.rol === 'administrador'
              ? <span className='text-[12.5px] font-bold text-marca'>Administrador</span>
              : <span className='text-[12.5px] text-texto-2'>Usuario</span>}
            <InsigniaEstado estado={u.estado} />
            <span className='font-mono text-[12px] text-texto-2'>{u.ultimo_acceso ?? '—'}</span>
            <span className='font-mono text-[12px] text-texto-2'>{u.inspecciones}</span>
            <span className='flex gap-2'>
              {u.estado === 'pendiente' && (
                <>
                  <button
                    onClick={() => { ejecutar(u, 'aprobar') }}
                    className='bg-marca px-3.5 py-1.5 text-[12px] font-bold text-white'
                  >
                    Aprobar
                  </button>
                  <BotonSecundario texto='Rechazar' alPulsar={() => setConfirmacion({ usuario: u, accion: 'rechazar' })} />
                </>
              )}
              {u.estado === 'activo' && u.correo !== sesion?.correo && (
                <BotonSecundario texto='Desactivar' alPulsar={() => setConfirmacion({ usuario: u, accion: 'desactivar' })} />
              )}
              {u.estado === 'desactivado' && (
                <BotonSecundario texto='Reactivar' alPulsar={() => { ejecutar(u, 'reactivar') }} />
              )}
              {u.estado === 'activo' && u.correo === sesion?.correo && <span className='text-[12px] text-texto-4'>—</span>}
            </span>
          </div>
        ))}
      </div>

      <p className='mt-3 text-[12px] text-texto-4'>
        Toda la actividad queda registrada por usuario. El rol se verifica en el servidor en cada
        acción; Aprobar y Reactivar son reversibles y no piden confirmación. No es posible
        desactivar la última cuenta de administrador.
      </p>

      {aviso !== null && (
        <div className='fixed right-8 bottom-16 flex items-center gap-2.5 bg-tinta px-4 py-3 text-[12.5px] text-papel shadow-[4px_4px_0_rgba(22,24,26,0.15)]'>
          <svg width='16' height='16' viewBox='0 0 24 24' fill='none' aria-hidden='true'>
            <circle cx='12' cy='12' r='9.5' stroke='#1e9e6a' strokeWidth='2' />
            <path d='M7.5 12.5 L10.8 15.5 L16.5 9' stroke='#1e9e6a' strokeWidth='2' strokeLinecap='round' strokeLinejoin='round' />
          </svg>
          {aviso}
        </div>
      )}

      {confirmacion !== null && (
        <div className='fixed inset-0 z-10 flex items-center justify-center bg-tinta/40 px-6'>
          <div className='flex w-[400px] flex-col gap-2.5 border-[1.5px] border-tinta bg-white p-5 shadow-[6px_6px_0_rgba(22,24,26,0.2)]'>
            <h2 className='font-serif text-lg'>{TEXTO_CONFIRMACION[confirmacion.accion].titulo}</h2>
            <span className='font-mono text-[12px] text-texto-2'>{confirmacion.usuario.correo}</span>
            <p className='text-[12px] leading-relaxed text-texto-2'>
              {TEXTO_CONFIRMACION[confirmacion.accion].cuerpo}
            </p>
            <div className='mt-1.5 flex justify-end gap-2'>
              <button
                onClick={() => setConfirmacion(null)}
                className='border border-hairline px-3.5 py-1.5 text-[12.5px] font-semibold text-texto-2'
              >
                Cancelar
              </button>
              <button
                onClick={() => { ejecutar(confirmacion.usuario, confirmacion.accion) }}
                className='bg-anomalo px-3.5 py-1.5 text-[12.5px] font-bold text-white'
              >
                {TEXTO_CONFIRMACION[confirmacion.accion].boton}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
