from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError, DataError
from datetime import datetime
import requests
from flask_bcrypt import Bcrypt
#session handling
from flask_login import LoginManager, login_user, logout_user, login_required, current_user

# email handling
import os
from flask_mail import Mail,Message


app = Flask(__name__)
app.debug = True
bcrypt=Bcrypt()

login_manager = LoginManager()
login_manager.init_app(app)

app.secret_key = str(os.environ.get('SECRET_KEY'))

app.config['MAIL_SERVER'] = 'smtp.sendgrid.net'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'apikey'
app.config['MAIL_PASSWORD'] = os.environ.get('SENDGRID_API_KEY')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER')
mail = Mail(app)


#app.config['SQLALCHEMY_DATABASE_URI']='postgresql+psycopg2://sa:12345678@localhost:5432/meteorologio'
app.config['SQLALCHEMY_DATABASE_URI']='postgres://qxacugfabwkwrx:b8eda11a40abab9e8f7fb76f2a560069dc8ba6864562bc961657dc5cef482fee@ec2-54-225-18-166.compute-1.amazonaws.com:5432/dbjcdbuo0fnkth'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# API_KEY

api_token = os.environ.get('WEATHER_API_KEY')
api_url_base = 'https://api.openweathermap.org/data/2.5/weather?q='
headers = {'Content-Type': 'application/json',
           'Authorization': 'Bearer {0}'.format(api_token)
}

class Usuario(db.Model):
    __tablename__ = 'usuario'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True)
    passwd = db.Column(db.String(250))
    email = db.Column(db.String(250), unique=True, index=True)
    status = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    def __init__(self,username,passwd,email):
        self.username = username
        self.passwd = passwd
        self.email = email
    
    def is_authenticated(self):
	    return True
    
    def is_active(self):
        return True
    
    def is_anonymous(self):
        return False
    
    def get_id(self):
        return str(self.id)
    
class Consulta(db.Model):
    __tablename__ = 'consulta'
    idConsulta = db.Column(db.Integer, primary_key=True)
    idUsuario = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    ciudad = db.Column(db.String(50))
    clima = db.Column(db.String(50))
    temperatura = db.Column(db.Integer)
    sensacion = db.Column(db.Integer)
    humedad = db.Column(db.Integer)
    status = db.Column(db.Boolean, default=True)
    fecha = db.Column(db.DateTime)

    def __init__(self,idUsuario,ciudad,clima,temperatura,sensacion,humedad,fecha):
        self.idUsuario = idUsuario
        self.ciudad = ciudad
        self.clima = clima
        self.temperatura = temperatura
        self.sensacion = sensacion
        self.humedad = humedad
        self.fecha = fecha

@login_manager.user_loader
def load_user(user_id):
	return Usuario.query.filter_by(id=user_id).first()

@app.route('/',methods=['POST','GET'])
def inicio():
    records=""
    if current_user.is_authenticated:
        records = getRecord()

    if request.method == "POST":
        ciudad = request.form['ciudad']
        clima=""
        message = ""
        if request.form.get('ciudad') != "":
            clima = getWeather(ciudad)
            if current_user.is_authenticated:
                records = getRecord()
        if(type(clima) != dict):
            clima=""
            #flash("Ciudad no encontrada")
        
        return render_template("index.html", data=clima, historial=records)

    return render_template("index.html",historial=records)

def getWeather(ciudad):
    api_url ='{}&appid='.format(api_url_base+ciudad)+api_token
    response = requests.get(api_url,headers=headers).json()

    if(response.get('cod') == '404'):
        return response.get('message')
    
    clima = round(response.get('main').get('temp') - 273.15)
    sensacion = round(response.get('main').get('feels_like') - 273.15 )
    humedad = response.get('main').get('humidity')
    estado = response.get('weather')[0].get('main')
    ciudad = response.get('name')
    pais = response.get('sys').get('country')
    data = {
        "clima":clima,
        "sensacion":sensacion,
        "humedad":humedad,
        "estado":estado,
        "ciudad":ciudad,
        "pais":pais
    }
    if current_user.is_authenticated:
        fecha=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        consulta=Consulta(idUsuario=current_user.id,ciudad=ciudad,clima=estado,temperatura=clima,sensacion=sensacion,humedad=humedad,fecha=fecha)
        db.session.add(consulta)
        db.session.commit()
    
    return data

@app.route('/signup', methods=['GET','POST'])
def signup():
    if current_user.is_authenticated:
        return redirect("/")

    if request.method == "POST":
        print(request.form)
        pwd = request.form["psw"] 
        vpwd = request.form["psw-repeat"] 
        if pwd != vpwd:
            flash ("Las contraseñas no coinciden!","error") 
            return render_template("signup.html")
        else:
            name = request.form["user"]
            correo = request.form["email"] 
            passwd=bcrypt.generate_password_hash(request.form["psw"]).decode("utf-8")
            try:
                usuario=Usuario(username=name,passwd=passwd,email=correo)
                db.session.add(usuario)
                db.session.commit()

                #Enviar correo
                msg = Message("Bienvenido a Meteorologio", recipients=[correo])
                msg.html = render_template('email.html',user=name,passwd=request.form["psw"])
                mail.send(msg)
                
                flash("Hemos enviado un correo de verificación a {}".format(correo),"success")

            except IntegrityError as error:
                db.session.rollback()
                flash(str((error.orig.diag.message_detail)),"error")
            except DataError as derror:
                flash(str((derror.orig.diag.message_primary)),"error")

        return render_template("signup.html")
            
    return render_template("signup.html")

@app.route('/login', methods=['GET','POST'])
def login():
    if current_user.is_authenticated:
        return redirect("/")
    if request.method == "POST":
        email = request.form["email"]
        pwd = request.form["psw"]
        user_exists = Usuario.query.filter_by(email=email).first()
        if user_exists:
            if bcrypt.check_password_hash(user_exists.passwd,pwd):
                login_user(user_exists)
                if current_user.is_authenticated:
                    return redirect("/")
            else:
                flash("usuario o contraseña inválidos ","error")
        else:
            flash("Usuario o contraseña inválidos","error")

    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect("/")

def getRecord():
    record= Consulta.query.filter_by(idUsuario=current_user.id).order_by(Consulta.idConsulta.desc()).all()
    return record

if __name__ == '__main__':
    db.create_all()
    app.run()