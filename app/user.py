from datetime import datetime
from flask import Blueprint, request, render_template, redirect, flash, url_for
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
    new_user = User()
    if request.method == 'POST':
        form = UserForm(request.form, obj=new_user)
        if form.validate():
            form.populate_obj(new_user)
            new_user.save()
            flash('Sukses menambah %s' % new_user.usernama, 'success')
            return redirect(url_for('user'))
    else:
        if current_user.tenant:
            form = UserForm(tenant=current_user.tenant)
            form.location.choices = [(l.id, l.nama) for l in Location.select().where(Location.tenant==current_user.tenant)]
        else:
            form = UserForm()
            form.location.choices=[(l.id, l.nama) for l in Location.select()]
    return render_template('user/add.html', form=form)

@bp.route('/')
@login_required
def index():
    if current_user.tenant:
        users = User.select().where(User.tenant==current_user.tenant)
    else:
        users = User.select()
    return render_template('user/index.html', users=users)
