# SamCore — MVP

Detección de anomalías en productos (SAM + PatchCore sobre MVTec AD).

- `backend/` — API FastAPI: cuentas con aprobación del operador (roles
  usuario/administrador), galería cerrada de MVTec AD, inspección con
  **motor simulado** (determinista; el motor real se conecta leyendo los
  artefactos por categoría de `backend/artefactos/`, ver su README),
  historial por usuario, estadísticas y administración.
- `frontend/` — React + TypeScript (Vite), Tailwind v4 y lint con
  neostandard.

## Correr en desarrollo

Backend (puerto 8000):

```powershell
cd backend
python -m venv .venv            # solo la primera vez
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\python -m uvicorn app.main:app --port 8000
```

En el primer arranque se crea la cuenta de administrador y su contraseña
queda en `backend/.admin_inicial.txt` (bórralo tras el primer login).

Frontend (puerto 5173, proxy a `/api`):

```powershell
cd frontend
npm install                     # solo la primera vez
npm run dev
```

Abrir <http://localhost:5173>. Verificaciones: `npm run lint`
(neostandard) y `npm run build` (tsc + vite).
