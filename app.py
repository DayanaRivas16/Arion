from flask import Flask, render_template, redirect, url_for, session, flash, jsonify, request, abort
from dotenv import load_dotenv
from functools import wraps
import psycopg2
from psycopg2.extras import RealDictCursor
from authlib.integrations.flask_client import OAuth
from flask_mail import Mail, Message
import os
from werkzeug.utils import secure_filename
from datetime import datetime
import uuid

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')


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
# RUTA DE PRUEBA PARA CONEXIÓN
# =====================================================================
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

# =====================================================================
# CONTROLES DE ACCESO Y DEMÁS RUTAS... 
# =====================================================================
# =====================================================================
# CONTROLES DE ACCESO 
# =====================================================================
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Por favor, inicia sesión para acceder a esta página.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# =====================================================================
# RUTAS PÚBLICAS
# =====================================================================
@app.route('/login')
def login():

    if 'user_id' in session:
        return redirect(url_for('home'))

    return render_template('login.html')

@app.route('/register')
def register():

    if 'user_id' in session:
        return redirect(url_for('home'))

    return render_template('register.html')

# ======================================================
# AUTENTICACIÓN CON GOOGLE
# ======================================================

@app.route('/login/google')
def google_login():
    redirect_uri = url_for('google_callback', _external=True)
    return google.authorize_redirect(redirect_uri)


@app.route('/google/callback')
def google_callback():

    try:
        # Obtener el token de Google
        token = google.authorize_access_token()

        # Obtener información del usuario
        userinfo = token.get('userinfo')

        if not userinfo:
            flash('No fue posible obtener la información de Google.', 'error')
            return redirect(url_for('login'))

        google_id = userinfo.get('sub')
        email = userinfo.get('email')

        if not email:
            flash('Google no proporcionó un correo electrónico.', 'error')
            return redirect(url_for('login'))

        # Solo permitir correos cuyo dominio esté registrado en la tabla
        # dominios_permitidos. Se compara el dominio completo después de @.
        partes_correo = email.strip().lower().rsplit('@', 1)
        if len(partes_correo) != 2 or not all(partes_correo):
            flash('El correo electrónico no es válido.', 'error')
            return redirect(url_for('login'))
        dominio_correo = partes_correo[1]
        nombre = userinfo.get('name') or partes_correo[0]

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
                flash('Debes usar un correo de un dominio institucional permitido.', 'error')
                return redirect(url_for('login'))

            id_dominio = dominio_permitido['id_dominio']

            # Buscar si el usuario ya existe
            cursor.execute("""
                SELECT id_usuario, nombre_completo, correo_usuario
                FROM usuarios
                WHERE correo_usuario = %s;
            """, (email.strip(),))

            usuario = cursor.fetchone()

            # ==================================================
            # SI NO EXISTE → CREARLO
            # ==================================================

            if not usuario:

                cursor.execute("""
                    INSERT INTO usuarios
                    (
                        google_id,
                        nombre_completo,
                        correo_usuario,
                        id_tipo,
                        id_dominio
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id_usuario, nombre_completo, correo_usuario;
                """, (
                    google_id,
                    nombre,
                    email.strip(),
                    1,
                    id_dominio
                ))

                usuario = cursor.fetchone()

                conn.commit()

            else:
                # Vincula usuarios existentes con el dominio permitido.
                cursor.execute("""
                    UPDATE usuarios
                    SET id_dominio = %s
                    WHERE id_usuario = %s
                """, (id_dominio, usuario['id_usuario']))
                conn.commit()

            # ==================================================
            # CREAR SESIÓN
            # ==================================================

            session.clear()

            session['user_id'] = usuario['id_usuario']
            session['user_name'] = usuario['nombre_completo']
            session['user_email'] = usuario['correo_usuario']
            session['google_id'] = google_id

            return redirect(url_for('home'))

        except Exception as e:

            if conn:
                conn.rollback()

            app.logger.exception(
                f'Error registrando usuario con Google: {e}'
            )

            flash(
                'Ocurrió un error al crear o iniciar tu cuenta.',
                'error'
            )

            return redirect(url_for('login'))

        finally:

            if cursor:
                cursor.close()

            if conn:
                conn.close()

    except Exception as e:

        app.logger.exception(
            f'Error en autenticación de Google: {e}'
        )

        flash(
            'No fue posible iniciar sesión con Google.',
            'error'
        )

        return redirect(url_for('login'))


# =====================================================================
# RUTAS PROTEGIDAS 
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
    return filas


@app.route('/')
@login_required
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

@app.route('/explorar')
@login_required
def explorar():
    filas = []
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT p.id_proyecto AS id,
                   p.titulo,
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
            ORDER BY p.fecha_creacion DESC;
        """)
        filas = cursor.fetchall()
    except Exception:
        app.logger.exception('Error cargando proyectos')
        flash('No se pudieron cargar los proyectos.', 'danger')
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

    proyectos = []
    for f in filas:
        iniciales = ''.join(p[0] for p in f['autor'].split()[:2]).upper() or '?'
        proyectos.append({
            'id': f['id'],
            'title': f['titulo'],
            'category': f['categoria'],
            'author': f['autor'],
            'avatar': iniciales,
            'rating': f['rating'],
            'views': f['vistas'] or 0,
            'likes': f['likes'] or 0,
            'image': url_for('static', filename=f['imagen_portada']) if f['imagen_portada'] else '',
            'featured': bool(f['destacado']),
            'date': f['fecha_creacion'].timestamp() if f['fecha_creacion'] else 0,
        })

    return render_template('explorar_proyectos.html', proyectos=proyectos)

@app.route('/acerca')
@login_required
def acerca():
    return render_template('acerca.html')


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

# ==========================================================
# RUTAS DE VISTA DE PROYECTOS, LIKES Y VALORACIONES
# ==========================================================

@app.template_filter('iniciales')
def iniciales(nombre):
    return ''.join(p[0] for p in (nombre or '').split()[:2]).upper() or '?'


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
        # Un borrador solo lo ve su autor
        if (p['estado'] or '').lower() != 'publicado' and not es_autor:
            abort(404)

        # Suma una vista (no cuenta las del autor)
        p['vistas'] = p['vistas'] or 0
        if not es_autor:
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


# ==========================================================
# RUTA COMPLETA PARA SUBIR PROYECTOS
# ==========================================================

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
            FROM usuarios WHERE id_usuario <> %s ORDER BY nombre_completo;
        """, (uid,))
        usuarios = cursor.fetchall()
    finally:
        cursor.close()
        conn.close()
    return {'categorias': categorias, 'usuarios': usuarios}


@app.route('/subir', methods=['GET', 'POST'])
@login_required
def subir():
    uid = session['user_id']

    if request.method == 'GET':
        return render_template('subir_proyecto.html', **datos_formulario(uid))

    def volver(mensaje):
        flash(mensaje, 'danger')
        return redirect(url_for('subir'))

    # 1. Leer el formulario
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

    # 2. Validar texto
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

    # 3. Validar la portada
    if not imagen or not imagen.filename:
        return volver('Elige una imagen de portada.')
    ext_img, tam_img, cab_img = info_archivo(imagen)
    if ext_img not in EXTENSIONES_PERMITIDAS or not contenido_valido(ext_img, cab_img):
        return volver('La portada debe ser una imagen PNG, JPG o WEBP.')
    if tam_img > MAX_IMAGEN:
        return volver('La portada supera los 5 MB.')

    # 4. Validar los documentos
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

    # 5. Guardar en la base de datos y en disco
    conn = None
    cursor = None
    escritos = []          # archivos que ya están en disco
    confirmado = False
    id_proyecto = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute("SELECT 1 FROM categorias WHERE id_categoria = %s;", (id_categoria,))
        if not cursor.fetchone():
            return volver('La categoría seleccionada no es válida.')

        # Solo integrantes que existan de verdad
        ids_ok = []
        if ids_integrantes:
            cursor.execute("SELECT id_usuario FROM usuarios WHERE id_usuario = ANY(%s);", (list(ids_integrantes),))
            ids_ok = [f['id_usuario'] for f in cursor.fetchall()]

        # Portada
        nombre_img = f'{uuid.uuid4().hex}.{ext_img}'
        ruta_img = os.path.join(app.config['UPLOAD_FOLDER'], nombre_img)
        imagen.save(ruta_img)
        escritos.append(ruta_img)

        cursor.execute("""
            INSERT INTO proyectos (
                titulo, descripcion, imagen_portada, profesor_a_cargo, grado, estado,
                es_destacado, vistas_count, likes_count, calificacion, id_usuario, id_categoria
            )
            VALUES (%s, %s, %s, %s, %s, %s, FALSE, 0, 0, NULL, %s, %s)
            RETURNING id_proyecto;
        """, (
            titulo, descripcion, f'uploads/proyectos/{nombre_img}', profesor, grado,
            'Publicado' if estado_form == 'publicado' else 'Borrador',
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

    flash('¡Proyecto guardado correctamente!', 'success')
    return redirect(url_for('ver_proyecto', id=id_proyecto))

# Ruta del perfil
@app.route('/perfil')
@login_required
def perfil():
    return render_template('mi_perfil.html')


# ======================================================
# RUTA DE RECURSOS
# ======================================================

@app.route('/recursos')
@login_required
def recursos():
    return render_template('recursos.html')

# =====================================================================
# MANEJO DE ERRORES 
# =====================================================================
@app.errorhandler(413)
def archivo_muy_grande(e):
    flash('El envío es demasiado grande. La portada puede pesar máximo 5 MB y los documentos, 10 MB en total.', 'danger')
    return redirect(url_for('subir'))

# Captura el error 404 (Página no encontrada)
@app.errorhandler(404)
def page_not_found(e):
    # plantillas específicas no existen en el proyecto; usar una respuesta segura
    try:
        return render_template('base.html'), 404
    except Exception:
        return "Página no encontrada.", 404

@app.route('/error-registro')
def user_not_registered_error():
    # plantilla no incluida; redirigir al registro o mostrar mensaje
    try:
        return render_template('register.html')
    except Exception:
        return "Usuario no registrado.", 200

# Ruta auxiliar para cerrar sesión
@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('Has cerrado sesión correctamente.', 'success')
    return redirect(url_for('login'))


if __name__ == '__main__':
    app.run(debug=True)
