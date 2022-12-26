import datetime
from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, SelectField, BooleanField, PasswordField
from wtforms import HiddenField, SubmitField, DateField, DateTimeField, FloatField
from flask_wtf.file import FileField, FileRequired, FileAllowed
from wtforms.validators import ValidationError, DataRequired, Email, EqualTo

from .models import TIPE_POS

class NoteForm(FlaskForm):
    object_type = HiddenField()
    object_id = HiddenField()
    content = StringField()
    submit = SubmitField()
    
class ManualChForm(FlaskForm):
    location = HiddenField()
    sampling = DateField('Tanggal Data')
    ch = FloatField('Curah Hujan (mm)', default=0)
    submit = SubmitField('Kirim')
    
class ManualTmaForm(FlaskForm):
    location = HiddenField()
    sampling = DateField('Tanggal Data')
    waktu = StringField()
    tma = StringField('TMA (meter)')
    submit = SubmitField('Kirim')
    
class DataDownloadForm(FlaskForm):
    location = SelectField(validators=[])
    bulan = SelectField(validators=[])
    submit = SubmitField()
    
class DataUploadForm(FlaskForm):
    to_import = FileField("File Data", validators=[FileRequired(), FileAllowed(['csv'], "File CSV dari primabot")])
    submit = SubmitField('Upload')
    
class DasForm(FlaskForm):
    nama = StringField()
    
class PasswordForm(FlaskForm):
    new_password = StringField()
    
class UserForm(FlaskForm):
    username = StringField('Username')
    password = PasswordField('Password')
    location = SelectField()
    tenant = HiddenField()
    submit = SubmitField('Kirim')
    

class PosForm(FlaskForm):
    nama = StringField('Nama')
    tipe = SelectField(choices=TIPE_POS)
    elevasi = IntegerField('Elevasi (mdpl)')
    ll = StringField('Koordinat Pos Pada Peta')
    
    
class TenantForm(FlaskForm):
    nama = StringField()
    
    
class LoggerForm(FlaskForm):
    location = SelectField()
    
    