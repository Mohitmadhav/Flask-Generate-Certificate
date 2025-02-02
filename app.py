import pdfkit
import os
from flask.globals import current_app
from oauthlib.oauth2 import WebApplicationClient
from flask import Flask, render_template, redirect, request, flash, url_for, jsonify, abort, send_from_directory, make_response
from flask_login import LoginManager, current_user, login_user, logout_user, login_required
from flask_sqlalchemy import SQLAlchemy
# import requests_oauthlib
# from requests_oauthlib.compliance_fixes import facebook_compliance_fix
from passlib.hash import sha256_crypt
from password_generator import PasswordGenerator
from flask_mail import Mail, Message
from datetime import datetime
import json as json_lib
import requests
import random
import string
import pytz
import re
import razorpay
import hmac
import hashlib
from itsdangerous import SignatureExpired, URLSafeTimedSerializer
import qrcode
from flask_login import UserMixin
from functools import wraps
from decouple import config
import boto3
import io
import csv


regex = '^[a-z0-9]+[\._]?[a-z0-9]+[@]\w+[.]\w{2,3}$'


def check(email):
    return re.search(regex, email)


# end

app = Flask(__name__)
app.config.from_object(config("app_settings"))
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = config('email_username')
app.config['MAIL_PASSWORD'] = config('email_password')
app.config['MAIL_DEBUG'] = False

db = SQLAlchemy(app)
mail = Mail(app)

os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

# serializer for registration
s = URLSafeTimedSerializer(app.secret_key)


login_manager = LoginManager(app)
login_manager.login_view = 'loginPage'
login_manager.login_message_category = 'info'

RAZORPAY_KEY_ID = config("razorpay_key_id")
RAZORPAY_KEY_SECRET = config("razorpay_key_secret")

# Google Login Credentials
# FB_AUTHORIZATION_BASE_URL = "https://www.facebook.com/dialog/oauth"
# FB_TOKEN_URL = config('facebook_token_url')
# FB_CLIENT_ID = config("facebook_app_id")
# FB_CLIENT_SECRET = config("facebook_secret")
GOOGLE_CLIENT_ID = config("google_client_id")
GOOGLE_CLIENT_SECRET = config("google_client_secret")
GOOGLE_DISCOVERY_URL = (
    "https://accounts.google.com/.well-known/openid-configuration"
)

IST = pytz.timezone('Asia/Kolkata')
x = datetime.now(IST)
time = x.strftime("%c")
host = config('host_status', default=False, cast=bool)
ipc = config("demo_ip")
favTitle = config("favTitle")
site_url = config("site_url")


@login_manager.user_loader
def load_user(user_id):
    return Users.query.get(user_id)


class Users(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(50), nullable=False)
    password = db.Column(db.String(500), nullable=False)
    profile_image = db.Column(db.String(500), nullable=True)
    status = db.Column(db.Integer, nullable=False)
    is_staff = db.Column(db.Boolean, default=False, nullable=False)
    last_login = db.Column(db.String(50), nullable=False)
    group = db.relationship('Group', cascade="all,delete", backref='group')


class Token(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), nullable=False)
    token_id = db.Column(db.String(200), nullable=False)
    # U->Used, E->Expired, A->Available
    status = db.Column(db.String(50), nullable=False, default='A')


class Group(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    subname = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(50), nullable=False)
    phone = db.Column(db.String(50), nullable=False)
    date = db.Column(db.String(50), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    certificates = db.relationship(
        'Certificate', cascade="all,delete", backref='certificates')


class Certificate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.String(50), nullable=False)
    name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(50), nullable=False)
    coursename = db.Column(db.String(500), nullable=False)
    last_update = db.Column(db.String(50), nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    qrcode = db.relationship('QRCode', cascade="all,delete", backref='qrcode')


class QRCode(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    certificate_num = db.Column(db.String(50), nullable=False)
    link = db.Column(db.String(200), nullable=False)
    qr_code = db.Column(db.String(100), nullable=True)
    certificate_id = db.Column(db.Integer, db.ForeignKey('certificate.id'))


class Newsletter(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(50), nullable=False)
    ip = db.Column(db.String(200), nullable=False)
    date = db.Column(db.String(50), nullable=False)


class Contact(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(50), nullable=False)
    phone = db.Column(db.String(50), nullable=False)
    message = db.Column(db.String(500), nullable=False)
    ip = db.Column(db.String(200), nullable=False)
    date = db.Column(db.String(50), nullable=False)


class Feedback(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(50), nullable=False)
    phone = db.Column(db.String(50), nullable=False)
    rating = db.Column(db.String(10), nullable=False)
    message = db.Column(db.String(500), nullable=False)
    ip = db.Column(db.String(200), nullable=False)
    date = db.Column(db.String(50), nullable=False)


class Transactions(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(127), nullable=False)
    email = db.Column(db.String(127), nullable=False)
    phone = db.Column(db.String(15), nullable=False)
    order_id = db.Column(db.String(50), nullable=False)
    amount = db.Column(db.String(50), nullable=False)
    currency = db.Column(db.String(50), nullable=False)
    payment_id = db.Column(db.String(127), nullable=False)
    response_msg = db.Column(db.Text(), nullable=False)
    status = db.Column(db.String(25), nullable=False)
    error_code = db.Column(db.String(127), nullable=True)
    error_source = db.Column(db.String(127), nullable=True)
    txn_timestamp = db.Column(
        db.DateTime(), default=datetime.now(IST), nullable=False)


# Admin Required Decorator

def admin_required(func):
    @wraps(func)
    def decorated_view(*args, **kwargs):
        if not current_user.is_staff:
            flash('You are not authorized to access this page.', 'danger')
            return render_template('block.html', favTitle=favTitle, user=current_user)
        return func(*args, **kwargs)
    return decorated_view


def send_email_now(email, subject, from_email, from_email_name, template_name, **kwargs):
    msg = Message(
        sender=(from_email_name, from_email),
        recipients=[email],
        subject=subject
    )
    msg.html = render_template(template_name, **kwargs)
    try:
        mail.send(msg)
        return True
    except Exception:
        return False


def upload_image(file, bucket="cgv", **kwargs):
    """
    Function to upload an image to an S3 bucket
    """
    s3_client = boto3.client('s3', aws_access_key_id=config(
        "S3_KEY"), aws_secret_access_key=config("S3_SECRET_ACCESS_KEY"))
    response = s3_client.put_object(
        Bucket=bucket,
        Key=f'qr_codes/{kwargs["number"]}.png',
        Body=file,
        ContentType='image/png',
    )

    return response


def upload_doc(file, bucket="cgv", **kwargs):
    """
    Function to upload a raw file to an S3 bucket
    """
    s3_client = boto3.client('s3', aws_access_key_id=config(
        "S3_KEY"), aws_secret_access_key=config("S3_SECRET_ACCESS_KEY"))
    if kwargs["localhost"]:
        with open(file, "rb") as f:
            response = s3_client.upload_fileobj(
                f, bucket, f'certificates/{kwargs["number"]}.pdf')
    else:
        response = s3_client.put_object(
            Bucket=bucket,
            Key=f'certificates/{kwargs["number"]}.pdf',
            Body=file,
        )

    return response


# For Gravatar
def avatar(email, size):
    digest = hashlib.md5(email.lower().encode('utf-8')).hexdigest()
    return f'https://www.gravatar.com/avatar/{digest}?d=identicon&s={size}'


def send_password_reset_email(name, email):
    token = s.dumps(email, salt='cgv-password-reset')
    new_token = Token(email=email, token_id=token, status='A')
    db.session.add(new_token)
    db.session.commit()
    if app.debug:
        link = f"http://127.0.0.1:5000/reset-password/{token}"
    else:
        link = f"{config('site_url')}/reset-password/{token}"
    print(link)
    subject = "Password Reset Link | CGV"
    return send_email_now(email, subject, 'password-bot@cgv.in.net', 'Password Bot CGV', 'emails/reset-password.html', name=name, link=link)


@app.route('/forgot', methods=['GET', 'POST'])
def forgot_password_page():
    if (request.method == 'POST'):
        email = request.form.get('email')
        post = Users.query.filter_by(email=email).first()
        name = post.name
        if (post != None):
            if (post.email == config("admin_email")):
                flash("You can't reset password of administrator!", "danger")
            else:
                if send_password_reset_email(name, email):
                    flash(
                        f"We've sent a password reset link on {email}", "success")
                else:
                    flash("Error while sending password reset email!", "danger")
        elif (post == None):
            flash("We didn't find your account!", "danger")
            return render_template('forgot-password.html', favTitle=favTitle, verified=False)

    return render_template('forgot-password.html', favTitle=favTitle, verified=False)


@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('dashboard_page'))
    if request.method == 'POST':
        password = request.form.get('password')
        password = sha256_crypt.hash(password)
        email = s.loads(token, salt="cgv-password-reset")
        user = Users.query.filter_by(email=email).first()
        user.password = password
        db_token = Token.query.filter_by(token_id=token).first()
        db_token.status = 'U'
        db.session.commit()
        flash('Password changed successfully.', 'success')
        return redirect(url_for('loginPage'))
    try:
        email = s.loads(token, salt="cgv-password-reset", max_age=1800)
    except SignatureExpired:
        db_token = Token.query.filter_by(token_id=token).first()
        db_token.status = 'E'
        db.session.commit()
        flash("Sorry, link has been expired.", "danger")
        return render_template('forgot-password.html', favTitle=favTitle, verified=False)
    except Exception:
        flash("Sorry, Invalid token.", "danger")
        return render_template('forgot-password.html', favTitle=favTitle, verified=False)
    user = Users.query.filter_by(email=email).first()
    first_name = user.name.split(" ")[0]
    db_token = Token.query.filter_by(token_id=token).first()
    if db_token.status == 'U':
        flash("Sorry, link has been already used.", "danger")
        return render_template("forgot-password.html", favTitle=favTitle, name=first_name, token=token, verified=False)
    elif db_token.status == 'E':
        flash("Sorry, link has been expired.", "danger")
        return render_template("forgot-password.html", favTitle=favTitle, name=first_name, token=token, verified=False)
    return render_template("forgot-password.html", favTitle=favTitle, name=first_name, token=token, verified=True)


@app.route('/')
def home_page():
    try:
        response = requests.get(config("contributors_api"))
        team = response.json()
    except Exception:
        team = {}
    return render_template('index.html', favTitle=favTitle, team=team, user=current_user)


@app.route('/contact', methods=['GET', 'POST'])
def contact_page():
    if (request.method == 'POST'):
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        message = request.form.get('editordata')
        if (host == True):
            try:
                ip_address = request.environ['HTTP_X_FORWARDED_FOR']
            except KeyError:
                ip_address = request.remote_addr
            except Exception:
                ip_address = ipc
        else:
            ip_address = ipc
        # name validation it must be greater than than 2 letters and less than 40 letters
        if len(name) >= 2 and len(name) <= 40:
            pass
        else:
            flash("Please Enter Your Name Correctly!! ", "danger")
            return redirect("/#footer")
        # email validation
        if check(email):
            pass
        else:
            flash(
                "Email is not Correct Please Check it and Try It once again!!", "danger")
            return redirect('/#footer')
        # number validation
        if len(phone) >= 8 and len(phone) <= 13:
            pass
        else:
            flash(
                "Phone Number is not Correct Please Check it and Try It once again!!", "danger")
            return redirect('/#footer')
        entry = Contact(name=name, phone=phone, message=message, ip=ip_address, date=time,
                        email=email)
        db.session.add(entry)
        db.session.commit()
        flash("Thank you for contacting us – we will get back to you soon!", "success")
    return redirect('/#footer')


@app.route('/feedback', methods=['GET', 'POST'])
def feedback_page():
    if (request.method == 'POST'):
        data = json_lib.loads(request.data)
        name = data["name"]
        email = data["email"]
        phone = data["phone"]
        rating = data["rating"]
        message = data["message"]
        if (host == True):
            try:
                ip_address = request.environ['HTTP_X_FORWARDED_FOR']
            except KeyError:
                ip_address = request.remote_addr
            except Exception:
                ip_address = ipc
        else:
            ip_address = ipc
        try:
            entry = Feedback(name=name, phone=phone, rating=rating,
                             message=message, ip=ip_address, date=time, email=email)
            db.session.add(entry)
            db.session.commit()
            return jsonify(feedback_success="Thank you for feedback – we will get back to you soon!", status=200)
        except Exception:
            return jsonify(feedback_error="Sorry, we could not record your feedback.", status=400)
    return redirect('/#footer')


@app.route('/newsletter', methods=['GET', 'POST'])
def newsletter_page():
    if (request.method == 'POST'):
        email = request.form.get('email')
        if (host == True):
            try:
                ip_address = request.environ['HTTP_X_FORWARDED_FOR']
            except KeyError:
                ip_address = request.remote_addr
            except Exception:
                ip_address = ipc
        else:
            ip_address = ipc
        post = Newsletter.query.filter_by(email=email).first()
        if (post == None):
            entry = Newsletter(ip=ip_address, date=time, email=email)
            db.session.add(entry)
            db.session.commit()
            flash("Thank you for subscribing!", "success")
        else:
            flash("You have already subscribed!", "danger")
    return redirect('/#footer')


@app.route("/certificate/verify", methods=['GET', 'POST'])
def certificate_verify():
    if (host == True):
        try:
            ip_address = request.environ['HTTP_X_FORWARDED_FOR']
        except KeyError:
            ip_address = request.remote_addr
        except Exception:
            ip_address = ipc
    else:
        ip_address = ipc
    if (request.method == 'POST'):
        certificate_no = request.form.get('certificateno')
        postc = Certificate.query.filter_by(number=certificate_no).first()
        if (postc != None):
            posto = Group.query.filter_by(id=postc.group_id).first()
            flash("Certificate Number Valid!", "success")
            return render_template('Redesign-verify2.html', postc=postc, posto=posto, favTitle=favTitle, ip=ip_address)
        elif (postc == None):
            flash("No details found. Contact your organization!", "danger")
    return render_template('Redesign-verify2.html', favTitle=favTitle, ip=ip_address,user=current_user)


@app.route("/certificate/generate", methods=['GET', 'POST'])
def certificate_generate():
    if (host == True):
        try:
            ip_address = request.environ['HTTP_X_FORWARDED_FOR']
        except KeyError:
            ip_address = request.remote_addr
        except Exception:
            ip_address = ipc
    else:
        ip_address = ipc
    if (request.method == 'POST'):
        certificateno = request.form.get('certificateno')
        postc = Certificate.query.filter_by(number=certificateno).first()
        if (postc != None):
            posto = Group.query.filter_by(id=postc.group_id).first()
            qr_code = QRCode.query.filter_by(
                certificate_num=certificateno).first()
            img_url = qr_code.qr_code
            rendered_temp = render_template('certificate.html', postc=postc, posto=posto, qr_code=img_url, favTitle=favTitle, site_url=site_url, number=certificateno, pdf=True)
            if not app.debug:
                configr = pdfkit.configuration(wkhtmltopdf='/app/bin/wkhtmltopdf')
                file = pdfkit.from_string(
                    rendered_temp, False, css='static/css/certificate.css', configuration=configr)
                upload_doc(file, number=certificateno, localhost=False)
                download_url = f"https://cgv.s3.us-east-2.amazonaws.com/certificates/{certificateno}.pdf"
            else:
                try:
                    pdfkit.from_string(
                        rendered_temp, f"{certificateno}.pdf", css='static/css/certificate.css')
                except OSError:
                    download_url = f"http://127.0.0.1:5000/download/{certificateno}.pdf"
            return render_template('certificate.html', postc=postc, qr_code=img_url, posto=posto, favTitle=favTitle, site_url=site_url, ip=ip_address, download_url=download_url)
        elif (postc == None):
            flash("No details found. Contact your organization!", "danger")
    return render_template('Redesign-generate.html', favTitle=favTitle, ip=ip_address, user=current_user)


@app.route("/certify/<string:number>", methods=['GET'])
def certificate_generate_string(number):
    postc = Certificate.query.filter_by(number=number).first()
    if (postc != None):
        style = "display: none;"
        posto = Group.query.filter_by(id=postc.group_id).first()
        qr_code = QRCode.query.filter_by(certificate_num=number).first()
        img_url = qr_code.qr_code
        rendered_temp = render_template('certificate.html', postc=postc, posto=posto, qr_code=img_url,favTitle=favTitle, site_url=site_url, number=number, style=style, pdf=True)
        if not app.debug:
            configr = pdfkit.configuration(wkhtmltopdf='/app/bin/wkhtmltopdf')
            file = pdfkit.from_string(
                rendered_temp, False, css='static/css/certificate.css', configuration=configr)
            upload_doc(file, number=number, localhost=False)
            download_url = f"https://cgv.s3.us-east-2.amazonaws.com/certificates/{number}.pdf"
        else:
            try:
                pdfkit.from_string(
                    rendered_temp, f"{number}.pdf", css='static/css/certificate.css')
            except OSError:
                download_url = f"http://127.0.0.1:5000/download/{number}.pdf"
        return render_template('certificate.html', postc=postc, posto=posto, qr_code=img_url, favTitle=favTitle, site_url=site_url, number=number, download_url=download_url, pdf=False)
    else:
        return redirect('/')


@app.route('/download/<path:filename>', methods=['GET', 'POST'])
def download(filename):
    docs = os.path.join(current_app.root_path)
    return send_from_directory(directory=docs, filename=filename)


# Payment Views
@app.route("/pay", methods=["GET", "POST"])
def pay_now():
    name = request.form.get("name")
    email = request.form.get("email")
    phone = request.form.get("phone")
    plan = request.form.get("plan")
    plan_info = {
        "Basic Plan": 100,
        "Regular Plan": 200,
        "Premium Plan": 300
    }
    order_amount = plan_info[plan] * 100
    order_currency = 'INR'
    client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
    order = client.order.create(
        {'amount': order_amount, 'currency': order_currency, 'payment_capture': '1'})
    context = {
        "payment": order,
        "name": name,
        "phone": phone,
        "email": email,
        "rzp_id": RAZORPAY_KEY_ID,
        "currency": order_currency
    }
    return render_template("razorpay.html", context=context)


@app.route("/razorpay-handler/", methods=["GET", "POST"])
def razorpay_handler():
    # from front end
    payment_id = request.form.get('payment_id')
    order_id = request.form.get('order_id')
    sign = request.form.get('sign')
    server_order = request.form.get('server_order')
    name = request.form.get('name')
    email = request.form.get('email')
    phone = request.form.get('phone')
    amount = int(request.form.get('amount')) // 100
    currency = request.form.get('currency')
    # genrate signature
    secret_key = bytes(RAZORPAY_KEY_SECRET, 'utf-8')
    generated_signature = hmac.new(secret_key, bytes(server_order + "|" + payment_id, 'utf-8'),
                                   hashlib.sha256).hexdigest()
    # checking authentic source
    if generated_signature == sign:
        new_txn = Transactions(name=name, email=email, phone=phone, order_id=order_id, amount=amount, currency=currency,
                               payment_id=payment_id, response_msg=sign, status="SUCCESS")
        db.session.add(new_txn)
        db.session.commit()
        return jsonify(success=True)
    return jsonify(success=False)


@app.route("/payment-failure/", methods=["GET", "POST"])
def failed_payment():
    # from front end
    payment_id = request.form.get('payment_id')
    order_id = request.form.get('order_id')
    server_order = request.form.get('server_order')
    reason = request.form.get('reason')
    step = request.form.get('step')
    source = request.form.get('source')
    description = request.form.get('description')
    code = request.form.get('code')
    name = request.form.get('name')
    email = request.form.get('email')
    phone = request.form.get('phone')
    amount = int(request.form.get('amount')) // 100
    currency = request.form.get('currency')
    new_txn = Transactions(name=name, email=email, phone=phone, order_id=order_id, amount=amount, currency=currency,
                           payment_id=payment_id, error_source=source, error_code=code,
                           response_msg="Step : " + step + ", Reason : " + reason + ", Desc: " + description,
                           status="FAILURE")
    db.session.add(new_txn)
    db.session.commit()
    return jsonify(success=True)


@app.route('/login', methods=['GET', 'POST'])
def loginPage():
    # TODO: Check for active session
    if current_user.is_authenticated:
        return redirect(url_for('dashboard_page'))
    if (request.method == 'POST'):
        email = request.form.get('email')
        password = request.form.get('password')
        remember = request.form.get('remember')
        response = Users.query.filter_by(email=email).first()
        if ((response != None) and (response.status == 1) and (response.email == email) and (
                sha256_crypt.verify(password, response.password) == 1) and (response.status == 1)):
            updateloginTime = Users.query.filter_by(email=email).first()
            updateloginTime.last_login = time
            db.session.commit()
            login_user(response, remember=remember)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('dashboard_page'))
        else:
            flash("Invalid credentials or account not activated!", "danger")
            return render_template('login.html', favTitle=favTitle)
    else:
        return render_template('login.html', favTitle=favTitle)


@app.route('/validate/email', methods=['POST'])
def email_validation():
    data = json_lib.loads(request.data)
    email = data['email']
    pattern = '^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
    user = Users.query.filter_by(email=email).first()

    if user and user.status == 0:
        return jsonify(account_inactive=True)
    if user:
        return jsonify(email_error='You are already registered. Please login to continue.', status=409)
    if not bool(re.match(pattern, email)):
        return jsonify(email_pattern_error='Please enter a valid email address.')
    return jsonify(email_valid=True)


@app.route('/validate/password', methods=['POST'])
def validate_password():
    data = json_lib.loads(request.data)
    password = data["password"]
    pattern = '^(?=.*[0-9])(?=.*[a-z])(?=.*[A-Z])(?=.*[$#@!%^&*()])(?=\S+$).{8,30}$'
    if bool(re.match(pattern, password)):
        return jsonify(password_valid=True)
    return jsonify(
        password_error='Password must be 8-30 characters long and must contain atleast one uppercase letter, one lowercase letter, one number(0-9) and one special character(@,#,$,%,&,_)')


@app.route('/match/passwords', methods=["POST"])
def match_passwords():
    data = json_lib.loads(request.data)
    password1 = data['password']
    password2 = data['password2']
    if str(password1) == str(password2):
        return jsonify(password_match=True)
    return jsonify(password_mismatch='Password and Confirm Password do not match.')


def send_activation_email(name, email):
    token = s.dumps(email, salt='cgv-email-confirm')
    new_token = Token(email=email, token_id=token, status='A')
    db.session.add(new_token)
    db.session.commit()
    if app.debug:
        link = f"http://127.0.0.1:5000/confirm-email/{token}"
    else:
        link = f"{config('site_url')}/confirm-email/{token}"
    print(link)
    subject = "Welcome aboard " + name + "!"
    return send_email_now(email, subject, 'register-bot@cgv.in.net', 'Register Bot CGV', 'emails/account-activation.html', name=name, link=link)


@app.route('/register', methods=['GET', 'POST'])
def register_page():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard_page'))
    if (request.method == 'POST'):
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        password = sha256_crypt.hash(password)
        profile_image = avatar(email, 128)
        entry = Users(name=name, email=email, password=password, profile_image=profile_image,
                      status=0, is_staff=0, last_login=time,)
        db.session.add(entry)
        db.session.commit()
        if send_activation_email(name, email):
            flash(
                f"We've sent an account activation link on {email}", "success")
        else:
            flash("Error while sending account activation email!", "danger")
            return render_template('resend.html', favTitle=favTitle)
    return render_template('register.html', favTitle=favTitle)


@app.route('/resend-link/', methods=['GET', 'POST'])
def resend_email():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard_page'))
    if request.method == 'POST':
        email = request.form.get('email')
        user = Users.query.filter_by(email=email).first()
        if user:
            if user.status == 1:
                flash('Your account is already activated. Please login', 'danger')
                return redirect(url_for('resend_email'))
            name = user.name
            if send_activation_email(name, email):
                flash(
                    f"We've sent an account activation link on {email}", "success")
            else:
                flash("Error while sending account activation email!", "danger")
        else:
            flash('You are not registered yet.', 'danger')
            return redirect(url_for('resend_email'))
    return render_template("resend.html", favTitle=favTitle)


@app.route('/confirm-email/<token>', methods=['GET'])
def confirm_email(token):
    if current_user.is_authenticated:
        return redirect(url_for('dashboard_page'))
    try:
        email = s.loads(token, salt="cgv-email-confirm", max_age=1800)
    except SignatureExpired:
        db_token = Token.query.filter_by(token_id=token).first()
        db_token.status = 'E'
        flash("Sorry, link has been expired.")
        return render_template('login.html', favTitle=favTitle)
    db_token = Token.query.filter_by(token_id=token).first()
    if db_token.status == 'U':
        flash("Sorry, link has been already used.", "danger")
        return render_template("resend.html", favTitle=favTitle)
    elif db_token.status == 'E':
        flash("Sorry, link has been expired.", "danger")
        return render_template("resend.html", favTitle=favTitle)
    user = Users.query.filter_by(email=email).first()
    user.status = 1
    db_token = Token.query.filter_by(token_id=token).first()
    db_token.status = 'U'
    user.last_login = time
    db.session.commit()
    # Some error here
    if (host == True):
        try:
            ip_address = request.environ['HTTP_X_FORWARDED_FOR']
        except KeyError:
            ip_address = request.remote_addr
        except Exception:
            ip_address = ipc
    else:
        ip_address = ipc
    try:
        url = requests.get("http://ip-api.com/json/{}".format(ip_address))
        j = url.json()
        city = j["city"]
        country = j["country"]
        subject = " New device login from " + \
            str(city) + ", " + str(country) + " detected."
        email_sent = send_email_now(email, subject, 'login-alert@cgv.in.net',
                                    'Security Bot CGV', 'emails/login-alert.html', city=city, country=country, time=str(time), ip_address=str(ip_address))
    except Exception:
        pass
    login_user(user)
    next_page = request.args.get('next')
    return redirect(next_page) if next_page else redirect(url_for('dashboard_page'))


@app.route('/dashboard')
@login_required
def dashboard_page():
    postc = len(Certificate.query.order_by(Certificate.id).all())
    postct = len(Contact.query.order_by(Contact.id).all())
    postf = len(Feedback.query.order_by(Feedback.id).all())
    postn = len(Newsletter.query.order_by(Newsletter.id).all())
    return render_template('dashboard.html', favTitle=favTitle, postc=postc, postct=postct, postf=postf, postn=postn, user=current_user, )


@app.route("/view/groups", methods=['GET', 'POST'])
@login_required
def view_org_page():
    if current_user.is_staff:
        post = Group.query.order_by(Group.id).all()
    else:
        post = Group.query.filter_by(
            user_id=current_user.id).order_by(Group.id).all()
    return render_template('org_table.html', post=post, favTitle=favTitle, user=current_user)


@app.route("/view/users", methods=['GET', 'POST'])
@login_required
@admin_required
def view_users_page():
    post = Users.query.order_by(Users.id).all()
    return render_template('users_table.html', post=post, favTitle=favTitle, user=current_user)


@app.route("/view/<string:grp_id>/certificates", methods=['GET', 'POST'])
@login_required
def view_certificate_page(grp_id):
    if current_user.is_staff:
        post = Certificate.query.filter_by(
            group_id=grp_id).order_by(Certificate.id)
    else:
        post = Certificate.query.filter_by(
            group_id=grp_id, email=current_user.email).order_by(Certificate.id)
    return render_template('certificate_table.html', post=post, favTitle=favTitle, c_user_name=current_user.name, user=current_user, grp_id=grp_id)


@app.route("/view/contacts", methods=['GET', 'POST'])
@login_required
@admin_required
def view_contacts_page():
    post = Contact.query.order_by(Contact.id).all()
    return render_template('contact_table.html', post=post, favTitle=favTitle, c_user_name=current_user.name, user=current_user)


@app.route("/view/feedbacks", methods=['GET', 'POST'])
@login_required
@admin_required
def view_feedbacks_page():
    post = Feedback.query.order_by(Feedback.id).all()
    return render_template('feedback_table.html', post=post, favTitle=favTitle, c_user_name=current_user.name, user=current_user)


@app.route("/view/newsletters", methods=['GET', 'POST'])
@login_required
@admin_required
def view_newsletters_page():
    post = Newsletter.query.order_by(Newsletter.id).all()
    return render_template('newsletter_table.html', post=post, favTitle=favTitle, c_user_name=current_user.name, user=current_user)


@app.route("/view/transactions", methods=['GET'])
@login_required
@admin_required
def view_transactions_page():
    post = Transactions.query.order_by(Transactions.id).all()
    return render_template('transaction_table.html', post=post, favTitle=favTitle, c_user_name=current_user.name, user=current_user)


@app.route("/view/messages/<string:id>", methods=['GET'])
@login_required
@admin_required
def view_message_page(id):
    post = Contact.query.filter_by(id=id).first()
    return render_template('view_message.html', post=post, favTitle=favTitle, c_user_name=current_user.name, user=current_user)


@app.route("/edit/<string:grp_id>/certificates/<string:id>", methods=['GET', 'POST'])
@login_required
def edit_certificates_page(grp_id, id):
    if request.method == 'POST':
        data = json_lib.loads(request.data)
        name = data["name"]
        coursename = data["course"]
        email = data["email"]
        letters = string.ascii_letters
        number = ''.join(random.choice(letters) for _ in range(4))
        number = 'CGV' + name[0:4].upper() + number
        userid = current_user.id
        last_update = time
        if id == '0':
            postcheck = Certificate.query.filter_by(
                email=email, coursename=coursename).first()
            if (postcheck == None):
                try:
                    post = Certificate(name=name, number=number, email=email, coursename=coursename, user_id=userid,
                                       group_id=grp_id, last_update=last_update)
                    db.session.add(post)
                    db.session.commit()
                    # Create QR Code for this certificate
                    link = f'{config("site_url")}/certify/{number}'
                    new_qr = QRCode(certificate_num=number, link=link)
                    qr_image = qrcode.QRCode(version=1, box_size=10, border=5)
                    qr_image.add_data(link)
                    qr_image.make(fit=True)
                    img = qr_image.make_image(fill='black', back_color='white')
                    buffer = io.BytesIO()
                    img.save(buffer, format="PNG")
                    buffer.seek(0)
                    try:
                        if not app.debug:
                            upload_image(buffer, number=number)
                            img_url = f"https://cgv.s3.us-east-2.amazonaws.com/qr_codes/{number}.png"
                        else:
                            try:
                                os.mkdir("static/qr_codes")
                            except Exception:
                                pass
                            img.save("static/qr_codes/"+f"{number}.png")
                            img_url = f"http://127.0.0.1:5000/static/qr_codes/{number}.png"
                        new_qr.qr_code = f"{img_url}"
                        new_qr.certificate_id = post.id
                        db.session.add(new_qr)
                        db.session.commit()
                    except Exception as e:
                        print(e)
                    subject = "Certificate Generated With Certificate Number : " + \
                        str(number)
                    email_sent = send_email_now(email, subject, 'certificate-bot@cgv.in.net', 'Certificate Generate Bot CGV',
                                                'emails/new-certificate.html', number=str(number), name=name, site_url=config("site_url"))
                    if not email_sent:
                        flash("Error while sending mail!", "danger")
                    else:
                        flash(
                            "An email with certificate details has been sent!", "success")
                    return jsonify(certificate_success=True)
                except Exception as e:
                    print(e)
                    return jsonify(certificate_error=True)
            else:
                return jsonify(certificate_duplicate=True)
        else:
            try:
                post = Certificate.query.filter_by(id=id).first()
                post.name = name
                post.coursename = coursename
                post.email = email
                post.user_id = current_user.id
                post.group_id = grp_id
                post.last_update = time
                db.session.commit()
                return jsonify(certificate_success=True)
            except Exception as e:
                print(e)
                return jsonify(certificate_error=True)
    cert = Certificate.query.filter_by(id=id).first()
    post = {
        "id": cert.id,
        "name": cert.name,
        "coursename": cert.coursename,
        "email": cert.email,
        "last_update": cert.last_update,
        "number": cert.number
    }
    return jsonify(favTitle=favTitle, id=id, post=post)


@app.route('/upload/<string:grp_id>/certificate', methods=['POST', 'GET'])
@login_required
def upload_csv(grp_id):
    csv_file = request.files['fileToUpload']
    csv_file = io.TextIOWrapper(csv_file, encoding='utf-8')
    csv_reader = csv.reader(csv_file, delimiter=',')
    # This skips the first row of the CSV file.
    next(csv_reader)
    for row in csv_reader:
        number = ''.join(random.choice(string.ascii_letters) for _ in range(4))
        number = 'CGV' + row[0][0:4].upper() + number
        certificate = Certificate(number=number, name=row[0], email=row[1], coursename=row[2], user_id=current_user.id, group_id=grp_id, last_update=time)
        db.session.add(certificate)
        db.session.commit()
        # Create QR Code for this certificate
        link = f'{config("site_url")}/certify/{number}'
        new_qr = QRCode(certificate_num=number, link=link)
        qr_image = qrcode.QRCode(version=1, box_size=10, border=5)
        qr_image.add_data(link)
        qr_image.make(fit=True)
        img = qr_image.make_image(fill='black', back_color='white')
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        try:
            if not app.debug:
                upload_image(buffer, number=number)
                img_url = f"https://cgv.s3.us-east-2.amazonaws.com/qr_codes/{number}.png"
            else:
                try:
                    os.mkdir("static/qr_codes")
                except Exception:
                    pass
                    img.save("static/qr_codes/"+f"{number}.png")
                    img_url = f"http://127.0.0.1:5000/static/qr_codes/{number}.png"
            new_qr.qr_code = f"{img_url}"
            new_qr.certificate_id = certificate.id
            db.session.add(new_qr)
            db.session.commit()
                
        except Exception as e:
            print(e)
    return jsonify(result=True, status=200)

# For Certificate
def row_to_list(obj):
    lst = []
    lst.append(obj.number)
    lst.append(obj.name)
    lst.append(obj.email)
    lst.append(obj.coursename)
    lst.append(obj.last_update)
    return lst

@app.route("/download/<string:grp_id>/certificate")
def export_certificate_csv(grp_id):
    all_certificates = Certificate.query.filter_by(group_id=grp_id).order_by(Certificate.id)
    if all_certificates.count()<=0:
        flash("No certificates available in this group", "danger")
        return redirect(f"/view/{grp_id}/certificates")
    si = io.StringIO()
    cw = csv.writer(si, delimiter=",")
    cw.writerow(["Number", "Name", "Email" , "Course Name", "Date Created"])
    for row in all_certificates:
        row = row_to_list(row)
        cw.writerow(row)
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = f"attachment; filename=group{grp_id}.csv"
    output.headers["Content-type"] = "text/csv"
    return output
    

@app.route("/activate/user/<string:id>", methods=['GET', 'POST'])
@login_required
@admin_required
def activate_users(id):
    activate = Users.query.filter_by(id=id).first()
    if (activate.email == config("admin_email")):
        flash("Administrator account will always be active!", "warning")
        return redirect(url_for('view_users_page'))
    else:
        if (activate.status == 1):
            activate.status = 0
            flash("User account deactivated!", "warning")
            db.session.commit()
            return redirect(url_for('view_users_page'))
        else:
            activate.status = 1
            flash("User account activated!", "success")
            db.session.commit()
            return redirect(url_for('view_users_page'))


@app.route("/permissions/<string:perm>/users/<string:id>", methods=['GET', 'POST'])
@login_required
def change_permissions(perm, id):
    user = Users.query.filter_by(id=id).first()
    if current_user.is_admin:
        if current_user.id != user.id:
            if perm == 'staff':
                if user.is_staff:
                    user.is_staff = False
                else:
                    user.is_staff = True
            elif perm == 'admin':
                if user.is_admin:
                    user.is_admin = False
                else:
                    user.is_admin = True
            db.session.commit()
        else:
            flash("You cannot change your own permission", "danger")
    else:
        flash("You are not authorised to change permissions", "danger")
    return redirect(url_for('view_users_page'))


@app.route("/edit/group/<string:id>", methods=['GET', 'POST'])
@login_required
def edit_org_page(id):
    if request.method == 'POST':
        data = json_lib.loads(request.data)
        name = data["name"]
        dept = data["dept"]
        email = data["email"]
        phone = data["phone"]
        date = time
        if id == '0':
            if Group.query.filter_by(email=email).first():
                return jsonify(group_duplicate=True)
            try:
                post = Group(name=name, subname=dept, email=email,
                             phone=phone, date=date, user_id=current_user.id)
                db.session.add(post)
                db.session.commit()
                return jsonify(group_success=True)
            except Exception:
                return jsonify(group_error=True)

        else:
            try:
                post = Group.query.filter_by(id=id).first()
                post.name = name
                post.subname = dept
                post.phone = phone
                post.email = email
                post.date = date
                post.user_id = current_user.id
                db.session.commit()
                return jsonify(group_success=True)
            except Exception:
                return jsonify(group_error=True)
    grp = Group.query.filter_by(id=id).first()
    post = {
        "id": grp.id,
        "name": grp.name,
        "subname": grp.subname,
        "email": grp.email,
        "phone": grp.phone
    }
    return jsonify(favTitle=favTitle, id=id, post=post)


@app.route("/delete/group/<string:id>", methods=['GET', 'POST'])
@login_required
def delete_org_page(id):
    delete_org_page = Group.query.filter_by(id=id).first()
    if (delete_org_page.email == config("admin_email")):
        flash("Default organization can't be deleted!", "danger")
    else:
        db.session.delete(delete_org_page)
        db.session.commit()
        flash("Organization deleted successfully!", "success")
    return redirect('/view/groups')


@app.route("/delete/users/<string:id>", methods=['GET', 'POST'])
@login_required
@admin_required
def delete_users_page(id):
    delete_users_page = Users.query.filter_by(id=id).first()
    if (delete_users_page.email == config("admin_email")) or delete_users_page.is_staff:        
        flash("You can't delete administrator!", "danger")
    else:        
        db.session.delete(delete_users_page)
        db.session.commit()
        flash("User deleted successfully!", "success")
        return redirect('/view/users')
    return redirect('/view/users')


@app.route("/delete/<string:grp_id>/certificates/<string:id>", methods=['GET', 'POST'])
@login_required
def delete_certificates_page(grp_id, id):
    delete_certificates_page = Certificate.query.filter_by(id=id).first()
    db.session.delete(delete_certificates_page)
    db.session.commit()
    flash("Certificate deleted successfully!", "success")
    return redirect(f'/view/{grp_id}/certificates')


@app.route("/delete/contact/<string:id>", methods=['GET', 'POST'])
@login_required
def delete_contact_page(id):
    delete_contact_page = Contact.query.filter_by(id=id).first()
    db.session.delete(delete_contact_page)
    db.session.commit()
    flash("Contact response deleted successfully!", "success")
    return redirect('/view/contacts')


@app.route("/delete/feedback/<string:id>", methods=['GET', 'POST'])
@login_required
def delete_feedback_page(id):
    delete_feedback_page = Feedback.query.filter_by(id=id).first()
    db.session.delete(delete_feedback_page)
    db.session.commit()
    flash("Feedback response deleted successfully!", "success")
    return redirect('/view/feedbacks')


@app.route("/delete/newsletter/<string:id>", methods=['GET', 'POST'])
@login_required
def delete_newsletter_page(id):
    delete_newsletter_page = Newsletter.query.filter_by(id=id).first()
    db.session.delete(delete_newsletter_page)
    db.session.commit()
    flash("Newsletter response deleted successfully!", "success")
    return redirect('/view/newsletters')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged Out Successfully!', 'success')
    return redirect(url_for('loginPage'))


# Google Login Starts Here

# OAuth 2 client setup
client = WebApplicationClient(GOOGLE_CLIENT_ID)


def get_google_provider_cfg():
    return requests.get(GOOGLE_DISCOVERY_URL).json()

# Google Login Route


@app.route('/login/google')
def google_login():
    # Find out what URL to hit for Google login
    google_provider_cfg = get_google_provider_cfg()
    authorization_endpoint = google_provider_cfg["authorization_endpoint"]

    # Use library to construct the request for Google login and provide
    # scopes that let us retrieve user's profile from Google

    request_uri = client.prepare_request_uri(
        authorization_endpoint,
        redirect_uri=request.base_url + "/callback",
        scope=["openid", "email", "profile"],
    )
    return redirect(request_uri)


@app.route('/login/google/callback')
def google_login_callback():
    # Get authorization code Google sent back to us
    code = request.args.get("code")

    # Find out what URL to hit to get tokens that allow us to ask for
    # things on behalf of a user
    google_provider_cfg = get_google_provider_cfg()
    token_endpoint = google_provider_cfg["token_endpoint"]

    token_url, headers, body = client.prepare_token_request(
        token_endpoint,
        authorization_response=request.url,
        redirect_url=request.base_url,
        code=code
    )
    token_response = requests.post(
        token_url,
        headers=headers,
        data=body,
        auth=(GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET),
    )

    # Parse the tokens!
    client.parse_request_body_response(json_lib.dumps(token_response.json()))

    # Now that we have tokens, let's find and hit the URL
    # from Google that gives us the user's profile information,
    # including their Google profile image and email
    userinfo_endpoint = google_provider_cfg["userinfo_endpoint"]
    uri, headers, body = client.add_token(userinfo_endpoint)
    userinfo_response = requests.get(uri, headers=headers, data=body)

    # You want to make sure their email is verified.
    # The user authenticated with Google, authorized your
    # app, and now we've verified their email through Google!
    if userinfo_response.json().get("email_verified"):
        users_email = userinfo_response.json()["email"]
        picture = userinfo_response.json()["picture"]
        users_name = userinfo_response.json()["name"]
    else:
        abort(401)
    pwo = PasswordGenerator()
    pwd = pwo.generate()
    password = sha256_crypt.hash(pwd)
    # Create a user in your db with the information provided
    # by Google

    # Doesn't exist? Add it to the database.
    if not Users.query.filter_by(email=users_email).first():
        entry = Users(name=users_name, email=users_email, password=password,
                      profile_image=picture, last_login=time, status=1)
        db.session.add(entry)
        db.session.commit()

    # Begin user session by logging the user in

    user = Users.query.filter_by(email=users_email).first()
    if user.status == 1:
        login_user(user)
    else:
        flash("Your account has been deactivated. Contact us to activate it.", "danger")
        return redirect(url_for("loginPage"))

    # Send user back to homepage
    return redirect(url_for("dashboard_page"))


# FB_SCOPE = ["email", "public_profile"]


# @app.route('/login/facebook')
# def facebook_login():
#     facebook = requests_oauthlib.OAuth2Session(
#         FB_CLIENT_ID, redirect_uri=request.base_url + "/fb-callback", scope=FB_SCOPE
#     )
#     authorization_url, _ = facebook.authorization_url(
#         FB_AUTHORIZATION_BASE_URL)

#     return redirect(authorization_url)


# @app.route('/login/facebook/callback')
# def facebook_login_callback():
#     facebook = requests_oauthlib.OAuth2Session(
#         FB_CLIENT_ID, scope=FB_SCOPE, redirect_uri=request.base_url + "/callback"
#     )

#     # we need to apply a fix for Facebook here
#     facebook = facebook_compliance_fix(facebook)

#     facebook.fetch_token(
#         FB_TOKEN_URL,
#         client_secret=FB_CLIENT_SECRET,
#         authorization_response=request.url,
#     )

#     # Fetch a protected resource, i.e. user profile, via Graph API

#     facebook_user_data = facebook.get(
#         "https://graph.facebook.com/me?fields=id,name,email,picture{url}"
#     ).json()

#     users_email = facebook_user_data["email"]
#     users_name = facebook_user_data["name"]
#     picture_url = facebook_user_data.get(
#         "picture", {}).get("data", {}).get("url")

#     pwo = PasswordGenerator()
#     pwd = pwo.generate()
#     password = sha256_crypt.hash(pwd)
#     if not Users.query.filter_by(email=users_email).first():
#         entry = Users(name=users_name, email=users_email, password=password,
#                       profile_image=picture_url, last_login=time, status=1)
#         db.session.add(entry)
#         db.session.commit()

#     user = Users.query.filter_by(email=users_email).first()
#     login_user(user)

#     # Send user back to homepage
#     return redirect(url_for("dashboard_page"))


@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


@app.errorhandler(401)
def user_not_authorized(e):
    return render_template('401.html'), 401

#for feedback
def rowToListFeedback(obj):
    lst = []
    name = obj.name
    email = obj.email
    rating = obj.rating
    msg = obj.message
    lst.append(name)
    lst.append(email)
    lst.append(rating)
    lst.append(msg)
    return lst


@app.route('/downloadfeedback')
@login_required
@admin_required
def ToCsv():
    allfeedback = Feedback.query.all()
    if len(allfeedback) == 0:
        flash("No Feedback available","danger")
        return redirect("/view/feedbacks")
    si = io.StringIO()
    cw = csv.writer(si, delimiter=",")
    cw.writerow(["Name",  "Email" , "Rating Out of 5" , "Message"])
    for row in allfeedback:
        row = rowToListFeedback(row)
        cw.writerow(row)
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = f"attachment; filename=feedback_response.csv"
    output.headers["Content-type"] = "text/csv"
    return output

#for contact
def rowToListContact(obj):
    lst = []
    name = obj.name
    email = obj.email
    number = obj.phone
    msg = obj.message[3:-4]
    date = obj.date
    ip = obj.ip
    lst.append(name)
    lst.append(email)
    lst.append(number)
    lst.append(msg)
    lst.append(date)
    lst.append(ip)
    return lst


@app.route('/downloadcontact')
@login_required
@admin_required
def ContactToCsv():
    allfeedback = Contact.query.all()
    if len(allfeedback) == 0:
        flash("No Contacts available","danger")
        return redirect("/view/contacts")
    si = io.StringIO()
    cw = csv.writer(si, delimiter=",")
    cw.writerow(["Name", "Email" , "Number", "Message" , "Date" , "IP"])
    for row in allfeedback:
        row = rowToListContact(row)
        cw.writerow(row)
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = f"attachment; filename=contact_response.csv"
    output.headers["Content-type"] = "text/csv"
    return output


#for Newsletter
def rowToListNewsletter(obj):
    lst = []
    email = obj.email
    ip = obj.ip
    date = obj.date
    lst.append(email)
    lst.append(ip)
    lst.append(date)
    return lst


@app.route('/downloadNewsletter')
@login_required
@admin_required
def NewsletterToCsv():
    allfeedback = Newsletter.query.all()
    if len(allfeedback) == 0:
        flash("No Newsletter available","danger")
        return redirect("/view/newsletters")
    si = io.StringIO()
    cw = csv.writer(si, delimiter=",")
    cw.writerow(["Email" , "IP", "Date"])
    for row in allfeedback:
        row = rowToListNewsletter(row)
        cw.writerow(row)
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = f"attachment; filename=NewsLetter.csv"
    output.headers["Content-type"] = "text/csv"
    return output

if __name__ == '__main__':
    app.run(debug=True)
