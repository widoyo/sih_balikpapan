from datetime import datetime
from flask import Blueprint, request, render_template
from flask_login import current_user, login_required

from .models import Logger

bp = Blueprint('logger', __name__)


@bp.before_request
def before_request():
    if current_user.is_authenticated:
        current_user.last_seen = datetime.utcnow()


@bp.route('/<sn>')
@login_required
def show(sn):
    logger = Logger.get(Logger.sn==sn)
    return render_template('logger/show.html', logger=logger)

@bp.route('/sehat')
@login_required
def sehat():
    return render_template('logger/sehat.html')


@bp.route('/', methods=['GET', 'POST'])
@bp.route('/index', methods=['GET', 'POST'])
@login_required
def index():
    logger = Logger.select().where(Logger.tenant==current_user.tenant)
    return render_template('logger/index.html', loggers=logger)