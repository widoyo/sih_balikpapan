from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, SelectField, BooleanField, PasswordField
from wtforms import HiddenField, SubmitField
from flask_wtf.file import FileField, FileRequired, FileAllowed
from wtforms.validators import ValidationError, DataRequired, Email, EqualTo

from .models import TIPE_POS

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
    username = StringField()
    new_password = StringField()
    
class UserForm(FlaskForm):
    username = StringField()
    password = PasswordField()
    is_petugas = BooleanField()
    location = SelectField()
    tenant = HiddenField()
    

class PosForm(FlaskForm):
    nama = StringField()
    tipe = SelectField(choices=TIPE_POS)
    elevasi = IntegerField()
    ll = StringField()
    
    
class TenantForm(FlaskForm):
    nama = StringField()
    
    
class LoggerForm(FlaskForm):
    location = SelectField()
    
    