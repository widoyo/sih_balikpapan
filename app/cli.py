import os
import time
import logging
from zoneinfo import ZoneInfo
import pytz
from logging.handlers import RotatingFileHandler
from datetime import datetime, timedelta
import shutil
from daemonocle.cli import DaemonCLI
import paho.mqtt.client as mqtt
import click
from flask import json
import pandas as pd
import numpy as np
from peewee import DoesNotExist

from app.models import db, Tenant, Logger, User, Location, Raw, Hourly, Daily

logging.basicConfig(
    filename='daemonocle_example.log',
    level=logging.DEBUG, format='%(asctime)s [%(levelname)s] %(message)s',
)
app_logger = logging.getLogger(__name__)

def to_hourly(data: dict):
    """
    msg dari primabot disiapkan utk ditambahkan ke data per jam
    """
    if not data:
        return
    (hourly, created) = Hourly.get_or_create(
        sn=data.get('sn'), 
        sampling=data.get('sampling').replace(minute=0),
        defaults={'num_data': 1,
                  'rain': data.get('rain'), 
                  'tick': data.get('tick'),
                  'distance': data.get('distance'),
                  'distance_n': data.get('distance'),
                  'distance_x': data.get('distance'),
                  'wlevel': data.get('wlevel'),
                  'wlevel_n': data.get('wlevel'),
                  'wlevel_x': data.get('wlevel'),
                  'location': data.get('location_id')})
    if not created:
        if data.get('distance'):
            hourly.distance_n = data.get('distance') < hourly.distance_n and data.get('distance') or hourly.distance_n
            hourly.distance_x = data.get('distance') > hourly.distance_x and data.get('distance') or hourly.distance_x
            hourly.wlevel_n = data.get('wlevel') < hourly.wlevel_n and data.get('wlevel') or hourly.wlevel_n
            hourly.wlevel_x = data.get('wlevel') > hourly.wlevel_x and data.get('wlevel') or hourly.wlevel_x
        try: 
            hourly.rain += data.get('rain')
        except TypeError:
            pass
        try:
            hourly.tick += data.get('tick')
        except TypeError:
            pass
        try:
            hourly.num_data += 1
        except TypeError:
            pass
    hourly.save()
    return hourly


def ps_rec(msg: str):
    d = json.loads(msg)
    sampling = datetime.fromtimestamp(d['sampling'])
    tzinfo = ZoneInfo('Asia/Jakarta')
    try:
        sn = d['device'].split('/')[1]
    except IndexError:
        return
    out = dict(sn=sn, sampling=sampling)
    #logger = Logger.get(sn=sn)
    #click.echo("{} pada {}".format(sn, sampling))
            
    try:
        logger = Logger.get(Logger.sn==sn)
        logger.latest = sampling
        logger.num_data = logger.num_data + 1
        logger.save()
    except DoesNotExist:
        return
    location = logger.location
    #click.echo(logger.location)
    #get_Hourly
    if location:
        out.update({'location': location.nama, 'location_id': location.id})
        tzinfo = ZoneInfo(logger.tenant.timezone)
    out['sampling'] = out['sampling'].replace(tzinfo=tzinfo)
    if 'tick' in d:
        tipping_factor = 0.2
        if logger.tipp_fac and logger.tipp_fac > 0:
            tipping_factor = logger.tipp_fac
        out.update({'tick': d['tick']})
        out['rain'] = tipping_factor * d['tick']
        #click.echo('tick: {} * {}'.format(d['tick'], tipping_factor))
    if 'distance' in d:
        out.update({'distance': d['distance']})
        sensor_height = logger.ting_son or 1000
        sensor_resolution = logger.son_res or 1
        wlevel = d['distance'] - (sensor_height * sensor_resolution)
        out.update({'wlevel': wlevel})
        #click.echo('dist: {} {} {}'.format(d['distance'], sensor_height, sensor_resolution))
        #click.echo('distance: {}, sensor_height: {}, sensor_resolution: {}'.format(d['distance'], d['sensor_height'], d['sensor_resolution']))
    if 'temperature' in d:
        out.update({'temperature': d['temperature']})
    if 'humidity' in d:
        out.update({'humidity': d['humidity']})
    if 'win_speed' in d:
        out.update({'wind_speed': d['wind_speed']})
    if 'wind_direction' in d:
        out.update({'wind_direction': d['wind_direction']})
    if 'sun_radiation' in d:
        out.update({'sun_radiation': d['sun_radiation']})
    #click.echo(datetime.fromtimestamp(d['sampling']))
    if 'wl_scale' in d:
        out.update({'wl_scale': d['wl_scale']})
        # long map(long x, long in_min, long in_max, long out_min, long out_max) {
        #   return (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min;
        # }
        # in_min = 0, out_min = 1023 (atmega 328p)
        # out_min = 0 (dasar sungai)
        # out_max = Muka Air Maksimum (config by user)
        # 
    return out


def _get_hour(sn: str, jam: datetime):
    """
    Mengambil data dalam sejam dan outputkan ringkasan
    """
    try:
        logger = Logger.get(sn=sn)
    except DoesNotExist:
        print('Tidak ditemukan')
        return
    tenant = logger.tenant
    tipping_factor = logger.tipp_fac or 0.2
    jam = jam.astimezone(pytz.timezone(logger.tenant.timezone))
    _sta = jam.replace(minute=0, second=0)
    print(_sta)
    _end = jam.replace(minute=55, second=0)
    sql = '''SELECT content from raw WHERE sn = %s AND (content->>'sampling')::bigint >= %s AND (content->>'sampling')::bigint <= %s ORDER BY id'''
    rst = db.database.execute_sql(sql, (sn, _sta.strftime('%s'), _end.strftime('%s')))
    print(_sta - _sta.utcoffset())
    for r in rst:
        print(r.content)
    
def _get_day(sn: str, tgl: datetime):
    """
    Mengambil rain&wlevel dijadikan ke daily"""
    try:
        logger = Logger.get(sn=sn)
    except DoesNotExist:
        print('Tidak ditemukan')
        return
    tenant = logger.tenant
    tipping_factor = logger.tipp_fac or 0.2
    tgl = tgl.astimezone(pytz.timezone(logger.tenant.timezone))
    _sta = tgl.replace(hour=7)
    _end = (tgl + timedelta(days=1)).replace(hour=6, minute=55)
    sql = '''SELECT content from raw WHERE sn = %s AND (content->>'sampling')::bigint >= %s AND (content->>'sampling')::bigint <= %s ORDER BY id'''
    rst = db.database.execute_sql(sql, (sn, (_sta - _sta.utcoffset()).strftime('%s'), (_end - _end.utcoffset()).strftime('%s')))
    click.echo(sql % (sn, (_sta - _sta.utcoffset()).strftime('%s'), (_end - _end.utcoffset()).strftime('%s')))
    dft = pd.DataFrame(index=pd.date_range(_sta, end=_end, freq='5T', tz=pytz.timezone(logger.tenant.timezone)))
    df = pd.DataFrame([r[0] for r in rst.fetchall()])
    if df.empty:
        return
    #print(df.info())
    df['sampling'] = pd.to_datetime(df['sampling'], unit='s', utc=True).map(lambda x: x.tz_convert(logger.tenant.timezone))
    df.set_index('sampling', inplace=True)
    df = dft.join(df)
    ds_num = df.groupby(pd.Grouper(freq='1h'))['battery'].count()
    ds_batt = df.groupby(pd.Grouper(freq='1D'))['battery'].tail(1)
    try:
        ds_signal = df.groupby(pd.Grouper(freq='1D'))['signal_quality'].tail(1)
    except KeyError:
        pass
    ds_rain = df.groupby(pd.Grouper(freq='1h'))['tick'].sum()
    ds_tick = df.groupby(pd.Grouper(freq='1h'))['tick'].sum()
    ds_rain = ds_rain.map(lambda x: x * tipping_factor, na_action='ignore').round(1)
    #print(df['battery'].tail(1))
    print(df['battery'].fillna(method='ffill').tail(1))
    print(ds_num.to_dict())
    #print(df['signal_quality'].fillna(method='ffill').tail(1))
    print((df['tick'].count() / 288) * 100, '%')

def register(app):
    
    @app.cli.command('hourly')
    @click.option('--n', default=5, help='banyaknya yang akan ditampilkan')
    def _show_hourly(n=5):
        """Menampilkan data hourly hari ini"""
        click.echo("Banyak Record: {}".format(Hourly.select().count()))
        for h in Hourly.select().order_by(Hourly.id.desc()).limit(n):
            click.echo("{} {}".format(h.sn, h.sampling))
        
    def on_connect(client, userdata, flags, rc):
        click.echo("Connected with result code "+str(rc))
        #client.app_logger.info("Connected: " + str(rc))
        #insert_into_hourly()
        # Subscribing in on_connect() means that if we lose the connection and
        # reconnect then subscriptions will be renewed.
        client.subscribe([('bbws-bsolo', 0), ('bws-sul2', 0), ('uns-ft', 0), ('pusair-bdg', 0), ('cimancis', 0), ('bwss2', 0), ('bwss4', 0), ('bws-kal3', 0), ('bws-sul1', 0), ('bws-kal1', 0), ('bws-pb', 0), ('bwss5', 0), ('upbbsolo', 0), ('bwsnt1', 0), ('banjarmasin', 0), ('btsungai', 0), ('bws-kal4', 0), ('float1', 0), ('dpublpp', 0), ('pdamgresik', 0), ('wikahutama', 0), ('bbwssul3', 0), ('purinilam', 0), ('palangkaraya', 0), ('pusdajatim', 0), ('dpuprklaten', 0), ('bwskal5', 0), ('bbwscitanduy', 0)])

    # The callback for when a PUBLISH message is received from the server.
    def on_message(client, userdata, msg):
        data = json.loads(msg.payload.decode('utf-8'))
        try:
            sn = data.get('device').split('/')[1]
        except IndexError:
            app_logger.info('SN tidak ditemukan: ' + data.get('device'))
            click.echo('SN tidak ditemukan')
            click.echo(data)
            return
        app_logger.info('SN: ' + sn)
        #logger = Logger.get(Logger.sn==sn)
        rst = db.database.execute_sql('''SELECT id from logger WHERE sn=%s''', (sn))

        #out = ps_rec(msg.payload.decode('utf-8'))
        #to_hourly(out)
        #with open('/tmp/out.txt', 'a') as f:
        #    f.write(str(out))

    
    @app.cli.command(cls=DaemonCLI, daemon_params={'pid_file': 'prinus_capture.pid',
                                                   'work_dir': '.'})
    def listen_prinus():
        """Listen MQTT insert/update table hourly"""
        #app = create_app(Config)
        client = mqtt.Client()
        client.enable_logger(app_logger)
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


    @app.cli.command('make-downloadable')
    @click.argument('tid')
    @click.option('--bl', help='tahun-bl')
    def make_downloadable(tid, bl):
        '''Membuat file zip per bulan berisi file-file csv'''
        dirname = 'pbot'
        if not os.path.exists(dirname):
            os.mkdir(dirname)
        tenant = Tenant.get(int(tid))
        tz = tenant.timezone or 'Asia/Jakarta'
        for l in tenant.logger_set:
            make_file(l.sn, bl, tz)
        
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
                    
    def make_file(sn, bl, tz):
        '''Browsing data (table 'raw')'''
        #sn = '1910-28'
        try:
            logger = Logger.get(Logger.sn==sn)
        except Logger.DoesNotExits:
            logger = None
        t,b = bl.split('-')
        bulan = datetime(int(t), int(b), 1).astimezone(pytz.timezone(tz))
        _sta = bulan.replace(hour=7)
        # _sta = 1648767600
        _end = (bulan + timedelta(days=32)).replace(day=1, hour=6, minute=55)
        today = datetime.now().astimezone(tz=pytz.timezone(tz))
        if bulan.month == today.month:
            _end = today
        # _end = 1648857300
        click.echo('_sta: {}'.format(_sta))
        click.echo('_end: {}'.format(_end))
        dft = pd.DataFrame(index=pd.date_range(_sta, end=_end, freq='5T', tz=tz))
        click.echo('SN: {}'.format(sn))
        rst = db.database.execute_sql("SELECT content FROM raw WHERE sn='{}' AND \
            (content->>'sampling')::int >= {} AND \
                (content->>'sampling')::int < {} \
                    ORDER BY id ".format(sn, (_sta - _sta.utcoffset()).strftime('%s'), _end.strftime('%s')))
        data = [r[0] for r in rst.fetchall()]
        click.echo('len(data): {}'.format(len(data)))
        if len(data) == 0: return
        df = pd.DataFrame(data)
        click.echo(df.info())
        df['sampling'] = pd.to_datetime(df['sampling'], unit='s', utc=True).map(lambda x: x.tz_convert(tz))
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
            ds_wlevel_s = df.groupby(pd.Grouper(freq='1h'))['distance'].std()
            ds_wlevel_a = ds_wlevel_a.map(lambda x: (ting_son - (x * son_res)) / 100.0, na_action='ignore').round(2)
            ds_wlevel_x = ds_wlevel_x.map(lambda x: (ting_son - (x * son_res)) / 100.0, na_action='ignore').round(2)
            ds_wlevel_n = ds_wlevel_n.map(lambda x: (ting_son - (x * son_res)) / 100.0, na_action='ignore').round(2)
            ds_wlevel_s = ds_wlevel_s.map(lambda x: (ting_son - (x * son_res)) / 100.0, na_action='ignore').round(2)
        
        # kemas output ke file
        fname = 'pbot/p_{lokasi}_{sn}_{blth}.csv'.format(lokasi=nama_lokasi, sn=sn, blth=bulan.strftime('%b%Y'))
        note = '{} - {}\n'.format(nama_lokasi, sn)

        newdf = pd.DataFrame()

        if logger.tipe == 'arr':        
            # Nambahi catatan untuk ARR
            note += 'Curah Hujan (mm), Timezone: {}\nDasar perhitungan:\n Tipping factor: {} mm\n'.format(tz, tf)
            newdf = pd.DataFrame({'banyak': ds_num, 'curah_hujan': ds_rain})
        if logger.tipe == 'awlr':
            # Nambahi catatan untuk AWLR
            note += 'Tinggi Muka Air (meter), Timezone: {}\nDasar perhitungan:\n Tinggi Sonar: {} cm\n Resolusi Sonar: {}\n'.format(tz, ting_son, son_res == 1 and 'cm' or 'mm')
            newdf = pd.DataFrame({'banyak': ds_num, 'tma_max': ds_wlevel_x, 'tma_average': ds_wlevel_a, 'tma_min': ds_wlevel_n})

        newdf.to_csv(fname, index_label='sampling')
        #click.echo(ds_num.to_string())

        with open(fname, 'r') as ori: data = ori.read()
        with open(fname, 'w') as dest: dest.write(note + '\n' + data)
        #df = df.resample('H').agg({'rain': 'sum', 'tick': 'count'})
        #click.echo(df.info())

    @app.cli.command('get-day')
    @click.argument('sn')
    @click.argument('sampling')
    def get_day(sn, sampling):
        for spliter in ('-', '/'):
            try:
                (tahun, bulan, tanggal) = sampling.split(spliter)
                break
            except:
                pass
        _get_day(sn, datetime(int(tahun), int(bulan), int(tanggal)))
        
    @app.cli.command('browse')
    @click.option('--sn', help="")
    @click.option('--bl', help="'2020-02' untuk bulan Februari 2020")
    def browse(sn, bl):
        '''Browsing data (table 'raw')'''
        #sn = '1910-28'
        try:
            logger = Logger.get(Logger.sn==sn)
        except Logger.DoesNotExist:
            logger = None
        t,b = bl.split('-')
        bulan = datetime(int(t), int(b), 1, 7)
        _sta = int(bulan.strftime('%s'))
        # _sta = 1648767600
        _end = (bulan + timedelta(days=32)).replace(day=1, hour=6, minute=55).strftime('%s')
        # _end = 1648857300
        dft = pd.DataFrame(index=pd.date_range(datetime.fromtimestamp(int(_sta)), datetime.fromtimestamp(int(_end)), freq='5T'))
        
        rst = db.database.execute_sql("SELECT content FROM raw WHERE sn='{}' AND (content->>'sampling')::INTEGER >= {} AND (content->>'sampling')::INTEGER < {} ORDER BY id ".format(sn, _sta, _end))
        for r in rst.fetchall():
            click.echo(r[0])
        data = []
        #data = [json.loads(r[0]) for r in rst.fetchall()]
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
            for l in Logger.select().order_by(Logger.sn):
                
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

    @app.cli.command('sehat')
    @click.option('--sn', help='SN primabot')
    @click.option('--s', help='Sampling: 2022-01-31')
    def test_hitungan_pandas(sn='2103-5', s=''):
        '''Menampilkan data 1 sn 1 hari'''
        logger = Logger.get(Logger.sn==sn)
        tenant = logger.tenant
        _sta = datetime(2022,10,14, 6).astimezone(pytz.timezone(logger.tenant.timezone))
        _end = datetime(2022,10,15,7).astimezone(pytz.timezone(logger.tenant.timezone))
        sql = '''SELECT content from raw WHERE sn in (%s) AND (content->>'sampling')::bigint >= %s AND (content->>'sampling')::bigint <= %s ORDER BY id'''
        rst = db.database.execute_sql(sql, (','.join([l.sn for l in tenant.logger_set]), (_sta - _sta.utcoffset()).strftime('%s'), (_end - _end.utcoffset()).strftime('%s')))
        dft = pd.DataFrame(index=pd.date_range(_sta, end=_end, freq='5T', tz=pytz.timezone(logger.tenant.timezone)))
        df = pd.DataFrame([r[0] for r in rst.fetchall()])
        df['sampling'] = pd.to_datetime(df['sampling'], unit='s', utc=True).map(lambda x: x.tz_convert(logger.tenant.timezone))
        df.set_index('sampling', inplace=True)
        df = dft.join(df)
        ds_num = df.groupby(pd.Grouper(freq='1h'))['battery'].count()
        ds_rain = df.groupby(pd.Grouper(freq='1h'))['tick'].sum()
        ds_rain = ds_rain.map(lambda x: x * 0.2, na_action='ignore').round(1)
        out = {}
        for i, o in ds_num.items():
            out = {i: [o]}
        for i, o in ds_rain.items():
            click.echo(i)
            click.echo(ds_num[i])
            click.echo(o)
            
    @app.cli.command('get_hourly')
    @click.argument('sn')
    @click.argument('s')
    def get_hourly(sn, s):
        rst = db.execute_sql("SELECT content FROM raw WHERE ")
        click.echo(sn)
        click.echo(s)
    
    
    @app.cli.command('ps')
    @click.argument('start')
    @click.argument('end')
    def ps(start, end):
        '''Memproses data dari primabot'''
        _start = datetime.strptime(start, "%Y/%m/%d")
        _end = datetime.strptime(end, "%Y/%m/%d")
        cr = db.database.execute_sql("SELECT content \
            FROM raw \
                WHERE (content->>'sampling')::BIGINT BETWEEN %s AND %s", 
                (int(_start.timestamp()), int(_end.timestamp())))
        click.echo(_start.toordinal())
        for row in cr:
            click.echo(row[0]['device'])
            Raw._to_daily(row[0])

