from datetime import datetime
from flask import Blueprint, request, render_template, redirect, flash, url_for, abort
from flask_login import current_user, login_required
from playhouse.flask_utils import get_object_or_404
from .models import Location, User
from .forms import PosForm, UserForm, PasswordForm

bp = Blueprint('user', __name__)


@bp.before_request
def before_request():
    if current_user.is_authenticated:
        current_user.last_seen = datetime.utcnow()


@bp.route('/<username>/password', methods=['GET', 'POST'])
@login_required
def set_password(username):
    user = User.select().where(User.username==username)
    return render_template('/user/set_password.html', user=user)


@bp.route('/add', methods=['POST', 'GET'])
@login_required
def add():
    if current_user.tenant:
        form = UserForm(tenant=current_user.tenant)
        form.location.choices = [('null', 'Kantor')] + [(l.id, l.nama) for l in Location.select().where(Location.tenant==current_user.tenant)]
    else:
        form = UserForm()
        form.location.choices=[(l.id, l.nama) for l in Location.select()]
    errors = None
    if form.validate_on_submit():
        new_user, created = User.get_or_create(username=form.username.data, 
                                               location=form.location.data,
                                               password=form.password.data,
                                               tenant=form.tenant.data)
        new_user.set_password(form.password.data)
        flash('Sukses menambah %s' % new_user.username, 'success')
        return redirect(url_for('user'))
    else:
        errors = form.errors
    return render_template('user/add.html', form=form, errors=errors)

@bp.route('/')
@login_required
def index():
    if current_user.location:
        abort(404)
    if current_user.tenant:
        users = User.select().where(User.tenant==current_user.tenant)
    else:
        users = User.select()
    return render_template('user/index.html', users=users)
