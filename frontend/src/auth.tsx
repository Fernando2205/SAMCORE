import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { api, ErrorApi } from './api'
import type { Sesion } from './api'

interface ContextoSesion {
  sesion: Sesion | null
  cargando: boolean
  entrar: (correo: string, contrasena: string) => Promise<void>
  salir: () => Promise<void>
}

const Contexto = createContext<ContextoSesion | null>(null)

export function ProveedorSesion ({ children }: { children: ReactNode }) {
  const [sesion, setSesion] = useState<Sesion | null>(null)
  const [cargando, setCargando] = useState(true)

  useEffect(() => {
    api<Sesion>('/sesion')
      .then(setSesion)
      .catch(() => setSesion(null))
      .finally(() => setCargando(false))
  }, [])

  const entrar = useCallback(async (correo: string, contrasena: string) => {
    const datos = await api<Sesion>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ correo, contrasena })
    })
    setSesion(datos)
  }, [])

  const salir = useCallback(async () => {
    try {
      await api('/auth/logout', { method: 'POST' })
    } catch (e) {
      if (!(e instanceof ErrorApi)) throw e
    }
    setSesion(null)
  }, [])

  const valor = useMemo(
    () => ({ sesion, cargando, entrar, salir }),
    [sesion, cargando, entrar, salir]
  )
  return <Contexto.Provider value={valor}>{children}</Contexto.Provider>
}

export function useSesion (): ContextoSesion {
  const contexto = useContext(Contexto)
  if (contexto === null) throw new Error('useSesion requiere ProveedorSesion')
  return contexto
}
