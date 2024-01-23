import datetime
import base64
import json
from zoneinfo import ZoneInfo
import pandas as pd
from enum import unique
from flask import url_for
from flask_login import UserMixin
from bcrypt import checkpw, hashpw, gensalt
import peewee as pw
from playhouse.flask_utils import FlaskDB
from playhouse.sqlite_ext import JSONField
#from playhouse.postgres_ext import JSONField

db = FlaskDB()

TIPE_POS = [(1, 'PCH'), (2, 'PDA'), (3, 'Klimatologi')]
TIPE_POS_COLOR = [(1, 'primary'), (2, 'danger'), (3, 'success')]

class Raw(db.Model):
    content = pw.TextField()
    received = pw.DateTimeField()
    sn = pw.CharField(max_length=10)
    
    @staticmethod
    def to_daily(sn: str, sampling: datetime):
        daily, created = Daily.get_or_create(sn=sn, sampling=sampling, defaults={'content': json.dumps([])})
        for d in daily.repopulate():
            Raw._to_daily(d)
        return daily

        
    @staticmethod
    def _to_daily(msg: dict):
        try:
            msg['sampling']
            sn = msg['device'].split('/')[1]
        except KeyError:
            return
        except ValueError:
            return
        try:
            logger = Logger.get(sn=sn)
        except Exception as e:
            return

        out = {'sampling': datetime.datetime.fromtimestamp(msg['sampling']) }
        tz = ZoneInfo('Asia/Jakarta')
        if logger.tenant.timezone:
            tz = ZoneInfo(logger.tenant.timezone)
        out['sampling'] = out['sampling'].astimezone(tz)

        logger.latest_sampling = out['sampling']
        logger.latest_battery = msg['battery']
        logger.latest_up = datetime.datetime.fromtimestamp(msg['up_since']).astimezone(tz)
        logger.save()
        print(logger.sn)
        
        location = None        
        if logger.location:
            location = logger.location
        daily, created = Daily.get_or_create(
            sn=sn, sampling=out['sampling'], 
            defaults={'content': json.dumps([msg]), 'location': location})
        if not created:
            content = json.loads(daily.content)
            if msg['sampling'] not in [c['sampling'] for c in content]:
                content.append(msg)
                daily.content = json.dumps(content)
                daily.save()
    

class Tenant(db.Model):
    nama = pw.CharField(max_length=35)
    slug = pw.CharField(max_length=12, unique=True)
    created = pw.DateTimeField(default=datetime.datetime.now)
    modified = pw.DateTimeField(null=True)
    alamat = pw.CharField(max_length=100, null=True)
    kodepos = pw.CharField(max_length=5, null=True)
    ll = pw.CharField(max_length=35, null=True)
    center_map = pw.CharField(max_length=60, null=True)
    zoom_map = pw.IntegerField(null=True)
    telegram_info_group = pw.TextField(null=True)
    telegram_info_id = pw.IntegerField(null=True)
    telegram_alert_group = pw.TextField(null=True)
    telegram_alert_id = pw.IntegerField(null=True)
    timezone = pw.CharField(max_length=35, default='Asia/Jakarta')
    email = pw.CharField(max_length=35, null=True)
    
    def to_dict(self):
        data = {
            'id': self.id,
            'nama': self.nama,
            '_links': {
                'self': url_for('api.get_tenant', id=self.id)
            },
            '_logger_set': [l.to_dict() for l in self.logger_set],
            '_location_set': [l.to_dict() for l in self.location_set]
        }
        return data
    
    def hujan_tanggal(self, tgl=datetime.datetime.today()):
        
        return tgl
    
class Das(db.Model):
    nama = pw.CharField(max_length=35, unique=True)
    tenant = pw.ForeignKeyField(Tenant)
    created_at = pw.DateTimeField(default=datetime.datetime.now)
    modified_at = pw.DateTimeField(null=True)
    alur = pw.TextField(null=True)
    
    def to_dict(self):
        data = {'nama': self.nama, 'tenant': self.tenant.nama, 'id': self.id}
        return data
    
    def from_dict(self, data, new=False):
        self.nama = data

class Ws(db.Model):
    nama = pw.CharField(max_length=35, unique=True)
    tenant = pw.ForeignKeyField(Tenant)
    created_at = pw.DateTimeField(default=datetime.datetime.now)
    modified_at = pw.DateTimeField(null=True)
    alur = pw.TextField(null=True)
    
class Location(db.Model):
    nama = pw.CharField(max_length=35)
    ll = pw.CharField(max_length=60, null=True)
    tenant = pw.ForeignKeyField(Tenant)
    created = pw.DateTimeField(default=datetime.datetime.now)
    modified = pw.DateTimeField(null=True)
    tipe = pw.CharField(max_length=3, null=True)
    elevasi = pw.IntegerField(null=True)
    latest_sampling = pw.DateTimeField(null=True)
    latest_up = pw.DateTimeField(null=True)
    das = pw.ForeignKeyField(Das, null=True)
    ws =  pw.ForeignKeyField(Ws, null=True)
    wilayah = pw.CharField(null=True)
    sh = pw.FloatField(null=True) # batas siaga Hijau dalam meter
    sk = pw.FloatField(null=True) # batas siaga Kuning dalam meter
    sm = pw.FloatField(null=True) # batas siaga Merah dalam meter
    desa = pw.CharField(max_length=30, null=True)
    kecamatan = pw.CharField(max_length=30, null=True)
    kabupaten = pw.CharField(max_length=30, null=True)
    
    def to_dict(self):
        aa = 'nama-ll-tipe-elevasi-latest_sampling-latest_up-sh-sk-sm'.split('-')
        data = dict([(l, getattr(self, l)) for l in aa])
        return data
    
    def str_tipe(self):
        try:
            return dict(TIPE_POS)[int(self.tipe)], dict(TIPE_POS_COLOR)[int(self.tipe)]
        except ValueError:
            return 'UNKNOWN', 'secondary'
    
    def get_sehari(self, day=datetime.date.today):
        print(day)
        
    class Meta:
        order_by = ['nama']
        
    
class Logger(db.Model):
    sn = pw.CharField(max_length=10)
    location = pw.ForeignKeyField(Location, null=True)
    created_at = pw.DateTimeField(default=datetime.datetime.now)
    modified_at = pw.DateTimeField(null=True)
    tenant = pw.ForeignKeyField(Tenant, null=True)
    tipe = pw.CharField(max_length=6, null=True)
    temp_cor = pw.FloatField(null=True)
    humi_cor = pw.FloatField(null=True)
    batt_cor = pw.FloatField(null=True)
    tipp_fac = pw.FloatField(null=True)
    ting_son = pw.FloatField(null=True)
    cols_show = pw.CharField(null=True)
    created = pw.DateTimeField(default=datetime.datetime.now)
    modified = pw.DateTimeField(null=True)
    son_res = pw.FloatField(null=True)
    latest = pw.DateTimeField(null=True)
    num_data = pw.IntegerField(default=0)
    latest_sampling = pw.DateTimeField(null=True)
    latest_up = pw.DateTimeField(null=True)
    latest_battery = pw.FloatField(null=True)
    sim  = pw.CharField(max_length=20, null=True)
    generasi = pw.IntegerField(default=3)
    sensors = pw.TextField(null=True) # catatan sensor yang terpasang
    
    class Meta:
        order_by = ['id']
        
    def to_dict(self):
        data = {
            'id': self.id,
            'sn': self.sn,
            'tipe': self.tipe,
            'tenant_id': self.tenant and self.tenant.id or None,
            'latest': datetime.datetime.now(),
            'up_since': datetime.datetime.now(),
            'first': datetime.datetime.now(),
            '_links': {
                'self': url_for('api.get_logger', sn=self.sn)
            }
        }
        return data

class Note(db.Model):
    object_type = pw.CharField(default='logger') # pos, daily
    object_id = pw.IntegerField()
    username = pw.CharField(max_length=35)
    content = pw.TextField()
    cdate = pw.DateTimeField(default=datetime.datetime.now)
    mdate = pw.DateTimeField(null=True)
    
    
class Petugas(db.Model):
    nama = pw.CharField(max_length=50)
    lokasi = pw.ForeignKeyField(Location)
    hp = pw.CharField(max_length=35, null=True)
    created = pw.DateTimeField(default=datetime.datetime.now)
    modified = pw.DateTimeField(null=True)
    
        
class User(UserMixin, db.Model):
    username = pw.CharField(unique=True, max_length=12)
    password = pw.CharField(max_length=255)
    is_active = pw.BooleanField(default=True)
    tenant = pw.ForeignKeyField(Tenant, null=True)
    email = pw.CharField(max_length=50, null=True)
    hp = pw.CharField(max_length=20, null=True)
    created = pw.DateTimeField(default=datetime.datetime.now)
    modified = pw.DateTimeField(null=True)
    location = pw.ForeignKeyField(Location, null=True)
    tz = pw.CharField(max_length=35, default='Asia/Jakarta')
    last_login = pw.DateTimeField(null=True)
    last_seen = pw.DateTimeField(null=True)
    token = pw.CharField(max_length=32)
    token_expiration = pw.DateTimeField()
    
    class Meta:
        table_name = 'users'
    
    def to_dict(self):
        data = {
            'id': self.id,
            'username': self.username,
            'last_seen': self.last_seen and self.last_seen.isoformat() or None,
            'tenant': self.tenant.to_dict(),
            '_links': {
                'self': url_for('api.get_user', id=self.id)
            }
        }
        return data
    
    def from_dict(self, data, new_user=False):
        for field in ['username', 'email']:
            if field in data:
                setattr(self, field, data[field])
        if new_user and 'password' in data:
            self.set_password(data['password'])

    def check_password(self, password):
        return checkpw(password.encode(), self.password.encode())
    
    def set_password(self, password):
        self.password = hashpw(password.encode('utf-8'), gensalt())
        
    def get_token(self, expires_in=3600):
        now = datetime.datetime.utcnow()
        if self.token and self.token_expiration > now + datetime.timedelta(seconds=60):
            return self.token
        import secrets
        self.token = secrets.token_urlsafe()
        self.token_expiration = now + datetime.timedelta(seconds=expires_in)
        self.save()
        return self.token
    
    def revoke_token(self):
        self.token_expiration = datetime.datetime.now() - datetime.timedelta(seconds=1)
        
    @staticmethod
    def check_token(token):
        try:
            user = User.get(User.token==token)
            if user.token_expiration < datetime.datetime.utcnow():
                return user
        except User.DoesNotExist:
            pass
        

class Daily(db.Model):
    '''Data per Hari, komilasi dari Hourly'''
    location = pw.ForeignKeyField(Location, null=True)
    sn = pw.CharField(max_length=10)
    sampling = pw.DateField() # Tanggal, start at jam 0
    rain = pw.IntegerField(null=True)
    tick = pw.IntegerField(null=True)
    distance = pw.FloatField(null=True) # data terakhir pada hari
    wlevel_a = pw.FloatField(null=True) # telemetri pagi
    wlevel_x = pw.FloatField(null=True) # telemetri siang
    wlevel_n = pw.FloatField(null=True) # telemetri sore
    num_data = pw.IntegerField(default=0)
    sq_a = pw.IntegerField(null=True)
    batt_a = pw.FloatField(null=True) # dalam volt
    m_rain = pw.FloatField(default=0) # Manual Rain, satuan mm
    m_wlevel_pa = pw.FloatField(null=True) # Manual TMA, satuan Meter Pagi
    m_wlevel_si = pw.FloatField(null=True) # Manual TMA, satuan Meter Siang
    m_wlevel_so = pw.FloatField(null=True) # Manual TMA, satuan Meter Sore
    petugas = pw.CharField(max_length=100, null=True) # username petugas, bisa comma separated
    num_start = pw.IntegerField(default=0) # banyaknya restart primabot pada jam ini
    content = pw.TextField(null=True)
    
    def sehat(self):
        newlist = [[r for r in json.loads(self.content) 
                    if datetime.datetime.fromtimestamp(r['sampling']).hour == h] for h in range(0, 24)]
        t = dict([(i,0) for i in range(0, 24)])
        t.update(dict([(datetime.datetime.fromtimestamp(o[0]['sampling']).hour, len(o)) for o in newlist if len(o)]))
        return t
    
    def battery(self):
        '''return list(jam, battery, sinyal)'''
        ret = []
        t = dict([(i,0) for i in range(0, 24)])
        jam = 0
        for c in json.loads(self.content):
            sampling = datetime.datetime.fromtimestamp(c['sampling'])
            if sampling.hour != jam:
                pass
        return ret
    
    def wlevels(self):
        '''return pagi, siang sore'''
        if 'distance' not in self.content:
            return []
        
        resolusi = 1
        tinggi_sonar = 10000
        try:
            logger = Logger.get(sn=self.sn)
            resolusi = logger.son_res
            tinggi_sonar = logger.ting_son
        except:
            pass
        data = [[(datetime.datetime.fromtimestamp(d['sampling']), (tinggi_sonar - d['distance'] * resolusi)) for d in json.loads(self.content) if datetime.datetime.fromtimestamp(d['sampling']).hour ==h] for h in range(0, 24)]
        ret = []
        for i in range(len(data)):
            if data[i]:
                ret.append((i, data[i]))
            else:
                ret.append((i, []))
        return ret
        
    def hourly_rain(self):
        if 'tick' not in self.content:
            return {}
        this_day = [r for r in json.loads(self.content) if datetime.datetime.fromtimestamp(r['sampling']).hour >= 7]
        next_day = Daily.select().where(Daily.sn==self.sn, Daily.sampling==self.sampling + datetime.timedelta(days=1)).first()
        if next_day:
            this_day = this_day + [r for r in json.loads(next_day.content) if datetime.datetime.fromtimestamp(r['sampling']).hour < 7]
        hourly_this_day = [[r for r in this_day if datetime.datetime.fromtimestamp(r['sampling']).hour == i] for i in range(0, 24)]
        hr = datetime.datetime.combine(self.sampling, datetime.time(7))
        out = dict([(hr + datetime.timedelta(hours=i), (0, 0)) for i in range(0, 24)]) # tick, num 
        out.update(dict([(datetime.datetime.fromtimestamp(r[0]['sampling']).replace(minute=0), (sum([j['tick'] for j in r]), len(r))) for r in hourly_this_day if len(r)]))
        
        return out
    
    def rain(self):
        rain, num = (0, 0)
        if self.hourly_rain():
            logger = Logger.get(sn=self.sn)
            rain = sum([v[0] for k, v in self.hourly_rain().items()]) * logger.tipp_fac
            num = sum([v[1] for k, v in self.hourly_rain().items()])
        return rain, num
        
    def repopulate(self, source='raw2'):
        '''Mengisi field content'''
        
        try:
            logger = Logger.get(sn=self.sn)
            tz = logger.tenant.timezone
        except:
            tz = 'Asia/Jakarta'
        sampling = datetime.datetime.combine(self.sampling, datetime.time())
        sampling = sampling.astimezone(ZoneInfo(tz))
        awal = int(sampling.timestamp())
        akhir = int(sampling.replace(hour=23, minute=56).timestamp())
        
        cursor = db.database.execute_sql(
            "SELECT content FROM raw \
                WHERE content->>'device' LIKE %s \
                    AND (content->>'sampling')::BIGINT BETWEEN %s AND %s ", ('%'+self.sn+'%', awal, akhir))
        return [c[0] for c in cursor]
        
        
    class Meta:
        order_by = ['-sampling']
        indexes = (
            (('sn', 'sampling'), True),
        )
        

class Hourly(db.Model):
    '''Data per jam, kompilasi dari 5 menitan'''
    location = pw.ForeignKeyField(Location, null=True)
    sn = pw.CharField(max_length=10)
    sampling = pw.DateTimeField(help_text='tanggal dan jam. Menit & Detik = 0') # tanggal dan jam. Menit & Detik = 0
    tick = pw.IntegerField(null=True, help_text='akumulasi tick') # nilai akumulasi tick
    rain = pw.IntegerField(null=True, help_text='akumulasi tick X tipp_factor') # akumulasi tick X tipp_factor
    distance = pw.IntegerField(null=True, help_text='distance pada jam') # distance terakhir pada jam
    distance_x = pw.IntegerField(null=True, help_text='Max') # distance max
    distance_n = pw.IntegerField(null=True, help_text='Min') # distance min
    wlevel = pw.FloatField(null=True, help_text='WLevel terakhir pada jam') # WLevel terakhir pada jam 
    wlevel_x = pw.FloatField(null=True, help_text='Max') # Max
    wlevel_n = pw.FloatField(null=True, help_text='Min') # Min
    num_data = pw.IntegerField(default=0, help_text='banyak data sejam') # banyak data
    sq = pw.IntegerField(null=True, help_text='rerata SQ') # rerata
    batt = pw.FloatField(null=True, help_text='rerata batt') # rerata
    num_start = pw.IntegerField(default=0, help_text='banyaknya restart primabot pada jam ini') # banyaknya restart primabot pada jam ini
    content = pw.TextField(null=True)
    
    class Meta:
        order_by = ['sampling']
        indexes = (('sn', 'sampling'), True),
    
    
class Offline(db.Model):
    '''Upload data dari Memory primaBot'''
    sn = pw.CharField(max_length=10)
    location = pw.CharField(max_length=50)
    fname = pw.CharField(max_length=100)
    content = pw.TextField()
    awal = pw.DateTimeField(null=True)
    akhir = pw.DateTimeField(null=True)
    banyak = pw.IntegerField(default=0)
    cdate = pw.DateTimeField(default=datetime.datetime.now)
    username = pw.CharField(null=True)
