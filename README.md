# Mercado Campesino Digital de Yopal

Prototipo académico multipágina con cuentas para personas compradoras y campesinos productores.

## Apartados

- **Inicio** (`/`): presentación del proyecto.
- **Productos** (`/productos`): catálogo, búsqueda, filtros, carrito y reservas.
- **Cómo funciona** (`/como-funciona`): pasos, calendario semanal y preguntas frecuentes.
- **Productores** (`/productores`): perfiles ilustrativos y solicitud de participación.
- **Ingresar** (`/ingresar`): acceso para persona compradora, campesino productor o administrador.
- **Crear cuenta** (`/registro`): registro público únicamente para compradores y campesinos.
- **Mi cuenta** (`/cuenta`): panel privado según el rol.
- **Administración** (`/administracion`): panel privado para revisar reservas, solicitudes de productores y notificaciones.

## Cuentas y funciones

- Las cuentas se guardan en `mercado.db` (SQLite), creado automáticamente al iniciar la aplicación.
- Las contraseñas se almacenan con hash mediante Werkzeug; no se guardan como texto legible.
- Las personas compradoras ven sus datos y el historial de reservas que hicieron mientras estaban conectadas.
- Los campesinos ven los datos de su unidad productiva. En esta versión, publicar o editar productos desde el panel campesino todavía no está habilitado; el catálogo sigue usando productos de demostración definidos en `app.py`.
- El administrador tiene una tabla de acceso separada: no puede crearse desde el registro público.
- Cada nueva reserva y cada solicitud enviada desde Productores se guarda en SQLite y genera una notificación visible únicamente al administrador.
- El administrador puede marcar notificaciones como leídas y marcar reservas/solicitudes como revisadas. El contador de notificaciones aparece únicamente en la sesión administrativa.
- Se conserva la posibilidad de hacer reservas sin iniciar sesión. Las reservas hechas con sesión iniciada quedan asociadas a esa cuenta.
- Las solicitudes enviadas desde el formulario público de Productores y las reservas de demostración siguen siendo información de prototipo.

## Instalar y ejecutar en Windows

1. Instala Python desde https://www.python.org/downloads/ y marca **Add Python to PATH**.
2. Extrae el ZIP y abre la carpeta del proyecto en Visual Studio Code.
3. En la terminal, dentro de la carpeta que contiene `app.py`, ejecuta:

   ```powershell
   py -m pip install -r requirements.txt
   py app.py
   ```

4. Abre http://127.0.0.1:5000.

Para apagar el servidor, presiona `Ctrl + C` en la terminal.

## Acceso de administrador

Al iniciar la aplicación por primera vez se crea automáticamente una cuenta administrativa local, separada de las cuentas públicas:

- **Tipo de cuenta al ingresar:** Administrador
- **Correo:** `admin@mercadocampesino.local`
- **Contraseña inicial:** `AdminYopal2026!`
- **Panel:** http://127.0.0.1:5000/administracion

Cambia estas credenciales antes de usar datos reales. Para definirlas antes del primer inicio en PowerShell:

```powershell
$env:ADMIN_EMAIL="tu-correo-administrador@ejemplo.com"
$env:ADMIN_PASSWORD="UnaClaveLargaYUnica2026!"
$env:ADMIN_NAME="Administrador del mercado"
py app.py
```

La cuenta administrativa se crea una sola vez en `mercado.db`. Si ya se creó con las credenciales iniciales, cambiar las variables de entorno no cambia automáticamente la contraseña almacenada. Este panel muestra notificaciones dentro de la aplicación; no envía correos, SMS ni notificaciones push al teléfono.

## Probar los dos tipos de cuenta

1. En el menú selecciona **Crear cuenta**.
2. Registra una **Persona compradora** con nombre, correo, teléfono y contraseña.
3. Cierra sesión y crea otra cuenta seleccionando **Campesino productor**. Completa también finca, vereda y productos.
4. Ingresa con cada tipo de cuenta y comprueba que `/cuenta` muestra un panel diferente.

La contraseña debe tener al menos 8 caracteres. Para iniciar sesión selecciona el mismo tipo de cuenta con el que te registraste.

## Imágenes y rendimiento del catálogo

Coloca las fotografías en `static/img/`. La lista de nombres esperados está en `static/img/LEEME.txt`. Las fotografías personalizadas del proyecto anterior no se incluyen en este ZIP: copia tu carpeta `static/img/` anterior dentro de esta versión para conservarlas (mantén también `cart.svg`). Puedes cambiar las rutas de imagen en `app.py` o en las plantillas si utilizas otros nombres.

La página de Productos carga las imágenes de las tarjetas desde el inicio (`loading=eager`), usa decodificación asíncrona, dimensiones reservadas para evitar saltos de diseño, texto alternativo y un emoji de respaldo si una imagen no se encuentra. El buscador encuentra coincidencias en nombre, categoría, productor y ubicación; también puedes ordenar por nombre o precio.

### Optimización de velocidad (no es un cambio de diseño móvil)

- Las fotos de los productos se solicitan desde que abre el catálogo (`loading=eager`), para que estén disponibles al filtrar, ordenar o volver a verlas.
- Las tarjetas fuera de pantalla usan `content-visibility: auto` para reducir el trabajo de renderizado en catálogos largos.
- Las imágenes se decodifican en segundo plano para no bloquear el renderizado de la página.
- El servidor permite guardar CSS, JavaScript e imágenes en la caché del navegador durante 30 días.
- El buscador espera 100 ms después de que dejas de escribir antes de filtrar.

**Imágenes:** no necesitas instalar Pillow para que funcione la caché ni la carga anticipada. Mantén las fotografías en `static/img/`. Para que carguen rápido, conviene que las fotos de tarjetas estén cerca de 600 × 450 px y las portadas cerca de 1400 × 900 px.
Después reinicia Flask y recarga el catálogo con `Ctrl + F5`. La mejora más grande normalmente viene de reducir el peso de las fotos: una imagen de varios megabytes puede tardar mucho aunque el diseño esté optimizado.

## Limitaciones y seguridad

Este proyecto es un prototipo local, no está listo para publicar en internet ni para manejar datos reales. La clave secreta predeterminada es únicamente para desarrollo. Antes de desplegarlo, configura una variable de entorno `SECRET_KEY` fuerte, configura `ADMIN_EMAIL` y `ADMIN_PASSWORD` seguros, activa HTTPS, revisa políticas de privacidad y protección de datos y revisa el modelo de reservas e inventario. La publicación de productos desde cuentas campesinas no está implementada todavía.
