import datetime
import base64
import os
import json
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
        self.token = base64.b64encode(os.urandom(24)).decode('utf-8')
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
        return None

class Daily(db.Model):
    '''Data per Hari, komilasi dari Hourly'''
    location = pw.ForeignKeyField(Location, null=True)
    sn = pw.CharField(max_length=10)
    sampling = pw.DateField() # Tanggal, start jam 7, pada hari lalu
    rain = pw.IntegerField(default=0)
    wlevel_a = pw.FloatField(null=True) # average
    wlevel_x = pw.FloatField(null=True) # Max
    wlevel_n = pw.FloatField(null=True) # Min
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
    
    class Meta:
        order_by = ['-sampling']
        

class Hourly(db.Model):
    '''Data per jam, kompilasi dari 5 menitan'''
    location = pw.ForeignKeyField(Location, null=True)
    sn = pw.CharField(max_length=10)
    sampling = pw.DateTimeField(help_text='tanggal dan jam. Menit & Detik = 0') # tanggal dan jam. Menit & Detik = 0
    tick = pw.IntegerField(default=0, help_text='akumulasi tick') # nilai akumulasi tick
    rain = pw.IntegerField(default=0, help_text='akumulasi tick X tipp_factor') # akumulasi tick X tipp_factor
    distance = pw.IntegerField(null=True, help_text='distance pada jam') # distance pada jam
    distance_x = pw.IntegerField(null=True, help_text='Max') # distance max
    distance_n = pw.IntegerField(null=True, help_text='Min') # distance min
    wlevel_a = pw.FloatField(null=True, help_text='Rerata') # average
    wlevel_x = pw.FloatField(null=True, help_text='Max') # Max
    wlevel_n = pw.FloatField(null=True, help_text='Min') # Min
    num_data = pw.IntegerField(default=0, help_text='banyak data sejam') # banyak data
    sq_a = pw.IntegerField(null=True, help_text='rerata SQ') # rerata
    batt_a = pw.FloatField(null=True, help_text='rerata batt') # rerata
    num_start = pw.IntegerField(default=0, help_text='banyaknya restart primabot pada jam ini') # banyaknya restart primabot pada jam ini
    content = pw.TextField(null=True)
    
    
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