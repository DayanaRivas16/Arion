from flask import Flask, render_template, redirect, url_for, session, flash, jsonify
from dotenv import load_dotenv
from functools import wraps
import psycopg2
from psycopg2.extras import RealDictCursor
from authlib.integrations.flask_client import OAuth
from flask_mail import Mail, Message
import os

load_dotenv()

app = Flask(__name__)

app.secret_key = os.getenv('SECRET_KEY')
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
# CONTROLES DE ACCESO Y DEMÁS RUTAS... (Tu código se mantiene abajo)
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
        nombre = userinfo.get('name') or email.split('@')[0]

        if not email:
            flash('Google no proporcionó un correo electrónico.', 'error')
            return redirect(url_for('login'))

        conn = None
        cursor = None

        try:
            conn = get_db_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            # Buscar si el usuario ya existe
            cursor.execute("""
                SELECT id_usuario, nombre_completo, correo_usuario
                FROM usuarios
                WHERE correo_usuario = %s;
            """, (email,))

            usuario = cursor.fetchone()

            # ==================================================
            # SI NO EXISTE → CREARLO
            # ==================================================

            if not usuario:

                cursor.execute("""
                    INSERT INTO usuarios
                    (
                        nombre_completo,
                        correo_usuario,
                        password,
                        id_tipo,
                        verificado
                    )
                    VALUES (%s, %s, %s, %s, TRUE)
                    RETURNING id_usuario, nombre_completo, correo_usuario;
                """, (
                    nombre,
                    email,
                    None,
                    1
                ))

                usuario = cursor.fetchone()

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

@app.route('/forgot-password')
def forgot_password():
    return render_template('forgot_password.html')

@app.route('/reset-password')
def reset_password():
    return render_template('reset_password.html')


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

@app.route('/subir')
@login_required
def subir():
    return render_template('subir_proyecto.html')

@app.route('/perfil')
@login_required
def perfil():
    return render_template('mi_perfil.html')

@app.route('/recursos')
@login_required
def recursos():
    return render_template('recursos.html')

# Ruta dinámica para ver un proyecto por su ID 
@app.route('/proyecto/<int:id>')
@login_required
def ver_proyecto(id):
    return render_template('ver_proyecto.html', proyecto_id=id)
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