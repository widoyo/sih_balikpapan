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
    center_map = "-1.4775533,116.4311507"
    if current_user.tenant:
        center_map = current_user.tenant.center_map
    return render_template('map.html', center_map=center_map)