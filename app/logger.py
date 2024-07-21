import datetime
import json
from flask import abort
from flask import Blueprint, request, render_template, Response
from flask_login import current_user, login_required
from peewee import DoesNotExist

from .models import Logger, Location, Raw, Daily
from .forms import LoggerForm

bp = Blueprint('logger', __name__)


@bp.route('/<sn>/download')
@login_required
def download(sn):
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
        sampling = datetime.datetime.strptime(sampling, '%Y-%m-%d')
    daily = Daily.select().where(Daily.sn==sn, 
                                 Daily.sampling.year==sampling.year,
                                 Daily.sampling.month==sampling.month).order_by(Daily.sampling)
    if len(daily) == 0:
        return abort(404)
    
    sample = json.loads(daily[0].content)
    header = 'sampling'
    if 'tick' in sample[0]:
        header += ',rain,rain30,tick,tipping_factor'
    if 'wind_speed' in sample[0]:
        header += ',wind_speed'
    if 'distance' in sample[0]:
        header += ',tma,distance,sensor_height,sensor_resolution'
    if 'alarm' in sample[0]:
        header += ',alarm'
    if 'alarm_time' in sample[0]:
        header += ',alarm_time'
    header += '\n'
    out = [header]
    for data in daily:
        rain51, rain52 = 0, 0
        rain5 = rain51
        jam = 0
        j = 0
        for d in json.loads(data.content):
            samp = datetime.datetime.fromtimestamp(d['sampling'])
            row = ''
            if 'tick' in d:
                # proses data hujan
                # sampling,rain,rain30,rain24,tick,tipping_factor,
                if jam != samp.hour:
                    j = 0
                    rain51, rain52 = 0, 0
                    jam = samp.hour
                if samp.minute >= 30:
                    j = 1
                    
                if j==0: 
                    rain51 += d['tick']
                    rain5 = rain51
                else: 
                    rain52 += d['tick']
                    rain5 = rain52
                row = ',{},{},{},{}'.format(d['tick']*d['tipping_factor'], rain5*d['tipping_factor'], d['tick'], d['tipping_factor'])
            if 'wind_speed' in sample[0]:
                row = row + ',{}'.format(d['wind_speed'])
            if 'distance' in sample[0]:
                tma = d['sensor_height'] - (d['distance'] * d['sensor_resolution'])
                row = row + ',{},{},{},{}'.format(tma, d['distance'], d['sensor_height'], d['sensor_resolution'])
            if 'alarm' in sample[0]:
                row = row + ',{}'.format(d['alarm'])
                out[samp.strftime('%Y-%m-%d %H:%M')] = row
            if 'alarm_time' in d:
                at = datetime.datetime.fromtimestamp(d['alarm_time'])
                row = row + ',{}'.format(at.strftime('%Y-%m-%d %H:%M:%S'))
            out.append(samp.strftime('%Y-%m-%d %H:%M:%S') + row + '\n')
    resp = Response(out, content_type='text/csv')
    resp.headers['Content-Disposition'] = "attachment; filename={}_{}.csv".format(logger.sn, sampling.strftime('%Y%b'))
    return resp

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
            del r['up_since']
            del r['time_set_at']
            del r['device']
            periodik.append(r)
        sp = sorted(periodik, key=lambda x: x['sampling'])
        periodik = sp
    except:
        pass
    cols = []
    if len(periodik):
        cols = ['sampling'] + [c for c in periodik[0].keys() if c != 'sampling']
    next_s = sampling + datetime.timedelta(days=1)
    prev_s = sampling - datetime.timedelta(days=1)
    
    ctx = {
        'logger': logger,
        'periodik': periodik,
        'sampling': sampling,
        'next_s': next_s,
        'prev_s': prev_s,
        'cols': cols,
    }

    return render_template('logger/show.html', ctx=ctx)

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