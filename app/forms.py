from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, SelectField, BooleanField, PasswordField, HiddenField, SubmitField
from wtforms.validators import ValidationError, DataRequired, Email, EqualTo

from .models import TIPE_POS

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
    
    