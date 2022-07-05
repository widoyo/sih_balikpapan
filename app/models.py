import datetime
import base64
import os
from enum import unique
from flask_login import UserMixin
from bcrypt import checkpw, hashpw, gensalt
import peewee as pw
from playhouse.flask_utils import FlaskDB

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
    
    
class Das(db.Model):
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
    wilayah = pw.CharField(null=True)
    sh = pw.FloatField(null=True) # batas siaga Hijau dalam meter
    sk = pw.FloatField(null=True) # batas siaga Kuning dalam meter
    sm = pw.FloatField(null=True) # batas siaga Merah dalam meter
    
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
    

class Note(db.Model):
    object = pw.IntegerField(unique=True)
    object_id = pw.IntegerField()
    username = pw.CharField(max_length=35)
    content = pw.TextField()
    created = pw.DateTimeField(default=datetime.datetime.now)
    
    
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
    created = pw.DateTimeField(default=datetime.datetime.now)
    modified = pw.DateTimeField(null=True)
    is_petugas = pw.BooleanField(default=False)
    location = pw.ForeignKeyField(Location, null=True)
    tz = pw.CharField(max_length=35, default='Asia/Jakarta')
    last_login = pw.DateTimeField(null=True)
    last_seen = pw.DateTimeField(null=True)
    token = pw.CharField(max_length=32)
    token_expiration = pw.DateTimeField()
    
    class Meta:
        table_name = 'users'
    
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
    location = pw.ForeignKeyField(Location, null=True)
    sn = pw.CharField(max_length=10)
    sampling = pw.DateField()
    content = pw.TextField()
        

class Hourly(db.Model):
    location = pw.ForeignKeyField(Location, null=True)
    sn = pw.CharField(max_length=10)
    sampling = pw.DateTimeField()
    content = pw.TextField()
        
    
# $2y$10$ziru/DpvwZOvGp7pNNcU5u0pcUVdFHPV0Z7/NCTsruaq/YdAiklJ.