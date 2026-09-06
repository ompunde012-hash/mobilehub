from flask import (
    Flask,
    request,
    redirect,
    url_for,
    session,
    flash,
    render_template_string,
    jsonify
)
import sqlite3
import os
import secrets
from functools import wraps
from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)

# Optional Razorpay
try:
    import razorpay
except ImportError:
    razorpay = None


# =========================================================
# APP CONFIG
# =========================================================

app = Flask(__name__)

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "mobilehub-dev-secret-change-this"
)

DB = "shop.db"

RAZORPAY_KEY_ID = os.environ.get(
    "RAZORPAY_KEY_ID",
    ""
)

RAZORPAY_KEY_SECRET = os.environ.get(
    "RAZORPAY_KEY_SECRET",
    ""
)

razorpay_client = None

if (
    razorpay
    and RAZORPAY_KEY_ID
    and RAZORPAY_KEY_SECRET
):
    razorpay_client = razorpay.Client(
        auth=(
            RAZORPAY_KEY_ID,
            RAZORPAY_KEY_SECRET
        )
    )


# =========================================================
# DATABASE
# =========================================================

def db():

    conn = sqlite3.connect(DB)

    conn.row_factory = sqlite3.Row

    conn.execute(
        "PRAGMA foreign_keys = ON"
    )

    return conn


def column_exists(
    conn,
    table,
    column
):

    columns = conn.execute(
        f"PRAGMA table_info({table})"
    ).fetchall()

    return any(
        row["name"] == column
        for row in columns
    )


def add_column_if_missing(
    conn,
    table,
    column,
    definition
):

    if not column_exists(
        conn,
        table,
        column
    ):

        conn.execute(
            f"""
            ALTER TABLE {table}
            ADD COLUMN {column} {definition}
            """
        )


def init_db():

    conn = db()

    # =====================================================
    # USERS
    # =====================================================

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            is_admin INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # =====================================================
    # PRODUCTS
    # =====================================================

    conn.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            brand TEXT NOT NULL,
            price INTEGER NOT NULL,
            image TEXT NOT NULL
        )
    """)

    add_column_if_missing(
        conn,
        "products",
        "description",
        "TEXT DEFAULT ''"
    )

    add_column_if_missing(
        conn,
        "products",
        "stock",
        "INTEGER DEFAULT 10"
    )

    add_column_if_missing(
        conn,
        "products",
        "rating",
        "REAL DEFAULT 4.5"
    )

    # =====================================================
    # ORDERS
    # =====================================================

    conn.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            customer_name TEXT NOT NULL,
            address TEXT NOT NULL,
            total INTEGER NOT NULL,
            payment TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id)
                REFERENCES users(id)
        )
    """)

    add_column_if_missing(
        conn,
        "orders",
        "status",
        "TEXT DEFAULT 'Pending'"
    )

    add_column_if_missing(
        conn,
        "orders",
        "payment_id",
        "TEXT DEFAULT ''"
    )

    # =====================================================
    # ORDER ITEMS
    # =====================================================

    conn.execute("""
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            price INTEGER NOT NULL,
            FOREIGN KEY(order_id)
                REFERENCES orders(id),
            FOREIGN KEY(product_id)
                REFERENCES products(id)
        )
    """)

    # =====================================================
    # WISHLIST
    # =====================================================

    conn.execute("""
        CREATE TABLE IF NOT EXISTS wishlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            UNIQUE(user_id, product_id),
            FOREIGN KEY(user_id)
                REFERENCES users(id),
            FOREIGN KEY(product_id)
                REFERENCES products(id)
        )
    """)

    # =====================================================
    # REVIEWS
    # =====================================================

    conn.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            rating INTEGER NOT NULL,
            comment TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            UNIQUE(user_id, product_id),

            FOREIGN KEY(user_id)
                REFERENCES users(id),

            FOREIGN KEY(product_id)
                REFERENCES products(id)
        )
    """)

    # =====================================================
    # ADMIN
    # =====================================================

    admin = conn.execute(
        """
        SELECT *
        FROM users
        WHERE email=?
        """,
        ("admin@gmail.com",)
    ).fetchone()

    if not admin:

        conn.execute("""
            INSERT INTO users
            (
                name,
                email,
                password,
                is_admin
            )
            VALUES(?,?,?,?)
        """, (
            "Admin",
            "admin@gmail.com",
            generate_password_hash("admin123"),
            1
        ))

    # =====================================================
    # DEMO PRODUCTS
    # =====================================================

    count = conn.execute(
        "SELECT COUNT(*) FROM products"
    ).fetchone()[0]

    if count == 0:

        products = [

            (
                "iPhone 15",
                "Apple",
                69999,
                "https://images.unsplash.com/photo-1592899677977-9c10ca588bbd?w=700",
                "iPhone 15 with powerful performance, premium design and excellent camera.",
                15,
                4.8
            ),

            (
                "Galaxy S24",
                "Samsung",
                64999,
                "https://images.unsplash.com/photo-1610945265064-0e34e5519bbf?w=700",
                "Samsung Galaxy S24 with AMOLED display and flagship performance.",
                12,
                4.7
            ),

            (
                "OnePlus 12",
                "OnePlus",
                59999,
                "https://images.unsplash.com/photo-1598327105666-5b89351aff97?w=700",
                "OnePlus 12 with fast performance and premium display.",
                20,
                4.6
            ),

            (
                "Pixel 8",
                "Google",
                49999,
                "https://images.unsplash.com/photo-1598327105666-5b89351aff97?w=700",
                "Google Pixel with excellent photography and clean Android.",
                10,
                4.5
            ),

            (
                "Redmi Note 13",
                "Xiaomi",
                24999,
                "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=700",
                "Affordable smartphone with great battery and modern design.",
                30,
                4.4
            ),

            (
                "Vivo V30",
                "Vivo",
                32999,
                "https://images.unsplash.com/photo-1567581935884-3349723552ca?w=700",
                "Stylish Vivo smartphone with excellent camera features.",
                18,
                4.5
            )
        ]

        conn.executemany("""
            INSERT INTO products
            (
                name,
                brand,
                price,
                image,
                description,
                stock,
                rating
            )
            VALUES(?,?,?,?,?,?,?)
        """, products)

    conn.commit()

    conn.close()


# =========================================================
# SECURITY
# =========================================================

def csrf_token():

    if "csrf_token" not in session:

        session["csrf_token"] = secrets.token_urlsafe(32)

    return session["csrf_token"]


def validate_csrf():

    token = request.form.get(
        "csrf_token",
        ""
    )

    return (
        token
        and token == session.get("csrf_token")
    )


@app.context_processor
def inject_globals():

    return {
        "csrf_token": csrf_token()
    }


# =========================================================
# AUTH
# =========================================================

def login_required(func):

    @wraps(func)
    def wrapper(*args, **kwargs):

        if "user_id" not in session:

            flash(
                "Please login first.",
                "warning"
            )

            return redirect(
                url_for("login")
            )

        return func(
            *args,
            **kwargs
        )

    return wrapper


def admin_required(func):

    @wraps(func)
    def wrapper(*args, **kwargs):

        if not session.get("is_admin"):

            return (
                "Access Denied - Admin Only",
                403
            )

        return func(
            *args,
            **kwargs
        )

    return wrapper


# =========================================================
# TEMPLATE
# =========================================================

BASE = """

<!DOCTYPE html>

<html>

<head>

<meta charset="UTF-8">

<meta
name="viewport"
content="width=device-width, initial-scale=1.0"
>

<title>{{ title }} - MobileHub</title>

<style>

* {
    box-sizing: border-box;
}

body {
    margin: 0;
    font-family:
        Arial,
        Helvetica,
        sans-serif;

    background: #f1f3f6;
    color: #222;
}

header {
    background: #2874f0;
    color: white;
    padding: 14px 5%;

    display: flex;
    align-items: center;

    gap: 20px;
    flex-wrap: wrap;
}

.logo {
    font-size: 26px;
    font-weight: bold;
}

.search {
    flex: 1;
    max-width: 560px;
    display: flex;
}

.search input {
    width: 100%;
    padding: 13px;
    border: 0;
    outline: 0;
}

.search button {
    padding: 13px 18px;
    border: 0;
    background: white;
    cursor: pointer;
}

nav {
    display: flex;
    align-items: center;
    gap: 13px;
    flex-wrap: wrap;
}

nav a {
    color: white;
    text-decoration: none;
}

nav a:hover {
    text-decoration: underline;
}

.container {
    max-width: 1200px;
    margin: auto;
    padding: 25px;
}

.hero {
    background:
        linear-gradient(
            135deg,
            #2874f0,
            #6c5ce7
        );

    color: white;
    text-align: center;

    padding: 70px 20px;
}

.hero h1 {
    font-size: 42px;
    margin: 0 0 15px;
}

.hero p {
    font-size: 18px;
}

.filters {
    background: white;
    padding: 20px;
    text-align: center;
}

.filters a {
    display: inline-block;

    padding: 9px 17px;
    margin: 5px;

    border-radius: 20px;

    color: #2874f0;
    background: #f1f6ff;

    text-decoration: none;
}

.products {
    display: grid;

    grid-template-columns:
        repeat(
            auto-fit,
            minmax(230px, 1fr)
        );

    gap: 25px;

    padding: 30px 5%;
}

.card {
    background: white;

    border-radius: 12px;

    overflow: hidden;

    box-shadow:
        0 3px 12px #ddd;

    transition: .2s;
}

.card:hover {
    transform: translateY(-5px);
}

.card img {
    width: 100%;
    height: 230px;

    object-fit: contain;

    padding: 15px;
}

.info {
    padding: 20px;
}

.price {
    font-size: 23px;
}

.rating {
    color: #ff9800;
    font-weight: bold;
}

.button {
    display: inline-block;

    padding: 11px 16px;

    border: 0;
    border-radius: 5px;

    color: white;

    text-decoration: none;

    cursor: pointer;

    background: #ff9f00;
}

.button:hover {
    opacity: .9;
}

.blue {
    background: #2874f0;
}

.green {
    background: #2e7d32;
}

.red {
    background: #e53935;
}

.dark {
    background: #333;
}

.form-box {
    background: white;

    max-width: 520px;

    margin: 45px auto;

    padding: 30px;

    border-radius: 12px;

    box-shadow:
        0 3px 12px #ddd;
}

.form-box input,
.form-box textarea,
.form-box select {
    width: 100%;

    padding: 13px;

    margin: 9px 0;

    border:
        1px solid #ddd;

    border-radius: 5px;
}

.form-box textarea {
    min-height: 120px;
}

.form-box button {
    width: 100%;

    padding: 13px;

    background: #2874f0;

    color: white;

    border: 0;

    border-radius: 5px;

    cursor: pointer;
}

.message {
    max-width: 750px;

    margin: 15px auto;

    padding: 13px;

    text-align: center;

    border-radius: 6px;

    background: #fff3cd;
}

.success {
    max-width: 700px;

    margin: 60px auto;

    padding: 45px;

    text-align: center;

    background: white;

    border-radius: 15px;

    box-shadow: 0 3px 12px #ddd;
}

.product-detail {
    max-width: 1050px;

    margin: 40px auto;

    padding: 35px;

    background: white;

    border-radius: 15px;

    display: grid;

    grid-template-columns:
        1fr 1fr;

    gap: 45px;

    box-shadow:
        0 3px 15px #ddd;
}

.product-detail img {
    width: 100%;
    height: 430px;
    object-fit: contain;
}

.big-price {
    font-size: 32px;
    font-weight: bold;
}

.stock {
    color: #2e7d32;
    font-weight: bold;
}

.out-stock {
    color: #e53935;
    font-weight: bold;
}

.cart {
    max-width: 950px;
    margin: 30px auto;
    padding: 20px;
}

.cart-item {
    background: white;

    padding: 20px;

    margin-bottom: 15px;

    border-radius: 9px;

    display: flex;

    align-items: center;

    gap: 25px;

    box-shadow:
        0 2px 8px #ddd;
}

.cart-item img {
    width: 120px;
    height: 120px;

    object-fit: contain;
}

.cart-content {
    flex: 1;
}

.qty {
    display: flex;

    align-items: center;

    gap: 10px;
}

.qty a {
    background: #2874f0;

    color: white;

    text-decoration: none;

    padding: 5px 12px;

    border-radius: 4px;
}

.total {
    background: white;

    padding: 25px;

    text-align: right;

    border-radius: 8px;
}

.order {
    background: white;

    max-width: 900px;

    margin: 18px auto;

    padding: 22px;

    border-radius: 9px;

    box-shadow:
        0 2px 8px #ddd;
}

.status {
    display: inline-block;

    padding: 7px 14px;

    border-radius: 20px;

    background: #e3f2fd;

    color: #1565c0;

    font-weight: bold;
}

.review {
    background: #fafafa;

    padding: 15px;

    margin: 10px 0;

    border-radius: 7px;
}

.admin {
    max-width: 1150px;

    margin: auto;

    padding: 25px;
}

.dashboard {
    display: grid;

    grid-template-columns:
        repeat(
            auto-fit,
            minmax(190px, 1fr)
        );

    gap: 20px;
}

.stat {
    background: white;

    padding: 25px;

    text-align: center;

    border-radius: 10px;

    box-shadow:
        0 2px 8px #ddd;
}

.stat h2 {
    color: #2874f0;
    font-size: 28px;
}

.track {
    display: flex;

    justify-content:
        space-between;

    margin: 25px 0;

    position: relative;
}

.track-step {
    text-align: center;

    flex: 1;

    position: relative;
}

.track-circle {
    width: 38px;
    height: 38px;

    margin: auto;

    border-radius: 50%;

    background: #ddd;

    color: white;

    display: flex;

    align-items: center;

    justify-content: center;

    font-weight: bold;
}

.track-step.active
.track-circle {
    background: #2874f0;
}

.bar {
    height: 10px;

    background: #2874f0;

    margin-top: 10px;

    border-radius: 10px;
}

footer {
    margin-top: 70px;

    background: #172337;

    color: white;

    padding: 35px;

    text-align: center;
}

table {
    width: 100%;
    border-collapse: collapse;
}

td,
th {
    padding: 10px;

    border-bottom:
        1px solid #ddd;

    text-align: left;
}

@media(max-width:700px) {

    header {
        justify-content: center;
    }

    .search {
        flex-basis: 100%;
        order: 3;
    }

    nav {
        justify-content: center;
    }

    .hero h1 {
        font-size: 28px;
    }

    .product-detail {
        grid-template-columns: 1fr;

        margin: 20px;
    }

    .product-detail img {
        height: 280px;
    }

    .cart-item {
        flex-direction: column;
        text-align: center;
    }

    .total {
        text-align: center;
    }

}

</style>

</head>

<body>

<header>

<div class="logo">
📱 MobileHub
</div>

<form
class="search"
action="{{ url_for('home') }}"
method="GET"
>

<input
name="search"
value="{{ request.args.get('search','') }}"
placeholder="Search mobile..."
>

<button>
🔍
</button>

</form>

<nav>

<a href="{{ url_for('home') }}">
Home
</a>

<a href="{{ url_for('cart') }}">
🛒 Cart
</a>

{% if session.get('user_id') %}

<a href="{{ url_for('wishlist') }}">
❤️ Wishlist
</a>

<a href="{{ url_for('orders') }}">
📦 Orders
</a>

<a href="{{ url_for('profile') }}">
👤 Profile
</a>

<span>
Hello, {{ session.get('user_name') }}
</span>

<a href="{{ url_for('logout') }}">
Logout
</a>

{% if session.get('is_admin') %}

<a href="{{ url_for('admin') }}">
🛠️ Admin
</a>

{% endif %}

{% else %}

<a href="{{ url_for('login') }}">
Login
</a>

<a href="{{ url_for('register') }}">
Register
</a>

{% endif %}

</nav>

</header>

{% with messages =
get_flashed_messages(with_categories=true)
%}

{% for category, message in messages %}

<div class="message">
{{ message }}
</div>

{% endfor %}

{% endwith %}

{{ content|safe }}

<footer>

📱 MobileHub

<br><br>

Online Mobile Shopping

<br><br>

© 2026 MobileHub

</footer>

</body>

</html>
"""


def page(
    title,
    content
):

    return render_template_string(
        BASE,
        title=title,
        content=content
    )


# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():

    search = request.args.get(
        "search",
        ""
    ).strip()

    brand = request.args.get(
        "brand",
        ""
    ).strip()

    min_price = request.args.get(
        "min_price",
        ""
    ).strip()

    max_price = request.args.get(
        "max_price",
        ""
    ).strip()

    sort = request.args.get(
        "sort",
        ""
    )

    conn = db()

    query = """
        SELECT *
        FROM products
        WHERE 1=1
    """

    params = []

    if search:

        query += """
            AND (
                name LIKE ?
                OR brand LIKE ?
            )
        """

        params.extend([
            f"%{search}%",
            f"%{search}%"
        ])

    if brand:

        query += """
            AND brand=?
        """

        params.append(brand)

    if min_price:

        try:

            query += """
                AND price>=?
            """

            params.append(
                int(min_price)
            )

        except ValueError:
            pass

    if max_price:

        try:

            query += """
                AND price<=?
            """

            params.append(
                int(max_price)
            )

        except ValueError:
            pass

    if sort == "low":

        query += """
            ORDER BY price ASC
        """

    elif sort == "high":

        query += """
            ORDER BY price DESC
        """

    elif sort == "rating":

        query += """
            ORDER BY rating DESC
        """

    else:

        query += """
            ORDER BY id DESC
        """

    products = conn.execute(
        query,
        params
    ).fetchall()

    brands = conn.execute("""
        SELECT DISTINCT brand
        FROM products
        ORDER BY brand
    """).fetchall()

    conn.close()

    cards = ""

    for p in products:

        if p["stock"] > 0:

            stock = f"""
                <p class="stock">
                    ✅ In Stock: {p["stock"]}
                </p>
            """

            add_button = f"""
                <a
                class="button"
                href="/add/{p['id']}">

                🛒 Add

                </a>
            """

        else:

            stock = """
                <p class="out-stock">
                    ❌ Out of Stock
                </p>
            """

            add_button = ""

        cards += f"""

        <div class="card">

            <a href="/product/{p['id']}">

                <img
                src="{p['image']}"
                alt="{p['name']}">

            </a>

            <div class="info">

                <small>
                    {p['brand']}
                </small>

                <h3>
                    {p['name']}
                </h3>

                <div class="rating">
                    ⭐ {p['rating']}
                </div>

                <h2 class="price">
                    ₹{p['price']:,}
                </h2>

                {stock}

                <a
                class="button blue"
                href="/product/{p['id']}">

                View

                </a>

                {add_button}

            </div>

        </div>

        """

    if not cards:

        cards = """
            <div class="success">
                <h2>
                    No products found 😕
                </h2>

                <a
                class="button blue"
                href="/">

                View All Products

                </a>
            </div>
        """

    filter_html = """
        <a href="/">
            All
        </a>
    """

    for b in brands:

        filter_html += f"""
            <a
            href="/?brand={b['brand']}">

                {b['brand']}

            </a>
        """

    content = f"""

<section class="hero">

<h1>
Find Your Perfect Smartphone 📱
</h1>

<p>
Latest smartphones at the best prices
</p>

</section>

<div class="filters">

{filter_html}

<br><br>

<form method="GET">

<input
name="min_price"
type="number"
placeholder="Min Price"
style="padding:10px"
>

<input
name="max_price"
type="number"
placeholder="Max Price"
style="padding:10px"
>

<select
name="sort"
style="padding:10px">

<option value="">
Sort By
</option>

<option value="low">
Price Low → High
</option>

<option value="high">
Price High → Low
</option>

<option value="rating">
Top Rated
</option>

</select>

<button
class="button blue"
type="submit">

Apply

</button>

</form>

</div>

<h2 style="text-align:center;margin:30px">
Latest Mobiles
</h2>

<div class="products">

{cards}

</div>

"""

    return page(
        "Home",
        content
    )


# =========================================================
# PRODUCT DETAILS
# =========================================================

@app.route(
    "/product/<int:product_id>"
)
def product_detail(product_id):

    conn = db()

    product = conn.execute(
        """
        SELECT *
        FROM products
        WHERE id=?
        """,
        (product_id,)
    ).fetchone()

    if not product:

        conn.close()

        return "Product Not Found", 404

    reviews = conn.execute("""
        SELECT
            reviews.*,
            users.name
        FROM reviews
        JOIN users
        ON reviews.user_id = users.id
        WHERE reviews.product_id=?
        ORDER BY reviews.id DESC
    """, (
        product_id,
    )).fetchall()

    conn.close()

    if product["stock"] > 0:

        stock = f"""
            <p class="stock">
                ✅ In Stock
                ({product['stock']} available)
            </p>
        """

        cart_button = f"""
            <a
            class="button"
            href="/add/{product['id']}">

            🛒 Add to Cart

            </a>
        """

    else:

        stock = """
            <p class="out-stock">
                ❌ Out of Stock
            </p>
        """

        cart_button = ""

    reviews_html = ""

    for r in reviews:

        reviews_html += f"""

        <div class="review">

            <strong>
                {r['name']}
            </strong>

            <div class="rating">
                {"⭐" * r['rating']}
            </div>

            <p>
                {r['comment']}
            </p>

            <small>
                {r['created_at']}
            </small>

        </div>

        """

    if not reviews_html:

        reviews_html = """
            <p>
                No reviews yet.
            </p>
        """

    review_form = ""

    if session.get("user_id"):

        review_form = f"""

        <h3>
            ⭐ Write a Review
        </h3>

        <form
        method="POST"
        action="/review/{product['id']}">

        <input
        type="hidden"
        name="csrf_token"
        value="{csrf_token()}">

        <select
        name="rating"
        required>

        <option value="">
            Select Rating
        </option>

        <option value="5">
            ⭐⭐⭐⭐⭐
        </option>

        <option value="4">
            ⭐⭐⭐⭐
        </option>

        <option value="3">
            ⭐⭐⭐
        </option>

        <option value="2">
            ⭐⭐
        </option>

        <option value="1">
            ⭐
        </option>

        </select>

        <textarea
        name="comment"
        placeholder="Write your review..."
        required></textarea>

        <button class="button blue">
            Submit Review
        </button>

        </form>

        """

    content = f"""

<div class="product-detail">

<div>

<img
src="{product['image']}"
alt="{product['name']}">

</div>

<div>

<small>
{product['brand']}
</small>

<h1>
{product['name']}
</h1>

<div class="rating">
⭐ {product['rating']} / 5
</div>

<p class="big-price">
₹{product['price']:,}
</p>

{stock}

<p>
{product['description']}
</p>

<br>

{cart_button}

<a
class="button blue"
href="/wishlist/add/{product['id']}">

❤️ Wishlist

</a>

</div>

</div>

<div class="container">

<h2>
⭐ Customer Reviews
</h2>

{reviews_html}

{review_form}

</div>

"""

    return page(
        product["name"],
        content
    )


# =========================================================
# REVIEWS
# =========================================================

@app.route(
    "/review/<int:product_id>",
    methods=["POST"]
)
@login_required
def add_review(product_id):

    if not validate_csrf():

        return "Invalid CSRF token", 400

    try:

        rating = int(
            request.form.get(
                "rating",
                0
            )
        )

    except ValueError:

        rating = 0

    comment = request.form.get(
        "comment",
        ""
    ).strip()

    if rating not in range(1, 6):

        flash(
            "Please select a rating.",
            "warning"
        )

        return redirect(
            url_for(
                "product_detail",
                product_id=product_id
            )
        )

    if not comment:

        flash(
            "Review cannot be empty.",
            "warning"
        )

        return redirect(
            url_for(
                "product_detail",
                product_id=product_id
            )
        )

    conn = db()

    try:

        conn.execute("""
            INSERT INTO reviews
            (
                user_id,
                product_id,
                rating,
                comment
            )
            VALUES(?,?,?,?)
        """, (
            session["user_id"],
            product_id,
            rating,
            comment
        ))

        # Recalculate product rating
        avg = conn.execute("""
            SELECT AVG(rating)
            FROM reviews
            WHERE product_id=?
        """, (
            product_id,
        )).fetchone()[0]

        conn.execute("""
            UPDATE products
            SET rating=?
            WHERE id=?
        """, (
            round(avg, 1),
            product_id
        ))

        conn.commit()

        flash(
            "Review submitted successfully!",
            "success"
        )

    except sqlite3.IntegrityError:

        flash(
            "You have already reviewed this product.",
            "warning"
        )

    conn.close()

    return redirect(
        url_for(
            "product_detail",
            product_id=product_id
        )
    )


# =========================================================
# REGISTER
# =========================================================

@app.route(
    "/register",
    methods=["GET", "POST"]
)
def register():

    if request.method == "POST":

        if not validate_csrf():

            return "Invalid CSRF token", 400

        name = request.form.get(
            "name",
            ""
        ).strip()

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        password = request.form.get(
            "password",
            ""
        )

        if not name or not email:

            flash(
                "Please fill all fields.",
                "warning"
            )

        elif len(password) < 6:

            flash(
                "Password must be at least 6 characters.",
                "warning"
            )

        else:

            conn = db()

            try:

                conn.execute("""
                    INSERT INTO users
                    (
                        name,
                        email,
                        password
                    )
                    VALUES(?,?,?)
                """, (
                    name,
                    email,
                    generate_password_hash(password)
                ))

                conn.commit()

                conn.close()

                flash(
                    "Account created successfully!",
                    "success"
                )

                return redirect(
                    url_for("login")
                )

            except sqlite3.IntegrityError:

                conn.close()

                flash(
                    "Email already registered.",
                    "warning"
                )

    content = f"""

<div class="form-box">

<h2>
👤 Create Account
</h2>

<form method="POST">

<input
type="hidden"
name="csrf_token"
value="{csrf_token()}">

<input
name="name"
placeholder="Full Name"
required
>

<input
name="email"
type="email"
placeholder="Email"
required
>

<input
name="password"
type="password"
placeholder="Password"
required
>

<button>
Register
</button>

</form>

<p>
Already have account?
<a href="/login">
Login
</a>
</p>

</div>

"""

    return page(
        "Register",
        content
    )


# =========================================================
# LOGIN
# =========================================================

@app.route(
    "/login",
    methods=["GET", "POST"]
)
def login():

    if request.method == "POST":

        if not validate_csrf():

            return "Invalid CSRF token", 400

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        password = request.form.get(
            "password",
            ""
        )

        conn = db()

        user = conn.execute(
            """
            SELECT *
            FROM users
            WHERE email=?
            """,
            (email,)
        ).fetchone()

        conn.close()

        if (
            user
            and check_password_hash(
                user["password"],
                password
            )
        ):

            session.clear()

            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            session["is_admin"] = user["is_admin"]

            csrf_token()

            flash(
                "Welcome back!",
                "success"
            )

            return redirect(
                url_for("home")
            )

        flash(
            "Invalid email or password.",
            "warning"
        )

    content = f"""

<div class="form-box">

<h2>
🔐 Login
</h2>

<form method="POST">

<input
type="hidden"
name="csrf_token"
value="{csrf_token()}">

<input
name="email"
type="email"
placeholder="Email"
required
>

<input
name="password"
type="password"
placeholder="Password"
required
>

<button>
Login
</button>

</form>

<p>
Don't have account?
<a href="/register">
Register
</a>
</p>

</div>

"""

    return page(
        "Login",
        content
    )


# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    session.clear()

    flash(
        "Logged out successfully.",
        "success"
    )

    return redirect(
        url_for("home")
    )


# =========================================================
# PROFILE
# =========================================================

@app.route(
    "/profile",
    methods=["GET", "POST"]
)
@login_required
def profile():

    conn = db()

    user = conn.execute(
        """
        SELECT *
        FROM users
        WHERE id=?
        """,
        (session["user_id"],)
    ).fetchone()

    if request.method == "POST":

        if not validate_csrf():

            conn.close()

            return "Invalid CSRF token", 400

        name = request.form.get(
            "name",
            ""
        ).strip()

        if not name:

            flash(
                "Name cannot be empty.",
                "warning"
            )

        else:

            conn.execute("""
                UPDATE users
                SET name=?
                WHERE id=?
            """, (
                name,
                session["user_id"]
            ))

            conn.commit()

            session["user_name"] = name

            flash(
                "Profile updated!",
                "success"
            )

            user = conn.execute(
                """
                SELECT *
                FROM users
                WHERE id=?
                """,
                (session["user_id"],)
            ).fetchone()

    conn.close()

    content = f"""

<div class="form-box">

<h2>
👤 My Profile
</h2>

<form method="POST">

<input
type="hidden"
name="csrf_token"
value="{csrf_token()}">

<label>
Name
</label>

<input
name="name"
value="{user['name']}"
required
>

<label>
Email
</label>

<input
value="{user['email']}"
disabled
>

<button>
Save Changes
</button>

</form>

</div>

"""

    return page(
        "Profile",
        content
    )


# =========================================================
# CART
# =========================================================

@app.route("/add/<int:product_id>")
def add_to_cart(product_id):

    conn = db()

    product = conn.execute(
        """
        SELECT *
        FROM products
        WHERE id=?
        """,
        (product_id,)
    ).fetchone()

    conn.close()

    if not product:

        flash(
            "Product not found.",
            "warning"
        )

        return redirect(
            url_for("home")
        )

    if product["stock"] <= 0:

        flash(
            "Product is out of stock.",
            "warning"
        )

        return redirect(
            url_for(
                "product_detail",
                product_id=product_id
            )
        )

    cart = session.get(
        "cart",
        {}
    )

    pid = str(product_id)

    current = cart.get(
        pid,
        0
    )

    if current >= product["stock"]:

        flash(
            "Maximum available stock reached.",
            "warning"
        )

    else:

        cart[pid] = current + 1

        session["cart"] = cart

        flash(
            "Added to cart 🛒",
            "success"
        )

    return redirect(
        request.referrer
        or url_for("cart")
    )


@app.route("/cart")
def cart():

    cart_data = session.get(
        "cart",
        {}
    )

    conn = db()

    items = []

    total = 0

    for pid, qty in cart_data.items():

        p = conn.execute(
            """
            SELECT *
            FROM products
            WHERE id=?
            """,
            (pid,)
        ).fetchone()

        if p and p["stock"] > 0:

            qty = min(
                qty,
                p["stock"]
            )

            subtotal = (
                p["price"] * qty
            )

            total += subtotal

            items.append(
                (
                    p,
                    qty,
                    subtotal
                )
            )

    conn.close()

    if not items:

        return page(
            "Cart",
            """
            <div class="success">

                <h2>
                    🛒 Cart is Empty
                </h2>

                <a
                class="button blue"
                href="/">

                    Continue Shopping

                </a>

            </div>
            """
        )

    html = """
        <div class="cart">
    """

    for p, qty, subtotal in items:

        html += f"""

        <div class="cart-item">

            <img
            src="{p['image']}"
            alt="{p['name']}">

            <div class="cart-content">

                <h3>
                    {p['name']}
                </h3>

                <p>
                    ₹{p['price']:,}
                </p>

                <div class="qty">

                    <a
                    href="/decrease/{p['id']}">
                    −
                    </a>

                    <strong>
                        {qty}
                    </strong>

                    <a
                    href="/increase/{p['id']}">
                    +
                    </a>

                </div>

                <br>

                <a
                class="button red"
                href="/remove/{p['id']}">

                    Remove

                </a>

            </div>

            <strong>
                ₹{subtotal:,}
            </strong>

        </div>

        """

    html += f"""

        <div class="total">

            <h2>
                Total:
                ₹{total:,}
            </h2>

            <a
            class="button blue"
            href="/checkout">

                Checkout →

            </a>

        </div>

        </div>

    """

    return page(
        "Cart",
        html
    )


@app.route(
    "/increase/<int:product_id>"
)
def increase(product_id):

    cart = session.get(
        "cart",
        {}
    )

    pid = str(product_id)

    conn = db()

    p = conn.execute(
        """
        SELECT stock
        FROM products
        WHERE id=?
        """,
        (product_id,)
    ).fetchone()

    conn.close()

    if not p:

        return redirect(
            url_for("cart")
        )

    current = cart.get(
        pid,
        0
    )

    if current < p["stock"]:

        cart[pid] = current + 1

        session["cart"] = cart

    else:

        flash(
            "No more stock available.",
            "warning"
        )

    return redirect(
        url_for("cart")
    )


@app.route(
    "/decrease/<int:product_id>"
)
def decrease(product_id):

    cart = session.get(
        "cart",
        {}
    )

    pid = str(product_id)

    if pid in cart:

        cart[pid] -= 1

        if cart[pid] <= 0:

            del cart[pid]

    session["cart"] = cart

    return redirect(
        url_for("cart")
    )


@app.route(
    "/remove/<int:product_id>"
)
def remove(product_id):

    cart = session.get(
        "cart",
        {}
    )

    cart.pop(
        str(product_id),
        None
    )

    session["cart"] = cart

    return redirect(
        url_for("cart")
    )


# =========================================================
# WISHLIST
# =========================================================

@app.route("/wishlist")
@login_required
def wishlist():

    conn = db()

    products = conn.execute("""
        SELECT products.*
        FROM wishlist
        JOIN products
        ON wishlist.product_id =
           products.id

        WHERE wishlist.user_id=?

        ORDER BY wishlist.id DESC
    """, (
        session["user_id"],
    )).fetchall()

    conn.close()

    cards = ""

    for p in products:

        cards += f"""

        <div class="card">

            <img
            src="{p['image']}"
            alt="{p['name']}">

            <div class="info">

                <small>
                    {p['brand']}
                </small>

                <h3>
                    {p['name']}
                </h3>

                <h2>
                    ₹{p['price']:,}
                </h2>

                <a
                class="button"
                href="/add/{p['id']}">

                    🛒 Add

                </a>

                <a
                class="button red"
                href="/wishlist/remove/{p['id']}">

                    Remove

                </a>

            </div>

        </div>

        """

    if not cards:

        cards = """

        <div class="success">

            <h2>
                ❤️ Wishlist Empty
            </h2>

            <a
            class="button blue"
            href="/">

                Explore Mobiles

            </a>

        </div>

        """

    return page(
        "Wishlist",
        f"""

        <h2
        style="text-align:center;margin:30px">

            ❤️ My Wishlist

        </h2>

        <div class="products">

            {cards}

        </div>

        """
    )


@app.route(
    "/wishlist/add/<int:product_id>"
)
@login_required
def wishlist_add(product_id):

    conn = db()

    try:

        conn.execute("""
            INSERT INTO wishlist
            (
                user_id,
                product_id
            )
            VALUES(?,?)
        """, (
            session["user_id"],
            product_id
        ))

        conn.commit()

        flash(
            "Added to wishlist ❤️",
            "success"
        )

    except sqlite3.IntegrityError:

        flash(
            "Already in wishlist.",
            "warning"
        )

    conn.close()

    return redirect(
        request.referrer
        or url_for("home")
    )


@app.route(
    "/wishlist/remove/<int:product_id>"
)
@login_required
def wishlist_remove(product_id):

    conn = db()

    conn.execute("""
        DELETE FROM wishlist
        WHERE user_id=?
        AND product_id=?
    """, (
        session["user_id"],
        product_id
    ))

    conn.commit()

    conn.close()

    return redirect(
        url_for("wishlist")
    )


# =========================================================
# CHECKOUT
# =========================================================

@app.route(
    "/checkout",
    methods=["GET", "POST"]
)
@login_required
def checkout():

    cart_data = session.get(
        "cart",
        {}
    )

    if not cart_data:

        return redirect(
            url_for("home")
        )

    conn = db()

    items = []

    total = 0

    for pid, qty in cart_data.items():

        p = conn.execute(
            """
            SELECT *
            FROM products
            WHERE id=?
            """,
            (pid,)
        ).fetchone()

        if not p:

            continue

        if p["stock"] < qty:

            conn.close()

            flash(
                f"Not enough stock for {p['name']}.",
                "warning"
            )

            return redirect(
                url_for("cart")
            )

        total += (
            p["price"] * qty
        )

        items.append(
            (
                p,
                qty
            )
        )

    if request.method == "POST":

        if not validate_csrf():

            conn.close()

            return "Invalid CSRF token", 400

        name = request.form.get(
            "name",
            ""
        ).strip()

        address = request.form.get(
            "address",
            ""
        ).strip()

        payment = request.form.get(
            "payment",
            ""
        )

        if not name or not address:

            conn.close()

            flash(
                "Please fill all details.",
                "warning"
            )

            return redirect(
                url_for("checkout")
            )

        if payment not in [
            "COD",
            "UPI",
            "Card"
        ]:

            conn.close()

            flash(
                "Invalid payment method.",
                "warning"
            )

            return redirect(
                url_for("checkout")
            )

        try:

            # Final stock check
            for p, qty in items:

                latest = conn.execute(
                    """
                    SELECT stock
                    FROM products
                    WHERE id=?
                    """,
                    (p["id"],)
                ).fetchone()

                if (
                    not latest
                    or latest["stock"] < qty
                ):

                    raise ValueError(
                        f"Stock unavailable for {p['name']}"
                    )

            cur = conn.execute("""
                INSERT INTO orders
                (
                    user_id,
                    customer_name,
                    address,
                    total,
                    payment,
                    status
                )
                VALUES(?,?,?,?,?,?)
            """, (
                session["user_id"],
                name,
                address,
                total,
                payment,
                "Pending"
            ))

            order_id = cur.lastrowid

            for p, qty in items:

                conn.execute("""
                    INSERT INTO order_items
                    (
                        order_id,
                        product_id,
                        quantity,
                        price
                    )
                    VALUES(?,?,?,?)
                """, (
                    order_id,
                    p["id"],
                    qty,
                    p["price"]
                ))

                conn.execute("""
                    UPDATE products
                    SET stock =
                        stock - ?
                    WHERE id=?
                """, (
                    qty,
                    p["id"]
                ))

            conn.commit()

            session["cart"] = {}

            conn.close()

            flash(
                "Order placed successfully!",
                "success"
            )

            return redirect(
                url_for(
                    "order_detail",
                    order_id=order_id
                )
            )

        except Exception as e:

            conn.rollback()

            conn.close()

            flash(
                str(e),
                "warning"
            )

            return redirect(
                url_for("checkout")
            )

    conn.close()

    payment_status = (
        "Razorpay configured"
        if razorpay_client
        else "Demo payment mode"
    )

    content = f"""

<div class="form-box">

<h2>
💳 Checkout
</h2>

<h2>
Total:
₹{total:,}
</h2>

<p>
Payment:
<strong>
{payment_status}
</strong>
</p>

<form method="POST">

<input
type="hidden"
name="csrf_token"
value="{csrf_token()}">

<input
name="name"
placeholder="Full Name"
required
>

<textarea
name="address"
placeholder="Delivery Address"
required
></textarea>

<select
name="payment"
required>

<option value="">
Select Payment
</option>

<option value="COD">
Cash on Delivery
</option>

<option value="UPI">
UPI
</option>

<option value="Card">
Card
</option>

</select>

<button>
Place Order 🚀
</button>

</form>

</div>

"""

    return page(
        "Checkout",
        content
    )


# =========================================================
# ORDERS
# =========================================================

@app.route("/orders")
@login_required
def orders():

    conn = db()

    orders_data = conn.execute("""
        SELECT *
        FROM orders
        WHERE user_id=?
        ORDER BY id DESC
    """, (
        session["user_id"],
    )).fetchall()

    conn.close()

    html = """
        <div class="container">

        <h2>
            📦 My Orders
        </h2>
    """

    if not orders_data:

        html += """
            <div class="success">

                <h2>
                    No orders yet.
                </h2>

                <a
                class="button blue"
                href="/">

                    Start Shopping

                </a>

            </div>
        """

    for o in orders_data:

        html += f"""

        <div class="order">

            <h3>
                Order #{o['id']}
            </h3>

            <span class="status">
                {o['status']}
            </span>

            <p>
                Date:
                {o['created_at']}
            </p>

            <p>
                Payment:
                {o['payment']}
            </p>

            <h3>
                ₹{o['total']:,}
            </h3>

            <a
            class="button blue"
            href="/order/{o['id']}">

                Track Order →

            </a>

        </div>

        """

    html += """
        </div>
    """

    return page(
        "My Orders",
        html
    )


# =========================================================
# ORDER DETAIL / TRACKING
# =========================================================

@app.route(
    "/order/<int:order_id>"
)
@login_required
def order_detail(order_id):

    conn = db()

    order = conn.execute("""
        SELECT *
        FROM orders
        WHERE id=?
        AND user_id=?
    """, (
        order_id,
        session["user_id"]
    )).fetchone()

    if not order:

        conn.close()

        return "Order Not Found", 404

    items = conn.execute("""
        SELECT
            order_items.*,
            products.name,
            products.image
        FROM order_items

        JOIN products
        ON order_items.product_id =
           products.id

        WHERE order_items.order_id=?
    """, (
        order_id,
    )).fetchall()

    conn.close()

    statuses = [
        "Pending",
        "Confirmed",
        "Shipped",
        "Delivered"
    ]

    current = order["status"]

    if current == "Cancelled":

        tracking = """
            <p class="out-stock">
                ❌ Order Cancelled
            </p>
        """

    else:

        try:
            current_index = statuses.index(
                current
            )
        except ValueError:
            current_index = 0

        tracking = """
            <div class="track">
        """

        for i, status in enumerate(statuses):

            active = (
                "active"
                if i <= current_index
                else ""
            )

            tracking += f"""

            <div
            class="track-step {active}">

                <div class="track-circle">
                    {i + 1}
                </div>

                <p>
                    {status}
                </p>

            </div>

            """

        tracking += """
            </div>
        """

    item_html = ""

    for item in items:

        subtotal = (
            item["price"]
            * item["quantity"]
        )

        item_html += f"""

        <div class="review">

            <strong>
                {item['name']}
            </strong>

            <p>
                Quantity:
                {item['quantity']}
            </p>

            <p>
                ₹{subtotal:,}
            </p>

        </div>

        """

    content = f"""

<div class="container">

<div class="order">

<h2>
📦 Order #{order['id']}
</h2>

<span class="status">
{order['status']}
</span>

{tracking}

<hr>

<h3>
Items
</h3>

{item_html}

<hr>

<p>
Customer:
{order['customer_name']}
</p>

<p>
Address:
{order['address']}
</p>

<p>
Payment:
{order['payment']}
</p>

<h2>
Total:
₹{order['total']:,}
</h2>

</div>

</div>

"""

    return page(
        "Order Tracking",
        content
    )


# =========================================================
# RAZORPAY PAYMENT ORDER
# =========================================================

@app.route(
    "/payment/create/<int:order_id>",
    methods=["POST"]
)
@login_required
def payment_create(order_id):

    if not razorpay_client:

        return jsonify({
            "success": False,
            "message": "Razorpay is not configured."
        }), 400

    conn = db()

    order = conn.execute("""
        SELECT *
        FROM orders
        WHERE id=?
        AND user_id=?
    """, (
        order_id,
        session["user_id"]
    )).fetchone()

    conn.close()

    if not order:

        return jsonify({
            "success": False,
            "message": "Order not found."
        }), 404

    amount = (
        order["total"] * 100
    )

    razorpay_order = (
        razorpay_client.order.create(
            {
                "amount": amount,
                "currency": "INR",
                "receipt": f"order_{order_id}"
            }
        )
    )

    return jsonify({
        "success": True,
        "order_id": razorpay_order["id"],
        "amount": amount,
        "key": RAZORPAY_KEY_ID
    })


# =========================================================
# ADMIN DASHBOARD
# =========================================================

@app.route("/admin")
@admin_required
def admin():

    conn = db()

    total_products = conn.execute(
        """
        SELECT COUNT(*)
        FROM products
        """
    ).fetchone()[0]

    total_users = conn.execute(
        """
        SELECT COUNT(*)
        FROM users
        """
    ).fetchone()[0]

    total_orders = conn.execute(
        """
        SELECT COUNT(*)
        FROM orders
        """
    ).fetchone()[0]

    revenue = conn.execute(
        """
        SELECT COALESCE(
            SUM(total),
            0
        )
        FROM orders
        WHERE status != 'Cancelled'
        """
    ).fetchone()[0]

    products = conn.execute("""
        SELECT *
        FROM products
        ORDER BY id DESC
    """).fetchall()

    orders_data = conn.execute("""
        SELECT
            orders.*,
            users.email
        FROM orders
        JOIN users
        ON orders.user_id=users.id
        ORDER BY orders.id DESC
    """).fetchall()

    conn.close()

    product_html = ""

    for p in products:

        product_html += f"""

        <div class="order">

            <h3>
                {p['name']}
            </h3>

            <p>
                Brand:
                {p['brand']}
            </p>

            <p>
                Price:
                ₹{p['price']:,}
            </p>

            <p>
                Stock:
                {p['stock']}
            </p>

            <p>
                Rating:
                ⭐ {p['rating']}
            </p>

            <a
            class="button blue"
            href="/admin/edit/{p['id']}">

                Edit

            </a>

            <a
            class="button red"
            href="/admin/delete/{p['id']}">

                Delete

            </a>

        </div>

        """

    orders_html = ""

    for o in orders_data:

        orders_html += f"""

        <div class="order">

            <h3>
                Order #{o['id']}
            </h3>

            <p>
                Customer:
                {o['customer_name']}
            </p>

            <p>
                Email:
                {o['email']}
            </p>

            <p>
                Total:
                ₹{o['total']:,}
            </p>

            <p>
                Current:
                <strong>
                    {o['status']}
                </strong>
            </p>

            <form
            method="POST"
            action="/admin/order/{o['id']}/status">

            <input
            type="hidden"
            name="csrf_token"
            value="{csrf_token()}">

            <select name="status">

                <option
                value="Pending"
                {"selected" if o['status']=="Pending" else ""}>
                    Pending
                </option>

                <option
                value="Confirmed"
                {"selected" if o['status']=="Confirmed" else ""}>
                    Confirmed
                </option>

                <option
                value="Shipped"
                {"selected" if o['status']=="Shipped" else ""}>
                    Shipped
                </option>

                <option
                value="Delivered"
                {"selected" if o['status']=="Delivered" else ""}>
                    Delivered
                </option>

                <option
                value="Cancelled"
                {"selected" if o['status']=="Cancelled" else ""}>
                    Cancelled
                </option>

            </select>

            <button
            class="button blue"
            type="submit">

                Update Status

            </button>

            </form>

        </div>

        """

    content = f"""

<div class="admin">

<h1>
🛠️ Admin Dashboard
</h1>

<div class="dashboard">

<div class="stat">

<h2>
{total_products}
</h2>

<p>
Products
</p>

</div>

<div class="stat">

<h2>
{total_users}
</h2>

<p>
Users
</p>

</div>

<div class="stat">

<h2>
{total_orders}
</h2>

<p>
Orders
</p>

</div>

<div class="stat">

<h2>
₹{revenue:,}
</h2>

<p>
Revenue
</p>

</div>

</div>

<div class="form-box">

<h2>
➕ Add Product
</h2>

<form
method="POST"
action="/admin/add">

<input
type="hidden"
name="csrf_token"
value="{csrf_token()}">

<input
name="name"
placeholder="Mobile Name"
required
>

<input
name="brand"
placeholder="Brand"
required
>

<input
name="price"
type="number"
min="1"
placeholder="Price"
required
>

<input
name="stock"
type="number"
min="0"
value="10"
placeholder="Stock"
required
>

<input
name="rating"
type="number"
min="0"
max="5"
step="0.1"
value="4.5"
placeholder="Rating"
>

<input
name="image"
placeholder="Image URL"
required
>

<textarea
name="description"
placeholder="Product Description"
></textarea>

<button>
Add Product
</button>

</form>

</div>

<h2>
📱 Products
</h2>

{product_html}

<h2>
📦 Customer Orders
</h2>

{orders_html}

</div>

"""

    return page(
        "Admin Dashboard",
        content
    )


# =========================================================
# ADMIN ADD PRODUCT
# =========================================================

@app.route(
    "/admin/add",
    methods=["POST"]
)
@admin_required
def admin_add():

    if not validate_csrf():

        return "Invalid CSRF token", 400

    name = request.form.get(
        "name",
        ""
    ).strip()

    brand = request.form.get(
        "brand",
        ""
    ).strip()

    image = request.form.get(
        "image",
        ""
    ).strip()

    description = request.form.get(
        "description",
        ""
    ).strip()

    try:

        price = int(
            request.form.get(
                "price",
                0
            )
        )

        stock = int(
            request.form.get(
                "stock",
                0
            )
        )

        rating = float(
            request.form.get(
                "rating",
                4.5
            )
        )

    except ValueError:

        flash(
            "Invalid product values.",
            "warning"
        )

        return redirect(
            url_for("admin")
        )

    if (
        not name
        or not brand
        or not image
        or price <= 0
        or stock < 0
    ):

        flash(
            "Please enter valid product details.",
            "warning"
        )

        return redirect(
            url_for("admin")
        )

    rating = max(
        0,
        min(
            5,
            rating
        )
    )

    conn = db()

    conn.execute("""
        INSERT INTO products
        (
            name,
            brand,
            price,
            image,
            description,
            stock,
            rating
        )
        VALUES(?,?,?,?,?,?,?)
    """, (
        name,
        brand,
        price,
        image,
        description,
        stock,
        rating
    ))

    conn.commit()

    conn.close()

    flash(
        "Product added successfully!",
        "success"
    )

    return redirect(
        url_for("admin")
    )


# =========================================================
# ADMIN EDIT PRODUCT
# =========================================================

@app.route(
    "/admin/edit/<int:product_id>",
    methods=["GET", "POST"]
)
@admin_required
def admin_edit(product_id):

    conn = db()

    product = conn.execute(
        """
        SELECT *
        FROM products
        WHERE id=?
        """,
        (product_id,)
    ).fetchone()

    if not product:

        conn.close()

        return "Product Not Found", 404

    if request.method == "POST":

        if not validate_csrf():

            conn.close()

            return "Invalid CSRF token", 400

        name = request.form.get(
            "name",
            ""
        ).strip()

        brand = request.form.get(
            "brand",
            ""
        ).strip()

        image = request.form.get(
            "image",
            ""
        ).strip()

        description = request.form.get(
            "description",
            ""
        ).strip()

        try:

            price = int(
                request.form.get(
                    "price",
                    0
                )
            )

            stock = int(
                request.form.get(
                    "stock",
                    0
                )
            )

            rating = float(
                request.form.get(
                    "rating",
                    4.5
                )
            )

        except ValueError:

            conn.close()

            flash(
                "Invalid values.",
                "warning"
            )

            return redirect(
                url_for(
                    "admin_edit",
                    product_id=product_id
                )
            )

        rating = max(
            0,
            min(
                5,
                rating
            )
        )

        conn.execute("""
            UPDATE products

            SET
                name=?,
                brand=?,
                price=?,
                image=?,
                description=?,
                stock=?,
                rating=?

            WHERE id=?
        """, (
            name,
            brand,
            price,
            image,
            description,
            stock,
            rating,
            product_id
        ))

        conn.commit()

        conn.close()

        flash(
            "Product updated successfully!",
            "success"
        )

        return redirect(
            url_for("admin")
        )

    conn.close()

    content = f"""

<div class="form-box">

<h2>
✏️ Edit Product
</h2>

<form method="POST">

<input
type="hidden"
name="csrf_token"
value="{csrf_token()}">

<input
name="name"
value="{product['name']}"
required
>

<input
name="brand"
value="{product['brand']}"
required
>

<input
name="price"
type="number"
value="{product['price']}"
required
>

<input
name="stock"
type="number"
min="0"
value="{product['stock']}"
required
>

<input
name="rating"
type="number"
min="0"
max="5"
step="0.1"
value="{product['rating']}"
required
>

<input
name="image"
value="{product['image']}"
required
>

<textarea
name="description"
>{product['description']}</textarea>

<button>
Update Product
</button>

</form>

<br>

<a
class="button dark"
href="/admin">

← Back

</a>

</div>

"""

    return page(
        "Edit Product",
        content
    )


# =========================================================
# ADMIN DELETE
# =========================================================

@app.route(
    "/admin/delete/<int:product_id>"
)
@admin_required
def admin_delete(product_id):

    conn = db()

    ordered = conn.execute(
        """
        SELECT id
        FROM order_items
        WHERE product_id=?
        LIMIT 1
        """,
        (product_id,)
    ).fetchone()

    if ordered:

        conn.close()

        flash(
            "Cannot delete a product that exists in an order.",
            "warning"
        )

        return redirect(
            url_for("admin")
        )

    conn.execute(
        """
        DELETE FROM wishlist
        WHERE product_id=?
        """,
        (product_id,)
    )

    conn.execute(
        """
        DELETE FROM reviews
        WHERE product_id=?
        """,
        (product_id,)
    )

    conn.execute(
        """
        DELETE FROM products
        WHERE id=?
        """,
        (product_id,)
    )

    conn.commit()

    conn.close()

    flash(
        "Product deleted.",
        "success"
    )

    return redirect(
        url_for("admin")
    )


# =========================================================
# ADMIN ORDER STATUS
# =========================================================

@app.route(
    "/admin/order/<int:order_id>/status",
    methods=["POST"]
)
@admin_required
def admin_order_status(order_id):

    if not validate_csrf():

        return "Invalid CSRF token", 400

    status = request.form.get(
        "status",
        ""
    )

    allowed = [
        "Pending",
        "Confirmed",
        "Shipped",
        "Delivered",
        "Cancelled"
    ]

    if status not in allowed:

        flash(
            "Invalid order status.",
            "warning"
        )

        return redirect(
            url_for("admin")
        )

    conn = db()

    conn.execute("""
        UPDATE orders
        SET status=?
        WHERE id=?
    """, (
        status,
        order_id
    ))

    conn.commit()

    conn.close()

    flash(
        "Order status updated.",
        "success"
    )

    return redirect(
        url_for("admin")
    )


# =========================================================
# ERROR HANDLERS
# =========================================================

@app.errorhandler(404)
def not_found(error):

    return page(
        "404",
        """
        <div class="success">

            <h1>
                404
            </h1>

            <h2>
                Page Not Found
            </h2>

            <a
            class="button blue"
            href="/">

                Go Home

            </a>

        </div>
        """
    ), 404


# =========================================================
# START SERVER
# =========================================================

if __name__ == "__main__":

    init_db()

    print()
    print("======================================")
    print("📱 MobileHub v3")
    print("======================================")
    print(
        "Website: http://127.0.0.1:5000"
    )
    print(
        "Admin:   admin@gmail.com"
    )
    print(
        "Password: admin123"
    )
    print(
        "Razorpay:",
        "Enabled"
        if razorpay_client
        else "Demo Mode"
    )
    print("======================================")
    print()

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )
