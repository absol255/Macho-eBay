from flask import (
    Flask,
    request,
    jsonify,
    render_template,
    redirect,
    url_for,
    session,
)
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from config import Config
from models import db, User, Admin, Product
from decimal import Decimal, InvalidOperation
import os
import time
import click
import json

app = Flask(
    __name__,
    template_folder="templates",
    static_folder="static",
)

app.config.from_object(Config)

if os.getenv("VERCEL"):
    from werkzeug.middleware.proxy_fix import ProxyFix

    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"


def init_db():
    with app.app_context():
        db.create_all()


def ensure_tables():
    """Create tables if missing. Returns an error string or None."""
    try:
        db.create_all()
        return None
    except Exception as exc:
        app.logger.exception("ensure_tables failed")
        return str(exc)


class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


app.json_encoder = DecimalEncoder


def maybe_bootstrap_admin():
    """Optional: set BOOTSTRAP_ADMIN_USER + BOOTSTRAP_ADMIN_PASSWORD in Vercel once."""
    user = os.getenv("BOOTSTRAP_ADMIN_USER")
    password = os.getenv("BOOTSTRAP_ADMIN_PASSWORD")
    if not user or not password:
        return
    try:
        if Admin.query.count() > 0:
            return
        admin = Admin(username=user.strip()[:64])
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()
        app.logger.info("Bootstrapped admin user: %s", user)
    except Exception:
        app.logger.exception("bootstrap admin failed")
        db.session.rollback()


def parse_bank_account_number(value):
    if value is None or value == "":
        return None
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def find_user_by_credentials(username, bank_account_number):
    username = (username or "").strip()
    bank_num = parse_bank_account_number(bank_account_number)
    if not username or bank_num is None:
        return None
    return User.query.filter_by(
        username=username,
        bank_account_number=bank_num,
    ).first()


def get_seller_user_id():
    seller_id = session.get("seller_user_id")
    if not seller_id:
        return None
    return db.session.get(User, int(seller_id))


def parse_positive_int(value, field_name):
    try:
        num = int(value)
    except (TypeError, ValueError):
        return None, f"{field_name} must be a positive integer"
    if num <= 0:
        return None, f"{field_name} must be a positive integer"
    return num, None


def parse_price(value):
    try:
        price = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None, "Price must be a valid number"
    if price <= 0:
        return None, "Price must be greater than zero"
    return price, None


@login_manager.user_loader
def load_user(user_id):
    try:
        return db.session.get(Admin, int(user_id))
    except (TypeError, ValueError):
        return None


@login_manager.unauthorized_handler
def unauthorized():
    if request.path.startswith("/api/"):
        return jsonify({"error": "Login required"}), 401
    return redirect(url_for("login"))


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/selling")
def selling():
    return render_template("selling.html")


@app.route("/admin")
@login_required
def admin():
    return render_template("admin.html")


@app.route("/login")
def login():
    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect("/")


def _config_error():
    if not app.config.get("SECRET_KEY"):
        return "SECRET_KEY is not set on the server"
    if not app.config.get("SQLALCHEMY_DATABASE_URI"):
        return "DATABASE_URL is not set on the server"
    return None


@app.route("/api/health")
def api_health():
    err = _config_error()
    if err:
        return jsonify({"ok": False, "error": err}), 503
    try:
        db.session.execute(db.text("SELECT 1"))
        table_err = ensure_tables()
        maybe_bootstrap_admin()
        admin_count = Admin.query.count()
        payload = {
            "ok": table_err is None,
            "db": True,
            "tables_ok": table_err is None,
            "admin_count": admin_count,
        }
        if table_err:
            payload["error"] = table_err
        elif admin_count == 0:
            payload["hint"] = (
                "No admin users. Run: flask --app app create-admin USER PASS "
                "with production DATABASE_URL, or set BOOTSTRAP_ADMIN_USER and "
                "BOOTSTRAP_ADMIN_PASSWORD in Vercel temporarily."
            )
        status = 503 if table_err else 200
        return jsonify(payload), status
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 503


@app.route("/api/login", methods=["POST"])
def api_login():
    err = _config_error()
    if err:
        return jsonify({"error": err}), 503

    table_err = ensure_tables()
    if table_err:
        return jsonify({"error": "Tables not ready: " + table_err}), 503

    maybe_bootstrap_admin()

    data = request.get_json(silent=True) or {}

    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    if not username or not password:
        return jsonify({"error": "Username and password required"}), 400

    try:
        admin = Admin.query.filter_by(username=username).first()
    except Exception as exc:
        app.logger.exception("login database error")
        return jsonify({"error": "Database error: " + str(exc)}), 503

    if not admin:
        if not os.getenv("VERCEL"):
            time.sleep(1)
        return jsonify({
            "error": "Invalid username (no admin in this database — check /api/health admin_count)",
        }), 401

    if not admin.check_password(password):
        if not os.getenv("VERCEL"):
            time.sleep(1)
        return jsonify({"error": "Invalid password"}), 401

    session.permanent = True
    login_user(admin)
    return jsonify({"success": True, "username": admin.username})


@app.route("/api/session", methods=["POST"])
def api_session():
    err = _config_error()
    if err:
        return jsonify({"error": err}), 503

    table_err = ensure_tables()
    if table_err:
        return jsonify({"error": "Tables not ready: " + table_err}), 503

    data = request.get_json(silent=True) or {}
    username = data.get("username")
    bank_account_number = data.get("bank_account_number")

    user = find_user_by_credentials(username, bank_account_number)
    if not user:
        return jsonify({"error": "Invalid username or bank account number"}), 401

    session.permanent = True
    session["seller_user_id"] = user.id
    return jsonify({"success": True, "user": user.to_dict()})


@app.route("/api/session", methods=["GET"])
def api_session_status():
    user = get_seller_user_id()
    if not user:
        return jsonify({"signed_in": False})
    return jsonify({"signed_in": True, "user": user.to_dict()})


@app.route("/api/session", methods=["DELETE"])
def api_session_logout():
    session.pop("seller_user_id", None)
    return jsonify({"success": True})


@app.route("/api/products", methods=["GET"])
def api_products_list():
    err = _config_error()
    if err:
        return jsonify({"error": err}), 503

    table_err = ensure_tables()
    if table_err:
        return jsonify({"error": "Tables not ready: " + table_err}), 503

    products = (
        Product.query.filter_by(status="approved")
        .filter(Product.quantity > 0)
        .order_by(Product.created_at.desc())
        .all()
    )
    return jsonify([p.to_dict() for p in products])


@app.route("/api/products/mine", methods=["GET"])
def api_products_mine():
    err = _config_error()
    if err:
        return jsonify({"error": err}), 503

    table_err = ensure_tables()
    if table_err:
        return jsonify({"error": "Tables not ready: " + table_err}), 503

    user = get_seller_user_id()
    if not user:
        return jsonify({"error": "Sign in required"}), 401

    products = (
        Product.query.filter_by(seller_id=user.id)
        .order_by(Product.created_at.desc())
        .all()
    )
    return jsonify([p.to_dict(include_image=False) for p in products])


@app.route("/api/products/pending", methods=["GET"])
@login_required
def api_products_pending():
    err = _config_error()
    if err:
        return jsonify({"error": err}), 503

    table_err = ensure_tables()
    if table_err:
        return jsonify({"error": "Tables not ready: " + table_err}), 503

    products = (
        Product.query.filter_by(status="pending")
        .order_by(Product.created_at.asc())
        .all()
    )
    return jsonify([p.to_dict() for p in products])


@app.route("/api/products/approved", methods=["GET"])
@login_required
def api_products_approved():
    err = _config_error()
    if err:
        return jsonify({"error": err}), 503

    table_err = ensure_tables()
    if table_err:
        return jsonify({"error": "Tables not ready: " + table_err}), 503

    products = (
        Product.query.filter_by(status="approved")
        .order_by(Product.created_at.desc())
        .all()
    )
    return jsonify([p.to_dict() for p in products])


@app.route("/api/products", methods=["POST"])
def api_products_create():
    err = _config_error()
    if err:
        return jsonify({"error": err}), 503

    table_err = ensure_tables()
    if table_err:
        return jsonify({"error": "Tables not ready: " + table_err}), 503

    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    image_data = (data.get("image_data") or "").strip()

    quantity, qty_err = parse_positive_int(data.get("quantity"), "Quantity")
    if qty_err:
        return jsonify({"error": qty_err}), 400

    price, price_err = parse_price(data.get("price"))
    if price_err:
        return jsonify({"error": price_err}), 400

    if not name:
        return jsonify({"error": "Product name is required"}), 400
    if not image_data:
        return jsonify({"error": "Product image is required"}), 400

    is_admin = current_user.is_authenticated

    if is_admin:
        seller = find_user_by_credentials(
            data.get("username"),
            data.get("bank_account_number"),
        )
        if not seller:
            return jsonify({"error": "Seller username and bank account number required"}), 400
        status = "approved"
    else:
        seller = get_seller_user_id()
        if not seller:
            return jsonify({"error": "Sign in required"}), 401
        status = "pending"

    product = Product(
        seller_id=seller.id,
        name=name[:128],
        image_data=image_data,
        quantity=quantity,
        price=price,
        status=status,
    )
    db.session.add(product)
    db.session.commit()

    return jsonify({
        "success": True,
        "product": product.to_dict(include_image=False),
        "auto_approved": is_admin,
    })


@app.route("/api/products/<int:product_id>/approve", methods=["POST"])
@login_required
def api_products_approve(product_id):
    err = _config_error()
    if err:
        return jsonify({"error": err}), 503

    table_err = ensure_tables()
    if table_err:
        return jsonify({"error": "Tables not ready: " + table_err}), 503

    product = db.session.get(Product, product_id)
    if not product:
        return jsonify({"error": "Product not found"}), 404
    if product.status != "pending":
        return jsonify({"error": "Product is not pending approval"}), 400

    product.status = "approved"
    db.session.commit()
    return jsonify({"success": True, "product": product.to_dict(include_image=False)})


@app.route("/api/products/<int:product_id>/reject", methods=["POST"])
@login_required
def api_products_reject(product_id):
    err = _config_error()
    if err:
        return jsonify({"error": err}), 503

    table_err = ensure_tables()
    if table_err:
        return jsonify({"error": "Tables not ready: " + table_err}), 503

    product = db.session.get(Product, product_id)
    if not product:
        return jsonify({"error": "Product not found"}), 404
    if product.status != "pending":
        return jsonify({"error": "Product is not pending approval"}), 400

    product.status = "rejected"
    db.session.commit()
    return jsonify({"success": True, "product": product.to_dict(include_image=False)})


@app.route("/api/products/<int:product_id>", methods=["DELETE"])
@login_required
def api_products_remove(product_id):
    err = _config_error()
    if err:
        return jsonify({"error": err}), 503

    table_err = ensure_tables()
    if table_err:
        return jsonify({"error": "Tables not ready: " + table_err}), 503

    product = db.session.get(Product, product_id)
    if not product:
        return jsonify({"error": "Product not found"}), 404
    if product.status != "approved":
        return jsonify({"error": "Only approved listings can be removed from the shop"}), 400

    db.session.delete(product)
    db.session.commit()
    return jsonify({"success": True})


@app.route("/api/purchase", methods=["POST"])
def api_purchase():
    err = _config_error()
    if err:
        return jsonify({"error": err}), 503

    table_err = ensure_tables()
    if table_err:
        return jsonify({"error": "Tables not ready: " + table_err}), 503

    data = request.get_json(silent=True) or {}
    product_id = data.get("product_id")

    try:
        product_id = int(product_id)
    except (TypeError, ValueError):
        return jsonify({"error": "Product id is required"}), 400

    quantity, qty_err = parse_positive_int(data.get("quantity"), "Quantity")
    if qty_err:
        return jsonify({"error": qty_err}), 400

    buyer = find_user_by_credentials(
        data.get("username"),
        data.get("bank_account_number"),
    )
    if not buyer:
        return jsonify({"error": "Invalid username or bank account number"}), 401

    product = db.session.get(Product, product_id)
    if not product or product.status != "approved":
        return jsonify({"error": "Product not available"}), 404

    if product.quantity < quantity:
        return jsonify({"error": "Not enough stock available"}), 400

    seller = db.session.get(User, product.seller_id)
    if not seller:
        return jsonify({"error": "Seller not found"}), 404

    if buyer.id == seller.id:
        return jsonify({"error": "You cannot buy your own listing"}), 400

    total = product.price * quantity
    buyer_balance = Decimal(str(buyer.macho_bucks))
    if buyer_balance < total:
        return jsonify({"error": "Not enough M$"}), 400

    buyer.macho_bucks = buyer_balance - total
    seller.macho_bucks = Decimal(str(seller.macho_bucks)) + total
    product.quantity -= quantity

    db.session.commit()

    return jsonify({
        "success": True,
        "total": total,
        "remaining_balance": buyer.macho_bucks,
        "product": product.to_dict(include_image=False),
    })


@app.cli.command("create-admin")
@click.argument("username")
@click.argument("password")
def create_admin(username, password):
    """Create a admin (run once): flask create-admin user pass"""
    init_db()
    if Admin.query.filter_by(username=username).first():
        click.echo("Admin already exists.")
        return
    admin = Admin(username=username)
    admin.set_password(password)
    db.session.add(admin)
    db.session.commit()
    click.echo("Admin created: " + username)


try:
    init_db()
except Exception:
    pass
