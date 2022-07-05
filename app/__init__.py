from email.policy import HTTP
from datetime import datetime, timedelta
import os
import time
import click
from flask import Flask, jsonify, render_template, redirect, url_for, request, json
from flask import flash, send_from_directory
from flask_httpauth import HTTPBasicAuth, HTTPTokenAuth
#from werkzeug import generate_password_hash, check_password_hash
from werkzeug.urls import url_parse
from flask_login import LoginManager, login_required, login_user, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import ValidationError, DataRequired, Email, EqualTo
from .forms import UserForm
import pandas as pd

from config import Config

basic_auth = HTTPBasicAuth()
token_auth = HTTPTokenAuth()

login_manager = LoginManager()    
login_manager.login_view = 'login'

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Sign In')


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    from app.models import db, User, Logger, Tenant, Raw
    from app import pos 
    from app import logger
    from app import user
    from app import tenant
    from app import map
    
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
    
    app.register_blueprint(pos.bp, url_prefix='/pos')
    app.register_blueprint(logger.bp, url_prefix='/logger')
    app.register_blueprint(user.bp, url_prefix='/user')
    app.register_blueprint(tenant.bp, url_prefix='/tenant')
    app.register_blueprint(map.bp, url_prefix='/map')

    @login_manager.user_loader
    def load_user(user_id):
        try:
            return User.get_by_id(user_id)
        except:
            return None

    @app.before_request
    def before_request():
        if current_user.is_authenticated:
            current_user.last_seen = datetime.utcnow()
            current_user.save()
            if current_user.tenant:
                os.environ['TZ'] = current_user.tenant.timezone
            else:
                os.environ['TZ'] = 'Asia/Jakarta'
            time.tzset()
            
    @app.cli.command('ke_jam')
    @click.option('--jam', help='Jam data yang akan diproses')
    @click.argument('sn')
    def ringkas_ke_jam(jam, sn):
        if not jam:
            jam = datetime.now().replace(minute=0, second=0) - timedelta(hours=1)
        click.echo(sn)
        click.echo(jam)
        
    @app.cli.command('browse')
    def browse():
        '''Browsing data (table 'raw')'''
        sn = '1910-28'
        _sta = 1648767600
        _end = 1648857300
        rst = db.database.execute_sql("SELECT content FROM raw WHERE sn='{}' AND content->>'sampling' >= {} AND content->>'sampling' < {} ORDER BY id ".format(sn, _sta, _end))
        data = [json.loads(r[0]) for r in rst]
        '''
        for r in data:
            click.echo(datetime.fromtimestamp(r['sampling']))
        return
        '''
        click.echo(data[0])
        df = pd.DataFrame(data)
        df['sampling'] = pd.to_datetime(df['sampling'], unit='s')
        df.drop(columns=['device', 'time_set_at', 'signal_quality', 'pressure', 'altitude', 'temperature'], inplace=True)
        df.set_index('sampling')
        if 'tipping_factor' in df:
            tf = df['tipping_factor']
        else:
            tf = 0.2
        df['rain'] = df['tick'] * tf
        click.echo(df)
        #click.echo(pd.__version__)
        #click.echo(df.groupby(pd.Grouper(key='sampling', freq='1h'))['rain'].sum())
        #click.echo(df.info())
                    
    @app.cli.command('list-user')
    def list_user():
        '''Menampilkan daftar user'''
        rst = User.select()
        for u in rst:
            click.echo("{}\t{}".format(u.id, u.username))
            
    @app.cli.command('list-tenant')
    def list_tenant():
        '''Menampilkan daftar Tenant'''
        rst = Tenant.select()
        for t in rst:
            click.echo("{:>3}\t{}\t{}".format(t.id, t.slug, t.nama))
    
    @app.cli.command('periodik')
    def test_hitungan_pandas():
        mydata = []
        click.echo('mytest')
    
    @app.cli.command('ps')
    def ps():
        rst = db.database.execute_sql("SELECT content FROM raw LIMIT 50")
        for r in rst.fetchall():
            ps_rec(r[0])
    
    def ps_rec(msg):
        d = json.loads(msg)
        sampling = datetime.fromtimestamp(d['sampling'])
        try:
            sn = d['device'].split('/')[1]
        except IndexError:
            return
        click.echo("{} pada {}".format(sn, sampling))
        if 'tick' in d:
            tipping_factor = 0.2
            if 'tipping_factor' in d:
                tipping_factor = d['tipping_factor']
            click.echo('tick: {} * {}'.format(d['tick'], tipping_factor))
            
        if 'distance' in d:
            sensor_height = 0
            sensor_resolution = 0
            if 'sensor_height' in d:
                sensor_height = d['sensor_height']
            if 'sensor_resolution' in d:
                sensor_resolution = d['sensor_resolution']
            click.echo('dist: {} {} {}'.format(d['distance'], sensor_height, sensor_resolution))
            #click.echo('distance: {}, sensor_height: {}, sensor_resolution: {}'.format(d['distance'], d['sensor_height'], d['sensor_resolution']))
        #click.echo(datetime.fromtimestamp(d['sampling']))
        
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
            return redirect(url_for('index'))
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
    
    @app.route('/')
    def homepage():
        if current_user.is_authenticated:
            if not current_user.tenant:
                return render_template('home_master.html')
            else:
                if current_user.is_petugas:
                    return render_template('home_petugas.html')
                list_petugas = User.select().where(User.tenant==current_user.tenant).order_by(User.username)
                loggers_count = Logger.select().where(Logger.tenant==current_user.tenant).count()
                form_user = UserForm()
                return render_template('home_tenant.html', 
                                       loggers_count=loggers_count, 
                                       list_petugas=list_petugas,
                                       user_form=form_user)
        else:
            return render_template('welcome.html', form=LoginForm())
    
    return app
