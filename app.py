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
    return render_template("admin.html")

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
            (name,description,price,image)
            VALUES(%s,%s,%s,%s)
            """,
            (
                name,
                description,
                price,
                filename
            )
        )
        db.commit()
        cur.close()
        db.close()
        
        flash("Food Item Added Successfully.", "success")
        return redirect(url_for("add_item"))
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
            (user_id,item_id,item_name,item_price,quantity)
            VALUES(%s,%s,%s,%s,%s)
            """,
            (
                user_id,
                item_id,
                item_name,
                item_price,
                quantity
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

    user_id = session.get("user_id")
    db = get_db()
    cur = db.cursor()
    total_order_price = 0
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

    for cart_item in cart_items:
        item_id = cart_item[2]
        quantity = cart_item[5]
        cur.execute(
            "SELECT * FROM menu_items WHERE item_id=%s",
            (item_id,)
        )
        item = cur.fetchone()

        if item:
            item_name = item[1]
            item_price = float(item[2])
            total_item_price = item_price * quantity
            total_order_price += total_item_price
            cur.execute(
                """
                INSERT INTO orders
                (user_id,item_id,item_name,item_price,quantity,total_price)
                VALUES(%s,%s,%s,%s,%s,%s)
                """,
                (
                    user_id,
                    item_id,
                    item_name,
                    item_price,
                    quantity,
                    total_item_price
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
            total_order_price=total_order_price
        )
    )

# Order Summary
@app.route("/order/<float:total_order_price>")
def order(total_order_price):
    if not session.get("logged_in"):
        flash("Please login first.", "warning")
        return redirect(url_for("login"))

    user_id = session.get("user_id")
    db = get_db()
    cur = db.cursor()

    cur.execute(
        "SELECT * FROM users WHERE user_id=%s",
        (user_id,)
    )
    user = cur.fetchone()
    cur.execute(
        "SELECT * FROM orders WHERE user_id=%s",
        (user_id,)
    )
    order_items = cur.fetchall()
    cur.close()
    db.close()

    return render_template(
        "order.html",
        user=user,
        order_items=order_items,
        total_order_price=total_order_price
    )

# Checkout
@app.route("/checkout", methods=["POST"])
def checkout():
    if not session.get("logged_in"):
        flash("Please login first.", "warning")
        return redirect(url_for("login"))

    user_id = session.get("user_id")
    db = get_db()
    cur = db.cursor()

    current_time = datetime.datetime.now()
    cur.execute(
        "SELECT * FROM orders WHERE user_id=%s",
        (user_id,)
    )
    order_items = cur.fetchall()
    total_order_price = 0

    for item in order_items:
        total_order_price += item[6]

    cur.execute(
        "SELECT address FROM users WHERE user_id=%s",
        (user_id,)
    )

    user = cur.fetchone()
    address = user[0] if user else "Address Not Available"

    cur.execute(
        "DELETE FROM orders WHERE user_id=%s",
        (user_id,)
    )

    db.commit()
    cur.close()
    db.close()

    delivery_time = current_time + datetime.timedelta(minutes=22)
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

if __name__ == "__main__":
    app.run(debug=True)