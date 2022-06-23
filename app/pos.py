from datetime import datetime
from flask import Blueprint, request, render_template, redirect, flash
from flask_login import current_user, login_required
from playhouse.flask_utils import get_object_or_404
from .models import Location
from.forms import PosForm

bp = Blueprint('pos', __name__)


@bp.before_request
def before_request():
    if current_user.is_authenticated:
        current_user.last_seen = datetime.utcnow()

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


@bp.route('/<id>')
@login_required
def show(id):
    id = int(id.split('-')[0])
    pos = get_object_or_404(Location, (Location.id == id))
    return render_template('pos/show.html', pos=pos)


@bp.route('/', methods=['GET', 'POST'])
@bp.route('/index', methods=['GET', 'POST'])
@login_required
def index():
    poses = Location.select().where(Location.tenant == current_user.tenant)
    #print(current_user.tenant.id)
    return render_template('pos/index.html', poses=poses)