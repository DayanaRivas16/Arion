from flask import Flask, render_template, redirect, url_for, session, flash, jsonify, request
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
app.config['UPLOAD_FOLDER'] = os.path.join(
    app.root_path, 'static', 'uploads', 'proyectos'
)
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5 MB

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

EXTENSIONES_PERMITIDAS = {'png', 'jpg', 'jpeg', 'webp'}

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

@app.route('/')
@login_required
def home():
    return render_template('home.html')

@app.route('/explorar')
@login_required
def explorar():
    return render_template('explorar_proyectos.html')


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
# RUTA COMPLETA PARA SUBIR PROYECTOS
# ==========================================================

@app.route('/subir', methods=['GET', 'POST'])
@login_required
def subir():

    if request.method == 'GET':
        return render_template('subir_proyecto.html')

    conn = None
    cursor = None
    ruta_guardada = None

    try:
        # 1. Recibir los datos del formulario
        titulo = request.form.get('titulo', '').strip()
        categoria = request.form.get('categoria', '').strip()
        descripcion = request.form.get('descripcion', '').strip()
        recursos = request.form.get('recursos', '').strip()
        integrantes = request.form.get('integrantes', '').strip()
        fecha = request.form.get('fecha', '').strip()
        etiquetas = request.form.get('etiquetas', '').strip()
        estado_formulario = request.form.get('estado', '').strip()

        imagen = request.files.get('imagen_principal')

        # 2. Validar los campos obligatorios
        if not all([
            titulo,
            categoria,
            descripcion,
            recursos,
            integrantes,
            fecha,
            etiquetas,
            estado_formulario
        ]):
            flash('Completa todos los campos obligatorios.', 'warning')
            return redirect(url_for('subir'))

        if estado_formulario not in ('publicado', 'borrador'):
            flash('Selecciona un estado válido.', 'warning')
            return redirect(url_for('subir'))

        # 3. Validar la fecha
        from datetime import datetime

        try:
            datetime.strptime(fecha, '%Y-%m-%d')
        except ValueError:
            flash('La fecha de realización no es válida.', 'warning')
            return redirect(url_for('subir'))

        # 4. Validar la imagen
        if not imagen or not imagen.filename:
            flash('Selecciona una imagen de portada.', 'warning')
            return redirect(url_for('subir'))

        from werkzeug.utils import secure_filename
        import uuid

        nombre_seguro = secure_filename(imagen.filename)

        if '.' not in nombre_seguro:
            flash('El archivo no tiene una extensión válida.', 'warning')
            return redirect(url_for('subir'))

        extension = nombre_seguro.rsplit('.', 1)[1].lower()
        extensiones_permitidas = {'jpg', 'jpeg', 'png', 'webp'}

        if extension not in extensiones_permitidas:
            flash('Usa una imagen JPG, JPEG, PNG o WEBP.', 'warning')
            return redirect(url_for('subir'))

        # 5. Preparar la carpeta y el nombre de la imagen
        carpeta = os.path.join(
            app.root_path,
            'static',
            'uploads',
            'proyectos'
        )

        os.makedirs(carpeta, exist_ok=True)

        nombre_archivo = f'{uuid.uuid4().hex}.{extension}'
        ruta_guardada = os.path.join(carpeta, nombre_archivo)
        ruta_relativa = f'uploads/proyectos/{nombre_archivo}'

        # 6. Conectar con PostgreSQL
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # 7. Buscar la categoría seleccionada
        cursor.execute("""
            SELECT id_categoria
            FROM categorias
            WHERE LOWER(nombre_categoria) = LOWER(%s)
            LIMIT 1;
        """, (categoria,))

        fila_categoria = cursor.fetchone()

        if not fila_categoria:
            flash(
                'La categoría seleccionada no existe en la base de datos.',
                'warning'
            )
            return redirect(url_for('subir'))

        id_categoria = fila_categoria['id_categoria']

        # 8. Obtener el usuario que publica el proyecto
        cursor.execute("""
            SELECT nombre_completo
            FROM usuarios
            WHERE id_usuario = %s;
        """, (session['user_id'],))

        usuario = cursor.fetchone()

        if not usuario:
            raise Exception('No se encontró el usuario de la sesión.')

        profesor_a_cargo = usuario['nombre_completo']

        # 9. Guardar la imagen
        imagen.save(ruta_guardada)

        # 10. Insertar el proyecto
        cursor.execute("""
            INSERT INTO proyectos (
                titulo,
                descripcion,
                imagen_portada,
                profesor_a_cargo,
                grado,
                estado,
                es_destacado,
                vistas_count,
                likes_count,
                calificacion,
                id_usuario,
                id_categoria,
                fecha_creacion
            )
            VALUES (
                %s, %s, %s, %s, %s, %s,
                FALSE, 0, 0, 5.0, %s, %s,
                CURRENT_TIMESTAMP
            )
            RETURNING id_proyecto;
        """, (
            titulo,
            descripcion,
            ruta_relativa,
            profesor_a_cargo,
            'No especificado',
            'Publicado' if estado_formulario == 'publicado' else 'Borrador',
            session['user_id'],
            id_categoria
        ))

        resultado = cursor.fetchone()
        id_proyecto = resultado['id_proyecto']

        # 11. Guardar las etiquetas y relacionarlas con el proyecto
        guardar_etiquetas(cursor, id_proyecto, etiquetas)

        # 12. Confirmar todos los cambios
        conn.commit()

        flash('¡Proyecto guardado correctamente!', 'success')

        return redirect(url_for('ver_proyecto', id=id_proyecto))

    except Exception:
        if conn:
            conn.rollback()

        if ruta_guardada and os.path.exists(ruta_guardada):
            os.remove(ruta_guardada)

        app.logger.exception('Error al guardar el proyecto')

        flash(
            'No se pudo guardar el proyecto. Revisa la terminal de Flask.',
            'error'
        )

        return redirect(url_for('subir'))

    finally:
        if cursor:
            cursor.close()

        if conn:
            conn.close()


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
