from datetime import datetime
from flask import Blueprint, request, render_template, redirect, flash
from flask_login import current_user, login_required
from playhouse.flask_utils import get_object_or_404
from .models import Location
from .forms import PosForm, UserForm

bp = Blueprint('pos', __name__)


@bp.before_request
def before_request():
    if current_user.is_authenticated:
        current_user.last_seen = datetime.utcnow()
        current_user.save()

@bp.route('/pch/')
def pch():
    '''Tampilkan tentang curah hujan'''
    pch = Location.select().where(Location.tipe=='1', Location.tenant==current_user.tenant)
    return render_template('pos/pch.html', poses=pch)

@bp.route('/pda/')
def pda():
    '''Tampilkan tentang Duga Air'''
    pda = Location.select().where(Location.tipe=='2', Location.tenant==current_user.tenant)
    return render_template('pos/pda.html', poses=pda)

@bp.route('/add/', methods=['POST', 'GET'])
@login_required
def add():
    tipe = request.args.get('tipe')
    form = PosForm(tipe=tipe)
    if form.validate_on_submit():
        flash('Sukses')
        pos_baru = Location(nama=form.nama.data, tipe=form.tipe.data, tenant=current_user.tenant)
        pos_baru.modified = datetime.now()
        pos_baru.save()
        return redirect('/pos')
    return render_template('pos/add.html', form=form)

@bp.route('/<id>/edit')
@login_required
def edit(id):
    id = int(id.split('-')[0])
    pos = get_object_or_404(Location, (Location.id == id))
    if request.method == 'POST':
        pass
    return render_template('pos/edit.html', pos=pos)


@bp.route('/<id>/setahun')
@login_required
def show_setahun(id):
    id = int(id.split('-')[0])
    pos = get_object_or_404(Location, (Location.id == id))
    if pos.tipe not in ('1', '2', '3'):
        return "Error: Data tipe pos {}: {}".format(pos.nama, pos.tipe)
    return render_template('pos/show_setahun_{}.html'.format(pos.tipe), pos=pos)


@bp.route('/<id>/sebulan')
@login_required
def show_sebulan(id):
    id = int(id.split('-')[0])
    pos = get_object_or_404(Location, (Location.id == id))
    if pos.tipe not in ('1', '2', '3'):
        return "Error: Data tipe pos {}: {}".format(pos.nama, pos.tipe)
    return render_template('pos/show_sebulan_{}.html'.format(pos.tipe), pos=pos)


@bp.route('/<id>')
@login_required
def show(id):
    id = int(id.split('-')[0])
    pos = get_object_or_404(Location, (Location.id == id))
    if pos.tipe not in ('1', '2', '3'):
        return "Error: Data tipe pos {}: {}".format(pos.nama, pos.tipe)
    user_form = UserForm(is_petugas=True, tenant=current_user.tenant, location=pos)
    if user_form.validate_on_submit():
        pass
    return render_template('pos/show_{}.html'.format(pos.tipe), pos=pos, user_form=user_form)


@bp.route('/', methods=['GET', 'POST'])
@bp.route('/index', methods=['GET', 'POST'])
@login_required
def index():
    poses = Location.select().where(Location.tenant == current_user.tenant)
    #print(current_user.tenant.id)
    return render_template('pos/index.html', poses=poses)