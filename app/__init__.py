import os
import logging
from logging.handlers import RotatingFileHandler, SMTPHandler
import time
from email.policy import HTTP
import datetime
import click
from flask import Flask, jsonify, render_template, redirect, url_for, request, json
from flask import flash, send_from_directory
from flask_httpauth import HTTPBasicAuth, HTTPTokenAuth
#from werkzeug import generate_password_hash, check_password_hash
from werkzeug.urls import url_parse
from werkzeug.utils import secure_filename
from flask_login import LoginManager, login_required, login_user, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import ValidationError, DataRequired, Email, EqualTo
from flask_debugtoolbar import DebugToolbarExtension

from app.forms import ManualChForm, ManualTmaForm, UserForm, DataUploadForm, DataDownloadForm
from app.models import Location, Logger, Offline, Ws, Das
from app import errors
import pandas as pd

from config import Config

debug_toolbar = DebugToolbarExtension()

basic_auth = HTTPBasicAuth()
token_auth = HTTPTokenAuth()

login_manager = LoginManager()    
login_manager.login_view = 'login'

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Sign In')

def next_month(dt):
    return (dt.replace(day=1) + datetime.timedelta(days=32)).replace(day=1)

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    if not app.debug:
        if not os.path.exists('logs'):
            os.mkdir('logs')
        file_handler = RotatingFileHandler('logs/prinus_app.log', maxBytes=10240,
                                           backupCount=10)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
    
        if app.config['MAIL_SERVER']:
            auth = None
            if app.config['MAIL_USERNAME'] or app.config['MAIL_PASSWORD']:
                auth = (app.config['MAIL_USERNAME'], app.config['MAIL_PASSWORD'])
            secure = None
            if app.config['MAIL_USE_TLS']:
                secure = ()
            mail_handler = SMTPHandler(
                mailhost=(app.config['MAIL_SERVER'], app.config['MAIL_PORT']),
                fromaddr='no-reply@' + app.config['MAIL_SERVER'],
                toaddrs=app.config['ADMINS'], subject='[PRINUS_APP]',
                credentials=auth, secure=secure)
            mail_handler.setLevel(logging.ERROR)
            app.logger.addHandler(mail_handler)

    from app.models import db, User, Logger, Tenant, Raw, Daily
    from app import pos 
    from app import logger
    from app import user
    from app import tenant
    from app import map
    from app import api
    
    @basic_auth.verify_password
    def verify_password(username, password):
        try:
            user = User.get(User.username==username)
        except User.DoesNotExist:
            return
        if user and user.check_password(password):
            return user

    @token_auth.verify_token
    def verify_token(token):
        return User.check_token(token) if token else None
    
    login_manager.init_app(app)
    db.init_app(app)
    
    debug_toolbar.init_app(app)
    
    app.register_blueprint(pos.bp, url_prefix='/pos')
    app.register_blueprint(logger.bp, url_prefix='/logger')
    app.register_blueprint(user.bp, url_prefix='/user')
    app.register_blueprint(tenant.bp, url_prefix='/tenant')
    app.register_blueprint(map.bp, url_prefix='/map')
    app.register_blueprint(api.bp, url_prefix='/api' )

    @login_manager.user_loader
    def load_user(user_id):
        try:
            return User.get_by_id(user_id)
        except:
            return None

    @app.before_request
    def before_request():
        if current_user.is_authenticated:
            current_user.last_seen = datetime.datetime.utcnow()
            current_user.save()
            if current_user.tenant:
                os.environ['TZ'] = current_user.tenant.timezone
            else:
                os.environ['TZ'] = 'Asia/Jakarta'
            time.tzset()
    
    @app.route('/ws', methods=['POST'])
    @login_required
    def create_ws():
        new_ws = Ws(nama=request.form.get('nama'), tenant=current_user.tenant)
        new_ws.save()
        return redirect('/pos')
        
    @app.route('/download', methods=['GET', 'POST'])
    @login_required
    def data_download():
        form = DataDownloadForm()
        banyak = 3
        bl = datetime.date.today() - \
            pd.offsets.DateOffset(months=banyak)
        form.bulan.choices = [i * 30 for i in range(banyak)]
        if current_user.tenant:
            location_list = [(l.id, l.nama) for l in current_user.tenant.location_set]  
        else:
            location_list = [(l.id, l.nama) for l in Location.select()]
        if form.validate_on_submit():
            pass
        form.location.choices = location_list
        return render_template('data_download.html', form=form)
        
    
    @app.route('/offline')
    @login_required
    def offline():
        offs = Offline.select().where(Offline.username==current_user.username)
        return render_template('offline.html', offlines=offs)
    
    
    @app.route('/upload', methods=['POST', 'GET'])
    @login_required
    def data_upload():
        form = DataUploadForm()
        if form.validate_on_submit():
            '''Isi file harus minimal 3 baris'''
            f = form.to_import.data
            filename = secure_filename(f.filename)
            lines = f.readlines()
            error = []
            if len(lines) >= 3:
                # temukan logger
                loc = '-'
                try:
                    sn = lines[0].decode('utf-8').split(' ')[0].split('/')[1]
                except IndexError:
                    error.append('Tidak ditemukan sn logger. File data tidak diterima.')
                    return render_template('upload.html', data_upload_form=form)
                sn = "".join(s for s in sn if s.isdigit() or s == '-')
                try:
                    logger = Logger.get(Logger.sn==sn)
                    if logger.tenant:
                        tenant_id = logger.tenant.id
                    else:
                        tenant_id = None
                    if logger.location:
                        loc = logger.location.nama
                except Logger.DoesNotExist:
                    error.append('SN: <b>{}</b> belum terdaftar. Data tetap diupload'.format(sn))
                banyak = len(lines) - 2
                try:
                    sawal = lines[2].decode('utf-8').strip().split(',')[0].strip('"')
                    tz = int(sawal[-2])
                    awal = datetime.datetime.strptime(sawal[:-3], '%Y-%m-%dT%H:%M:%S')
                    awal -= datetime.timedelta(hours=tz)
                except IndexError:
                    error.append("sampling awal tidak terdeteksi")
                try:
                    sakhir = lines[-1].decode('utf-8').strip().split(',')[0].strip('"')
                    akhir = datetime.datetime.strptime(sakhir[:-3], '%Y-%m-%dT%H:%M:%S')
                    akhir -= datetime.timedelta(hours=tz)
                except IndexError:
                    error.append("Sampling akhir tidak terdeteksi")
                offline = Offline(sn=sn, location=loc, awal=awal, akhir=akhir, 
                                  banyak=banyak, fname=filename,  
                                  username=current_user.username,
                                  content=''.join(s.decode('utf-8') for s in lines))
                offline.save()
                error = 'File offline telah berhasil diupload, sn: {}, {} baris data'.format(sn, banyak)
            else:
                error = 'Isi file kurang dari 3 baris.'
            flash(error)
            return redirect('/')
        return render_template('uploaded.html', data_upload_form=form)
    
    @app.route('/token', methods=['POST'])
    @basic_auth.login_required
    def get_token():
        token = basic_auth.current_user().get_token()
        return jsonify({'token': token})
        
    @app.route('/map')
    def map():
        t = None
        if current_user.is_authenticated and current_user.tenant:
            t = current_user.tenant
        return render_template('map.html')

    @app.route('/tv')
    def tv():
        t = None
        if current_user.is_authenticated and current_user.tenant:
            t = current_user.tenant
        return render_template('tv.html', tenant=t)
    
    @app.route('/favicon.ico')
    def favicon():
        print(app.root_path)
        return send_from_directory(os.path.join(app.root_path, 'static'),
                                'favicon.ico', mimetype='image/vnd.microsoft.icon')
    
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for('homepage'))
        form = LoginForm()
        if form.validate_on_submit():
            try:
                user = User.get(User.username==form.username.data)
            except User.DoesNotExist:
                flash('Invalid username or password')
                return redirect(url_for('login'))
            if user is None or not user.check_password(form.password.data):
                flash('Invalid username or password')
                return redirect(url_for('login'))
            login_user(user, remember=form.remember_me.data)
            
            next_page = request.args.get('next')
            if not next_page or url_parse(next_page).netloc != '':
                next_page = '/'
            return redirect(next_page)
        return render_template('login.html', title='Sign In', form=form)
    
    @app.route('/logout')
    def logout():
        logout_user()
        return redirect('/')    

    @app.route('/', methods=['POST', 'GET'])
    def homepage():
        if current_user.is_authenticated:
            data_upload_form = DataUploadForm()
            today = datetime.date.today()
            if request.args.get('s'):
                today = datetime.datetime.strptime(request.args.get('s'), '%Y-%m-%d').date()
            if not current_user.tenant:
                return render_template('home_master.html', data_upload_form=data_upload_form)
            else:
                if current_user.location_id: # Petugas Lapangan
                    template_name = 'home_petugas_{}.html'.format(current_user.location.tipe)
                    next_month = (today.replace(day=1) + datetime.timedelta(days=32)).replace(day=1)
                    prev_month = (today.replace(day=1) - datetime.timedelta(days=2)).replace(day=1)

                    daily_set = current_user.location.daily_set.where((Daily.sampling.year == today.year) & (Daily.sampling.month == today.month))
                    if current_user.location.tipe == '1':
                        form = ManualChForm(sampling=(today - datetime.timedelta(days=1)), \
                            location=current_user.location.id)
                    elif current_user.location.tipe == '2':
                        form = ManualTmaForm(sampling=today, \
                            location=current_user.location.id)
                    else:
                        form = ManualChForm()
                    form.location.data = current_user.location_id
                    errors = None
                    if form.validate_on_submit():
                        sampling = datetime.datetime.combine(form.sampling.data, datetime.datetime.min.time())
                        data = {'sampling': int(sampling.strftime('%s')), 'petugas': current_user.username}
                        daily_default = {'petugas': current_user.username, 'sn': '-'}
                        if hasattr(form, 'ch'):
                            data.update({'m_rain': float(form.ch.data)})
                            daily_default.update({'m_rain': float(form.ch.data)})
                        elif hasattr(form, 'tma'):
                            m_level_field = 'm_wlevel_{}'.format(form.waktu.data)
                            data.update({m_level_field: float(form.tma.data)})
                            daily_default.update({m_level_field: float(form.tma.data)})
                        db.database.execute_sql('INSERT INTO raw_manual (content, location_id) VALUES (%(cnt)s, %(loc)s)', 
                                                {'cnt': json.dumps(data), 'loc': current_user.location_id})
                        flash('Sukses menambah data')
                        
                        new_daily, created = Daily.get_or_create(sampling=form.sampling.data, \
                            location=current_user.location, defaults=daily_default)
                        new_daily.save()
                        return redirect('/')
                    else:
                        errors = form.errors
                    return render_template(template_name, data_upload_form=data_upload_form, \
                        daily_set=daily_set, manual_form=form, today=today, next_month=next_month, \
                            prev_month=prev_month, errors=errors)
                list_petugas = User.select().where(User.tenant==current_user.tenant).order_by(User.username)
                sns = [l.sn for l in current_user.tenant.logger_set]
                #sql = f"SELECT id,content->>'tick', content->>'distance' AS distance, content->>'sampling' FROM raw WHERE sn IN ({','.join('?' for _ in sns)}) AND distance IS NOT NULL LIMIT 3000"
                #rst = db.database.execute_sql(sql, sns)
                #for r in rst:
                #    print(r)
                #loggers_count = Logger.select().where(Logger.tenant==current_user.tenant).count()
                return render_template('home_tenant.html', 
                                       loggers_count=current_user.tenant.logger_set.count(), 
                                       list_petugas=list_petugas,
                                       data_upload_form=data_upload_form)
        else:
            return render_template('welcome.html', form=LoginForm())
    
    return app
