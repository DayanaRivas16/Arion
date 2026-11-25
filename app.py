from flask import Flask, render_template, redirect, url_for, session, flash, jsonify, request, abort
from dotenv import load_dotenv
from functools import wraps
import psycopg2
from psycopg2.extras import RealDictCursor
from authlib.integrations.flask_client import OAuth
from flask_mail import Mail, Message
import os
import math
from werkzeug.utils import secure_filename
from datetime import datetime
import uuid
from urllib.parse import urlsplit
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = False

# =====================================================================
# INICIALIZACIÓN Y FUNCIONES COMPARTIDAS
# =====================================================================

ID_TIPO_ESTUDIANTE = 1
ID_TIPO_DOCENTE = 2
ID_TIPO_ADMIN = 3

# ---------------------------------------------------------------------
# Acceso a la base de datos (para no repetir conexión y cursor en cada ruta)
# ---------------------------------------------------------------------
def consultar(sql, params=None, uno=False):
    """Corre un SELECT. Devuelve una lista de diccionarios, o un solo diccionario si uno=True."""
    conn = cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(sql, params or ())
        return cur.fetchone() if uno else cur.fetchall()
    finally:
        if cur: cur.close()
        if conn: conn.close()


def ejecutar_uno(sql, params=None):
    """Corre un INSERT/UPDATE/DELETE y guarda el cambio. Devuelve la fila del RETURNING,
    o None si no afectó ninguna fila (por ejemplo, si el id no existe)."""
    conn = cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(sql, params or ())
        # cur.description solo existe cuando la consulta lleva RETURNING
        fila = cur.fetchone() if cur.description else None
        conn.commit()
        return fila
    except Exception:
        if conn: conn.rollback()                         # si algo falla no queda nada a medias
        raise
    finally:
        if cur: cur.close()
        if conn: conn.close()


def _ok(msg):
    return jsonify(ok=True, msg=msg)


def _no(msg, codigo=404):
    return jsonify(ok=False, msg=msg), codigo


# ---------------------------------------------------------------------
# Roles
# ---------------------------------------------------------------------
def rol_clave(id_tipo):
    """Resume el id_tipo en administrador / docente / estudiante. Solo se usa para escoger
    el color de la etiqueta; el nombre que se muestra sale de tipos_usuario."""
    return {ID_TIPO_ADMIN: 'administrador', ID_TIPO_DOCENTE: 'docente'}.get(id_tipo, 'estudiante')


@app.template_filter('iniciales')
def iniciales(nombre):
    """'Ana Sofía Rodríguez' -> 'AS' (el circulito del avatar en la tabla)."""
    partes = (nombre or '?').split()
    return (partes[0][0] + (partes[1][0] if len(partes) > 1 else '')).upper()


# ---------------------------------------------------------------------
# Seguridad
# ---------------------------------------------------------------------
def admin_required(f):
    """Deja pasar solo a un administrador. El rol se guarda en la sesión (session['id_tipo'])
    cuando la persona inicia sesión, así que no hace falta consultar la BD en cada página.
    Esta verificación es la que protege el panel de verdad: la redirección del login solo
    decide a dónde mandar a cada quien, pero cualquiera podría escribir /admin/... en la barra."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            flash('Por favor, inicia sesión para acceder a esta página.', 'warning')
            return redirect(url_for('login'))
        if session.get('id_tipo') != ID_TIPO_ADMIN:
            # las llamadas fetch esperan JSON; las páginas normales, un 403
            if request.path.startswith('/admin/api/'):
                return _no('No tienes permisos de administrador.', 403)
            abort(403)
        return f(*args, **kwargs)
    return wrapper
# Conserva la validación que ya usaban las rutas administrativas.
admin_required_inicial = admin_required

def api_seguro(f):
    """Si algo revienta en una ruta /admin/api/ devolvemos JSON con el error, para que el
    JS lo muestre en el aviso en vez de recibir la página de error de Flask."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            app.logger.exception(f'Error en {request.path}: {e}')
            return _no('Hubo un error en el servidor, intenta de nuevo.', 500)
    return wrapper


@app.template_filter('tamano_legible')
def tamano_legible(b):
    # 4977015 -> "4.7 MB"
    if not b:
        return '—'
    for unidad in ('B', 'KB', 'MB', 'GB'):
        if b < 1024 or unidad == 'GB':
            return f"{b:.0f} {unidad}" if unidad == 'B' else f"{b:.1f} {unidad}"
        b /= 1024


def destino_volver():
    """A dónde regresa la ficha: la página desde la que se abrió (viene en ?volver=).
    Solo se aceptan rutas internas del panel; cualquier otra cosa vuelve al dashboard."""
    volver = request.values.get('volver', '')
    if volver.startswith('/admin') and not volver.startswith('//'):
        return volver
    return url_for('admin_dashboard')
# Los borradores son privados del estudiante, el panel solo modera estos tres
ESTADOS_MODERABLES = (
    'Pendiente',
    'Publicado',
    'Rechazado',
    'Observado',
    'Borrador'
)
PROYECTOS_POR_PAGINA = 10

def borrar_archivo_subido(ruta_relativa):
    """Borra un archivo guardado en static/ (portadas y documentos).
    Solo toca rutas que queden dentro de static para no borrar algo ajeno por error."""
    if not ruta_relativa:
        return
    base = os.path.abspath(app.static_folder)
    destino = os.path.abspath(os.path.join(base, ruta_relativa))
    if destino.startswith(base + os.sep) and os.path.isfile(destino):
        try:
            os.remove(destino)
        except OSError:
            app.logger.warning(f'No se pudo borrar el archivo {destino}')

SECCIONES_CONFIG = ('general', 'categorias', 'almacenamiento', 'permisos')

PERMISOS_ACCIONES = [
    ('subir',     'Subir y editar proyectos propios'),
    ('aprobar',   'Aprobar o rechazar proyectos escolares'),
    ('gestionar', 'Gestionar usuarios y cuentas'),
]
PERMISOS_ROLES = [
    ('estudiante',    'Estudiante'),
    ('docente',       'Docente'),
    ('administrador', 'Administrador'),
]
# Celdas de la matriz que no se pueden cambiar: el administrador siempre conserva todo
# (así nadie se queda sin acceso al panel), el estudiante nunca aprueba y solo el
# administrador gestiona usuarios.
PERMISOS_FIJOS = {
    ('aprobar', 'estudiante'), ('gestionar', 'estudiante'), ('gestionar', 'docente'),
    ('subir', 'administrador'), ('aprobar', 'administrador'), ('gestionar', 'administrador'),
}

# ---------------------------------------------------------------------
# Helpers de configuración
# ---------------------------------------------------------------------
def leer_config():
    """Lee la tabla configuracion (clave/valor) y devuelve cada ajuste ya con su tipo."""
    c = {f['clave']: f['valor'] for f in consultar("SELECT clave, valor FROM configuracion")}

    def entero(clave, defecto):
        try:
            return int(c.get(clave, defecto))
        except (TypeError, ValueError):
            return defecto

    def booleano(clave, defecto=True):
        return c.get(clave, 'true' if defecto else 'false') == 'true'

    return {
        'institucion': c.get('institucion', ''),
        'anio_lectivo': c.get('anio_lectivo', ''),
        'max_mb': entero('max_mb', 10),
        'moderacion': booleano('moderacion'),
        'permite_pdf': booleano('permite_pdf'),
        'permite_docx': booleano('permite_docx'),
        'almacenamiento_total_gb': entero('almacenamiento_total_gb', 20),
    }


def ejecutar_lote(sentencias):
    """Corre varias sentencias en una sola transacción: o se guardan todas o ninguna."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            for sql, params in sentencias:
                cur.execute(sql, params)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def guardar_config(pares):
    """Guarda ajustes {clave: valor}. Si la clave no existe la crea."""
    ejecutar_lote([
        ("""INSERT INTO configuracion (clave, valor) VALUES (%s, %s)
            ON CONFLICT (clave) DO UPDATE SET valor = EXCLUDED.valor""",
         (clave, 'true' if valor is True else 'false' if valor is False else str(valor)))
        for clave, valor in pares.items()
    ])


def bytes_en_carpeta(ruta):
    total = 0
    for raiz, _, archivos in os.walk(ruta):
        for nombre in archivos:
            try:
                total += os.path.getsize(os.path.join(raiz, nombre))
            except OSError:
                pass
    return total


def volver_config(seccion):
    return redirect(url_for('admin_configuracion', seccion=seccion))


# ---------------------------------------------------------------------
# Almacenamiento y archivos
# ---------------------------------------------------------------------
# ---------------------------------------------------------------------
# Permisos de roles
# ---------------------------------------------------------------------
# ======================================================
# CONFIGURACIÓN DE CARGA DE ARCHIVOS
# ======================================================

app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'uploads', 'proyectos')
UPLOAD_DOCUMENTOS = os.path.join(app.root_path, 'static', 'uploads', 'documentos')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024   # portada 5 MB + documentos 10 MB + texto

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(UPLOAD_DOCUMENTOS, exist_ok=True)

EXTENSIONES_PERMITIDAS = {'png', 'jpg', 'jpeg', 'webp'}
EXTENSIONES_DOCUMENTOS = {'pdf', 'docx'}

MAX_IMAGEN = 5 * 1024 * 1024
MAX_TOTAL_DOCUMENTOS = 10 * 1024 * 1024
MAX_DOCUMENTOS = 5

# ======================================================
# CONFIGURACIÓN DEL CORREO
# ======================================================

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False

app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER')

mail = Mail(app)


# ======================================================
# CONFIGURACIÓN DE GOOGLE OAUTH
# ======================================================

app.config['GOOGLE_CLIENT_ID'] = os.getenv('GOOGLE_CLIENT_ID')
app.config['GOOGLE_CLIENT_SECRET'] = os.getenv('GOOGLE_CLIENT_SECRET')

oauth = OAuth(app)

google = oauth.register(
    name='google',
    client_id=app.config['GOOGLE_CLIENT_ID'],
    client_secret=app.config['GOOGLE_CLIENT_SECRET'],
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={
        'scope': 'openid email profile'
    }
)

# =====================================================================
# CONFIGURACIÓN DE LA BASE DE DATOS POSTGRESQL
# =====================================================================
DB_HOST = "localhost"
DB_NAME = "arion_db"     #Recuerden que acá deben colocar el nombre de la base de datos que ustedes tienen.
DB_USER = "postgres"      
DB_PASS = "123456"  

def get_db_connection():
    """Establece una conexión limpia con la base de datos."""
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASS
    )
    return conn
# =====================================================================
# CONTROLES DE ACCESO
# =====================================================================

def login_required(f): #login required es un decorador que protege rutas que requieren autenticación
    @wraps(f) # el wraps preserva la información de la función original
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Por favor, inicia sesión para acceder a esta página.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function
MESES_ES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun',
            'jul', 'ago', 'sep', 'oct', 'nov', 'dic']


@app.template_filter('fecha_es')
def fecha_es(valor):
    # 25 Oct 2026 (strftime sale en inglés, por eso se arma a mano)
    if not valor:
        return '—'
    return f"{valor.day:02d} {MESES_ES[valor.month - 1].capitalize()} {valor.year}"


def admin_required(f):
    """Solo deja pasar a usuarios activos con rol administrador.
    Se consulta la BD en cada petición para que un cambio de rol aplique al instante."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Por favor, inicia sesión para acceder a esta página.', 'warning')
            return redirect(url_for('login'))

        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT 1
                    FROM usuarios u
                    JOIN tipos_usuario t ON t.id_tipo = u.id_tipo
                    WHERE u.id_usuario = %s
                      AND u.activo
                      AND LEFT(LOWER(t.nombre_tipo), 5) = 'admin'
                """, (session['user_id'],))
                es_admin = cur.fetchone()
        finally:
            conn.close()

        if not es_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated


def consultar(sql, params=None, uno=False):
    """SELECT rápido que devuelve dicts (una fila si uno=True, lista si no)."""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            return cur.fetchone() if uno else cur.fetchall()
    finally:
        conn.close()


def ejecutar(sql, params=None):
    """INSERT/UPDATE/DELETE con commit. Devuelve cuántas filas afectó."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            filas = cur.rowcount
        conn.commit()
        return filas
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def registrar_revision(id_proyecto, accion, comentario=None):
    """Deja constancia en el historial de quién revisó el proyecto y qué decidió."""
    try:
        ejecutar("""
            INSERT INTO historial_revisiones
                (id_proyecto, id_revisor, id_tipo_revisor, accion, comentario, numero_revision)
            VALUES (%s, %s, %s, %s, %s,
                    (SELECT COUNT(*) + 1 FROM historial_revisiones WHERE id_proyecto = %s))
        """, (id_proyecto, session['user_id'], session.get('id_tipo'),
              accion, comentario, id_proyecto))
    except Exception:
        # si el historial falla, la aprobación o el rechazo igual se queda guardado
        app.logger.exception('No se pudo guardar la revisión en el historial')

# =====================================================================
# Funciones auxiliares para proyectos
# =====================================================================
def tarjetas_proyectos(cursor, solo_destacados, limite):
    filtro = "AND p.es_destacado = TRUE" if solo_destacados else ""
    cursor.execute(f"""
        SELECT p.id_proyecto AS id, p.titulo,
               COALESCE(c.nombre_categoria, 'Sin categoría') AS categoria,
               COALESCE(u.nombre_completo, 'Autor desconocido') AS autor,
               p.calificacion::float AS rating,
               COALESCE(p.vistas_count, 0) AS vistas,
               p.imagen_portada
        FROM proyectos p
        LEFT JOIN categorias c ON c.id_categoria = p.id_categoria
        LEFT JOIN usuarios u ON u.id_usuario = p.id_usuario
        WHERE LOWER(p.estado) = 'publicado' {filtro}
        ORDER BY p.fecha_creacion DESC
        LIMIT %s;
    """, (limite,))
    filas = cursor.fetchall()
    for f in filas:
        f['imagen'] = url_for('static', filename=f['imagen_portada']) if f['imagen_portada'] else ''
        if 'user_id' not in session:
            f['rating'] = None
            f['vistas'] = None
    return filas
# ==========================================================
# GUARDAR ETIQUETAS DEL PROYECTO
# ==========================================================

def guardar_etiquetas(cursor, id_proyecto, texto_etiquetas):
    nombres = {
        nombre.strip().lower(): nombre.strip()
        for nombre in texto_etiquetas.split(',')
        if nombre.strip()
    }

    for nombre_normalizado, nombre in nombres.items():
        cursor.execute("""
            SELECT id_etiqueta
            FROM etiquetas
            WHERE LOWER(nombre_etiqueta) = %s
            LIMIT 1;
        """, (nombre_normalizado,))

        etiqueta = cursor.fetchone()

        if etiqueta:
            id_etiqueta = etiqueta['id_etiqueta']
        else:
            cursor.execute("""
                INSERT INTO etiquetas (nombre_etiqueta)
                VALUES (%s)
                RETURNING id_etiqueta;
            """, (nombre,))

            etiqueta = cursor.fetchone()
            id_etiqueta = etiqueta['id_etiqueta']

        cursor.execute("""
            INSERT INTO proyectos_etiquetas (id_proyecto, id_etiqueta)
            SELECT %s, %s
            WHERE NOT EXISTS (
                SELECT 1
                FROM proyectos_etiquetas
                WHERE id_proyecto = %s
                  AND id_etiqueta = %s
            );
        """, (
            id_proyecto,
            id_etiqueta,
            id_proyecto,
            id_etiqueta
        ))

def info_archivo(archivo):
    """Extensión, tamaño y primeros bytes de un archivo subido."""
    extension = os.path.splitext(archivo.filename or '')[1].lstrip('.').lower()
    archivo.stream.seek(0, os.SEEK_END)
    tamano = archivo.stream.tell()
    archivo.stream.seek(0)
    cabecera = archivo.stream.read(12)
    archivo.stream.seek(0)
    return extension, tamano, cabecera


def contenido_valido(extension, cabecera):
    """Comprueba que el contenido real coincida con la extensión."""
    if extension == 'png':
        return cabecera.startswith(b'\x89PNG')
    if extension in ('jpg', 'jpeg'):
        return cabecera.startswith(b'\xff\xd8')
    if extension == 'webp':
        return cabecera[:4] == b'RIFF' and cabecera[8:12] == b'WEBP'
    if extension == 'pdf':
        return cabecera.startswith(b'%PDF')
    if extension == 'docx':
        return cabecera.startswith(b'PK\x03\x04')
    return False


def datos_formulario(uid):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute("SELECT id_categoria AS id, nombre_categoria AS nombre FROM categorias ORDER BY nombre_categoria;")
        categorias = cursor.fetchall()
        cursor.execute("""
            SELECT id_usuario AS id, nombre_completo AS nombre, foto_perfil AS foto
            FROM usuarios
            WHERE id_usuario <> %s
              AND id_tipo = %s
              AND COALESCE(activo, TRUE) = TRUE
            ORDER BY nombre_completo;
        """, (uid, ID_TIPO_ESTUDIANTE))
        usuarios = cursor.fetchall()
    finally:
        cursor.close()
        conn.close()
    return {'categorias': categorias, 'usuarios': usuarios}
#=========================================================
#=========================================================
# ======================================================
# Controles para las rutas docentes
# ======================================================

def docente_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Por favor, inicia sesión para acceder a esta página.', 'warning')
            return redirect(url_for('login'))
        if session.get('id_tipo') != ID_TIPO_DOCENTE:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


@app.context_processor
def inyectar_pendientes_docente():
    if session.get('user_id') and session.get('id_tipo') == ID_TIPO_DOCENTE:
        conn = cur = None
        try:
            conn = get_db_connection()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SELECT nombre_completo FROM usuarios WHERE id_usuario = %s;", (session['user_id'],))
            docente = cur.fetchone()
            nombre_docente = (docente['nombre_completo'] or '').strip() if docente else ''

            cur.execute("""
                SELECT COUNT(*) AS total
                FROM proyectos
                WHERE LOWER(COALESCE(estado, '')) = 'pendiente'
                  AND LOWER(TRIM(COALESCE(profesor_a_cargo, ''))) = LOWER(TRIM(%s));
            """, (nombre_docente,))
            fila = cur.fetchone()
            return {'pendientes_revision_count': fila['total'] if fila else 0}
        except Exception:
            app.logger.exception('Error calculando pendientes del docente')
            return {'pendientes_revision_count': 0}
        finally:
            if cur: cur.close()
            if conn: conn.close()
    return {'pendientes_revision_count': 0}

@app.context_processor
def inyectar_notificaciones_usuario():
    uid = session.get('user_id')
    if not uid or session.get('id_tipo') != ID_TIPO_ESTUDIANTE:
        return {'notificaciones_usuario': [], 'notificaciones_count': 0}

    conn = cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT id_notificacion AS id,
                   tipo,
                   titulo,
                   mensaje,
                   motivo,
                   url_destino AS url,
                   fecha_creacion
            FROM notificaciones_usuario
            WHERE id_usuario = %s
              AND leida = FALSE
            ORDER BY fecha_creacion DESC, id_notificacion DESC
            LIMIT 10;
        """, (uid,))
        avisos = [dict(f) for f in cur.fetchall()]
        return {'notificaciones_usuario': avisos, 'notificaciones_count': len(avisos)}
    except Exception:
        app.logger.exception('Error cargando notificaciones del usuario')
        return {'notificaciones_usuario': [], 'notificaciones_count': 0}
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()
#=========================================================
#=========================================================
#=========================================================
#=========================================================
#=========================================================
#=========================================================


# BASE DE DATOS
# Comprueba la conexión a la base de datos y devuelve usuarios registrados.
@app.route('/test-db')
def test_db():
    try:
        # 1. Conectamos a la base de datos
        conn = get_db_connection()
        # Usamos RealDictCursor para que nos devuelva los resultados como diccionarios Python
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # 2. Hacemos una consulta para traer los usuarios (ajustada a esquema)
        cursor.execute("SELECT id_usuario, nombre_completo, correo_usuario FROM usuarios;")
        usuarios_registrados = cursor.fetchall()

        # 3. Cerramos los flujos de conexión de forma limpia
        cursor.close()
        conn.close()

        # 4. Mostramos el resultado en formato JSON en el navegador para verificar
        return jsonify({
            "status": "Conexión exitosa a PostgreSQL",
            "usuarios_en_bd": usuarios_registrados
        }), 200

    except Exception as e:
        # Si algo falla (contraseña mal puesta, BD apagada, etc.), te dirá el error exacto
        return jsonify({
            "status": "Error de conexión",
            "detalles": str(e)
        }), 500



# ACCESO Y REGISTRO
# Muestra el acceso o redirige si ya hay una sesión activa.
@app.route('/login') #muestra la página de login si no hay sesión activa, si ya hay sesión activa redirige al home
def login():

    if 'user_id' in session:
        if session.get('id_tipo') == ID_TIPO_ADMIN:
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('home'))
    return render_template('login.html')

# Dirige el registro al flujo de acceso institucional.
@app.route('/register')
def register():
    return redirect(url_for('login'))

# Inicia la autenticación con la cuenta de Google.
@app.route('/login/google')
def google_login(): #inica el proceso de autenticación con Google
    redirect_uri = url_for('google_callback', _external=True)
    return google.authorize_redirect(redirect_uri)

# Valida la respuesta de Google y crea o inicia la sesión.
@app.route('/google/callback')
def google_callback(): #maneja la respuesta de Google después de que el usuario autoriza la aplicación
    try:
        token = google.authorize_access_token()
        userinfo = token.get('userinfo')

        if not userinfo:
            flash('No fue posible obtener la información de Google.', 'error')
            return redirect(url_for('login'))

        google_id = userinfo.get('sub')
        email_google = userinfo.get('email')
        foto_google = userinfo.get('picture')

        if not isinstance(google_id, str) or not google_id.strip(): #isinstance verifica que google_id sea una cadena de texto y no esté vacía
            flash('Google no proporcionó un identificador de usuario válido.', 'error')
            return redirect(url_for('login'))

        if not isinstance(email_google, str) or not email_google.strip():
            flash('Google no proporcionó un correo electrónico.', 'error')
            return redirect(url_for('login'))

        if userinfo.get('email_verified') is not True:
            flash('Debes iniciar sesión con un correo verificado por Google.', 'error')
            return redirect(url_for('login'))

        google_id = google_id.strip()
        email = email_google.strip().lower()
        if email.count('@') != 1:
            flash('El correo electrónico no es válido.', 'error')
            return redirect(url_for('login'))
        parte_local, dominio_correo = email.split('@')
        if not parte_local or not dominio_correo:
            flash('El correo electrónico no es válido.', 'error')
            return redirect(url_for('login'))

        nombre_google = userinfo.get('name')
        nombre = nombre_google.strip() if isinstance(nombre_google, str) and nombre_google.strip() else parte_local

        conn = None
        cursor = None

        try:
            conn = get_db_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            cursor.execute("""
                SELECT id_dominio
                FROM dominios_permitidos
                WHERE LOWER(TRIM(BOTH '@' FROM BTRIM(dominio))) = %s;
            """, (dominio_correo,))
            dominio_permitido = cursor.fetchone()

            if not dominio_permitido:
                conn.rollback()
                flash('Debes usar un correo de un dominio institucional permitido.', 'error')
                return redirect(url_for('login'))

            id_dominio = dominio_permitido['id_dominio']

            cursor.execute("""
                SELECT id_usuario, nombre_completo, correo_usuario, google_id, id_tipo
                FROM usuarios
                WHERE LOWER(BTRIM(correo_usuario)) = %s
                   OR google_id = %s
                FOR UPDATE;
            """, (email, google_id))

            usuarios_encontrados = cursor.fetchall()

            if len(usuarios_encontrados) > 1:
                conn.rollback()
                app.logger.error(
                    'La autenticación de Google encontró cuentas duplicadas para el correo o identificador.'
                )
                flash('No fue posible validar tu cuenta. Contacta al administrador.', 'error')
                return redirect(url_for('login'))

            usuario = usuarios_encontrados[0] if usuarios_encontrados else None

            if usuario and usuario['google_id'] not in (None, google_id):
                conn.rollback()
                flash(
                    'Esta cuenta ya está vinculada a otra identidad de Google. Contacta al administrador.',
                    'error'
                )
                return redirect(url_for('login'))

            if usuario:
                cursor.execute("""
                    UPDATE usuarios
                    SET google_id = COALESCE(google_id, %s),
                        id_dominio = %s,
                        foto_perfil = COALESCE(foto_perfil, %s)
                    WHERE id_usuario = %s
                      AND (google_id IS NULL OR google_id = %s)
                    RETURNING id_usuario, nombre_completo, correo_usuario, google_id, id_tipo;
                """, (
                    google_id,
                    id_dominio,
                    foto_google,
                    usuario['id_usuario'],
                    google_id
                ))
                usuario = cursor.fetchone()
                if not usuario:
                    raise RuntimeError('La cuenta cambió durante la autenticación de Google.')
            else:
                cursor.execute("""
                    SELECT id_tipo
                    FROM tipos_usuario
                    WHERE LOWER(BTRIM(nombre_tipo)) = %s;
                """, ('estudiante',))
                roles_estudiante = cursor.fetchall()
                if len(roles_estudiante) != 1:
                    raise RuntimeError(
                        'Se esperaba exactamente un rol Estudiante en tipos_usuario.'
                    )

                cursor.execute("""
                    INSERT INTO usuarios
                    (
                        google_id,
                        nombre_completo,
                        correo_usuario,
                        id_tipo,
                        id_dominio,
                        foto_perfil
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id_usuario, nombre_completo, correo_usuario, google_id, id_tipo;
                """, (
                    google_id,
                    nombre,
                    email,
                    roles_estudiante[0]['id_tipo'],
                    id_dominio,
                    foto_google
                ))

                usuario = cursor.fetchone()

            conn.commit()

            session.clear()
            session['user_id'] = usuario['id_usuario']
            session['user_name'] = usuario['nombre_completo']
            session['user_email'] = usuario['correo_usuario']
            session['google_id'] = usuario['google_id']
            session['id_tipo'] = usuario['id_tipo']

            if usuario['id_tipo'] == ID_TIPO_ADMIN:
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('home'))

        except Exception as e:
            if conn:
                conn.rollback()

            app.logger.exception('Error registrando o iniciando sesión con Google: %s', e)
            flash('Ocurrió un error al crear o iniciar tu cuenta.', 'error')
            return redirect(url_for('login'))

        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    except Exception as e:
        app.logger.exception('Error en autenticación de Google: %s', e)
        flash('No fue posible iniciar sesión con Google.', 'error')
        return redirect(url_for('login'))



# ESTUDIANTE Y PÁGINAS PÚBLICAS
# Muestra el inicio con proyectos y datos destacados.
@app.route('/')
def home():
    stats = {'proyectos': 0, 'usuarios': 0, 'destacados': 0}
    proyectos = []
    solo_recientes = False
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute("""
            SELECT (SELECT COUNT(*) FROM proyectos WHERE LOWER(estado) = 'publicado') AS proyectos,
                   (SELECT COUNT(*) FROM usuarios) AS usuarios,
                   (SELECT COUNT(*) FROM proyectos WHERE LOWER(estado) = 'publicado' AND es_destacado) AS destacados;
        """)
        stats = cursor.fetchone()

        proyectos = tarjetas_proyectos(cursor, True, 12)
        if not proyectos:                       # si aún no hay destacados, se muestran los más recientes
            proyectos = tarjetas_proyectos(cursor, False, 8)
            solo_recientes = True
    except Exception:
        app.logger.exception('Error cargando el home')
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

    return render_template('home.html', stats=stats, proyectos=proyectos, solo_recientes=solo_recientes)

# Lista los proyectos publicados y prepara sus filtros.
@app.route('/explorar')
def explorar():
    filas = []
    autores = []
    categorias = []
    conn = None
    cursor = None
    autenticado = 'user_id' in session
    ordenes = {
        'recientes': 'p.fecha_creacion DESC NULLS LAST, p.id_proyecto DESC',
        'vistas': 'COALESCE(p.vistas_count, 0) DESC, p.fecha_creacion DESC NULLS LAST, p.id_proyecto DESC',
        'valorados': 'p.calificacion DESC NULLS LAST, p.fecha_creacion DESC NULLS LAST, p.id_proyecto DESC',
        'gustados': 'COALESCE(p.likes_count, 0) DESC, p.fecha_creacion DESC NULLS LAST, p.id_proyecto DESC',
    }
    orden = request.args.get('orden', 'recientes')
    if orden not in ordenes or (not autenticado and orden != 'recientes'):
        orden = 'recientes'

    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute(f"""
            SELECT p.id_proyecto AS id,
                   p.titulo,
                   p.descripcion,
                   COALESCE(c.nombre_categoria, 'Sin categoría') AS categoria,
                   COALESCE(u.nombre_completo, 'Autor desconocido') AS autor,
                   p.calificacion::float AS rating,
                   p.vistas_count AS vistas,
                   p.likes_count AS likes,
                   p.imagen_portada,
                   p.es_destacado AS destacado,
                   p.fecha_creacion
            FROM proyectos p
            LEFT JOIN categorias c ON c.id_categoria = p.id_categoria
            LEFT JOIN usuarios u ON u.id_usuario = p.id_usuario
            WHERE LOWER(p.estado) = 'publicado'
            ORDER BY {ordenes[orden]};
        """)
        filas = cursor.fetchall()

        # Obtener autores distintos de proyectos publicados para el filtro
        cursor.execute("""
            SELECT DISTINCT u.id_usuario AS id, u.nombre_completo AS nombre
            FROM usuarios u
            JOIN proyectos p ON u.id_usuario = p.id_usuario
            WHERE LOWER(p.estado) = 'publicado'
            ORDER BY u.nombre_completo ASC;
        """)
        autores = cursor.fetchall()

        cursor.execute("""
            SELECT id_categoria AS id, nombre_categoria AS nombre
            FROM categorias
            ORDER BY nombre_categoria ASC;
        """)
        categorias = cursor.fetchall()

    except Exception:
        app.logger.exception('Error cargando proyectos, autores o categorías')
        flash('No se pudieron cargar los proyectos.', 'danger')
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

    proyectos = []
    for f in filas:
        iniciales = ''.join(p[0] for p in f['autor'].split()[:2]).upper() or '?'
        descripcion = (f['descripcion'] or '').strip()
        proyectos.append({
            'id': f['id'],
            'title': f['titulo'],
            'description': descripcion[:180] + ('...' if len(descripcion) > 180 else ''),
            'category': f['categoria'],
            'author': f['autor'],
            'avatar': iniciales,
            'rating': f['rating'] if autenticado else None,
            'views': (f['vistas'] or 0) if autenticado else None,
            'likes': (f['likes'] or 0) if autenticado else None,
            'image': url_for('static', filename=f['imagen_portada']) if f['imagen_portada'] else '',
            'featured': bool(f['destacado']),
            'date': f['fecha_creacion'].timestamp() if f['fecha_creacion'] else 0,
        })

    return render_template('explorar_proyectos.html', proyectos=proyectos, autores=autores,
                           categorias=categorias, orden=orden)

# Muestra información sobre el equipo y la plataforma.
@app.route('/acerca-de')
def acerca_de():
    return render_template('acerca_de.html')

# Presenta los términos de uso de Arion.
@app.route('/terminos-y-condiciones')
def terminos_condiciones():
    return render_template('terminos-y-condiciones.html')

# Presenta la política de privacidad y tratamiento de datos.
@app.route('/politica-de-privacidad')
def politica_privacidad():
    return render_template('politica-de-privacidad.html')

# Muestra el detalle de un proyecto publicado.
@app.route('/proyecto/<int:id>')
@login_required
def ver_proyecto(id):
    uid = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute("""
            SELECT p.id_proyecto AS id, p.titulo, p.descripcion, p.imagen_portada AS imagen,
                   p.profesor_a_cargo AS profesor, p.grado, p.estado,
                   p.es_destacado AS destacado, p.vistas_count AS vistas, p.likes_count AS likes,
                   p.calificacion::float AS rating, p.fecha_creacion AS fecha,
                   p.id_usuario AS id_autor,
                   COALESCE(c.nombre_categoria, 'Sin categoría') AS categoria,
                   COALESCE(u.nombre_completo, 'Autor desconocido') AS autor_nombre,
                   u.foto_perfil AS autor_foto,
                   COALESCE((SELECT string_agg(e.nombre_etiqueta, ',' ORDER BY e.nombre_etiqueta)
                             FROM proyectos_etiquetas pe
                             JOIN etiquetas e ON e.id_etiqueta = pe.id_etiqueta
                             WHERE pe.id_proyecto = p.id_proyecto), '') AS etiquetas
            FROM proyectos p
            LEFT JOIN categorias c ON c.id_categoria = p.id_categoria
            LEFT JOIN usuarios u ON u.id_usuario = p.id_usuario
            WHERE p.id_proyecto = %s;
        """, (id,))
        p = cursor.fetchone()
        if not p:
            abort(404)

        es_autor = p['id_autor'] == uid
        es_docente = session.get('id_tipo') == ID_TIPO_DOCENTE
        nombre_actual = ''
        if es_docente:
            cursor.execute("SELECT nombre_completo FROM usuarios WHERE id_usuario = %s;", (uid,))
            doc_actual = cursor.fetchone()
            nombre_actual = (doc_actual['nombre_completo'] or '').strip().lower() if doc_actual else ''

        es_docente_asignado = (
            es_docente
            and bool(nombre_actual)
            and (
                (p['profesor'] or '').strip().lower() == nombre_actual
                or (p['profesor'] or '').strip().lower() in nombre_actual
                or nombre_actual in (p['profesor'] or '').strip().lower()
            )
        )

        estado_actual = (p['estado'] or '').strip().lower()
        puede_ver = (estado_actual == 'publicado') or es_autor or es_docente_asignado

        if not puede_ver:
            abort(404)

        # Suma una vista (no cuenta las del autor ni del docente revisor)
        p['vistas'] = p['vistas'] or 0
        if not es_autor and not es_docente_asignado:
            cursor.execute("UPDATE proyectos SET vistas_count = COALESCE(vistas_count, 0) + 1 WHERE id_proyecto = %s;", (id,))
            conn.commit()
            p['vistas'] += 1

        # Integrantes (el autor siempre aparece)
        cursor.execute("""
            SELECT u.id_usuario, u.nombre_completo AS nombre, u.foto_perfil AS foto, pc.rol_en_equipo AS rol
            FROM proyecto_colaboradores pc
            JOIN usuarios u ON u.id_usuario = pc.id_usuario
            WHERE pc.id_proyecto = %s
            ORDER BY (u.id_usuario = %s) DESC, u.nombre_completo;
        """, (id, p['id_autor']))
        integrantes = cursor.fetchall()
        if p['id_autor'] and not any(i['id_usuario'] == p['id_autor'] for i in integrantes):
            integrantes.insert(0, {'id_usuario': p['id_autor'], 'nombre': p['autor_nombre'],
                                   'foto': p['autor_foto'], 'rol': 'Autor'})

        # Documentos y enlace (el enlace se guarda como documento de tipo 'enlace')
        cursor.execute("""
            SELECT nombre_archivo AS nombre, url_archivo, tipo_documento AS tipo, tamano_bytes AS tamano
            FROM documentos_proyecto WHERE id_proyecto = %s ORDER BY fecha_subida;
        """, (id,))
        enlace, documentos = '', []
        for d in cursor.fetchall():
            if (d['tipo'] or '').lower() == 'enlace':
                if not enlace and d['url_archivo'].lower().startswith(('http://', 'https://')):
                    enlace = d['url_archivo']
            else:
                d['url'] = url_for('static', filename=d['url_archivo'])
                documentos.append(d)

        # Likes, valoración y datos del autor
        cursor.execute("SELECT EXISTS(SELECT 1 FROM proyecto_likes WHERE id_proyecto = %s AND id_usuario = %s) AS ya_like;", (id, uid))
        ya_like = cursor.fetchone()['ya_like']

        cursor.execute("SELECT puntuacion FROM proyecto_valoraciones WHERE id_proyecto = %s AND id_usuario = %s;", (id, uid))
        fila = cursor.fetchone()
        mi_valoracion = fila['puntuacion'] if fila else 0

        cursor.execute("SELECT COUNT(*) AS total FROM proyecto_valoraciones WHERE id_proyecto = %s;", (id,))
        total_valoraciones = cursor.fetchone()['total']

        cursor.execute("SELECT COUNT(*) AS total FROM proyectos WHERE id_usuario = %s AND LOWER(estado) = 'publicado';", (p['id_autor'],))
        proyectos_autor = cursor.fetchone()['total']
    finally:
        cursor.close()
        conn.close()

    proyecto = {
        'id': p['id'], 'titulo': p['titulo'], 'descripcion': p['descripcion'],
        'imagen': p['imagen'], 'profesor': p['profesor'], 'grado': p['grado'],
        'estado': p['estado'] or '', 'destacado': p['destacado'], 'vistas': p['vistas'],
        'likes': p['likes'] or 0, 'rating': p['rating'], 'fecha': p['fecha'],
        'categoria': p['categoria'],
        'etiquetas': [t for t in p['etiquetas'].split(',') if t],
    }
    autor = {'nombre': p['autor_nombre'], 'foto': p['autor_foto'], 'proyectos': proyectos_autor}

    return render_template('ver_proyecto.html', proyecto=proyecto, autor=autor,
                           integrantes=integrantes, documentos=documentos, enlace=enlace,
                           ya_like=ya_like, mi_valoracion=mi_valoracion,
                           total_valoraciones=total_valoraciones, es_autor=es_autor)

# Registra o retira la reacción del usuario al proyecto.
@app.route('/proyecto/<int:id>/like', methods=['POST'])
@login_required
def toggle_like(id):
    uid = session['user_id']
    conn = cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT id_usuario, estado FROM proyectos WHERE id_proyecto = %s;", (id,))
        p = cursor.fetchone()
        if not p or ((p['estado'] or '').lower() != 'publicado' and p['id_usuario'] != uid):
            return jsonify(error='Proyecto no encontrado.'), 404

        cursor.execute("DELETE FROM proyecto_likes WHERE id_proyecto = %s AND id_usuario = %s;", (id, uid))
        liked = cursor.rowcount == 0          # si no había like, ahora se agrega
        if liked:
            cursor.execute("INSERT INTO proyecto_likes (id_proyecto, id_usuario) VALUES (%s, %s) ON CONFLICT DO NOTHING;", (id, uid))

        # Se recalcula desde la tabla para que el contador nunca se desfase
        cursor.execute("""
            UPDATE proyectos
            SET likes_count = (SELECT COUNT(*) FROM proyecto_likes WHERE id_proyecto = %s)
            WHERE id_proyecto = %s RETURNING likes_count;
        """, (id, id))
        likes = cursor.fetchone()['likes_count']
        conn.commit()
        return jsonify(liked=liked, likes=likes)
    except Exception:
        if conn: conn.rollback()
        app.logger.exception('Error al registrar el like')
        return jsonify(error='No se pudo registrar tu me gusta.'), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

# Guarda la valoración del usuario para el proyecto.
@app.route('/proyecto/<int:id>/valorar', methods=['POST'])
@login_required
def valorar_proyecto(id):
    uid = session['user_id']
    datos = request.get_json(silent=True) or {}
    try:
        puntuacion = int(datos.get('puntuacion'))
    except (TypeError, ValueError):
        puntuacion = 0
    if not 1 <= puntuacion <= 5:
        return jsonify(error='La valoración debe ser de 1 a 5.'), 400

    conn = cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT id_usuario, estado FROM proyectos WHERE id_proyecto = %s;", (id,))
        p = cursor.fetchone()
        if not p or (p['estado'] or '').lower() != 'publicado':
            return jsonify(error='Proyecto no encontrado.'), 404
        if p['id_usuario'] == uid:
            return jsonify(error='No puedes valorar tu propio proyecto.'), 403

        cursor.execute("""
            INSERT INTO proyecto_valoraciones (id_proyecto, id_usuario, puntuacion)
            VALUES (%s, %s, %s)
            ON CONFLICT (id_proyecto, id_usuario)
            DO UPDATE SET puntuacion = EXCLUDED.puntuacion, fecha_valoracion = CURRENT_TIMESTAMP;
        """, (id, uid, puntuacion))

        cursor.execute("""
            UPDATE proyectos
            SET calificacion = (SELECT ROUND(AVG(puntuacion)::numeric, 1)
                                FROM proyecto_valoraciones WHERE id_proyecto = %s)
            WHERE id_proyecto = %s
            RETURNING calificacion::float AS promedio,
                      (SELECT COUNT(*) FROM proyecto_valoraciones WHERE id_proyecto = %s) AS total;
        """, (id, id, id))
        resultado = cursor.fetchone()
        conn.commit()
        return jsonify(promedio=resultado['promedio'], total=resultado['total'])
    except Exception:
        if conn: conn.rollback()
        app.logger.exception('Error al valorar')
        return jsonify(error='No se pudo guardar tu valoración.'), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

# Muestra y procesa el formulario de publicación de proyectos.
@app.route('/subir', methods=['GET', 'POST'])
@login_required
def subir():
    uid = session['user_id']

    if session.get('id_tipo') == ID_TIPO_DOCENTE:
        flash('Los docentes no pueden subir proyectos.', 'warning')
        return redirect(url_for('aprobaciones'))

    if request.method == 'GET':
        return render_template('subir_proyecto.html', **datos_formulario(uid))

    def volver(mensaje):
        flash(mensaje, 'danger')
        return redirect(url_for('subir'))

    # validar y procesar el formulario
    titulo = request.form.get('titulo', '').strip()
    descripcion = request.form.get('descripcion', '').strip()
    profesor = request.form.get('profesor', '').strip()
    grado = request.form.get('grado', '').strip()
    enlace = request.form.get('enlace', '').strip()
    estado_form = request.form.get('estado', '').strip().lower()
    etiquetas = ','.join(
        [t.strip()[:30] for t in request.form.get('etiquetas', '').split(',') if t.strip()][:10]
    )
    try:
        id_categoria = int(request.form.get('categoria', ''))
    except ValueError:
        id_categoria = None
    ids_integrantes = {int(v) for v in request.form.getlist('integrantes') if v.isdigit()}
    ids_integrantes.discard(uid)

    imagen = request.files.get('imagen_portada')
    documentos = [d for d in request.files.getlist('documentos') if d and d.filename]

    # Validar texto
    if not all([titulo, descripcion, profesor, grado, etiquetas]) or id_categoria is None:
        return volver('Completa todos los campos obligatorios.')
    if len(titulo) > 200 or len(profesor) > 150 or len(grado) > 50:
        return volver('Alguno de los textos es demasiado largo.')
    if estado_form not in ('publicado', 'borrador'):
        return volver('Selecciona un estado válido.')

    if enlace:
        if not enlace.lower().startswith(('http://', 'https://')):
            enlace = 'https://' + enlace
        if len(enlace) > 500 or ' ' in enlace or '.' not in enlace:
            return volver('El enlace del proyecto no es válido.')

    #  Validar la portada
    if not imagen or not imagen.filename:
        return volver('Elige una imagen de portada.')
    ext_img, tam_img, cab_img = info_archivo(imagen)
    if ext_img not in EXTENSIONES_PERMITIDAS or not contenido_valido(ext_img, cab_img):
        return volver('La portada debe ser una imagen PNG, JPG o WEBP.')
    if tam_img > MAX_IMAGEN:
        return volver('La portada supera los 5 MB.')

    # Validar los documentos
    if len(documentos) > MAX_DOCUMENTOS:
        return volver(f'Solo puedes subir hasta {MAX_DOCUMENTOS} documentos.')

    docs_validos = []
    total_docs = 0
    for d in documentos:
        ext_doc, tam_doc, cab_doc = info_archivo(d)
        if ext_doc not in EXTENSIONES_DOCUMENTOS or not contenido_valido(ext_doc, cab_doc):
            return volver(f'"{d.filename}" no es un PDF o DOCX válido.')
        total_docs += tam_doc
        docs_validos.append((d, ext_doc, tam_doc))

    if total_docs > MAX_TOTAL_DOCUMENTOS:
        return volver('Los documentos suman más de 10 MB. Quita alguno o reduce su tamaño.')

    # Guardar en la bd
    conn = None
    cursor = None
    escritos = []
    confirmado = False
    id_proyecto = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute("SELECT 1 FROM categorias WHERE id_categoria = %s;", (id_categoria,))
        if not cursor.fetchone():
            return volver('La categoría seleccionada no es válida.')

        # Solo integrantes que existan de verdad y sean estudiantes activos
        ids_ok = []
        if ids_integrantes:
            cursor.execute("""
                SELECT id_usuario
                FROM usuarios
                WHERE id_usuario = ANY(%s)
                  AND id_tipo = %s
                  AND COALESCE(activo, TRUE) = TRUE;
            """, (list(ids_integrantes), ID_TIPO_ESTUDIANTE))
            ids_ok = [f['id_usuario'] for f in cursor.fetchall()]

        # Portada
        nombre_img = f'{uuid.uuid4().hex}.{ext_img}'
        ruta_img = os.path.join(app.config['UPLOAD_FOLDER'], nombre_img)
        imagen.save(ruta_img)
        escritos.append(ruta_img)

        estado_bd = 'Pendiente' if estado_form == 'publicado' else 'Borrador'

        cursor.execute("""
            INSERT INTO proyectos (
                titulo, descripcion, imagen_portada, profesor_a_cargo, grado, estado,
                es_destacado, vistas_count, likes_count, calificacion, id_usuario, id_categoria
            )
            VALUES (%s, %s, %s, %s, %s, %s, FALSE, 0, 0, NULL, %s, %s)
            RETURNING id_proyecto;
        """, (
            titulo, descripcion, f'uploads/proyectos/{nombre_img}', profesor, grado,
            estado_bd,
            uid, id_categoria
        ))
        id_proyecto = cursor.fetchone()['id_proyecto']

        # Autor e integrantes
        cursor.execute(
            "INSERT INTO proyecto_colaboradores (id_proyecto, id_usuario, rol_en_equipo) VALUES (%s, %s, 'Autor');",
            (id_proyecto, uid)
        )
        for id_integrante in ids_ok:
            cursor.execute(
                "INSERT INTO proyecto_colaboradores (id_proyecto, id_usuario, rol_en_equipo) VALUES (%s, %s, 'Integrante');",
                (id_proyecto, id_integrante)
            )

        # Documentos
        for archivo, ext_doc, tam_doc in docs_validos:
            nombre_doc = f'{uuid.uuid4().hex}.{ext_doc}'
            ruta_doc = os.path.join(UPLOAD_DOCUMENTOS, nombre_doc)
            archivo.save(ruta_doc)
            escritos.append(ruta_doc)
            nombre_original = os.path.basename(archivo.filename.replace('\\', '/'))[:255]
            cursor.execute("""
                INSERT INTO documentos_proyecto (id_proyecto, nombre_archivo, url_archivo, tipo_documento, tamano_bytes)
                VALUES (%s, %s, %s, %s, %s);
            """, (id_proyecto, nombre_original, f'uploads/documentos/{nombre_doc}', ext_doc, tam_doc))

        # Enlace (se guarda como un documento de tipo 'enlace')
        if enlace:
            cursor.execute("""
                INSERT INTO documentos_proyecto (id_proyecto, nombre_archivo, url_archivo, tipo_documento, tamano_bytes)
                VALUES (%s, 'Enlace del proyecto', %s, 'enlace', NULL);
            """, (id_proyecto, enlace))

        guardar_etiquetas(cursor, id_proyecto, etiquetas)

        conn.commit()
        confirmado = True

    except Exception:
        if conn:
            conn.rollback()
        # Solo se borran los archivos si NO se alcanzó a guardar el proyecto
        if not confirmado:
            for ruta in escritos:
                if os.path.exists(ruta):
                    os.remove(ruta)
        app.logger.exception('Error al guardar el proyecto')
        return volver('No se pudo guardar el proyecto. Revisa la terminal de Flask.')

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

    if estado_bd == 'Pendiente':
        flash('¡Proyecto enviado a revisión del docente!', 'success')
    else:
        flash('¡Proyecto guardado en borradores correctamente!', 'success')
    return redirect(url_for('ver_proyecto', id=id_proyecto))

# Muestra el perfil y la actividad del usuario.
@app.route('/perfil')
@login_required
def perfil():
    uid = session['user_id']
    conn = None
    cursor = None
    usuario = {}
    proyectos = []
    borradores = []
    en_revision = []
    categorias = []
    mis_consultas = []

    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # 1. Datos del usuario y su rol
        cursor.execute("""
            SELECT u.nombre_completo AS nombre, u.correo_usuario AS correo,
                   u.foto_perfil AS foto, u.fecha_creacion AS desde,
                   t.nombre_tipo AS rol
            FROM usuarios u
            LEFT JOIN tipos_usuario t ON t.id_tipo = u.id_tipo
            WHERE u.id_usuario = %s;
        """, (uid,))
        usuario_db = cursor.fetchone()

        if not usuario_db:
            flash('No se encontró la información del usuario.', 'warning')
            return redirect(url_for('login'))

        usuario = {
            'nombre': usuario_db['nombre'],
            'correo': usuario_db['correo'],
            'foto': usuario_db['foto'],
            'desde': usuario_db['desde'],
            'rol': usuario_db['rol']
        }

        # 2. Mis proyectos publicados
        cursor.execute("""
            SELECT DISTINCT p.id_proyecto AS id, p.titulo, p.descripcion,
                   p.imagen_portada, p.estado, p.es_destacado AS destacado,
                   p.vistas_count AS vistas, p.likes_count AS likes,
                   p.calificacion::float AS rating, p.id_categoria,
                   COALESCE(c.nombre_categoria, 'Sin categoría') AS categoria,
                   (p.id_usuario = %s) AS es_autor,
                   p.fecha_creacion
            FROM proyectos p
            LEFT JOIN categorias c ON c.id_categoria = p.id_categoria
            LEFT JOIN proyecto_colaboradores pc ON pc.id_proyecto = p.id_proyecto
            WHERE LOWER(p.estado) = 'publicado'
              AND (p.id_usuario = %s OR pc.id_usuario = %s)
            ORDER BY p.fecha_creacion DESC;
        """, (uid, uid, uid))
        for p in cursor.fetchall():
            p_dict = dict(p)
            p_dict['imagen'] = url_for('static', filename=p_dict['imagen_portada']) if p_dict.get('imagen_portada') else ''
            proyectos.append(p_dict)

        # 3. Borradores
        cursor.execute("""
            SELECT p.id_proyecto AS id, p.titulo, p.descripcion,
                   p.imagen_portada, p.estado, p.motivo_rechazo,
                   p.es_destacado AS destacado,
                   p.vistas_count AS vistas, p.likes_count AS likes,
                   p.calificacion::float AS rating, p.id_categoria,
                   COALESCE(c.nombre_categoria, 'Sin categoría') AS categoria,
                   TRUE AS es_autor,
                   p.fecha_creacion
            FROM proyectos p
            LEFT JOIN categorias c ON c.id_categoria = p.id_categoria
            WHERE LOWER(p.estado) = 'borrador' AND p.id_usuario = %s
            ORDER BY p.fecha_creacion DESC;
        """, (uid,))
        for p in cursor.fetchall():
            p_dict = dict(p)
            p_dict['imagen'] = url_for('static', filename=p_dict['imagen_portada']) if p_dict.get('imagen_portada') else ''
            borradores.append(p_dict)

        # 4. Proyectos en revisión (solo los pendientes de aprobación del docente)
        en_revision = []
        try:
            cursor.execute("""
                SELECT DISTINCT p.id_proyecto AS id, p.titulo, p.descripcion,
                       p.imagen_portada, p.estado, p.motivo_rechazo,
                       p.es_destacado AS destacado,
                       p.vistas_count AS vistas, p.likes_count AS likes,
                       p.calificacion::float AS rating, p.id_categoria,
                       COALESCE(c.nombre_categoria, 'Sin categoría') AS categoria,
                       (p.id_usuario = %s) AS es_autor,
                       p.fecha_creacion
                FROM proyectos p
                LEFT JOIN categorias c ON c.id_categoria = p.id_categoria
                LEFT JOIN proyecto_colaboradores pc ON pc.id_proyecto = p.id_proyecto
                WHERE LOWER(COALESCE(p.estado, '')) = 'pendiente'
                  AND (p.id_usuario = %s OR pc.id_usuario = %s)
                ORDER BY p.fecha_creacion DESC;
            """, (uid, uid, uid))
            for p in cursor.fetchall():
                p_dict = dict(p)
                p_dict['imagen'] = url_for('static', filename=p_dict['imagen_portada']) if p_dict.get('imagen_portada') else ''
                en_revision.append(p_dict)
        except Exception:
            conn.rollback()
            app.logger.exception('Error cargando proyectos en revisión en perfil')

        # 5. Categorías
        cursor.execute("SELECT id_categoria AS id, nombre_categoria AS nombre FROM categorias ORDER BY nombre_categoria;")
        categorias = cursor.fetchall()

        # 6. Consultas de soporte
        try:
            cursor.execute("""
                SELECT s.id_soporte,
                       s.asunto,
                       s.descripcion,
                       s.estado,
                       s.respuesta,
                       s.fecha_creacion,
                       s.fecha_respuesta,
                       u_resp.nombre_completo AS respondido_por_nombre
                FROM soporte s
                LEFT JOIN usuarios u_resp ON u_resp.id_usuario = s.respondido_por
                WHERE s.usuario_id = %s
                ORDER BY s.fecha_creacion DESC;
            """, (uid,))
            mis_consultas = cursor.fetchall()
        except Exception:
            conn.rollback()
            app.logger.exception('Error cargando consultas de soporte en perfil')

    except Exception as e:
        if conn:
            conn.rollback()
        app.logger.exception('Error cargando el perfil del usuario')
        flash(f'No se pudo cargar la información del perfil: {e}', 'danger')

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

    return render_template(
        'mi_perfil.html',
        usuario=usuario,
        proyectos=proyectos,
        borradores=borradores,
        en_revision=en_revision,
        categorias=categorias,
        mis_consultas=mis_consultas
    )

# Muestra los recursos disponibles para el usuario.
@app.route('/recursos')
@login_required
def recursos():
    return render_template('recursos.html')

# Marca como leídas las notificaciones seleccionadas.
@app.route('/notificaciones/leer', methods=['POST'])
@login_required
def marcar_notificaciones_leidas():
    uid = session['user_id']
    notif_id = request.form.get('id', type=int)
    conn = cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        if notif_id:
            cur.execute("""
                UPDATE notificaciones_usuario
                SET leida = TRUE
                WHERE id_notificacion = %s AND id_usuario = %s;
            """, (notif_id, uid))
        else:
            cur.execute("""
                UPDATE notificaciones_usuario
                SET leida = TRUE
                WHERE id_usuario = %s AND leida = FALSE;
            """, (uid,))
        conn.commit()
    except Exception:
        if conn:
            conn.rollback()
        app.logger.exception('Error al marcar notificaciones como leídas')
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

    destino = request.form.get('destino') or (url_for('perfil') + '#tab-borradores')
    if not destino.startswith('/'):
        destino = url_for('perfil') + '#tab-borradores'
    return redirect(destino)

# Actualiza los datos y archivos de un proyecto existente.
@app.route('/proyecto/<int:id>/editar', methods=['POST'])
@login_required
def editar_proyecto(id):
    uid = session['user_id']

    titulo = request.form.get('titulo', '').strip()
    descripcion = request.form.get('descripcion', '').strip()
    estado_form = request.form.get('estado', '').strip().lower()
    enlace_raw = request.form.get('enlace', '').strip()

    try:
        id_categoria = int(request.form.get('categoria', ''))
    except ValueError:
        id_categoria = None

    if not titulo or not descripcion or id_categoria is None:
        flash('Completa todos los campos obligatorios para editar.', 'danger')
        return redirect(url_for('perfil'))

    if len(titulo) > 200:
        flash('El título no puede superar los 200 caracteres.', 'danger')
        return redirect(url_for('perfil'))

    if estado_form not in ('publicado', 'borrador'):
        flash('Selecciona un estado válido.', 'danger')
        return redirect(url_for('perfil'))

    enlace = ''
    if enlace_raw:
        enlace = enlace_raw if enlace_raw.lower().startswith(('http://', 'https://')) else 'https://' + enlace_raw
        if len(enlace) > 500 or ' ' in enlace or '.' not in enlace:
            flash('El enlace del proyecto no es válido.', 'danger')
            return redirect(url_for('perfil'))

    imagen = request.files.get('imagen_portada')
    documento = request.files.get('documento')

    nueva_img_info = None
    if imagen and imagen.filename:
        ext_img, tam_img, cab_img = info_archivo(imagen)
        if ext_img not in EXTENSIONES_PERMITIDAS or not contenido_valido(ext_img, cab_img):
            flash('La portada debe ser una imagen PNG, JPG o WEBP.', 'danger')
            return redirect(url_for('perfil'))
        if tam_img > MAX_IMAGEN:
            flash('La portada supera los 5 MB.', 'danger')
            return redirect(url_for('perfil'))
        nueva_img_info = (imagen, ext_img)

    nuevo_doc_info = None
    if documento and documento.filename:
        ext_doc, tam_doc, cab_doc = info_archivo(documento)
        if ext_doc not in EXTENSIONES_DOCUMENTOS or not contenido_valido(ext_doc, cab_doc):
            flash(f'"{documento.filename}" no es un PDF o DOCX válido.', 'danger')
            return redirect(url_for('perfil'))
        if tam_doc > MAX_TOTAL_DOCUMENTOS:
            flash('El documento supera los 10 MB permitidos.', 'danger')
            return redirect(url_for('perfil'))
        nuevo_doc_info = (documento, ext_doc, tam_doc)

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    archivos_nuevos_disco = []
    archivos_viejos_borrar = []
    confirmado = False

    try:
        cursor.execute("""
            SELECT p.id_usuario, p.estado, p.imagen_portada, u.id_tipo
            FROM proyectos p
            JOIN usuarios u ON u.id_usuario = %s
            WHERE p.id_proyecto = %s;
        """, (uid, id))
        resultado = cursor.fetchone()

        if not resultado:
            abort(404)

        id_autor_proyecto = resultado['id_usuario']
        estado_anterior = (resultado['estado'] or '').strip().lower()
        tipo_usuario_actual = resultado['id_tipo']

        cursor.execute("SELECT nombre_tipo FROM tipos_usuario WHERE id_tipo = %s;", (tipo_usuario_actual,))
        tipo_rol = cursor.fetchone()
        es_admin = tipo_rol and tipo_rol['nombre_tipo'].lower() in ['admin', 'administrador']

        if id_autor_proyecto != uid and not es_admin:
            abort(403)

        cursor.execute("SELECT 1 FROM categorias WHERE id_categoria = %s;", (id_categoria,))
        if not cursor.fetchone():
            flash('La categoría seleccionada no es válida.', 'danger')
            return redirect(url_for('perfil'))

        ruta_portada_bd = resultado['imagen_portada']
        if nueva_img_info:
            archivo_img, ext_img = nueva_img_info
            nombre_img = f'{uuid.uuid4().hex}.{ext_img}'
            ruta_disco_img = os.path.join(app.config['UPLOAD_FOLDER'], nombre_img)
            archivo_img.save(ruta_disco_img)
            archivos_nuevos_disco.append(ruta_disco_img)
            if resultado['imagen_portada']:
                archivos_viejos_borrar.append(resultado['imagen_portada'])
            ruta_portada_bd = f'uploads/proyectos/{nombre_img}'

        if estado_anterior == 'borrador':
            nuevo_estado = 'Pendiente'
            cursor.execute("""
                UPDATE proyectos
                SET titulo = %s,
                    descripcion = %s,
                    id_categoria = %s,
                    imagen_portada = %s,
                    estado = %s,
                    motivo_rechazo = NULL
                WHERE id_proyecto = %s;
            """, (titulo, descripcion, id_categoria, ruta_portada_bd, nuevo_estado, id))
            mensaje_exito = '¡Proyecto actualizado y enviado nuevamente a revisión!'
        else:
            nuevo_estado = 'Publicado' if estado_form == 'publicado' else 'Borrador'
            cursor.execute("""
                UPDATE proyectos
                SET titulo = %s,
                    descripcion = %s,
                    id_categoria = %s,
                    imagen_portada = %s,
                    estado = %s
                WHERE id_proyecto = %s;
            """, (titulo, descripcion, id_categoria, ruta_portada_bd, nuevo_estado, id))
            mensaje_exito = '¡Proyecto actualizado correctamente!'

        if nuevo_doc_info:
            archivo_doc, ext_doc, tam_doc = nuevo_doc_info
            nombre_doc = f'{uuid.uuid4().hex}.{ext_doc}'
            ruta_disco_doc = os.path.join(UPLOAD_DOCUMENTOS, nombre_doc)
            archivo_doc.save(ruta_disco_doc)
            archivos_nuevos_disco.append(ruta_disco_doc)

            cursor.execute("""
                SELECT url_archivo
                FROM documentos_proyecto
                WHERE id_proyecto = %s
                  AND LOWER(COALESCE(tipo_documento, '')) <> 'enlace';
            """, (id,))
            for fila_doc in cursor.fetchall():
                if fila_doc.get('url_archivo'):
                    archivos_viejos_borrar.append(fila_doc['url_archivo'])

            cursor.execute("""
                DELETE FROM documentos_proyecto
                WHERE id_proyecto = %s
                  AND LOWER(COALESCE(tipo_documento, '')) <> 'enlace';
            """, (id,))

            nombre_original = os.path.basename(archivo_doc.filename.replace('\\', '/'))[:255]
            cursor.execute("""
                INSERT INTO documentos_proyecto (id_proyecto, nombre_archivo, url_archivo, tipo_documento, tamano_bytes)
                VALUES (%s, %s, %s, %s, %s);
            """, (id, nombre_original, f'uploads/documentos/{nombre_doc}', ext_doc, tam_doc))

        if enlace:
            cursor.execute("""
                DELETE FROM documentos_proyecto
                WHERE id_proyecto = %s
                  AND LOWER(COALESCE(tipo_documento, '')) = 'enlace';
            """, (id,))
            cursor.execute("""
                INSERT INTO documentos_proyecto (id_proyecto, nombre_archivo, url_archivo, tipo_documento, tamano_bytes)
                VALUES (%s, 'Enlace del proyecto', %s, 'enlace', NULL);
            """, (id, enlace))

        conn.commit()
        confirmado = True
        for ruta_vieja in archivos_viejos_borrar:
            borrar_archivo_subido(ruta_vieja)
        flash(mensaje_exito, 'success')

    except Exception:
        if conn:
            conn.rollback()
        if not confirmado:
            for ruta_nueva in archivos_nuevos_disco:
                if os.path.exists(ruta_nueva):
                    os.remove(ruta_nueva)
        app.logger.exception('Error al actualizar el proyecto')
        flash('No se pudo actualizar el proyecto.', 'danger')
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('perfil'))

# Elimina un proyecto del usuario autenticado.
@app.route('/proyecto/<int:id>/eliminar', methods=['POST'])
@login_required
def eliminar_proyecto(id):
    uid = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute("SELECT id_usuario FROM proyectos WHERE id_proyecto = %s;", (id,))
        p = cursor.fetchone()
        if not p or p['id_usuario'] != uid:
            abort(403)

        cursor.execute("DELETE FROM proyectos WHERE id_proyecto = %s;", (id,))
        conn.commit()
        flash('Proyecto eliminado correctamente.', 'success')
    except Exception:
        conn.rollback()
        app.logger.exception('Error al eliminar el proyecto')
        flash('No se pudo eliminar el proyecto.', 'danger')
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('perfil'))

# Muestra el formulario y registra consultas de soporte.
@app.route('/soporte', methods=['GET', 'POST'])
def soporte():
    if request.method == 'GET':
        return render_template('soporte.html')

    if 'user_id' not in session:
        flash('Inicia sesión para enviar una consulta de soporte.', 'warning')
        return redirect(url_for('login'))

    uid = session['user_id']

    asunto = request.form.get('asunto', '').strip()
    descripcion = request.form.get('descripcion', '').strip()

    if not asunto or not descripcion:
        flash('El asunto y la descripción son obligatorios.', 'danger')
        return redirect(url_for('soporte'))

    if len(asunto) > 150:
        flash('El asunto no puede superar los 150 caracteres.', 'danger')
        return redirect(url_for('soporte'))

    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute("""
            INSERT INTO soporte (usuario_id, asunto, descripcion, estado)
            VALUES (%s, %s, %s, 'pendiente')
            RETURNING id_soporte;
        """, (uid, asunto, descripcion))
        cursor.fetchone()

        conn.commit()
    except Exception:
        if conn:
            conn.rollback()
        app.logger.exception('Error al guardar la consulta de soporte')
        flash('No se pudo registrar tu consulta. Inténtalo de nuevo.', 'danger')
        return redirect(url_for('soporte'))
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

    flash('¡Tu consulta fue registrada correctamente!', 'success')
    return redirect(url_for('soporte'))



# ADMINISTRACIÓN
# Muestra el resumen de actividad del panel administrativo.
@app.route('/admin/')
@admin_required_inicial
def admin_dashboard():
    stats = consultar("""
        SELECT
            (SELECT COUNT(*) FROM proyectos) AS total_proyectos,
            (SELECT COUNT(*) FROM proyectos
              WHERE fecha_creacion >= date_trunc('month', now())) AS creados_este_mes,
            (SELECT COUNT(*) FROM proyectos
              WHERE fecha_creacion >= date_trunc('month', now()) - interval '1 month'
                AND fecha_creacion <  date_trunc('month', now())) AS creados_mes_anterior,
            (SELECT COUNT(*) FROM usuarios u
               JOIN tipos_usuario t ON t.id_tipo = u.id_tipo
              WHERE u.activo AND LEFT(LOWER(t.nombre_tipo), 5) = 'estud') AS estudiantes,
            (SELECT COUNT(*) FROM proyectos WHERE estado = 'Pendiente') AS pendientes,
            (SELECT COUNT(*) FROM reportes_proyecto WHERE NOT resuelto) AS reportes
    """, uno=True)

    # Variación mensual; si el mes pasado no hubo proyectos no hay base para el porcentaje
    anterior = stats['creados_mes_anterior']
    variacion = None
    if anterior:
        variacion = round((stats['creados_este_mes'] - anterior) / anterior * 100)

    pendientes = consultar("""
        SELECT p.id_proyecto, p.titulo, p.grado, p.fecha_creacion,
               u.nombre_completo AS autor,
               c.nombre_categoria AS categoria
        FROM proyectos p
        JOIN usuarios u ON u.id_usuario = p.id_usuario
        LEFT JOIN categorias c ON c.id_categoria = p.id_categoria
        WHERE p.estado = 'Pendiente'
        ORDER BY p.fecha_creacion DESC
        LIMIT 5
    """)

    return render_template('admin/dashboard.html',
                            stats=stats, variacion=variacion, pendientes=pendientes)

@app.route('/proyectos/<int:id>/historial')
@login_required
def historial_proyecto(id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            SELECT h.numero_revision, h.accion, h.comentario,
                   h.fecha_revision AS fecha,
                   u.nombre_completo AS revisor,
                   t.nombre_tipo AS rol
            FROM historial_revisiones h
            LEFT JOIN usuarios u ON u.id_usuario = h.id_revisor
            LEFT JOIN tipos_usuario t ON t.id_tipo = h.id_tipo_revisor
            WHERE h.id_proyecto = %s
            ORDER BY h.fecha_revision ASC;
        """, (id,))
        filas = cur.fetchall()
    finally:
        cur.close()
        conn.close()

    for f in filas:
        f['fecha'] = f['fecha'].isoformat()
    return jsonify(filas)

@app.route('/admin/historial')
@admin_required_inicial
def historial_revisiones():
    filtro = request.args.get('accion', '')
    id_categoria = request.args.get('categoria', type=int)

    # Las fechas llegan como texto AAAA-MM-DD; si vienen mal escritas se ignoran
    def leer_fecha(nombre):
        try:
            return datetime.strptime(request.args.get(nombre, ''), '%Y-%m-%d').date()
        except ValueError:
            return None
    desde = leer_fecha('desde')
    hasta = leer_fecha('hasta')

    sql = """
        SELECT * FROM (
            SELECT h.id_revision, h.accion, h.comentario, h.fecha_revision,
                   p.titulo, p.imagen_portada, p.grado, p.id_categoria,
                   c.nombre_categoria AS categoria,
                   autor.nombre_completo AS autor,
                   u.nombre_completo AS revisor,
                   t.nombre_tipo AS rol,
                   COUNT(*) FILTER (WHERE h.accion = 'Observado')
                       OVER (PARTITION BY h.id_proyecto
                             ORDER BY h.fecha_revision, h.id_revision) AS n_observacion
            FROM historial_revisiones h
            JOIN proyectos p ON p.id_proyecto = h.id_proyecto
            LEFT JOIN categorias c ON c.id_categoria = p.id_categoria
            LEFT JOIN usuarios autor ON autor.id_usuario = p.id_usuario
            LEFT JOIN usuarios u ON u.id_usuario = h.id_revisor
            LEFT JOIN tipos_usuario t ON t.id_tipo = h.id_tipo_revisor
        ) x
    """
    # Cada filtro suma una condición; los valores van siempre en params
    condiciones, params = [], []
    if filtro in ('Aprobado', 'Observado', 'Rechazado'):
        condiciones.append("x.accion = %s")
        params.append(filtro)
    if id_categoria:
        condiciones.append("x.id_categoria = %s")
        params.append(id_categoria)
    if desde:
        condiciones.append("x.fecha_revision::date >= %s")
        params.append(desde)
    if hasta:
        condiciones.append("x.fecha_revision::date <= %s")
        params.append(hasta)
    if condiciones:
        sql += " WHERE " + " AND ".join(condiciones)
    sql += " ORDER BY x.fecha_revision DESC"

    historial = consultar(sql, params)
    categorias = consultar(
        "SELECT id_categoria, nombre_categoria FROM categorias ORDER BY nombre_categoria")

    return render_template('admin/historial_revisiones.html',
                           historial=historial, categorias=categorias,
                           filtro_accion=filtro, filtro_categoria=id_categoria,
                           desde=desde, hasta=hasta)

@app.route('/proyectos/<int:id>/revisar', methods=['POST'])
@login_required
def revisar_proyecto(id):
    accion = request.form.get('accion')
    comentario = request.form.get('comentario', '').strip()

    if accion not in ('Aprobado', 'Observado', 'Rechazado'):
        flash('Acción no válida.', 'danger')
        return redirect(request.referrer or url_for('home'))

    if accion != 'Aprobado' and not comentario:
        flash('Debes escribir un comentario.', 'danger')
        return redirect(request.referrer or url_for('home'))

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # Quién es el usuario y qué rol tiene
        cur.execute("SELECT id_tipo FROM usuarios WHERE id_usuario = %s",
                    (session['user_id'],))
        id_tipo = cur.fetchone()['id_tipo']

        # Ajusta estos números a los de la tabla tipos_usuario
        ES_PROFESOR, ES_ADMIN = 2, 3
        if id_tipo not in (ES_PROFESOR, ES_ADMIN):
            flash('No tienes permiso para revisar proyectos.', 'danger')
            return redirect(url_for('home'))

        # El profesor solo revisa sus proyectos; el admin revisa todos
        if id_tipo == ES_PROFESOR:
            cur.execute("""SELECT 1 FROM proyectos
                           WHERE id_proyecto = %s AND id_profesor = %s""",
                        (id, session['user_id']))
            if not cur.fetchone():
                flash('Este proyecto no está a tu cargo.', 'danger')
                return redirect(url_for('home'))

        cur.execute("SELECT COUNT(*) AS total FROM historial_revisiones WHERE id_proyecto = %s", (id,))
        numero = cur.fetchone()['total'] + 1

        estado_nuevo = {'Aprobado': 'Publicado',
                        'Observado': 'Observado',
                        'Rechazado': 'Rechazado'}[accion]

        cur.execute("""
            INSERT INTO historial_revisiones
                (id_proyecto, id_revisor, id_tipo_revisor, accion, comentario, numero_revision)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (id, session['user_id'], id_tipo, accion, comentario or None, numero))

        cur.execute("UPDATE proyectos SET estado = %s WHERE id_proyecto = %s",
                    (estado_nuevo, id))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

    return redirect(request.referrer or url_for('home'))

# Lista los proyectos para su gestión administrativa.
@app.route('/admin/proyectos')
@admin_required_inicial
def admin_proyectos():
    estado = request.args.get('estado', '')

    if estado not in ESTADOS_MODERABLES:
        estado = ''

    q = (request.args.get('q') or '').strip()
    pagina = max(request.args.get('pagina', 1, type=int), 1)

    # Contar absolutamente todos los proyectos
    conteos = consultar("""
            SELECT
            COUNT(*) AS todos,
            COUNT(*) FILTER (WHERE estado = 'Pendiente') AS pendientes,
            COUNT(*) FILTER (WHERE estado = 'Publicado') AS publicados,
            COUNT(*) FILTER (WHERE estado = 'Rechazado') AS rechazados,
            (
                SELECT COUNT(*)
                FROM proyectos p2
                WHERE (
                    SELECT h.accion
                    FROM historial_revisiones h
                    WHERE h.id_proyecto = p2.id_proyecto
                    ORDER BY h.fecha_revision DESC, h.id_revision DESC
                    LIMIT 1
                ) = 'Observado'
            ) AS observados,
            COUNT(*) FILTER (WHERE estado = 'Borrador') AS borradores
        FROM proyectos 
    """, uno=True)

    # No excluir ningún estado cuando se selecciona "Todos"
    condiciones = ["1=1"]
    params = []

    if estado == 'Observado':
        condiciones.append("""
            (
                SELECT h.accion
                FROM historial_revisiones h
                WHERE h.id_proyecto = p.id_proyecto
                ORDER BY h.fecha_revision DESC, h.id_revision DESC
                LIMIT 1
            ) = 'Observado'
        """)
    elif estado:
        condiciones.append("p.estado = %s")
        params.append(estado)

    if q:
        condiciones.append(
            "(p.titulo ILIKE %s OR u.nombre_completo ILIKE %s)"
        )
        params += [f'%{q}%', f'%{q}%']

    where = ' AND '.join(condiciones)

    total = consultar(f"""
        SELECT COUNT(*) AS n
        FROM proyectos p
        LEFT JOIN usuarios u ON u.id_usuario = p.id_usuario
        WHERE {where}
    """, params, uno=True)['n']

    total_paginas = max(
        math.ceil(total / PROYECTOS_POR_PAGINA), 1
    )
    pagina = min(pagina, total_paginas)

    proyectos = consultar(f"""
        SELECT
            p.id_proyecto,
            p.titulo,
            p.imagen_portada,
            p.grado,
            p.estado,
            p.es_destacado,
            p.fecha_creacion,
            (
                SELECT h.comentario
                FROM historial_revisiones h
                WHERE h.id_proyecto = p.id_proyecto
                AND h.accion = 'Observado'
                ORDER BY h.fecha_revision DESC, h.id_revision DESC
                LIMIT 1
            ) AS observacion,
            u.nombre_completo AS autor,
            c.nombre_categoria AS categoria
        FROM proyectos p
        LEFT JOIN usuarios u ON u.id_usuario = p.id_usuario
        LEFT JOIN categorias c ON c.id_categoria = p.id_categoria
        WHERE {where}
        ORDER BY
            CASE
                WHEN p.estado = 'Pendiente' THEN 1
                WHEN p.estado = 'Observado' THEN 2
                WHEN p.estado = 'Borrador' THEN 3
                ELSE 4
            END,
            p.fecha_creacion DESC
        LIMIT %s OFFSET %s
    """, params + [
        PROYECTOS_POR_PAGINA,
        (pagina - 1) * PROYECTOS_POR_PAGINA
    ])

    return render_template(
        'admin/proyectos.html',
        proyectos=proyectos,
        conteos=conteos,
        estado=estado,
        q=q,
        pagina=pagina,
        total_paginas=total_paginas,
        total=total
    )

# Muestra la ficha de revisión de un proyecto.
@app.route('/admin/proyectos/<int:id>')
@admin_required_inicial
def admin_revisar_proyecto(id):
    proyecto = consultar("""
        SELECT p.*,
               u.nombre_completo AS autor,
               u.correo_usuario  AS autor_correo,
               c.nombre_categoria AS categoria
        FROM proyectos p
        LEFT JOIN usuarios u ON u.id_usuario = p.id_usuario
        LEFT JOIN categorias c ON c.id_categoria = p.id_categoria
        WHERE p.id_proyecto = %s
    """, (id,), uno=True)

    if not proyecto:
        abort(404)

    etiquetas = consultar("""
        SELECT e.nombre_etiqueta
        FROM proyectos_etiquetas pe
        JOIN etiquetas e ON e.id_etiqueta = pe.id_etiqueta
        WHERE pe.id_proyecto = %s
        ORDER BY e.nombre_etiqueta
    """, (id,))

    documentos = consultar("""
        SELECT nombre_archivo, url_archivo, tipo_documento, tamano_bytes, fecha_subida
        FROM documentos_proyecto
        WHERE id_proyecto = %s
        ORDER BY fecha_subida
    """, (id,))

    colaboradores = consultar("""
        SELECT u.nombre_completo, pc.rol_en_equipo
        FROM proyecto_colaboradores pc
        JOIN usuarios u ON u.id_usuario = pc.id_usuario
        WHERE pc.id_proyecto = %s
        ORDER BY (pc.rol_en_equipo = 'Autor') DESC, u.nombre_completo
    """, (id,))

    reportes = consultar("""
        SELECT r.motivo, r.fecha, u.nombre_completo AS reportado_por
        FROM reportes_proyecto r
        LEFT JOIN usuarios u ON u.id_usuario = r.id_usuario
        WHERE r.id_proyecto = %s AND NOT r.resuelto
        ORDER BY r.fecha DESC
    """, (id,))

    volver_url = destino_volver()
    if urlsplit(volver_url).path == '/admin/proyectos':
        volver_texto = 'Volver a proyectos'
    else:
        volver_texto = 'Volver al dashboard'

    return render_template('admin/revisar_proyecto.html',
                            p=proyecto, etiquetas=etiquetas, documentos=documentos,
                            colaboradores=colaboradores, reportes=reportes,
                            volver_url=volver_url, volver_texto=volver_texto)

# Aprueba un proyecto desde el panel administrativo.
@app.route('/admin/proyectos/<int:id>/aprobar', methods=['POST'])
@admin_required_inicial
def admin_aprobar_proyecto(id):
    filas = ejecutar("""
        UPDATE proyectos
        SET estado = 'Publicado',
            motivo_rechazo = NULL
        WHERE id_proyecto = %s AND estado = 'Pendiente'
    """, (id,))

    if filas:
        registrar_revision(id, 'Aprobado')
        flash('Proyecto aprobado y publicado.', 'success')
    else:
        flash('Ese proyecto ya no está pendiente.', 'warning')

    # Vuelve a la página desde donde se pulsó el botón
    return redirect(request.referrer or url_for('admin_dashboard'))

# Rechaza un proyecto desde el panel administrativo.
@app.route('/admin/proyectos/<int:id>/rechazar', methods=['POST'])
@admin_required_inicial
def admin_rechazar_proyecto(id):
    motivo = (request.form.get('motivo') or '').strip()
    volver = destino_volver()

    # El estudiante necesita saber qué corregir, así que el motivo es obligatorio
    if len(motivo) < 10:
        flash('Escribe un motivo de rechazo (mínimo 10 caracteres).', 'warning')
        return redirect(url_for('admin_revisar_proyecto', id=id, volver=volver))

    filas = ejecutar("""
        UPDATE proyectos
        SET estado = 'Rechazado', motivo_rechazo = %s
        WHERE id_proyecto = %s AND estado = 'Pendiente'
    """, (motivo, id))

    if filas:
        registrar_revision(id, 'Rechazado', motivo)
        flash('Proyecto rechazado.', 'success')
    else:
        flash('Ese proyecto ya no está pendiente.', 'warning')

    return redirect(volver)

# Alterna el estado destacado de un proyecto.
@app.route('/admin/proyectos/<int:id>/destacar', methods=['POST'])
@admin_required_inicial
def admin_destacar_proyecto(id):
    destacar = request.form.get('valor') == '1'

    # Solo se pueden destacar proyectos ya publicados
    filas = ejecutar("""
        UPDATE proyectos
        SET es_destacado = %s
        WHERE id_proyecto = %s AND estado = 'Publicado'
    """, (destacar, id))

    if not filas:
        flash('Solo los proyectos publicados pueden destacarse.', 'warning')
    elif destacar:
        flash('Proyecto destacado.', 'success')
    else:
        flash('Se quitó el destacado del proyecto.', 'success')

    return redirect(request.referrer or url_for('admin_proyectos'))

# Elimina un proyecto desde el panel administrativo.
@app.route('/admin/proyectos/<int:id>/eliminar', methods=['POST'])
@admin_required_inicial
def admin_eliminar_proyecto(id):
    # Se anotan los archivos antes de borrar, porque el DELETE se lleva
    # también las filas de documentos_proyecto (ON DELETE CASCADE)
    archivos = consultar("""
        SELECT url_archivo AS ruta FROM documentos_proyecto WHERE id_proyecto = %s
        UNION ALL
        SELECT imagen_portada FROM proyectos
        WHERE id_proyecto = %s AND imagen_portada IS NOT NULL
    """, (id, id))

    filas = ejecutar("DELETE FROM proyectos WHERE id_proyecto = %s", (id,))

    if filas:
        for a in archivos:
            borrar_archivo_subido(a['ruta'])
        flash('Proyecto eliminado.', 'success')
    else:
        flash('Ese proyecto ya no existe.', 'warning')

    return redirect(request.referrer or url_for('admin_proyectos'))

# Muestra los reportes y consultas de soporte recibidos.
@app.route('/admin/reportes')
@admin_required_inicial
def admin_reportes():
    consultas = consultar("""
        SELECT s.id_soporte,
               u.nombre_completo AS nombre,
               u.correo_usuario AS correo,
               s.asunto,
               s.descripcion,
               s.estado
        FROM soporte s
        JOIN usuarios u ON u.id_usuario = s.usuario_id
        ORDER BY CASE WHEN LOWER(s.estado) = 'pendiente' THEN 0 ELSE 1 END,
                 s.fecha_creacion DESC;
    """)
    total_consultas = len(consultas)
    consultas_pendientes = sum(
        1 for consulta in consultas
        if (consulta.get('estado') or '').strip().lower() == 'pendiente'
    )

    anios_disponibles = consultar("""
        SELECT DISTINCT EXTRACT(YEAR FROM fecha_creacion)::int AS anio
        FROM proyectos
        WHERE LOWER(estado) = 'publicado'
        ORDER BY anio DESC;
    """)
    anios_disponibles = [fila['anio'] for fila in anios_disponibles]
    anio_solicitado = request.args.get('anio', type=int)
    anio_actual = anio_solicitado if anio_solicitado in anios_disponibles else (
        anios_disponibles[0] if anios_disponibles else datetime.now().year
    )

    proyectos_por_mes = consultar("""
        SELECT EXTRACT(MONTH FROM fecha_creacion)::int AS mes, COUNT(*) AS total
        FROM proyectos
        WHERE LOWER(estado) = 'publicado'
          AND EXTRACT(YEAR FROM fecha_creacion) = %s
        GROUP BY mes
        ORDER BY mes;
    """, (anio_actual,))
    totales_por_mes = {fila['mes']: fila['total'] for fila in proyectos_por_mes}
    nombres_meses = (
        'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
        'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre',
    )
    max_proyectos_mes = max(totales_por_mes.values(), default=0)
    meses = [
        {
            'nombre': nombre,
            'total': totales_por_mes.get(numero, 0),
            'porcentaje': (
                totales_por_mes.get(numero, 0) * 100 / max_proyectos_mes
                if max_proyectos_mes else 0
            ),
        }
        for numero, nombre in enumerate(nombres_meses, start=1)
    ]

    categorias = consultar("""
        SELECT COALESCE(c.nombre_categoria, 'Sin categoría') AS nombre,
               COUNT(*) AS total
        FROM proyectos p
        LEFT JOIN categorias c ON c.id_categoria = p.id_categoria
        WHERE LOWER(p.estado) = 'publicado'
          AND EXTRACT(YEAR FROM p.fecha_creacion) = %s
        GROUP BY nombre
        ORDER BY total DESC, nombre;
    """, (anio_actual,))
    total_proyectos_anio = sum(categoria['total'] for categoria in categorias)
    for categoria in categorias:
        categoria['porcentaje'] = (
            categoria['total'] * 100 / total_proyectos_anio
            if total_proyectos_anio else 0
        )

    estudiantes = consultar("""
        SELECT u.nombre_completo AS nombre,
               u.grado,
               COUNT(p.id_proyecto) AS proyectos,
               AVG(p.calificacion)::float AS valoracion_promedio,
               COALESCE(SUM(p.vistas_count), 0) AS vistas_totales
        FROM usuarios u
        JOIN proyectos p ON p.id_usuario = u.id_usuario
        WHERE u.id_tipo = %s
          AND LOWER(p.estado) = 'publicado'
          AND EXTRACT(YEAR FROM p.fecha_creacion) = %s
        GROUP BY u.id_usuario, u.nombre_completo, u.grado
        ORDER BY vistas_totales DESC, proyectos DESC, u.nombre_completo
        LIMIT 10;
    """, (ID_TIPO_ESTUDIANTE, anio_actual))

    return render_template(
        'admin/reportes.html',
        consultas=consultas,
        total_consultas=total_consultas,
        consultas_pendientes=consultas_pendientes,
        otras_consultas=total_consultas - consultas_pendientes,
        anios_disponibles=anios_disponibles or [anio_actual],
        anio_actual=anio_actual,
        meses=meses,
        categorias=categorias,
        total_proyectos_anio=total_proyectos_anio,
        estudiantes=estudiantes,
    )

# Muestra la configuración de la plataforma.
@app.route('/admin/configuracion')
@admin_required_inicial
def admin_configuracion():
    seccion = request.args.get('seccion', 'general')
    if seccion not in SECCIONES_CONFIG:
        seccion = 'general'

    config = leer_config()
    datos = {}

    if seccion == 'categorias':
        datos['categorias'] = consultar("""
            SELECT c.id_categoria, c.nombre_categoria, c.descripcion,
                    COUNT(p.id_proyecto) AS proyectos
            FROM categorias c
            LEFT JOIN proyectos p ON p.id_categoria = c.id_categoria
            GROUP BY c.id_categoria
            ORDER BY c.nombre_categoria
        """)

    elif seccion == 'almacenamiento':
        # Se mide lo que realmente hay en disco (portadas y documentos), no una cifra guardada
        carpeta = os.path.join(app.static_folder, 'uploads')
        portadas = bytes_en_carpeta(os.path.join(carpeta, 'proyectos'))
        documentos = bytes_en_carpeta(os.path.join(carpeta, 'documentos'))
        usado = portadas + documentos
        total = config['almacenamiento_total_gb'] * 1024 ** 3
        datos.update(usado=usado, total=total, portadas=portadas, documentos=documentos,
                     porcentaje=min(round(usado * 100 / total, 1), 100) if total else 0)

    elif seccion == 'permisos':
        filas = consultar("SELECT accion, rol, permitido FROM permisos_rol")
        datos['marcados'] = {f"{f['accion']}__{f['rol']}": f['permitido'] for f in filas}
        datos['acciones'] = PERMISOS_ACCIONES
        datos['roles'] = PERMISOS_ROLES
        datos['fijos'] = {f"{a}__{r}" for a, r in PERMISOS_FIJOS}

    return render_template('admin/configuracion.html', seccion=seccion, config=config, **datos)

# Guarda los cambios de configuración general.
@app.route('/admin/configuracion/general', methods=['POST'])
@admin_required_inicial
def admin_guardar_general():
    institucion = (request.form.get('institucion') or '').strip()
    anio = (request.form.get('anio_lectivo') or '').strip()
    max_mb = request.form.get('max_mb', type=int)

    if not institucion or len(institucion) > 150:
        flash('El nombre de la institución es obligatorio (máximo 150 caracteres).', 'warning')
        return volver_config('general')
    if not anio or len(anio) > 50:
        flash('El año lectivo es obligatorio (máximo 50 caracteres).', 'warning')
        return volver_config('general')
    # El servidor acepta 16 MB por envío (MAX_CONTENT_LENGTH), así que un archivo no puede pasar de ahí
    if max_mb is None or not 1 <= max_mb <= 15:
        flash('El tamaño máximo por archivo debe estar entre 1 y 15 MB.', 'warning')
        return volver_config('general')

    guardar_config({
        'institucion': institucion,
        'anio_lectivo': anio,
        'max_mb': max_mb,
        'moderacion': request.form.get('moderacion') == 'on',
    })
    flash('Parámetros generales guardados.', 'success')
    return volver_config('general')

# Crea una categoría para clasificar proyectos.
@app.route('/admin/configuracion/categorias/crear', methods=['POST'])
@admin_required_inicial
def admin_crear_categoria():
    nombre = (request.form.get('nombre') or '').strip()
    descripcion = (request.form.get('descripcion') or '').strip()[:300] or None

    if not nombre or len(nombre) > 100:
        flash('El nombre de la categoría es obligatorio (máximo 100 caracteres).', 'warning')
        return volver_config('categorias')

    # La BD ya impide nombres repetidos, pero así se compara sin importar mayúsculas
    existe = consultar("SELECT 1 FROM categorias WHERE LOWER(BTRIM(nombre_categoria)) = LOWER(%s)",
                        (nombre,), uno=True)
    if existe:
        flash(f'Ya existe una categoría llamada «{nombre}».', 'warning')
        return volver_config('categorias')

    ejecutar("""INSERT INTO categorias (nombre_categoria, descripcion)
                VALUES (%s, %s)""", (nombre, descripcion))
    flash(f'Categoría «{nombre}» creada.', 'success')
    return volver_config('categorias')

# Elimina una categoría existente.
@app.route('/admin/configuracion/categorias/<int:id>/eliminar', methods=['POST'])
@admin_required_inicial
def admin_eliminar_categoria(id):
    cat = consultar("""
        SELECT nombre_categoria,
               (SELECT COUNT(*) FROM proyectos WHERE id_categoria = %s) AS proyectos,
               (SELECT COUNT(*) FROM categorias) AS total
        FROM categorias WHERE id_categoria = %s
    """, (id, id), uno=True)

    if not cat:
        flash('Esa categoría ya no existe.', 'warning')
        return volver_config('categorias')
    # Al subir un proyecto es obligatorio elegir categoría, sin ninguna nadie podría subir
    if cat['total'] <= 1:
        flash('No puedes eliminar la única categoría que queda.', 'warning')
        return volver_config('categorias')

    ejecutar("DELETE FROM categorias WHERE id_categoria = %s", (id,))
    mensaje = f"Categoría «{cat['nombre_categoria']}» eliminada."
    if cat['proyectos']:
        mensaje += f" {cat['proyectos']} proyecto(s) quedaron sin categoría."
    flash(mensaje, 'success')
    return volver_config('categorias')

# Guarda los límites de almacenamiento configurados.
@app.route('/admin/configuracion/almacenamiento', methods=['POST'])
@admin_required_inicial
def admin_guardar_almacenamiento():
    permite_pdf = request.form.get('permite_pdf') == 'on'
    permite_docx = request.form.get('permite_docx') == 'on'

    if not (permite_pdf or permite_docx):
        flash('Debe quedar al menos un formato permitido.', 'warning')
        return volver_config('almacenamiento')

    guardar_config({'permite_pdf': permite_pdf, 'permite_docx': permite_docx})
    flash('Formatos permitidos guardados.', 'success')
    return volver_config('almacenamiento')

# Guarda los permisos configurados para los roles.
@app.route('/admin/configuracion/permisos', methods=['POST'])
@admin_required_inicial
def admin_guardar_permisos():
    sentencias = []
    for accion, _ in PERMISOS_ACCIONES:
        for rol, _ in PERMISOS_ROLES:
            if (accion, rol) in PERMISOS_FIJOS:
                continue            # las celdas fijas no se tocan aunque alguien manipule el formulario
            marcado = f'{accion}__{rol}' in request.form
            sentencias.append((
                "UPDATE permisos_rol SET permitido = %s WHERE accion = %s AND rol = %s",
                (marcado, accion, rol)))

    ejecutar_lote(sentencias)
    flash('Permisos guardados.', 'success')
    return volver_config('permisos')

# Lista las cuentas para su gestión administrativa.
@app.route('/admin/usuarios')
@admin_required_inicial
def admin_usuarios():
    q = request.args.get('q', '').strip()
    rol = request.args.get('rol', type=int)              # id_tipo elegido en el filtro (o None)
    grado = request.args.get('grado', '')

    # El WHERE se arma por pedazos según los filtros que lleguen. Los valores van siempre
    # en `params` (nunca pegados al texto del SQL) para evitar inyección.
    filtros, params = [], []
    if q:
        filtros.append("(LOWER(u.nombre_completo) LIKE %s OR LOWER(u.correo_usuario) LIKE %s "
                       "OR CAST(u.id_usuario AS TEXT) LIKE %s)")
        params += [f"%{q.lower()}%"] * 3
    if rol:
        filtros.append("u.id_tipo = %s")
        params.append(rol)
    if grado:
        filtros.append("u.grado = %s")
        params.append(grado)
    donde = ("WHERE " + " AND ".join(filtros)) if filtros else ""
    desde = "FROM usuarios u LEFT JOIN tipos_usuario t ON t.id_tipo = u.id_tipo"

    # Paginación: 10 por página. El total sirve para saber cuántas páginas hay.
    por_pagina = 10
    total = consultar(f"SELECT COUNT(*) AS n {desde} {donde}", params, uno=True)['n']
    paginas = max(1, -(-total // por_pagina))            # división hacia arriba
    pagina = min(max(request.args.get('page', 1, type=int), 1), paginas)

    filas = consultar(f"""
        SELECT u.id_usuario AS id, u.nombre_completo AS nombre, u.correo_usuario AS correo,
               u.id_tipo, t.nombre_tipo AS rol, u.grado, u.activo
        {desde} {donde}
        ORDER BY u.nombre_completo
        LIMIT %s OFFSET %s
    """, params + [por_pagina, (pagina - 1) * por_pagina])
    for u in filas:                                      # datos listos para que la plantilla los muestre tal cual
        u['rol'] = u['rol'] or 'Sin rol'
        u['es_admin'] = u['id_tipo'] == ID_TIPO_ADMIN
        u['rol_clave'] = rol_clave(u['id_tipo'])
        u['grado'] = u['grado'] or 'N/A'
        u['estado'] = 'Activo' if u['activo'] else 'Inactivo'

    # Opciones de los filtros y del modal de edición
    roles = consultar("SELECT id_tipo AS id, nombre_tipo AS nombre FROM tipos_usuario ORDER BY id_tipo")
    grados = [g['grado'] for g in consultar(
        "SELECT DISTINCT grado FROM usuarios WHERE grado IS NOT NULL AND grado <> '' ORDER BY grado")]
    return render_template('admin/usuarios.html', usuarios=filas, total=total, pagina=pagina,
                           paginas=paginas, q=q, rol=rol, grado=grado, grados=grados, roles=roles,
                           roles_editables=[r for r in roles if r['id'] != ID_TIPO_ADMIN])

# Actualiza los datos de una cuenta desde el panel.
@app.route('/admin/api/usuarios/<int:uid>', methods=['PUT'])
@admin_required_inicial
@api_seguro
def admin_api_editar_usuario(uid):
    d = request.get_json(silent=True) or {}
    nombre = (d.get('nombre') or '').strip()
    if not nombre:
        return _no('El nombre es obligatorio.', 400)

    # El rol llega como id. Se comprueba que exista en tipos_usuario y que no sea el de
    # administrador: ese rol no se asigna desde esta pantalla.
    try:
        id_tipo = int(d.get('rol'))
    except (TypeError, ValueError):
        return _no('Rol no válido.', 400)
    existe = consultar("SELECT 1 FROM tipos_usuario WHERE id_tipo = %s", (id_tipo,), uno=True)
    if not existe or id_tipo == ID_TIPO_ADMIN:
        return _no('Rol no válido.', 400)

    # Los docentes no tienen grado; a los estudiantes se les recorta a 10 caracteres (el tamaño de la columna)
    grado = None if id_tipo == ID_TIPO_DOCENTE else ((d.get('grado') or '').strip()[:10] or None)

    # El "id_tipo <> admin" del final evita que se pueda editar a un administrador desde acá
    fila = ejecutar_uno("""UPDATE usuarios SET nombre_completo = %s, id_tipo = %s, grado = %s
                           WHERE id_usuario = %s AND id_tipo <> %s
                           RETURNING id_usuario""",
                        (nombre, id_tipo, grado, uid, ID_TIPO_ADMIN))
    return _ok('Usuario actualizado.') if fila else _no('Usuario no encontrado.')

# Cambia el estado de una cuenta de usuario.
@app.route('/admin/api/usuarios/<int:uid>/estado', methods=['POST'])
@admin_required_inicial
@api_seguro
def admin_api_estado_usuario(uid):
    # Bloquear/activar: NOT activo invierte el valor que tenga. Un admin no puede bloquearse a sí mismo
    # ni a otros administradores.
    if uid == session.get('user_id'):
        return _no('No puedes bloquear tu propia cuenta.', 400)
    fila = ejecutar_uno("""UPDATE usuarios SET activo = NOT activo
                           WHERE id_usuario = %s AND id_tipo <> %s
                           RETURNING nombre_completo, activo""", (uid, ID_TIPO_ADMIN))
    if not fila:
        return _no('Usuario no encontrado.')
    return _ok(f'{fila["nombre_completo"]} ahora está {"activo" if fila["activo"] else "bloqueado"}.')

# Nombra o quita a un administrador.
@app.route('/admin/api/usuarios/<int:uid>/admin', methods=['POST'])
@admin_required_inicial
@api_seguro
def admin_api_cambiar_admin(uid):
    d = request.get_json(silent=True) or {}
    accion = d.get('accion')

    # Nadie se cambia el rol a sí mismo: lo hace otro administrador
    if uid == session.get('user_id'):
        return _no('No puedes cambiar tu propio rol. Pídeselo a otro administrador.', 400)

    usuario = consultar("""SELECT nombre_completo, id_tipo, activo
                           FROM usuarios WHERE id_usuario = %s""", (uid,), uno=True)
    if not usuario:
        return _no('Usuario no encontrado.')

    if accion == 'dar':
        if usuario['id_tipo'] == ID_TIPO_ADMIN:
            return _no('Esa persona ya es administradora.', 400)
        if not usuario['activo']:
            return _no('Activa la cuenta antes de nombrarla administradora.', 400)
        ejecutar("UPDATE usuarios SET id_tipo = %s WHERE id_usuario = %s",
                 (ID_TIPO_ADMIN, uid))
        return _ok(f'{usuario["nombre_completo"]} ahora es administrador.')

    if accion == 'quitar':
        if usuario['id_tipo'] != ID_TIPO_ADMIN:
            return _no('Esa persona no es administradora.', 400)
        try:
            nuevo_rol = int(d.get('rol'))
        except (TypeError, ValueError):
            nuevo_rol = None
        if nuevo_rol not in (ID_TIPO_ESTUDIANTE, ID_TIPO_DOCENTE):
            return _no('Elige a qué rol vuelve esa persona.', 400)
        ejecutar("UPDATE usuarios SET id_tipo = %s WHERE id_usuario = %s",
                 (nuevo_rol, uid))
        return _ok(f'{usuario["nombre_completo"]} ya no es administrador.')

    return _no('Acción no válida.', 400)

# Permite responder una consulta y notificar al usuario.
@app.route('/admin/soporte/<int:id_soporte>/responder', methods=['GET', 'POST'])
@admin_required
def responder_soporte(id_soporte):
    consulta = consultar("""
        SELECT s.id_soporte, s.usuario_id, s.asunto, s.descripcion,
               s.estado, s.respuesta, s.fecha_creacion, s.fecha_respuesta,
               u.nombre_completo AS usuario_nombre, u.correo_usuario AS usuario_correo
        FROM soporte s
        JOIN usuarios u ON u.id_usuario = s.usuario_id
        WHERE s.id_soporte = %s;
    """, (id_soporte,), uno=True)

    if not consulta:
        abort(404)

    if request.method == 'POST':
        respuesta_texto = (request.form.get('respuesta') or '').strip()

        if not respuesta_texto:
            flash('Escribe una respuesta antes de enviar.', 'warning')
            return redirect(url_for('responder_soporte', id_soporte=id_soporte))

        conn = cur = None
        try:
            conn = get_db_connection()
            cur = conn.cursor()

            cur.execute("""
                UPDATE soporte
                SET respuesta = %s,
                    estado = 'resuelta',
                    fecha_respuesta = CURRENT_TIMESTAMP,
                    respondido_por = %s
                WHERE id_soporte = %s;
            """, (
                respuesta_texto,
                session['user_id'],
                consulta['id_soporte']
            ))

            cur.execute("""
                INSERT INTO notificaciones_usuario (
                    id_usuario, id_proyecto, tipo, titulo, mensaje, motivo, url_destino, leida
                )
                VALUES (%s, NULL, 'soporte', %s, %s, NULL, %s, FALSE);
            """, (
                consulta['usuario_id'],
                f"Consulta: {consulta['asunto']}",
                'Tu consulta fue resuelta. Entra a ver la respuesta.',
                url_for('perfil') + '#tab-consultas'
            ))

            conn.commit()
        except Exception:
            if conn:
                conn.rollback()
            app.logger.exception('Error al responder la consulta y crear notificación')
            flash('No se pudo guardar la respuesta.', 'danger')
            return redirect(url_for('responder_soporte', id_soporte=id_soporte))
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()

        flash('Respuesta enviada, consulta marcada como resuelta y notificación enviada.', 'success')
        return redirect(url_for('admin_reportes'))

    return render_template('responder_soporte.html', consulta=consulta)



# DOCENTES
# Muestra los proyectos pendientes de revisión docente.
@app.route('/aprobaciones')
@docente_required
def aprobaciones():
    uid = session['user_id']
    conn = None
    cur = None
    proyectos_pendientes = []

    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute("""
            SELECT nombre_completo
            FROM usuarios
            WHERE id_usuario = %s;
        """, (uid,))
        docente = cur.fetchone()
        nombre_docente = (docente['nombre_completo'] or '').strip() if docente else ''

        cur.execute("""
            SELECT
                p.id_proyecto,
                p.titulo,
                p.descripcion,
                p.grado,
                p.profesor_a_cargo,
                p.imagen_portada,
                p.fecha_creacion,
                c.nombre_categoria AS categoria,
                u.nombre_completo AS autor
            FROM proyectos p
            LEFT JOIN usuarios u ON p.id_usuario = u.id_usuario
            LEFT JOIN categorias c ON p.id_categoria = c.id_categoria
            WHERE LOWER(COALESCE(p.estado, '')) = 'pendiente'
              AND LOWER(TRIM(COALESCE(p.profesor_a_cargo, ''))) = LOWER(TRIM(%s))
            ORDER BY p.id_proyecto DESC;
        """, (nombre_docente,))

        proyectos_pendientes = cur.fetchall()

    except Exception as e:
        app.logger.exception('Error al cargar proyectos en /aprobaciones: %s', e)
        flash('No se pudieron cargar los proyectos pendientes desde la base de datos.', 'danger')

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

    return render_template(
        'aprobaciones.html',
        proyectos=proyectos_pendientes,
        pendientes_count=len(proyectos_pendientes)
    )

# Aprueba un proyecto en la revisión docente.
@app.route('/aprobaciones/<int:id>/aprobar', methods=['POST'])
@docente_required
def aprobar_proyecto(id):
    uid = session['user_id']
    conn = cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute("SELECT nombre_completo FROM usuarios WHERE id_usuario = %s;", (uid,))
        docente = cur.fetchone()
        nombre_docente = (docente['nombre_completo'] or '').strip().lower() if docente else ''

        cur.execute("""
            SELECT id_proyecto, profesor_a_cargo
            FROM proyectos
            WHERE id_proyecto = %s;
        """, (id,))
        proyecto = cur.fetchone()

        if not proyecto:
            flash('El proyecto no existe.', 'danger')
            return redirect(url_for('aprobaciones'))

        if (proyecto['profesor_a_cargo'] or '').strip().lower() != nombre_docente:
            flash('No tienes permiso para aprobar este proyecto.', 'danger')
            return redirect(url_for('aprobaciones'))

        cur.execute("""
            UPDATE proyectos
            SET estado = 'Publicado',
                motivo_rechazo = NULL
            WHERE id_proyecto = %s;
        """, (id,))
        cur.execute("SELECT id_usuario, titulo FROM proyectos WHERE id_proyecto = %s;", (id,))
        datos_proy = cur.fetchone()
        if datos_proy and datos_proy.get('id_usuario'):
            cur.execute("""
                INSERT INTO notificaciones_usuario (
                    id_usuario, id_proyecto, tipo, titulo, mensaje, motivo, url_destino, leida
                )
                VALUES (%s, %s, 'aprobado', %s, %s, NULL, %s, FALSE);
            """, (
                datos_proy['id_usuario'],
                id,
                datos_proy.get('titulo') or 'Proyecto',
                'Tu proyecto fue aprobado y ya está publicado.',
                url_for('ver_proyecto', id=id)
            ))
        conn.commit()
        registrar_revision(id, 'Aprobado')
        flash('¡Proyecto aprobado y publicado correctamente!', 'success')
    except Exception:
        if conn:
            conn.rollback()
        app.logger.exception('Error al aprobar el proyecto')
        flash('No se pudo aprobar el proyecto.', 'danger')
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

    return redirect(url_for('aprobaciones'))

# Rechaza un proyecto en la revisión docente.
@app.route('/aprobaciones/<int:id>/rechazar', methods=['POST'])
@docente_required
def rechazar_proyecto(id):
    uid = session['user_id']
    motivo = (request.form.get('motivo_rechazo') or '').strip()

    if not motivo:
        flash('Debes escribir las observaciones o el motivo del rechazo.', 'warning')
        return redirect(url_for('aprobaciones'))

    conn = cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute("SELECT nombre_completo FROM usuarios WHERE id_usuario = %s;", (uid,))
        docente = cur.fetchone()
        nombre_docente = (docente['nombre_completo'] or '').strip().lower() if docente else ''

        cur.execute("""
            SELECT id_proyecto, profesor_a_cargo
            FROM proyectos
            WHERE id_proyecto = %s;
        """, (id,))
        proyecto = cur.fetchone()

        if not proyecto:
            flash('El proyecto no existe.', 'danger')
            return redirect(url_for('aprobaciones'))

        if (proyecto['profesor_a_cargo'] or '').strip().lower() != nombre_docente:
            flash('No tienes permiso para rechazar este proyecto.', 'danger')
            return redirect(url_for('aprobaciones'))

        cur.execute("""
            UPDATE proyectos
            SET estado = 'Borrador',
                motivo_rechazo = %s
            WHERE id_proyecto = %s;
        """, (motivo, id))

        cur.execute("SELECT id_usuario, titulo FROM proyectos WHERE id_proyecto = %s;", (id,))
        datos_proy = cur.fetchone()
        if datos_proy and datos_proy.get('id_usuario'):
            cur.execute("""
                INSERT INTO notificaciones_usuario (
                    id_usuario, id_proyecto, tipo, titulo, mensaje, motivo, url_destino, leida
                )
                VALUES (%s, %s, 'rechazado', %s, %s, %s, %s, FALSE);
            """, (
                datos_proy['id_usuario'],
                id,
                datos_proy.get('titulo') or 'Proyecto',
                'Tu proyecto fue rechazado y devuelto a borradores.',
                motivo,
                url_for('perfil') + '#tab-borradores'
            ))
        conn.commit()
        registrar_revision(id, 'Observado', motivo)
        flash('Proyecto devuelto a borrador con las observaciones.', 'success')
    except Exception:
        if conn:
            conn.rollback()
        app.logger.exception('Error al rechazar el proyecto')
        flash('No se pudo rechazar el proyecto.', 'danger')
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

    return redirect(url_for('aprobaciones'))



# RUTAS AUXILIARES Y ERRORES
# Informa cuando la cuenta institucional aún no está registrada.
@app.route('/error-registro')
def user_not_registered_error():
    flash('Continúa con Google usando tu cuenta institucional.', 'warning')
    return redirect(url_for('login'))

# Cierra la sesión activa y vuelve al acceso.
@app.route('/logout')
def logout():
    session.clear()
    flash('Has cerrado sesión correctamente.', 'success')
    return redirect(url_for('login'))

# Informa que el archivo enviado supera el tamaño permitido.
@app.errorhandler(413)
def archivo_muy_grande(e):
    flash('El envío es demasiado grande. La portada puede pesar máximo 5 MB y los documentos, 10 MB en total.', 'danger')
    return redirect(url_for('subir'))

# Muestra una respuesta para las páginas que no existen.
@app.errorhandler(404)
def page_not_found(e):
    # plantillas específicas no existen en el proyecto; usar una respuesta segura
    try:
        return render_template('base.html'), 404
    except Exception:
        return "Página no encontrada.", 404


if __name__ == '__main__':
    app.run(debug=True)
