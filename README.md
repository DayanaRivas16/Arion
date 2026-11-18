# ARION

ARION es una aplicación web institucional para compartir y explorar proyectos. Incluye cuentas de usuario, publicación e interacción con proyectos, perfiles, soporte y un panel de administración.

## Funcionalidades

- Registro e inicio de sesión, incluida la autenticación con Google.
- Exploración de proyectos publicados, por categoría y autor.
- Publicación, edición y eliminación de proyectos con imágenes y documentos.
- Interacción con proyectos mediante visitas, “Me gusta” y valoraciones.
- Formulario de soporte y notificación por correo a los administradores.
- Panel de administración para gestionar usuarios y proyectos.
- Reportes de consultas de soporte y estadísticas de proyectos publicados por mes, categoría y actividad estudiantil.

## Requisitos

- Python 3.
- PostgreSQL.
- Una base de datos PostgreSQL con el esquema que utiliza la aplicación.

## Instalación en Windows

Desde PowerShell, en la carpeta del proyecto:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Si PowerShell bloquea la activación del entorno, puedes ejecutar los comandos con el intérprete del entorno directamente:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Configuración

1. Crea o selecciona la base de datos PostgreSQL que utilizará la aplicación.
2. En `app.py`, revisa la configuración `DB_HOST`, `DB_NAME`, `DB_USER` y `DB_PASS` y ajústala a tu servidor y base de datos. No publiques credenciales reales.
3. La aplicación espera que las tablas y columnas que consulta ya existan. Si ya preparaste las tablas en tu base, no necesitas volver a ejecutar SQL de creación.
4. Crea un archivo `.env` en la raíz para los servicios opcionales y la clave de sesión:

   ```dotenv
   SECRET_KEY=usa-una-clave-aleatoria-larga
   MAIL_USERNAME=tu-cuenta-de-correo
   MAIL_PASSWORD=tu-clave-de-aplicacion
   MAIL_DEFAULT_SENDER=tu-cuenta-de-correo
   GOOGLE_CLIENT_ID=tu-client-id
   GOOGLE_CLIENT_SECRET=tu-client-secret
   ```

   El envío de correos usa SMTP de Gmail. La autenticación con Google requiere credenciales OAuth configuradas para la URL de retorno `/google/callback`. No compartas ni subas el archivo `.env`.

> `arion.sql` es un respaldo de PostgreSQL, no un archivo SQL de texto para pegar directamente en el editor de consultas. Antes de restaurarlo, confirma que corresponde al esquema esperado por esta versión de la aplicación y que no sobrescribirá datos que quieras conservar.

## Ejecutar

Con el entorno virtual activado:

```powershell
python app.py
```

Abre la dirección local indicada por Flask en la consola. La ruta `/test-db` permite comprobar la conexión y obtener usuarios; úsala solo durante el desarrollo.

## Reportes del administrador

En **Reportes** se muestran primero las consultas de soporte y, debajo, las estadísticas. Los botones del encabezado permiten saltar a cualquiera de las secciones. Las estadísticas se calculan con los datos existentes en PostgreSQL y permiten filtrar por año:

- Proyectos publicados por mes, agrupados por fecha de creación.
- Distribución de proyectos publicados por categoría.
- Estudiantes con proyectos publicados, ordenados por vistas totales, junto con sus valoraciones promedio.

Si la base no contiene los campos o tablas requeridos por el código, la página de reportes mostrará un error de consulta; no se crean columnas ni tablas automáticamente.
