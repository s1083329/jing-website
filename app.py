from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
import os
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash
from functools import wraps
import boto3
import click
import uuid
from dotenv import load_dotenv

load_dotenv()
R2_ACCESS_KEY = os.getenv("R2_ACCESS_KEY")
R2_SECRET_KEY = os.getenv("R2_SECRET_KEY")
R2_BUCKET = os.getenv("R2_BUCKET")
R2_ENDPOINT = os.getenv("R2_ENDPOINT")
R2_PUBLIC_URL = os.getenv("R2_PUBLIC_URL")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

s3 = boto3.client(
    "s3",
    endpoint_url=R2_ENDPOINT,
    aws_access_key_id=R2_ACCESS_KEY,
    aws_secret_access_key=R2_SECRET_KEY,
) if R2_ACCESS_KEY and R2_SECRET_KEY else None

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return wrapper

app = Flask(__name__)

# session需要secret key
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")
if not app.config["SECRET_KEY"]:
    raise RuntimeError("SECRET_KEY must be configured in .env")
app.config["SESSION_COOKIE_SECURE"] = os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"

# database設定
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///database.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# Gemini API設定
import google.generativeai as genai
from PIL import Image

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.5-flash")

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

@app.cli.command("init-db")
def init_db():
    """Create missing tables; never erase existing records."""
    db.create_all()
    click.echo("Database tables ready.")


@app.cli.command("create-admin")
@click.argument("username")
@click.password_option()
def create_admin(username, password):
    """Create an administrator without storing plaintext passwords."""
    from werkzeug.security import generate_password_hash
    if Admin.query.filter_by(username=username).first():
        raise click.ClickException("Administrator already exists.")
    db.session.add(Admin(username=username, password=generate_password_hash(password)))
    db.session.commit()
    click.echo("Administrator created.")


@app.route("/healthz")
def health():
    # Verify the actual schema, not just that the HTTP process is alive.
    try:
        db.session.execute(db.select(Product.id).limit(1))
        db.session.execute(db.select(Admin.id).limit(1))
    except Exception:
        db.session.rollback()
        return {"status": "unhealthy"}, 503
    return {"status": "ok"}


def generate_description(name, price, image_file, description):

    image = Image.open(image_file)

    prompt = f"""
    商品名稱：{name}
    商品價格：{price}元

    商品背景補充：

    {description}

    如果商品背景補充有內容，
    請以其為主要依據進行潤飾與擴寫。

    如果商品背景補充為空白，
    請根據商品圖片、名稱與價格自行生成完整商品介紹。

    要求：

    1. 使用繁體中文
    2. 長度約80~150字
    3. 不要使用Markdown格式
    4. 不要出現*、#、**等符號
    5. 不要列點
    6. 不要虛構醫療功效
    7. 直接輸出商品介紹內容
    """

    response = model.generate_content([
        prompt,
        image
    ])

    return response.text.strip()

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

        if file:
            filename = str(uuid.uuid4()) + "_" + file.filename

            s3.upload_fileobj(
                file,
                R2_BUCKET,
                filename,
                ExtraArgs={"ContentType": file.content_type}
            )

            image_url = f"{R2_PUBLIC_URL}/{filename}"

        product = Product(
            name=name,
            price=price,
            description=description,
            image=image_url
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
        image_name = product.image.replace(R2_PUBLIC_URL+ "/", "")

        # 先刪資料庫
        db.session.delete(product)
        db.session.commit()

        s3.delete_object(Bucket=R2_BUCKET, Key=image_name)

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

@app.route("/admin/generate-description", methods=["POST"])
@login_required
def generate_product_description():

    name = request.form["name"]
    price = request.form["price"]
    image = request.files["image"]
    description = request.form.get("description", "")

    generated = generate_description(
    name,
    price,
    image,
    description
    )

    return {"description": generated}
    #sleep模擬延遲
    # import time
    # time.sleep(2)
        
    # return {

    #     "description": "這是一段測試商品介紹，確認前端回填功能是否正常。"

    # }

if __name__ == "__main__":
    app.run(debug=True, port=5001)