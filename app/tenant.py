from datetime import datetime
from flask import Blueprint, request, render_template, flash, redirect
from flask_login import current_user, login_required
from playhouse.flask_utils import get_object_or_404
from .models import Location, Tenant
from .forms import TenantForm


bp = Blueprint('tenant', __name__)


@bp.before_request
def before_request():
    if current_user.is_authenticated:
        current_user.last_seen = datetime.utcnow()

@bp.route('/add', methods=['POST', 'GET'])
@login_required
def add():
    form = TenantForm(request.form)
    if request.method == 'POST' and form.validate():
        new_ = Tenant()
        new_.nama = form.nama.data
        new_.save()
        flash('Sukses')
        redirect('/tenant')
    return render_template('tenant/add.html', form=form)

@bp.route('/')
@login_required
def index():
    tenants = Tenant.select()
    return render_template('tenant/index.html', tenants=tenants)

