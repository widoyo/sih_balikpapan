import os
import time
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime, timedelta
import shutil
from daemonocle.cli import DaemonCLI
import paho.mqtt.client as mqtt
import click
from flask import json
import pandas as pd
import numpy as np

from app.models import db, Tenant, Logger, User, Location

def register(app):
    def on_connect(client, userdata, flags, rc):
        click.echo("Connected with result code "+str(rc))

        # Subscribing in on_connect() means that if we lose the connection and
        # reconnect then subscriptions will be renewed.
        client.subscribe([('bbws-bsolo', 0), ('bws-sul2', 0), ('uns-ft', 0), ('pusair-bdg', 0), ('cimancis', 0), ('bwss2', 0), ('bwss4', 0), ('bws-kal3', 0), ('bws-sul1', 0), ('bws-kal1', 0), ('bws-pb', 0), ('bwss5', 0), ('upbbsolo', 0), ('bwsnt1', 0), ('bws-kal2', 0), ('btsungai', 0), ('bws-kal4', 0), ('float1', 0), ('dpublpp', 0), ('pdamgresik', 0), ('wikahutama', 0), ('bbwssul3', 0), ('purinilam', 0), ('palangkaraya', 0), ('pusdajatim', 0), ('dpuprklaten', 0), ('bwskal5', 0), ('bbwscitanduy', 0)])

    # The callback for when a PUBLISH message is received from the server.
    def on_message(client, userdata, msg):
        data = json.loads(msg.payload.decode('utf-8'))
        try:
            sn = data.get('device').split('/')[1]
        except IndexError:
            click.echo('SN tidak ditemukan')
            click.echo(data)
            return
        logger = Logger.get(Logger.sn==sn)
        lid = None
        if logger.location:
            lid = logger.location.id
        rain = None
        wlevel = None
        if data.get('tick', None) != None:
            if logger.tipp_fac and logger.tipp_fac > 0:
                tf = logger.tipp_fac
            else:
                tf = 0.2
            rain = data.get('tick') * tf
        if data.get('distance', None) != None:
            wlevel = data.get('distance')
            
        ret = {'sn': sn, 'location_id': lid, 'sampling': datetime.fromtimestamp(data.get('sampling'))}
        if rain: ret.update({'rain': rain, 'tick': data.get('tick')})
        if wlevel: ret.update({'wlevel': wlevel, 'distance': data.get('distance')})
        with open('/tmp/out.txt', 'a') as f:
            f.write('{}\n'.format(str(ret)))

    def insert_into_hourly(data):
        click.echo(data)
    
    @app.cli.command(cls=DaemonCLI, daemon_params={'pid_file': '/var/run/prinus_capture.pid'})
    def listen_prinus():
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
    
    @app.cli.command('make-downloadable')
    @click.argument('tid')
    @click.option('--bl', help='tahun-bl')
    def make_downloadable(tid, bl):
        '''Membuat file zip per bulan berisi file-file csv'''
        dirname = 'pbot'
        if not os.path.exists(dirname):
            os.mkdir(dirname)
        tenant = Tenant.get(int(tid))
        os.environ['TZ'] = tenant.timezone
        time.tzset()
        for l in tenant.logger_set:
            make_file(l.sn, bl)
        
        # create zip file
        if len(os.listdir(dirname)) < 1:
            return
        nama_bulan = datetime.strptime(bl, '%Y-%m')
        arch_name = 'data_{}'.format(nama_bulan.strftime('%b_%Y'))
        dest_dir = '{}/{}/'.format(app.config['ARCH_DATA_DIR'], tenant.slug)
        if not os.path.exists(dest_dir):
            os.mkdir(dest_dir)
        shutil.make_archive(arch_name, 'zip', root_dir=dirname)
        if os.path.isfile(os.path.join(dest_dir, arch_name + '.zip')):
            os.remove(os.path.join(dest_dir, arch_name + '.zip'))
        shutil.move(arch_name + '.zip', dest_dir)
        # delete p_*.csv files
        for f in os.listdir(dirname):
            os.remove(dirname + '/' + f)
                    
    def make_file(sn, bl):
        '''Browsing data (table 'raw')'''
        #sn = '1910-28'
        try:
            logger = Logger.get(Logger.sn==sn)
        except Logger.DoesNotExits:
            logger = None
        t,b = bl.split('-')
        bulan = datetime(int(t), int(b), 1, 7)
        _sta = int(bulan.strftime('%s'))
        # _sta = 1648767600
        _end = (bulan + timedelta(days=32)).replace(day=1, hour=6, minute=55).strftime('%s')
        # _end = 1648857300
        dft = pd.DataFrame(index=pd.date_range(datetime.fromtimestamp(int(_sta)), datetime.fromtimestamp(int(_end)), freq='5T'))
        click.echo('SN: {}'.format(sn))
        rst = db.database.execute_sql("SELECT content FROM raw WHERE sn='{}' AND (content->>'sampling')::int >= {} AND (content->>'sampling')::int < {} ORDER BY id ".format(sn, _sta, _end))
        data = [r[0] for r in rst.fetchall()]
        click.echo('len(data): {}'.format(len(data)))
        if len(data) == 0: return
        df = pd.DataFrame(data)
        click.echo(df.info())
        df['sampling'] = pd.to_datetime(df['sampling'], unit='s')
        #df.drop(columns=['device', 'time_set_at', 'signal_quality', 'pressure', 'altitude', 'temperature'], inplace=True)
        df.set_index('sampling', inplace=True)
        #ds_batt = df.groupby(pd.Grouper(freq='1h'))['battery'].mean().round(1)
        df = dft.join(df)
        #click.echo(mys.to_string())
        #df = dft.join(df)
        #click.echo(df.info())
        ds_rain = None
        ds_wlevel_a = None
        ds_wlevel_x = None
        ds_wlevel_n = None
        ds_num = df.groupby(pd.Grouper(freq='1h'))['battery'].count()
        nama_lokasi = 'namalokasi'
        tf = 0.2
        if logger:
            if logger.location:
                nama_lokasi = ''.join([c.replace(' ', '_') for c in logger.location.nama if c.isalnum() or c.isspace()])
            if logger.tipp_fac:
                if logger.tipp_fac > 0:
                    tf = logger.tipp_fac
        if 'tick' in df:
            # data dari primabot ARR
            #if 'tipping_factor' in df: tf = df['tipping_factor'][0]
            #df['rain'] = df['tick'] * tf
            ds_rain = df.groupby(pd.Grouper(freq='1h'))['tick'].sum()
            ds_rain = ds_rain.map(lambda x: x * tf, na_action='ignore').round(1)
        
        if 'distance' in df:
            # data dari primabot AWLR Sonar (Maxbotix)
            if logger:
                son_res = logger.son_res
                ting_son = logger.ting_son
            else:
                if 'sensor_resolution' in df:
                    son_res  = df['sensor_resolution']
                if 'sensor_height' in df:
                    ting_son = df['sensor_height']
            if son_res == None:
                son_res = 0.1 # default resolusi maxbotix mm
            if ting_son == None:
                # default 10 meter
                ting_son = 10000              
            ds_wlevel_a = df.groupby(pd.Grouper(freq='1h'))['distance'].mean()
            ds_wlevel_n = df.groupby(pd.Grouper(freq='1h'))['distance'].max()
            ds_wlevel_x = df.groupby(pd.Grouper(freq='1h'))['distance'].min()
            ds_wlevel_a = ds_wlevel_a.map(lambda x: (ting_son - (x * son_res)) / 100.0, na_action='ignore').round(2)
            ds_wlevel_x = ds_wlevel_x.map(lambda x: (ting_son - (x * son_res)) / 100.0, na_action='ignore').round(2)
            ds_wlevel_n = ds_wlevel_n.map(lambda x: (ting_son - (x * son_res)) / 100.0, na_action='ignore').round(2)
        
        # kemas output ke file
        fname = 'pbot/p_{lokasi}_{sn}_{blth}.csv'.format(lokasi=nama_lokasi, sn=sn, blth=bulan.strftime('%b%Y'))
        note = '{} - {}\n'.format(nama_lokasi, sn)

        if logger.tipe == 'arr':        
            # Nambahi catatan untuk ARR
            note += 'Curah Hujan (mm)\nDasar perhitungan:\n Tipping factor: {} mm\n'.format(tf)
            newdf = pd.DataFrame({'banyak': ds_num, 'curah_hujan': ds_rain})
        if logger.tipe == 'awlr':
            # Nambahi catatan untuk AWLR
            note += 'Tinggi Muka Air (meter)\nDasar perhitungan:\n Tinggi Sonar: {} cm\n Resolusi Sonar: {}\n'.format(ting_son, son_res == 1 and 'cm' or 'mm')
            newdf = pd.DataFrame({'banyak': ds_num, 'tma_max': ds_wlevel_x, 'tma_average': ds_wlevel_a, 'tma_min': ds_wlevel_n})

        newdf.to_csv(fname, index_label='sampling')
        #click.echo(ds_num.to_string())

        with open(fname, 'r') as ori: data = ori.read()
        with open(fname, 'w') as dest: dest.write(note + '\n' + data)
        #df = df.resample('H').agg({'rain': 'sum', 'tick': 'count'})
        #click.echo(df.info())


    @app.cli.command('browse')
    @click.option('--sn', help="")
    @click.option('--bl', help="'2020-02' untuk bulan Februari 2020")
    def browse(sn, bl):
        '''Browsing data (table 'raw')'''
        #sn = '1910-28'
        try:
            logger = Logger.get(Logger.sn==sn)
        except Logger.DoesNotExits:
            logger = None
        t,b = bl.split('-')
        bulan = datetime(int(t), int(b), 1, 7)
        _sta = int(bulan.strftime('%s'))
        # _sta = 1648767600
        _end = (bulan + timedelta(days=32)).replace(day=1, hour=6, minute=55).strftime('%s')
        # _end = 1648857300
        dft = pd.DataFrame(index=pd.date_range(datetime.fromtimestamp(int(_sta)), datetime.fromtimestamp(int(_end)), freq='5T'))
        
        rst = db.database.execute_sql("SELECT content FROM raw WHERE sn='{}' AND content->>'sampling' >= {} AND content->>'sampling' < {} ORDER BY id ".format(sn, _sta, _end))
        data = [json.loads(r[0]) for r in rst.fetchall()]
        if not data: return
        df = pd.DataFrame(data)
        df['sampling'] = pd.to_datetime(df['sampling'], unit='s')
        #df.drop(columns=['device', 'time_set_at', 'signal_quality', 'pressure', 'altitude', 'temperature'], inplace=True)
        df.set_index('sampling', inplace=True)
        #ds_batt = df.groupby(pd.Grouper(freq='1h'))['battery'].mean().round(1)
        df = dft.join(df)
        #click.echo(mys.to_string())
        #df = dft.join(df)
        #click.echo(df.info())
        ds_rain = None
        ds_wlevel_a = None
        ds_wlevel_x = None
        ds_wlevel_n = None
        ds_num = df.groupby(pd.Grouper(freq='1h'))['battery'].count()
        nama_lokasi = 'namalokasi'
        tf = 0.2
        if logger:
            if logger.location:
                nama_lokasi = ''.join([c.replace(' ', '_') for c in logger.location.nama if c.isalnum() or c.isspace()])
            if logger.tipp_fac:
                if logger.tipp_fac > 0:
                    tf = logger.tipp_fac
        if 'tick' in df:
            # data dari primabot ARR
            #if 'tipping_factor' in df: tf = df['tipping_factor'][0]
            #df['rain'] = df['tick'] * tf
            ds_rain = df.groupby(pd.Grouper(freq='1h'))['tick'].sum()
            ds_rain = ds_rain.map(lambda x: x * tf, na_action='ignore').round(1)
        
        if 'distance' in df:
            # data dari primabot AWLR Sonar (Maxbotix)
            if logger:
                son_res = logger.son_res
                ting_son = logger.ting_son
            else:
                if 'sensor_resolution' in df:
                    son_res  = df['sensor_resolution']
                if 'sensor_height' in df:
                    ting_son = df['sensor_height']
            if son_res == None:
                son_res = 0.1 # default resolusi maxbotix mm
            if ting_son == None:
                # default 10 meter
                ting_son = 10000              
            ds_wlevel_a = df.groupby(pd.Grouper(freq='1h'))['distance'].mean()
            ds_wlevel_n = df.groupby(pd.Grouper(freq='1h'))['distance'].max()
            ds_wlevel_x = df.groupby(pd.Grouper(freq='1h'))['distance'].min()
            ds_wlevel_a = ds_wlevel_a.map(lambda x: (ting_son - (x * son_res)) / 100.0, na_action='ignore').round(2)
            ds_wlevel_x = ds_wlevel_x.map(lambda x: (ting_son - (x * son_res)) / 100.0, na_action='ignore').round(2)
            ds_wlevel_n = ds_wlevel_n.map(lambda x: (ting_son - (x * son_res)) / 100.0, na_action='ignore').round(2)
        
        # kemas output ke file
        fname = 'p_{lokasi}_{sn}_{blth}.csv'.format(lokasi=nama_lokasi, sn=sn, blth=bulan.strftime('%b%Y'))
        note = '{} - {}\n'.format(nama_lokasi, sn)

        if logger.tipe == 'arr':        
            # Nambahi catatan untuk ARR
            note += 'Curah Hujan (mm)\nDasar perhitungan:\n Tipping factor: {} mm\n'.format(tf)
            newdf = pd.DataFrame({'banyak': ds_num, 'curah_hujan': ds_rain})
        if logger.tipe == 'awlr':
            # Nambahi catatan untuk AWLR
            note += 'Tinggi Muka Air (meter)\nDasar perhitungan:\n Tinggi Sonar: {} cm\n Resolusi Sonar: {}\n'.format(ting_son, son_res == 1 and 'cm' or 'mm')
            newdf = pd.DataFrame({'banyak': ds_num, 'tma_max': ds_wlevel_x, 'tma_average': ds_wlevel_a, 'tma_min': ds_wlevel_n})

        newdf.to_csv(fname, index_label='sampling')
        #click.echo(ds_num.to_string())

        with open(fname, 'r') as ori: data = ori.read()
        with open(fname, 'w') as dest: dest.write(note + '\n' + data)
        #df = df.resample('H').agg({'rain': 'sum', 'tick': 'count'})
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
        for l in Location.select():
            if l.tenant:
                click.echo('{} {} {}'.format(l.id, l.nama, l.tenant))
            else:
                click.echo('{} {}'.format(l.id, l.nama))

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
        
