# Dashboard AutoJob AI

Next.js App Router, React, TypeScript, TanStack Query y Tailwind CSS. El diseño y los controles accesibles se implementan en componentes locales, sin dependencia de un servicio visual externo.

```powershell
npm.cmd ci
npm.cmd run dev
```

Abre `http://localhost:3000` para entrar directamente a tu espacio personal. Inicia el backend según el [manual principal](../README.md). Las pantallas muestran datos de la API local, sin registro ni login. El proveedor `demo` se selecciona expresamente en la búsqueda y sus registros se identifican como pruebas.

La variable `NEXT_PUBLIC_API_URL` tiene como valor predeterminado `http://localhost:8000/api/v1`. Next.js incorpora esta URL al compilar: configúrala antes de `npm run build` o mediante el argumento de construcción del Dockerfile.

**Oportunidades → Importar oferta** admite LinkedIn, Computrabajo y otros portales mediante
texto/enlace pegados por el usuario. No accede a las cuentas del portal. En **Candidaturas**,
«Copiar carta» usa el portapapeles local y «Abrir oferta original» abre una pestaña normal;
el usuario completa la postulación y registra después su resultado.

```powershell
npm.cmd run typecheck
npm.cmd run build
npm.cmd run start
```

No se guardan tokens de sesión ni claves de IA en el navegador. El espacio se identifica de forma persistente en el backend. En «Mi perfil» puedes introducir tus datos manualmente o cargar un CV; las cartas y el CV adaptado se preparan a partir de hechos profesionales verificados.

La carpeta `src/features` separa vista general, CV, oportunidades, candidaturas y configuración. Los controles compartidos están en `src/components/shared.tsx`; el diálogo admite teclado y conserva el foco. Los estilos contemplan navegación móvil y movimiento reducido.

La prueba opcional `scripts/smoke_ui.py` requiere el entorno Python con Playwright y Chromium, además del frontend activo. Arranca su propia API y base temporal y redirige las peticiones del navegador hacia ella; no modifica tu espacio personal. Comprueba apertura directa, entrada manual, persistencia al recargar, CV, flujo de candidaturas y vista móvil:

```powershell
# Desde la raíz del repositorio
$env:PLAYWRIGHT_BROWSERS_PATH = "$PWD\storage\browsers"
.venv\Scripts\python.exe frontend\scripts\smoke_ui.py
```

Las capturas se escriben en `storage/reports/ui-*.png`. El script no publica contenido ni contacta empleadores.
