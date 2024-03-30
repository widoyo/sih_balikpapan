from datetime import datetime
from flask import Blueprint, request, render_template
from flask_login import current_user, login_required

from .models import Logger

bp = Blueprint('map', __name__)


@bp.before_request
def before_request():
    if current_user.is_authenticated:
        current_user.last_seen = datetime.utcnow()
        current_user.save()

@bp.route('/')
def index():
    pchs = [l for l in current_user.tenant.location_set if l.ll is not None and l.tipe in ('1', '4')]
    pdas = [l for l in current_user.tenant.location_set if l.ll is not None and l.tipe in ('2', '4')]
    return render_template('map.html', pchs=pchs, pdas=pdas)