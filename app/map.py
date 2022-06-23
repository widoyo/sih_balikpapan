from flask import Blueprint, request, render_template
from flask_login import current_user, login_required

from .models import Logger

bp = Blueprint('map', __name__)


@bp.before_request
def before_request():
    if current_user.is_authenticated:
        current_user.last_seen = datetime.utcnow()

@bp.route('map')
def index():
    return render_template('map.html')