from datetime import datetime, timedelta, timezone
from functools import wraps
import json
import os
from contextlib import contextmanager
import re
import secrets
import sqlite3
import uuid

from flask import (
    Flask, abort, flash, g, jsonify, redirect, render_template,
    request, session, url_for
)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from PIL import Image, ImageSequence

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY", "clave-local-de-demostracion-cambiar-antes-de-publicar"
)
app.config["JSON_AS_ASCII"] = False
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5 MB por imagen o GIF de perfil
# Cachea recursos estáticos (CSS, JavaScript e imágenes) durante 30 días.
# Esto evita volver a descargar las mismas imágenes en cada visita.
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = timedelta(days=30)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("COOKIE_SECURE", "0") == "1"

# Colombia mantiene UTC-5 y no aplica horario de verano.
BOGOTA_TZ = timezone(timedelta(hours=-5), "America/Bogota")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, "mercado.db")
PROFILE_UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads", "profiles")
PROFILE_ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "gif"}

# Datos ilustrativos para el prototipo. Reemplazar por la oferta real.
PRODUCTS = [
    {
        "id": "tomate-chonto", "name": "Tomate chonto", "category": "Verduras",
        "price": 3500, "unit": "kg", "producer": "Don Álvaro", "place": "Morichal",
        "emoji": "🍅", "tone": "tomato", "image": "tomate.webp",
        "tag": "Favorito de la semana",
        "description": "Tomates frescos, ideales para ensaladas y guisos."
    },
    {
        "id": "yuca-fresca", "name": "Yuca fresca", "category": "Verduras",
        "price": 2800, "unit": "kg", "producer": "Doña Rosa", "place": "La Manga",
        "emoji": "🥔", "tone": "cassava", "image": "yuca.webp",
        "tag": "Cosecha fresca",
        "description": "Yuca de textura suave, seleccionada para tu cocina."
    },
    {
        "id": "platano-harton", "name": "Plátano hartón", "category": "Frutas",
        "price": 4000, "unit": "docena", "producer": "Familia Pérez", "place": "Tilodirán",
        "emoji": "🍌", "tone": "banana", "image": "platano.webp",
        "tag": "De temporada",
        "description": "Plátano de la región, perfecto para preparaciones tradicionales."
    },
    {
        "id": "mango-criollo", "name": "Mango criollo", "category": "Frutas",
        "price": 5000, "unit": "kg", "producer": "Doña Marta", "place": "El Taladro",
        "emoji": "🥭", "tone": "mango", "image": "mango.webp",
        "tag": "Sabor local",
        "description": "Fruta de temporada con el sabor dulce de nuestra tierra."
    },
    {
        "id": "cilantro", "name": "Cilantro fresco", "category": "Aromáticas",
        "price": 1500, "unit": "manojo", "producer": "Huerta El Recuerdo", "place": "Yopal rural",
        "emoji": "🌿", "tone": "herb", "image": "cilantro.webp",
        "tag": "Recién cosechado",
        "description": "Aromática fresca para darle un toque especial a tus platos."
    },
    {
        "id": "ahuyama", "name": "Ahuyama", "category": "Verduras",
        "price": 2500, "unit": "kg", "producer": "Don Álvaro", "place": "Morichal",
        "emoji": "🎃", "tone": "pumpkin", "image": "ahuyama.webp",
        "tag": "De la huerta",
        "description": "Producto versátil para sopas, cremas y recetas caseras."
    },
    {
        "id": "papaya", "name": "Papaya", "category": "Frutas",
        "price": 4500, "unit": "unidad", "producer": "Doña Rosa", "place": "La Manga",
        "emoji": "🍈", "tone": "papaya", "image": "papaya.webp",
        "tag": "Fruta fresca",
        "description": "Una opción fresca para desayunos y meriendas."
    },
    {
        "id": "huevos-campo", "name": "Huevos campesinos", "category": "Otros",
        "price": 9000, "unit": "cubeta x 15", "producer": "Familia Pérez", "place": "Tilodirán",
        "emoji": "🥚", "tone": "eggs", "image": "huevos.webp",
        "tag": "Producción local",
        "description": "Huevos de producción campesina, disponibles por cubeta."
    },
]

PRODUCERS = [
    {"name": "Don Álvaro", "place": "Morichal", "specialty": "Hortalizas de la huerta", "emoji": "👨🏽‍🌾", "tone": "producer-one", "image": "don-alvaro.webp"},
    {"name": "Doña Rosa", "place": "La Manga", "specialty": "Yuca y frutas de temporada", "emoji": "👩🏽‍🌾", "tone": "producer-two", "image": "dona-rosa.webp"},
    {"name": "Familia Pérez", "place": "Tilodirán", "specialty": "Plátano y productos campesinos", "emoji": "👨🏽‍🌾", "tone": "producer-three", "image": "familia-perez.webp"},
    {"name": "Doña Marta", "place": "El Taladro", "specialty": "Frutas de la región", "emoji": "👩🏽‍🌾", "tone": "producer-four", "image": "dona-marta.webp"},
]

# Las reservas y solicitudes de interés se conservan en memoria en este prototipo.
reservas = []
solicitudes_productores = []


def get_db():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


@contextmanager
def db_session():
    connection = get_db()
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def init_db():
    with db_session() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                phone TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('persona', 'campesino')),
                farm_name TEXT,
                place TEXT,
                products TEXT,
                created_at TEXT NOT NULL
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS admin_notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kind TEXT NOT NULL,
                message TEXT NOT NULL,
                related_id INTEGER,
                created_at TEXT NOT NULL,
                is_read INTEGER NOT NULL DEFAULT 0
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS producer_applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                farm TEXT NOT NULL,
                phone TEXT NOT NULL,
                products TEXT NOT NULL,
                place TEXT NOT NULL,
                created_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Pendiente'
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS reservations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL UNIQUE,
                user_id INTEGER,
                name TEXT NOT NULL,
                phone TEXT NOT NULL,
                items_json TEXT NOT NULL,
                total_estimated INTEGER NOT NULL,
                notes TEXT,
                created_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Pendiente',
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE SET NULL
            )
        """)
        # Migración segura: agrega foto de perfil sin perder usuarios existentes.
        user_columns = {row[1] for row in db.execute("PRAGMA table_info(users)")}
        if "profile_photo" not in user_columns:
            db.execute("ALTER TABLE users ADD COLUMN profile_photo TEXT")

        # Migración segura para bases de datos creadas con versiones anteriores.
        reservation_columns = {row[1] for row in db.execute("PRAGMA table_info(reservations)")}
        if "status" not in reservation_columns:
            db.execute("ALTER TABLE reservations ADD COLUMN status TEXT NOT NULL DEFAULT 'Pendiente'")

        admin_email = os.environ.get("ADMIN_EMAIL", "admin@mercadocampesino.local").strip().lower()
        admin_password = os.environ.get("ADMIN_PASSWORD", "AdminYopal2026!")
        admin_name = os.environ.get("ADMIN_NAME", "Administrador")
        if admin_email and admin_password:
            db.execute("""
                INSERT OR IGNORE INTO admins (name, email, password_hash, created_at)
                VALUES (?, ?, ?, ?)
            """, (admin_name, admin_email, generate_password_hash(admin_password), datetime.now(BOGOTA_TZ).isoformat()))


init_db()


def money(value):
    return f"${value:,.0f}".replace(",", ".")


def make_csrf_token():
    token = session.get("_csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["_csrf_token"] = token
    return token


def valid_csrf(value):
    expected = session.get("_csrf_token", "")
    return bool(expected and value and secrets.compare_digest(expected, value))


@app.before_request
def load_current_user():
    g.current_user = None
    admin_id = session.get("admin_id")
    user_id = session.get("user_id")
    if admin_id or user_id:
        with db_session() as db:
            if admin_id:
                admin = db.execute(
                    "SELECT id, name, email, created_at FROM admins WHERE id = ?", (admin_id,)
                ).fetchone()
                if admin:
                    g.current_user = {**dict(admin), "role": "admin", "phone": "", "farm_name": None, "place": None, "products": None}
                else:
                    session.pop("admin_id", None)
            else:
                row = db.execute(
                    "SELECT id, name, email, phone, role, farm_name, place, products, created_at, profile_photo "
                    "FROM users WHERE id = ?", (user_id,)
                ).fetchone()
                if row:
                    g.current_user = dict(row)
                else:
                    session.pop("user_id", None)


@app.context_processor
def inject_global_data():
    admin_unread_count = 0
    user = g.get("current_user")
    if user and user.get("role") == "admin":
        with db_session() as db:
            admin_unread_count = db.execute(
                "SELECT COUNT(*) FROM admin_notifications WHERE is_read = 0"
            ).fetchone()[0]
    return {
        "year": datetime.now(BOGOTA_TZ).year,
        "money": money,
        "current_user": user,
        "admin_unread_count": admin_unread_count,
        "csrf_token": make_csrf_token,
    }


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if g.current_user is None:
            flash("Ingresa a tu cuenta para acceder a este apartado.", "info")
            return redirect(url_for("ingresar", next=request.path))
        return view(*args, **kwargs)
    return wrapped_view


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped_view(*args, **kwargs):
        if g.current_user.get("role") != "admin":
            abort(403)
        return view(*args, **kwargs)
    return wrapped_view


def safe_next_url(target):
    # Solo acepta rutas locales para evitar redirecciones externas.
    if target and target.startswith("/") and not target.startswith("//"):
        return target
    return url_for("cuenta")


@app.get("/")
def home():
    return render_template("home.html", page="home", featured=PRODUCTS[:4])


@app.get("/productos")
def productos():
    categories = sorted({product["category"] for product in PRODUCTS})
    return render_template("productos.html", page="productos", products=PRODUCTS, categories=categories)


@app.get("/como-funciona")
def como_funciona():
    return render_template("como_funciona.html", page="como-funciona")


@app.get("/productores")
def productores():
    return render_template("productores.html", page="productores", producers=PRODUCERS)


@app.route("/ingresar", methods=["GET", "POST"])
def ingresar():
    if g.current_user:
        return redirect(url_for("cuenta"))

    error = None
    next_url = request.args.get("next") or request.form.get("next")

    if request.method == "POST":
        if not valid_csrf(request.form.get("csrf_token")):
            error = "La sesión del formulario venció. Recarga la página e inténtalo de nuevo."
        else:
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            role = request.form.get("role", "")

            if not email or not password or role not in ("persona", "campesino", "admin"):
                error = "Completa tu correo, contraseña y tipo de cuenta."
            else:
                with db_session() as db:
                    if role == "admin":
                        user = db.execute("SELECT * FROM admins WHERE email = ?", (email,)).fetchone()
                    else:
                        user = db.execute("SELECT * FROM users WHERE email = ? AND role = ?", (email, role)).fetchone()

                if not user or not check_password_hash(user["password_hash"], password):
                    error = "No encontramos una cuenta con esos datos y tipo de acceso."
                else:
                    session.clear()
                    if role == "admin":
                        session["admin_id"] = user["id"]
                    else:
                        session["user_id"] = user["id"]
                    make_csrf_token()
                    flash(f"¡Bienvenido/a, {user['name']}!", "success")
                    destination = url_for("admin_dashboard") if role == "admin" else safe_next_url(next_url)
                    return redirect(destination)

    return render_template("auth.html", mode="login", error=error, next_url=next_url or "")


@app.route("/registro", methods=["GET", "POST"])
def registro():
    if g.current_user:
        return redirect(url_for("cuenta"))

    error = None
    form_data = request.form if request.method == "POST" else {}

    if request.method == "POST":
        if not valid_csrf(request.form.get("csrf_token")):
            error = "La sesión del formulario venció. Recarga la página e inténtalo de nuevo."
        else:
            name = request.form.get("name", "").strip()
            email = request.form.get("email", "").strip().lower()
            phone = request.form.get("phone", "").strip()
            password = request.form.get("password", "")
            password_confirm = request.form.get("password_confirm", "")
            role = request.form.get("role", "persona")
            farm_name = request.form.get("farm_name", "").strip()
            place = request.form.get("place", "").strip()
            products = request.form.get("products", "").strip()

            if not all((name, email, phone, password, password_confirm)):
                error = "Completa todos los campos obligatorios."
            elif len(name) > 100 or len(email) > 160 or len(phone) > 30:
                error = "Revisa la longitud de los datos ingresados."
            elif not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
                error = "Escribe un correo electrónico válido."
            elif role not in ("persona", "campesino"):
                error = "Selecciona si tu cuenta será de persona o campesino."
            elif len(password) < 8:
                error = "La contraseña debe tener al menos 8 caracteres."
            elif password != password_confirm:
                error = "Las contraseñas no coinciden."
            elif role == "campesino" and not all((farm_name, place, products)):
                error = "Para la cuenta campesina, completa finca, ubicación y productos."
            elif any(len(value) > 120 for value in (farm_name, place, products)):
                error = "Alguno de los datos de tu unidad productiva es demasiado largo."
            else:
                try:
                    with db_session() as db:
                        cursor = db.execute("""
                            INSERT INTO users
                            (name, email, phone, password_hash, role, farm_name, place, products, created_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            name, email, phone, generate_password_hash(password), role,
                            farm_name if role == "campesino" else None,
                            place if role == "campesino" else None,
                            products if role == "campesino" else None,
                            datetime.now(BOGOTA_TZ).isoformat()
                        ))
                        new_user_id = cursor.lastrowid
                    session.clear()
                    session["user_id"] = new_user_id
                    make_csrf_token()
                    flash("Tu cuenta fue creada correctamente.", "success")
                    return redirect(url_for("cuenta"))
                except sqlite3.IntegrityError:
                    error = "Ya existe una cuenta con ese correo electrónico. Intenta ingresar."

    return render_template("auth.html", mode="register", error=error, form_data=form_data)


@app.errorhandler(413)
def upload_too_large(_error):
    flash("La imagen o GIF supera el límite de 5 MB. Elige un archivo más pequeño.", "error")
    return redirect(url_for("cuenta"))


@app.post("/cuenta/foto")
@login_required
def actualizar_foto_perfil():
    if g.current_user.get("role") == "admin":
        abort(403)
    if not valid_csrf(request.form.get("csrf_token")):
        flash("La sesión del formulario venció. Recarga la página e inténtalo de nuevo.", "error")
        return redirect(url_for("cuenta"))

    photo = request.files.get("profile_photo")
    if not photo or not photo.filename:
        flash("Selecciona una imagen o GIF antes de guardarlo.", "error")
        return redirect(url_for("cuenta"))

    original_name = secure_filename(photo.filename)
    extension = original_name.rsplit(".", 1)[-1].lower() if "." in original_name else ""
    if extension not in PROFILE_ALLOWED_EXTENSIONS:
        flash("Formato no válido. Usa JPG, PNG, WEBP o GIF.", "error")
        return redirect(url_for("cuenta"))

    # Comprueba la firma real del archivo, no solamente su extensión.
    photo.stream.seek(0)
    signature = photo.stream.read(12)
    photo.stream.seek(0)
    valid_signature = (
        (extension in {"jpg", "jpeg"} and signature.startswith(b"\xff\xd8\xff"))
        or (extension == "png" and signature.startswith(b"\x89PNG\r\n\x1a\n"))
        or (extension == "webp" and signature[:4] == b"RIFF" and signature[8:12] == b"WEBP")
        or (extension == "gif" and signature[:6] in {b"GIF87a", b"GIF89a"})
    )
    if not valid_signature:
        flash("El archivo no parece ser una imagen JPG, PNG, WEBP o GIF válida.", "error")
        return redirect(url_for("cuenta"))

    os.makedirs(PROFILE_UPLOAD_DIR, exist_ok=True)
    filename = f"user-{g.current_user['id']}-{uuid.uuid4().hex}.{extension}"
    destination = os.path.join(PROFILE_UPLOAD_DIR, filename)
    photo.save(destination)

    # Para GIF, recorta cada fotograma con el mismo encuadre y conserva la animación.
    if extension == "gif":
        try:
            crop_x = float(request.form.get("crop_x", "0"))
            crop_y = float(request.form.get("crop_y", "0"))
            crop_size = float(request.form.get("crop_size", "1"))
            with Image.open(destination) as source:
                width, height = source.size
                side = max(1, min(width, height, round(crop_size * min(width, height))))
                left = max(0, min(width - side, round(crop_x * width)))
                top = max(0, min(height - side, round(crop_y * height)))
                frames, durations = [], []
                for frame in ImageSequence.Iterator(source):
                    frames.append(frame.convert("RGBA").crop((left, top, left + side, top + side)))
                    durations.append(frame.info.get("duration", source.info.get("duration", 100)))
                if not frames:
                    raise ValueError("GIF sin fotogramas")
                temp_destination = destination + ".cropped.gif"
                frames[0].save(
                    temp_destination, format="GIF", save_all=True,
                    append_images=frames[1:], duration=durations,
                    loop=source.info.get("loop", 0), disposal=2, optimize=False
                )
            os.replace(temp_destination, destination)
        except Exception:
            if os.path.isfile(destination):
                os.remove(destination)
            flash("No fue posible recortar el GIF. Prueba con otro archivo.", "error")
            return redirect(url_for("cuenta"))

    old_photo = g.current_user.get("profile_photo")
    with db_session() as db:
        db.execute("UPDATE users SET profile_photo = ? WHERE id = ?", (filename, g.current_user["id"]))
    if old_photo and os.path.basename(old_photo) == old_photo:
        old_path = os.path.join(PROFILE_UPLOAD_DIR, old_photo)
        if os.path.isfile(old_path):
            os.remove(old_path)

    flash("Tu foto de perfil se actualizó correctamente.", "success")
    return redirect(url_for("cuenta"))


@app.post("/cuenta/foto/eliminar")
@login_required
def eliminar_foto_perfil():
    if g.current_user.get("role") == "admin":
        abort(403)
    if not valid_csrf(request.form.get("csrf_token")):
        flash("La sesión del formulario venció. Recarga la página e inténtalo de nuevo.", "error")
        return redirect(url_for("cuenta"))
    old_photo = g.current_user.get("profile_photo")
    with db_session() as db:
        db.execute("UPDATE users SET profile_photo = NULL WHERE id = ?", (g.current_user["id"],))
    if old_photo and os.path.basename(old_photo) == old_photo:
        old_path = os.path.join(PROFILE_UPLOAD_DIR, old_photo)
        if os.path.isfile(old_path):
            os.remove(old_path)
    flash("Volviste a la imagen de perfil predeterminada.", "success")
    return redirect(url_for("cuenta"))


@app.get("/cuenta")
@login_required
def cuenta():
    user = g.current_user
    if user["role"] == "admin":
        return redirect(url_for("admin_dashboard"))
    user_reservations = []
    if user["role"] == "persona":
        with db_session() as db:
            rows = db.execute(
                "SELECT code, items_json, total_estimated, created_at FROM reservations "
                "WHERE user_id = ? ORDER BY id DESC", (user["id"],)
            ).fetchall()
        for row in rows:
            item = dict(row)
            item["items"] = json.loads(item.pop("items_json"))
            user_reservations.append(item)
    return render_template(
        "account.html", page="cuenta", user=user,
        user_reservations=user_reservations
    )


@app.get("/administracion")
@admin_required
def admin_dashboard():
    with db_session() as db:
        reservations = db.execute("""
            SELECT id, code, name, phone, items_json, total_estimated, notes, created_at, status
            FROM reservations ORDER BY id DESC LIMIT 100
        """).fetchall()
        applications = db.execute("""
            SELECT id, name, farm, phone, products, place, created_at, status
            FROM producer_applications ORDER BY id DESC LIMIT 100
        """).fetchall()
        notifications = db.execute("""
            SELECT id, kind, message, related_id, created_at, is_read
            FROM admin_notifications ORDER BY id DESC LIMIT 30
        """).fetchall()
        unread_count = db.execute("SELECT COUNT(*) FROM admin_notifications WHERE is_read = 0").fetchone()[0]
        reservation_count = db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0]
        application_count = db.execute("SELECT COUNT(*) FROM producer_applications").fetchone()[0]

    reservation_rows = []
    for row in reservations:
        item = dict(row)
        item["items"] = json.loads(item.pop("items_json"))
        reservation_rows.append(item)
    return render_template(
        "admin.html", page="administracion", user=g.current_user,
        reservations=reservation_rows, applications=[dict(row) for row in applications],
        notifications=[dict(row) for row in notifications], unread_count=unread_count,
        reservation_count=reservation_count, application_count=application_count
    )


@app.post("/administracion/notificaciones/leidas")
@admin_required
def admin_mark_notifications_read():
    if not valid_csrf(request.form.get("csrf_token")):
        abort(400)
    with db_session() as db:
        db.execute("UPDATE admin_notifications SET is_read = 1 WHERE is_read = 0")
    flash("Notificaciones marcadas como leídas.", "success")
    return redirect(url_for("admin_dashboard"))


@app.post("/administracion/estado/<kind>/<int:item_id>")
@admin_required
def admin_update_status(kind, item_id):
    if not valid_csrf(request.form.get("csrf_token")):
        abort(400)
    if kind == "reserva":
        table = "reservations"
    elif kind == "productor":
        table = "producer_applications"
    else:
        abort(404)
    with db_session() as db:
        result = db.execute(f"UPDATE {table} SET status = 'Revisada' WHERE id = ?", (item_id,))
        if result.rowcount == 0:
            abort(404)
    flash("La solicitud se actualizó correctamente.", "success")
    return redirect(url_for("admin_dashboard"))


@app.post("/salir")
def salir():
    if not valid_csrf(request.form.get("csrf_token")):
        abort(400)
    session.clear()
    flash("Has cerrado sesión correctamente.", "success")
    return redirect(url_for("home"))


@app.post("/api/reservas")
def crear_reserva():
    if not valid_csrf(request.headers.get("X-CSRF-Token")):
        return jsonify(error="La sesión venció. Actualiza la página e inténtalo de nuevo."), 400

    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    phone = str(data.get("phone", "")).strip()
    raw_items = data.get("items", {})

    if not name or not phone or not isinstance(raw_items, dict) or not raw_items:
        return jsonify(error="Completa tu nombre, teléfono y selecciona al menos un producto."), 400
    if len(name) > 100 or len(phone) > 30:
        return jsonify(error="Revisa los datos ingresados e inténtalo nuevamente."), 400

    now = datetime.now(BOGOTA_TZ)
    if now.weekday() == 4 and (now.hour, now.minute) >= (18, 0):
        return jsonify(error="Las reservas de esta semana cerraron el viernes a las 6:00 p. m."), 400
    if now.weekday() in (5, 6):
        return jsonify(error="La jornada de recogida está en curso o ya terminó. Las reservas abrirán el lunes."), 400

    catalog = {product["id"]: product for product in PRODUCTS}
    normalized_items = []
    total = 0
    for product_id, raw_quantity in raw_items.items():
        product = catalog.get(product_id)
        try:
            quantity = int(raw_quantity)
        except (TypeError, ValueError):
            quantity = 0
        if not product or quantity < 1 or quantity > 99:
            return jsonify(error="Uno de los productos o cantidades no es válido. Actualiza tu carrito."), 400
        line_total = product["price"] * quantity
        total += line_total
        normalized_items.append({
            "id": product["id"], "producto": product["name"], "cantidad": quantity,
            "unidad": product["unit"], "precio_unitario": product["price"], "subtotal": line_total,
        })

    code = "MC-" + uuid.uuid4().hex[:6].upper()
    notes = str(data.get("notes", "")).strip()[:500]
    created_at = now.isoformat()
    with db_session() as db:
        cursor = db.execute("""
            INSERT INTO reservations
            (code, user_id, name, phone, items_json, total_estimated, notes, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            code, session.get("user_id"), name, phone,
            json.dumps(normalized_items, ensure_ascii=False), total, notes, created_at
        ))
        db.execute("""
            INSERT INTO admin_notifications (kind, message, related_id, created_at)
            VALUES ('reserva', ?, ?, ?)
        """, (f"Nueva reserva {code} de {name}.", cursor.lastrowid, created_at))

    reservas.append({
        "codigo": code, "nombre": name, "telefono": phone,
        "items": normalized_items, "total_estimado": total,
        "notas": notes, "creada": created_at,
    })
    return jsonify(codigo=code, mensaje="Tu solicitud de reserva quedó registrada."), 201


@app.post("/api/solicitud-productor")
def solicitud_productor():
    if not valid_csrf(request.headers.get("X-CSRF-Token")):
        return jsonify(error="La sesión venció. Actualiza la página e inténtalo de nuevo."), 400

    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    farm = str(data.get("farm", "")).strip()
    phone = str(data.get("phone", "")).strip()
    product = str(data.get("product", "")).strip()
    place = str(data.get("place", "")).strip()

    if not all((name, farm, phone, product, place)):
        return jsonify(error="Completa todos los campos para enviar tu solicitud."), 400
    if any(len(value) > 120 for value in (name, farm, phone, product, place)):
        return jsonify(error="Alguno de los campos supera la longitud permitida."), 400

    created_at = datetime.now(BOGOTA_TZ).isoformat()
    with db_session() as db:
        cursor = db.execute("""
            INSERT INTO producer_applications (name, farm, phone, products, place, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (name, farm, phone, product, place, created_at))
        db.execute("""
            INSERT INTO admin_notifications (kind, message, related_id, created_at)
            VALUES ('productor', ?, ?, ?)
        """, (f"Nueva solicitud de productor: {name} ({farm}).", cursor.lastrowid, created_at))
    return jsonify(mensaje="Recibimos tu solicitud de participación. ¡Gracias por sumarte!"), 201


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
