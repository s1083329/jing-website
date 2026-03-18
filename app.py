from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
import os
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash
from functools import wraps

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return wrapper

app = Flask(__name__)

# session需要secret key
app.config["SECRET_KEY"] =  "your_secret_key"

# database設定
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///database.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# 上傳圖片的資料夾
UPLOAD_FOLDER = "static/img"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

db = SQLAlchemy(app)

# Admin資料表
class Admin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(200))

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200))
    price = db.Column(db.Integer)
    description = db.Column(db.Text)
    image = db.Column(db.String(200))

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/products")
def products():
    products = Product.query.all()

    return render_template("products.html", products=products)

@app.route("/certificates")
def certificates():
    return render_template("certificates.html")

@app.route("/contact")
def contact():
    return render_template("contact.html")

# admin login page
@app.route("/admin", methods=["GET", "POST"])
def admin_login():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        admin = Admin.query.filter_by(username=username).first()

        if admin and check_password_hash(admin.password, password):
            session["admin_logged_in"] = True
            return redirect(url_for("admin_products"))

        else:
            flash("帳號或密碼錯誤")  
            return redirect(url_for("admin_login"))
        

    return render_template("admin_login.html")

@app.route("/admin/logout")
def admin_logout():

    session.pop("admin_logged_in", None)

    return redirect(url_for("admin_login"))

# # dashboard
# @app.route("/admin/dashboard")
#@login_required
# def admin_dashboard():

#     return render_template("admin_dashboard.html")

@app.route("/admin/products")
@login_required
def admin_products():

    products = Product.query.all()

    return render_template("admin_products.html", products=products)

@app.route("/admin/products/add", methods=["GET", "POST"])
@login_required
def add_product():

    if request.method == "POST":

        name = request.form["name"]
        price = request.form["price"]
        description = request.form["description"]

        file = request.files["image"]

        filename = secure_filename(file.filename)

        file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

        product = Product(
            name=name,
            price=price,
            description=description,
            image=filename
        )

        db.session.add(product)
        db.session.commit()

        return redirect(url_for("admin_products"))

    return render_template("add_product.html")

@app.route("/admin/delete/<int:id>")
@login_required
def delete_product(id):

    product = Product.query.get(id)

    if product:
        image_name = product.image

        # 先刪資料庫
        db.session.delete(product)
        db.session.commit()

        # 檢查是否還有其他產品用這張圖
        still_used = Product.query.filter_by(image=image_name).first()

        if not still_used:
            import os
            image_path = os.path.join("static/img", image_name)

            if os.path.exists(image_path):
                os.remove(image_path)

    return redirect(url_for("admin_products"))

@app.route("/admin/products/edit/<int:id>", methods=["GET","POST"])
@login_required
def edit_product(id):

    product = Product.query.get_or_404(id)

    if request.method == "POST":

        product.name = request.form["name"]
        product.price = request.form["price"]
        product.description = request.form["description"]
        # product.image = request.form["image"]

        db.session.commit()

        return redirect(url_for("admin_products"))

    return render_template("edit_product.html", product=product)

if __name__ == "__main__":
    app.run(debug=True)