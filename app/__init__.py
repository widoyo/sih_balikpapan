from app.models import Location
from email.policy import HTTP
from datetime import datetime, timedelta
import os
import logging
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
from daemonocle.cli import DaemonCLI
import paho.mqtt.client as mqtt

from app.forms import UserForm, DataUploadForm, DataDownloadForm
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

    def on_connect(client, userdata, flags, rc):
        click.echo("Connected with result code "+str(rc))

        # Subscribing in on_connect() means that if we lose the connection and
        # reconnect then subscriptions will be renewed.
        client.subscribe([('bbws-bsolo', 0), ('bws-sul2', 0), ('uns-ft', 0), ('pusair-bdg', 0), ('cimancis', 0), ('bwss2', 0), ('bwss4', 0), ('bws-kal3', 0), ('bws-sul1', 0), ('bws-kal1', 0), ('bws-pb', 0), ('bwss5', 0), ('upbbsolo', 0), ('bwsnt1', 0), ('bws-kal2', 0), ('btsungai', 0), ('bws-kal4', 0), ('float1', 0), ('dpublpp', 0), ('pdamgresik', 0), ('wikahutama', 0), ('bbwssul3', 0), ('purinilam', 0), ('palangkaraya', 0), ('pusdajatim', 0), ('dpuprklaten', 0), ('bwskal5', 0), ('bbwscitanduy', 0)])

    # The callback for when a PUBLISH message is received from the server.
    def on_message(client, userdata, msg):
        data = json.loads(msg.payload.decode('utf-8'))
        with open('/tmp/out.txt', 'w+') as f:
            f.write('{}\n'.format(data.get('device').split('/')[1]))
        sn = data.get('device').split('/')[1]
        #c.save()
        print(msg.topic+" "+msg.payload.decode('utf-8'))

    @app.cli.command(cls=DaemonCLI, daemon_params={'pid_file': '/var/run/prinus_capture.pid'})
    def prinus_capture():
        logging.basicConfig(
            filename='/var/log/daemonocle_example.log',
            level=logging.DEBUG, format='%(asctime)s [%(levelname)s] %(message)s',
        )
        logger = logging.getLogger(__name__)
        #app = create_app(Config)
        client = mqtt.Client()
        client.enable_logger(logger)
        client.on_connect = on_connect
        client.on_message = on_message
        client.connect('mqtt.prinus.net', 14983, 60)
        client.loop_forever()
        
    @app.cli.command('upload')
    def import_file(file):
        file = 'm_202207.csv' # file klimat
        #file = 'primaBot_2207-1_m_2022Jun.csv' # file ARR
        #file = 'primaBot_2207-2_m_2022Jul.csv' # file AWLR
        lines = open(file).readlines()
        msg = ''
        if len(lines) < 3:
            msg += 'File {} mungkin kosong.\n'.format(file)
            return msg
        #click.echo('{}{}'.format(lines[0], lines[1]))
        device = lines[0].split(' ')[0]
        headers = lines[1].strip().split(',')
        dates_col = ['sampling', 'up_since']
        for row in lines[2:]:
            cols = row.strip().split(',')
            content = {'device': device}
            for i in range(len(headers)):
                
                if headers[i] in dates_col:
                    sdate = cols[i].strip().replace('"', '')
                    tz = int(sdate[-3:])
                    val = datetime.strptime(sdate[:-3], '%Y-%m-%dT%H:%M:%S')
                    val -= timedelta(hours=tz)
                    val = int(val.timestamp())
                else:
                    if cols[i].strip() == 'nan':
                        val = 'null'
                    elif '.' in cols[i]:
                        val = float(cols[i])
                    else:
                        try:
                            val = int(cols[i])
                        except ValueError:
                            val = cols[i].strip(' "')
                if headers[i] == 'batt':
                    head = 'battery'
                elif headers[i] == 'sq':
                    head = 'signal_quality'
                else:
                    head = headers[i]
                #click.echo('{}: {}'.format(head, val))
                content[head] = val
            msg += content

    @app.cli.command('ke_jam')
    @click.option('--jam', help='Jam data yang akan diproses')
    @click.argument('sn')
    def ringkas_ke_jam(jam, sn):
        if not jam:
            jam = datetime.now().replace(minute=0, second=0) - timedelta(hours=1)
        click.echo(sn)
        click.echo(jam)
        
    @app.cli.command('browse')
    @click.option('--sn', help="")
    @click.option('--bl', help="'2020-02' untuk bulan Februari 2020")
    def browse(sn, bl):
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
        df.index = pd.to_datetime(df['sampling'], unit='s')
        if 'tipping_factor' in df:
            tf = df['tipping_factor']
        else:
            tf = 0.2
        df['rain'] = df['tick'] * tf
        df = df.resample('H').agg({'rain': 'sum', 'tick': 'count'})
        click.echo(df)
        #click.echo(df)
        #click.echo(pd.__version__)
        #click.echo(df.groupby(pd.Grouper(key='sampling', freq='1h'))['rain'].sum())
        #click.echo(df.info())
    
    @app.cli.command('list-logger')
    @click.option('--slug', help='SLUG tenant')
    def list_logger(slug=None):
        '''Menampilkan daftar logger'''
        if slug:
            tenant = Tenant.get(Tenant.slug==slug)
            for l in tenant.logger_set.order_by(Logger.sn):
                click.echo("{}\t{}".format(l.tipe, l.sn))
            return
        else:
            for l in Logger.select():
                click.echo("{}\t{}".format(l.tipe, l.sn))
            return
        
    @app.cli.command('list-location')
    def list_location():
        '''Menampilkan daftar lokasi'''
        pass
    
    @app.cli.command('list-user')
    def list_user():
        '''Menampilkan daftar user'''
        rst = User.select()
        for u in rst:
            t = u.tenant and u.tenant.nama or ''
            click.echo("{}\t{}\t{}".format(u.id, u.username, t))
            
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
        '''Memproses data dari primabot'''
        '''
        ids = [20540350, 20540352, 20540353, 20540354, 20540355]
        id = ids[0]
        rst = db.database.execute_sql("SELECT content FROM raw WHERE id IN ({})".format(ids))
        
        for r in rst.fetchall():
            ps_rec(r[0])
        '''
        s = '{"device": "primaBot/2002-2/0.6", "sampling": 1657612200, "distance": 4692, "signal_quality": 31, "battery": 9.96, "up_since": 1642763400, "time_set_at": 1657600500, "temperature": 40.66, "pressure": 994.12, "altitude": 160.51, "sensor": "Maxbotix"}'
        data = json.loads(s)
        click.echo(data.get('device'))
            
    def ps_rec(msg):
        d = json.loads(msg)
        sampling = datetime.fromtimestamp(d['sampling'])
        try:
            sn = d['device'].split('/')[1]
        except IndexError:
            return
        click.echo("{} pada {}".format(sn, sampling))
        logger = Logger.get(Logger.sn==sn)
        click.echo(logger.location)
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
      
    @app.route('/download', methods=['GET', 'POST'])
    @login_required
    def data_download():
        form = DataDownloadForm()
        banyak = 3
        bl = datetime.today() - \
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
        
    @app.route('/upload', methods=['POST', 'GET'])
    @login_required
    def data_upload():
        form = DataUploadForm()
        if form.validate_on_submit():
            f = form.to_import.data
            print(f.filename)
            with open('/tmp/out.txt', 'w') as outf:
                for l in f.readlines():
                    outf.write('{}\n'.format(l))
        return render_template('uploaded.html')
    
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
        data_upload_form = DataUploadForm()
        if current_user.is_authenticated:
            if not current_user.tenant:
                return render_template('home_master.html', data_upload_form=data_upload_form)
            else:
                if current_user.is_petugas:
                    return render_template('home_petugas.html', data_upload_form=data_upload_form)
                list_petugas = User.select().where(User.tenant==current_user.tenant).order_by(User.username)
                loggers_count = Logger.select().where(Logger.tenant==current_user.tenant).count()
                form_user = UserForm()
                return render_template('home_tenant.html', 
                                       loggers_count=loggers_count, 
                                       list_petugas=list_petugas,
                                       user_form=form_user, data_upload_form=data_upload_form)
        else:
            return render_template('welcome.html', form=LoginForm())
    
    return app
