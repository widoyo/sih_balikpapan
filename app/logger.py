import datetime
import json
from flask import abort
from flask import Blueprint, request, render_template
from flask_login import current_user, login_required
from peewee import DoesNotExist

from .models import Logger, Location, Raw, Daily
from .forms import LoggerForm

bp = Blueprint('logger', __name__)


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
    try:
        logger = Logger.get(Logger.sn==sn)
        if logger.tenant != current_user.tenant:
            return abort(404)
    except DoesNotExist:
        return abort(404)
    
    sampling = request.args.get('s', '')
    if sampling == '':
        sampling = datetime.date.today()
    else:
        sampling = datetime.datetime.strptime(sampling, '%Y/%m/%d')
    daily = Daily.select().where(Daily.sn==sn, Daily.sampling==sampling).first()
    periodik = []
    try:
        for r in json.loads(daily.content):
            r['sampling'] = datetime.datetime.fromtimestamp(r['sampling'])
            periodik.append(r)
        sp = sorted(periodik, key=lambda x: x['sampling'])
        periodik = sp
    except:
        pass
    next_s = sampling + datetime.timedelta(days=1)
    prev_s = sampling - datetime.timedelta(days=1)

    return render_template('logger/show.html', logger=logger, periodik=periodik,
                           sampling=sampling, next_s=next_s, prev_s=prev_s)

@bp.route('/sehat')
@login_required
def sehat():
    logger_list = Logger.select().where(Logger.tenant==current_user.tenant).order_by(Logger.sn.asc())
    sampling = request.args.get('s', '')
    if sampling == '':
        sampling = datetime.date.today()
    else:
        sampling = datetime.datetime.strptime(sampling, '%Y-%m-%d')
    ds = dict([(d.sn, d.sehat()) for d in Daily.select().where(Daily.sn.in_([l.sn for l in logger_list]), Daily.sampling==sampling).order_by(Daily.sn.asc())])
    logger_sehat_list = []
    
    for ll in logger_list:
        ll.sehat = ds.get(ll.sn)
        logger_sehat_list.append(ll)
    
    next_s = sampling + datetime.timedelta(days=1)
    prev_s = sampling - datetime.timedelta(days=1)
    return render_template('logger/sehat.html', logger_list=logger_sehat_list,
                           sampling=sampling, next_s=next_s, prev_s=prev_s)


@bp.route('/', methods=['GET', 'POST'])
@bp.route('/index', methods=['GET', 'POST'])
@login_required
def index():
    logger = Logger.select().where(Logger.tenant==current_user.tenant).order_by(Logger.sn.asc())
    return render_template('logger/index.html', loggers=logger)