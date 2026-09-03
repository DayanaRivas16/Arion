from flask import Flask, render_template, redirect, url_for, session, flash, jsonify, request, get_flashed_messages
from werkzeug.security import check_password_hash, generate_password_hash
from functools import wraps
import psycopg2
from psycopg2.extras import RealDictCursor
from flask_mail import Mail, Message
import random
from datetime import datetime, timedelta
import os

app = Flask(__name__)

# ======================================================
# CONFIGURACIÓN DEL CORREO
# ======================================================

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False

app.config['MAIL_USERNAME'] = 'diaznicolk@gmail.com'
app.config['MAIL_PASSWORD'] = 'fsbt hnng ozdu ehxq'
app.config['MAIL_DEFAULT_SENDER'] = 'ARION <diaznicolk@gmail.com>'

mail = Mail(app)

app.secret_key = 'mister'

# =====================================================================
# CONFIGURACIÓN DE LA BASE DE DATOS POSTGRESQL
# =====================================================================
DB_HOST = "localhost"
DB_NAME = "arion_db"     
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

def enviar_codigo(email, codigo):

    mensaje = Message(
        subject="Código de verificación - ARION",
        recipients=[email]
    )

    mensaje.body = f"""
Hola.

Gracias por registrarte en ARION.

Tu código de verificación es:

{codigo}

Este código vence en 10 minutos.

Si no solicitaste este registro puedes ignorar este correo.
"""
    try:
        mail.send(mensaje)
        app.logger.info(f"Email enviado a {email} con código {codigo}.")
        try:
            with open('email.log', 'a', encoding='utf-8') as fh:
                fh.write(f"{datetime.now().isoformat()} INFO Enviado a {email} codigo {codigo}\n")
        except Exception:
            app.logger.exception('No se pudo escribir en email.log')
        return True
    except Exception as ex:
        app.logger.exception(f"Error enviando email a {email}: {ex}")
        try:
            with open('email.log', 'a', encoding='utf-8') as fh:
                fh.write(f"{datetime.now().isoformat()} ERROR Envio a {email} codigo {codigo} fallo: {str(ex)}\n")
        except Exception:
            app.logger.exception('No se pudo escribir en email.log')
        return False
@app.route('/test-email')
def test_email():

    codigo = random.randint(100000,999999)

    enviar_codigo("anniacream@gmail.com", codigo)

    return f"Correo enviado con código {codigo}"
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
@app.route('/login', methods=['GET', 'POST']) # <-- ¡Aquí agregamos methods=['GET', 'POST']!
def login():
    # Si el usuario ya está logueado, lo mandamos al home
    if 'user_id' in session:
        return redirect(url_for('home'))

    # PROCESAR EL FORMULARIO CUANDO PRESIONAN EL BOTÓN (POST)
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        # Validación básica de campos vacíos
        if not email or not password:
            flash('Por favor, completa todos los campos.', 'error')
            return render_template('login.html')

        conn = None
        cursor = None
        try:
            # Conexión segura a tu base de datos PostgreSQL
            conn = get_db_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Consulta preparada para mitigar inyecciones SQL
            # Ajustar nombres de columnas y alias para que el resto del código funcione
            query = "SELECT id_usuario AS id, nombre_completo AS nombre, correo_usuario AS email, password FROM usuarios WHERE correo_usuario = %s;"
            cursor.execute(query, (email,))
            usuario = cursor.fetchone()
            
        except Exception as e:
            flash('Ocurrió un error en el servidor. Inténtalo más tarde.', 'error')
            return render_template('login.html')
        finally:
            if cursor: cursor.close()
            if conn: conn.close()

        # Validación de las credenciales usando hash seguro
        if usuario and check_password_hash(usuario['password'], password):
            session.clear()
            session['user_id'] = usuario['id']
            session['user_name'] = usuario['nombre']
            
            flash(f'¡Bienvenido de nuevo, {usuario["nombre"]}!', 'success')
            return redirect(url_for('home'))
            # MOSTRAR LA PÁGINA NORMALMENTE (GET)
            # Limpiamos los mensajes acumulados si el usuario no viene rebotado del guard de acceso
    if not session.pop('redirected_by_guard', None):
        get_flashed_messages(with_categories=True)
        
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():

    if 'user_id' in session:
        return redirect(url_for('home'))

    if request.method == 'POST':

        email = request.form.get('email').strip().lower()
        password = request.form.get('password')
        confirm = request.form.get('confirm')

        # Nombre temporal mientras lo agregamos al formulario
        nombre = email.split("@")[0]

        if not email or not password or not confirm:
            return jsonify({
                "success": False,
                "message": "Todos los campos son obligatorios."
            }), 400

        if password != confirm:
            return jsonify({
                "success": False,
                "message": "Las contraseñas no coinciden."
            }), 400

        conn = None
        cursor = None

        try:

            conn = get_db_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            # Verificar si el correo ya existe
            cursor.execute("""
                SELECT id_usuario
                FROM usuarios
                WHERE correo_usuario=%s;
            """, (email,))

            usuario = cursor.fetchone()

            if usuario:
                return jsonify({
                    "success": False,
                    "message": "Ese correo ya está registrado."
                }), 400

            # Encriptar contraseña
            password_hash = generate_password_hash(password)
            codigo = str(random.randint(100000, 999999))
            expiracion = datetime.now() + timedelta(minutes=10)

            # Guardar usuario
            cursor.execute ("""
                INSERT INTO usuarios
                (
                    nombre_completo,
                    correo_usuario,
                    password,
                    id_tipo,
                    codigo_otp,
                    otp_expira
                )
                VALUES (%s,%s,%s,%s,%s,%s)
            """,
            (
                nombre,
                email,
                password_hash,
                1,
                codigo,
                expiracion
            ))

            conn.commit()
            enviado = enviar_codigo(email, codigo)

            message_text = "Usuario registrado correctamente."
            if enviado:
                message_text += " Código enviado por correo."
            else:
                message_text += " No se pudo enviar el correo; revisa los logs."

            return jsonify({
                "success": True,
                "message": message_text
            }), 200

        except Exception as e:

            conn.rollback()

            return jsonify({
                "success": False,
                "message": str(e)
            }), 500

        finally:

            if cursor:
                cursor.close()

            if conn:
                conn.close()

    return render_template("register.html")
@app.route('/verify-otp', methods=['POST'])
def verify_otp():

    email = request.form.get('email')
    codigo = request.form.get('otp_code')

    if not email or not codigo:
        return jsonify({
            "success": False,
            "message": "Datos incompletos."
        }), 400


    conn = None
    cursor = None

    try:

        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)


        cursor.execute("""
            SELECT id_usuario, codigo_otp, otp_expira
            FROM usuarios
            WHERE correo_usuario=%s;
        """, (email,))


        usuario = cursor.fetchone()


        if not usuario:
            return jsonify({
                "success": False,
                "message": "Usuario no encontrado."
            }), 404


        # Validar código
        if usuario['codigo_otp'] != codigo:

            return jsonify({
                "success": False,
                "message": "Código incorrecto."
            }), 400


        # Validar expiración
        if usuario['otp_expira'] < datetime.now():

            return jsonify({
                "success": False,
                "message": "El código expiró."
            }), 400



        # Activar usuario
        cursor.execute("""
            UPDATE usuarios
            SET 
                verificado = TRUE,
                codigo_otp = NULL,
                otp_expira = NULL
            WHERE id_usuario=%s;
        """, (usuario['id_usuario'],))


        conn.commit()


        # Crear sesión automáticamente
        session['user_id'] = usuario['id_usuario']


        return jsonify({
            "success": True,
            "message": "Cuenta verificada correctamente."
        }), 200



    except Exception as e:

        if conn:
            conn.rollback()

        return jsonify({
            "success": False,
            "message": str(e)
        }), 500



    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()
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