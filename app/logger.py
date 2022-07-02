from datetime import datetime
from flask import Blueprint, request, render_template
from flask_login import current_user, login_required

from .models import Logger, Location
from .forms import LoggerForm

bp = Blueprint('logger', __name__)


@bp.before_request
def before_request():
    if current_user.is_authenticated:
        current_user.last_seen = datetime.utcnow()


@bp.route('/<sn>/edit')
@login_required
def edit(sn):
    logger = Logger.get(Logger.sn==sn)
    form = LoggerForm()
    if current_user.tenant:
        form.location.choices = [(l.id, l.nama) for l in Location.select().where(Location.tenant==current_user.tenant)]
    else:
        form.location.choices = [(l.id, l.nama) for l in Location.select()]
    if form.validate_on_submit():
        pass
    return render_template('logger/edit.html', logger=logger, form=form)


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