import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { ProveedorSesion } from './auth'
import { Marco } from './componentes/Marco'
import { PaginaAdmin } from './paginas/Admin'
import { PaginaEstadisticas } from './paginas/Estadisticas'
import { PaginaGaleria } from './paginas/Galeria'
import { PaginaHistorial } from './paginas/Historial'
import { PaginaInspeccion } from './paginas/Inspeccion'
import { PaginaLogin } from './paginas/Login'
import { PaginaSolicitarAcceso } from './paginas/SolicitarAcceso'

export function App () {
  return (
    <ProveedorSesion>
      <BrowserRouter>
        <Routes>
          <Route path='/login' element={<PaginaLogin />} />
          <Route path='/solicitar-acceso' element={<PaginaSolicitarAcceso />} />
          <Route element={<Marco />}>
            <Route index element={<PaginaGaleria />} />
            <Route path='/inspeccion' element={<PaginaInspeccion />} />
            <Route path='/historial' element={<PaginaHistorial />} />
            <Route path='/estadisticas' element={<PaginaEstadisticas />} />
            <Route path='/admin' element={<PaginaAdmin />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ProveedorSesion>
  )
}
