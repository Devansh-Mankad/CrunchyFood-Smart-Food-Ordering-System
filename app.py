from flask import Flask, render_template, request, session, url_for, redirect, flash
import pymysql
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import datetime
import os
pymysql.install_as_MySQLdb()

app = Flask(__name__)
app.secret_key = "your_secret_key_here"

# MySQL Configuration
app.config["MYSQL_HOST"] = "localhost"
app.config["MYSQL_USER"] = "root"
app.config["MYSQL_PASSWORD"] = ""
app.config["MYSQL_DB"] = "crunchy_food"

UPLOAD_FOLDER = "static/images/uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


# Database Connection
def get_db():
    return pymysql.connect(
        host=app.config["MYSQL_HOST"],
        user=app.config["MYSQL_USER"],
        password=app.config["MYSQL_PASSWORD"],
        database=app.config["MYSQL_DB"]
    )


# Home Page
@app.route("/")
def index():
    return render_template("index.html")

# Register
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email").strip()
        password = request.form.get("password")
        user_type = request.form.get("user")
        address = request.form.get("address").strip()

        # Validation
        if not email or not password or not address:
            flash("Please fill all fields.", "warning")
            return redirect(url_for("register"))

        if user_type not in ["user", "admin"]:
            flash("Invalid user type.", "danger")
            return redirect(url_for("register"))

        db = get_db()
        cur = db.cursor()
        
        # Check Existing User Record
        cur.execute("SELECT * FROM users WHERE email=%s",(email,))
        existing_user = cur.fetchone()

        if existing_user:
            flash("Email already registered.", "warning")
            cur.close()
            db.close()
            return redirect(url_for("register"))

        # Encrypt Password
        hashed_password = generate_password_hash(password)
        cur.execute(
            """
            INSERT INTO users
            (email,password,user_type,address)
            VALUES(%s,%s,%s,%s)
            """,
            (
                email,
                hashed_password,
                user_type,
                address
            )
        )

        db.commit()
        cur.execute("SELECT user_id FROM users WHERE email=%s",(email,))

        user_id = int(cur.fetchone()[0])
        session["user_id"] = user_id
        cur.close()
        db.close()
        flash("Registration Successful. Please Login.", "success")
        return redirect(url_for("login"))
    return render_template("register.html")

# Login
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email").strip()
        password = request.form.get("password").strip()

        if not email or not password:
            flash("Please enter Email and Password.", "warning")
            return redirect(url_for("login"))

        db = get_db()
        cur = db.cursor()
        cur.execute(
            "SELECT * FROM users WHERE email=%s",
            (email,)
        )
        user = cur.fetchone()
        cur.close()
        db.close()

        if user and check_password_hash(user[2], password):
            session["logged_in"] = True
            session["user_id"] = user[0]
            session["user_type"] = user[3]
            flash("Welcome back!", "success")

            if user[3] == "admin":
                return redirect(url_for("admin"))
            return redirect(url_for("index"))

        flash("Invalid Email or Password.", "danger")
    return render_template("login.html")

# Logout
@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully.", "success")
    return redirect(url_for("index"))

# Admin Home
@app.route("/admin")
def admin():
    if not session.get("logged_in"):
        flash("Please login first.", "warning")
        return redirect(url_for("login"))

    if session.get("user_type") != "admin":
        flash("Access Denied.", "danger")
        return redirect(url_for("index"))

    db = get_db()
    cur = db.cursor()

    # Total Revenue
    cur.execute("SELECT IFNULL(SUM(total_price),0) FROM orders")
    revenue = cur.fetchone()[0]
    # Total Orders
    cur.execute("SELECT COUNT(*) FROM orders")
    total_orders = cur.fetchone()[0]
    # Total Users
    cur.execute("SELECT COUNT(*) FROM users WHERE user_type='user'")
    users = cur.fetchone()[0]
    # Total Menu Items
    cur.execute("SELECT COUNT(*) FROM menu_items")
    menu_items = cur.fetchone()[0]
    # Pending Orders
    cur.execute("SELECT COUNT(*) FROM orders WHERE status='Pending'")
    pending = cur.fetchone()[0]
    # Delivered Orders
    cur.execute("SELECT COUNT(*) FROM orders WHERE status='Delivered'")
    delivered = cur.fetchone()[0]

    # Top Selling Food Items
    cur.execute("""
        SELECT
            item_name,
            SUM(quantity) AS total_quantity,
            SUM(total_price) AS revenue
        FROM order_items
        GROUP BY item_name
        ORDER BY total_quantity DESC
        LIMIT 5
    """)
    top_foods = cur.fetchall()

    # Recent Orders
    cur.execute("""
        SELECT
            order_id,
            user_id,
            total_price,
            status,
            payment_method,
            order_date
        FROM orders
        ORDER BY order_date DESC
        LIMIT 10
    """)
    recent_orders = cur.fetchall()

    cur.close()
    db.close()

    return render_template(
        "admin.html",
        revenue=revenue,
        total_orders=total_orders,
        users=users,
        menu_items=menu_items,
        pending=pending,
        delivered=delivered,
        top_foods=top_foods,
        recent_orders=recent_orders
    )

# Admin Menu
@app.route("/admin_menu", methods=["GET", "POST"])
def admin_menu():
    if not session.get("logged_in"):
        flash("Please login first.", "warning")
        return redirect(url_for("login"))

    if session.get("user_type") != "admin":
        flash("Access Denied.", "danger")
        return redirect(url_for("index"))

    if request.method == "POST":
        name = request.form.get("name").strip()
        price = request.form.get("price")
        description = request.form.get("description").strip()
        image = request.files.get("image")

        if image is None or image.filename == "":
            flash("Please select an image.", "warning")
            return redirect(url_for("admin_menu"))

        filename = secure_filename(image.filename)
        image.save(os.path.join(app.config["UPLOAD_FOLDER"],filename))
        db = get_db()
        cur = db.cursor()

        cur.execute(
            """
            INSERT INTO menu_items
            (item_name,price,description,image)
            VALUES(%s,%s,%s,%s)
            """,
            (
                name,
                price,
                description,
                filename
            )
        )
        db.commit()
        cur.close()
        db.close()
        
        flash("Food Item Added Successfully.", "success")
        return redirect(url_for("admin_menu"))
    return render_template("add_item.html")

# Service
@app.route("/service")
def service():
    return render_template("service.html")

# Menu
@app.route("/menu")
def menu():
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT * FROM menu_items")
    menu_items_data = cur.fetchall()

    cur.close()
    db.close()
    menu_items = []

    for item in menu_items_data:
        menu_items.append({
            "id": item[0],
            "name": item[1],
            "description": item[3],
            "price": item[2],
            "image": item[4]

        })
    return render_template(
        "menu.html",
        menu_items=menu_items
    )

# Add Cart
@app.route("/add_cart", methods=["POST"])
def add_cart():
    if not session.get("logged_in"):
        flash("Please login first.", "warning")
        return redirect(url_for("login"))

    item_id = request.form.get("item_id")
    quantity = int(request.form.get("quantity"))
    user_id = session.get("user_id")
    db = get_db()
    cur = db.cursor()
    cur.execute(
        "SELECT * FROM menu_items WHERE item_id=%s",
        (item_id,)
    )
    item = cur.fetchone()
    if item:
        item_name = item[1]
        item_price = item[2]
        cur.execute(
            """
            INSERT INTO cart
            (user_id,item_id,item_name,item_price,quantity,total_price)
            VALUES(%s,%s,%s,%s,%s,%s)
            """,
            (
                user_id,
                item_id,
                item_name,
                item_price,
                quantity,
                item_price*quantity
            )
        )
        db.commit()
        flash("Item Added To Cart.", "success")
    cur.close()
    db.close()
    return redirect(url_for("menu"))

# Cart
@app.route("/cart")
def cart():
    if not session.get("logged_in"):
        flash("Please login first.", "warning")
        return redirect(url_for("login"))

    user_id = session.get("user_id")
    db = get_db()
    cur = db.cursor()
    cur.execute(
        "SELECT * FROM cart WHERE user_id=%s",
        (user_id,)
    )
    cart_items_data = cur.fetchall()
    cur.close()
    db.close()

    cart_items = []
    for item in cart_items_data:
        cart_items.append({
            "item_id": item[2],
            "item_name": item[3],
            "item_price": item[4],
            "quantity": item[5]

        })
    return render_template(
        "cart.html",
        cart=cart_items
    )

# Place Order
@app.route("/place_order", methods=["POST"])
def place_order():
    if not session.get("logged_in"):
        flash("Please login first.", "warning")
        return redirect(url_for("login"))

    user_id = session["user_id"]
    db = get_db()
    cur = db.cursor()

    cur.execute(
        "SELECT * FROM cart WHERE user_id=%s",
        (user_id,)
    )
    cart_items = cur.fetchall()

    if not cart_items:
        flash("Your cart is empty.", "warning")
        cur.close()
        db.close()
        return redirect(url_for("cart"))
    
    total_order_price = 0
    for item in cart_items:
        total_order_price += float(item[6])

    cur.execute(
        """
        INSERT INTO orders
        (user_id, total_price)
        VALUES (%s,%s)
        """,
        (user_id, total_order_price)
    )

    order_id = cur.lastrowid
    for item in cart_items:
        cur.execute(
            """
            INSERT INTO order_items
            (order_id,item_id,item_name,item_price,quantity,total_price)
            VALUES(%s,%s,%s,%s,%s,%s)
            """,
            (
                order_id,
                item[2],
                item[3],
                item[4],
                item[5],
                item[6]
            )
        )

    cur.execute(
        "DELETE FROM cart WHERE user_id=%s",
        (user_id,)
    )
    db.commit()
    cur.close()
    db.close()

    return redirect(
        url_for(
            "order",
            order_id=order_id,
        )
    )

# Order History
@app.route("/order_history")
def order_history():
    if not session.get("logged_in"):
        flash("Please login first.", "warning")
        return redirect(url_for("login"))

    user_id = session["user_id"]
    db = get_db()
    cur = db.cursor()

    cur.execute(
        """
        SELECT
            order_id,
            total_price,
            status,
            payment_method,
            order_date
        FROM orders
        WHERE user_id=%s
        ORDER BY order_date DESC
        """,
        (user_id,)
    )

    orders = cur.fetchall()
    cur.close()
    db.close()

    return render_template(
        "order_history.html",
        orders=orders
    )

# Order Summary
@app.route("/order/<int:order_id>")
def order(order_id):
    if not session.get("logged_in"):
        flash("Please login first.", "warning")
        return redirect(url_for("login"))

    user_id = session["user_id"]
    db = get_db()
    cur = db.cursor()

    cur.execute(
        "SELECT * FROM users WHERE user_id=%s",
        (user_id,)
    )
    user = cur.fetchone()

    cur.execute(
        "SELECT * FROM orders WHERE order_id=%s",
        (order_id,)
    )
    order = cur.fetchone()
    cur.execute(
        """
        SELECT *
        FROM order_items
        WHERE order_id=%s
        """,
        (order_id,)
    )
    order_items = cur.fetchall()
    cur.close()
    db.close()

    return render_template(
        "order.html",
        user=user,
        order_items=order_items,
        total_order_price=order[2]
    )

# Checkout
@app.route("/checkout", methods=["POST"])
def checkout():
    if not session.get("logged_in"):
        flash("Please login first.", "warning")
        return redirect(url_for("login"))

    user_id = session["user_id"]

    db = get_db()
    cur = db.cursor()

    # Get latest order
    cur.execute("""
        SELECT *
        FROM orders
        WHERE user_id=%s
        ORDER BY order_id DESC
        LIMIT 1
    """, (user_id,))

    order = cur.fetchone()

    if not order:
        flash("No order found.", "warning")
        cur.close()
        db.close()
        return redirect(url_for("menu"))

    order_id = order[0]
    total_order_price = order[2]

    # Get all ordered items
    cur.execute("""
        SELECT *
        FROM order_items
        WHERE order_id=%s
    """, (order_id,))

    order_items = cur.fetchall()

    # Get user's address
    cur.execute("""
        SELECT address
        FROM users
        WHERE user_id=%s
    """, (user_id,))

    user = cur.fetchone()
    address = user[0] if user else "Address Not Available"

    cur.close()
    db.close()

    delivery_time = datetime.datetime.now() + datetime.timedelta(minutes=22)

    return render_template(
        "my_order.html",
        total_order_price=total_order_price,
        delivery_time=delivery_time,
        order_items=order_items,
        address=address
    )

# Edit Menu
@app.route("/edit_menu", methods=["GET", "POST"])
def edit_menu():
    if not session.get("logged_in"):
        flash("Please login first.", "warning")
        return redirect(url_for("login"))

    if session.get("user_type") != "admin":
        flash("Access Denied.", "danger")
        return redirect(url_for("index"))

    if request.method == "POST":
        item_name = request.form.get("name")
        new_price = request.form.get("price")
        new_description = request.form.get("description")

        db = get_db()
        cur = db.cursor()
        cur.execute(
            """
            UPDATE menu_items
            SET
            price=%s,
            description=%s
            WHERE name=%s
            """,
            (
                new_price,
                new_description,
                item_name
            )
        )
        db.commit()
        cur.close()
        db.close()

        flash("Menu Updated Successfully.", "success")
        return redirect(url_for("edit_menu"))
    return render_template("edit_menu.html")

# User Profile
@app.route("/profile")
def profile():
    if not session.get("logged_in"):
        flash("Please login first.", "warning")
        return redirect(url_for("login"))
    return render_template("myprofile.html")

# Admin Profile
@app.route("/admin_profile")
def admin_profile():
    if not session.get("logged_in"):
        flash("Please login first.", "warning")
        return redirect(url_for("login"))

    if session.get("user_type") != "admin":
        flash("Access Denied.", "danger")
        return redirect(url_for("index"))
    return render_template("admin_profile.html")

@app.route("/order_status")
def admin_orders():
    if not session.get("logged_in") or session.get("user_type") != "admin":
        flash("Unauthorized Access.", "danger")
        return redirect(url_for("login"))

    db = get_db()
    cur = db.cursor()
    cur.execute("""
        SELECT
            o.order_id,
            u.email,
            o.total_price,
            o.status,
            o.payment_method,
            o.order_date
        FROM orders o
        JOIN users u
            ON o.user_id = u.user_id
        ORDER BY o.order_date DESC
    """)

    orders = cur.fetchall()
    cur.close()
    db.close()

    return render_template(
        "admin_orders.html",
        orders=orders
    )

@app.route("/update_order_status/<int:order_id>", methods=["POST"])
def update_order_status(order_id):
    if not session.get("logged_in") or session.get("user_type") != "admin":
        flash("Unauthorized Access.", "danger")
        return redirect(url_for("login"))

    status = request.form.get("status")
    db = get_db()
    cur = db.cursor()

    cur.execute("""
        UPDATE orders
        SET status=%s
        WHERE order_id=%s
    """, (status, order_id))

    db.commit()
    cur.close()
    db.close()

    flash("Order status updated successfully.", "success")
    return redirect(url_for("admin_orders"))

if __name__ == "__main__":
    app.run(debug=True)