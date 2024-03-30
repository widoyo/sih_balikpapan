import json
from datetime import datetime, timedelta
from flask import Blueprint, request, Response, render_template, redirect, flash, abort
from flask_login import current_user, login_required
from playhouse.flask_utils import get_object_or_404
from peewee import Cast
import pandas as pd
from .models import Location, Das, Ws, DownloadLog, Logger, Daily
from .forms import PosForm, UserForm, NoteForm

bp = Blueprint('pos', __name__)


@bp.before_request
def before_request():
    if current_user.is_authenticated:
        current_user.last_seen = datetime.utcnow()
        current_user.save()


class DictObj:
    def __init__(self, in_dict:dict):
        assert isinstance(in_dict, dict)
        for key, val in in_dict.items():
            if isinstance(val, (list, tuple)):
               setattr(self, key, [DictObj(x) if isinstance(x, dict) else x for x in val])
            else:
               setattr(self, key, DictObj(val) if isinstance(val, dict) else val)


@bp.route('/pch/')
@login_required
def pch():
    '''Tampilkan tentang curah hujan'''
    sampling = request.args.get('s')
    try:
        tahun,bulan,tanggal = sampling.split('/')
    except:
        yesterday = datetime.today() - timedelta(days=1)
        tahun,bulan,tanggal = yesterday.strftime('%Y/%m/%d').split('/')
    tgl = datetime(int(tahun), int(bulan), int(tanggal))
    start = tgl.replace(hour=7)
    end = (tgl + timedelta(days=1)).replace(hour=6)
    pch = Location.select().where(Location.tipe=='1', Location.tenant==current_user.tenant).order_by(Location.nama.asc())
    hch = dict([(p.id, {'pch': p, 'pagi': None, 'siang': None, 'malam': None, 
            'dini': None, 'telemetri': None, 'manual': None}) for p in pch])
    
    #sql = "SELECT * from hourly WHERE location_id IN () AND sampling BETWEEN AND GROUP BY location_id"
    hourly_ch = dict([(d.location_id, d) for d in Daily.select().where((Daily.location.in_(pch)) & (Daily.sampling==tgl.date()))])
    for k, v in hourly_ch.items():
        try: 
            logger = Logger.get(sn=k)
            tf = logger.tipp_fac
        except:
            tf = 0.2
        hch[k]['telemetri'] = "%0.1f" % v.rain()[0]
        hch[k]['manual'] = v.m_rain
        pagi = sum([r[0] for h, r in v.hourly_rain().items() if h.hour >= 7 and h.hour < 13]) * tf
        siang = sum([r[0] for h, r in v.hourly_rain().items() if h.hour >= 13 and h.hour < 19]) * tf
        malam = sum([r[0] for h, r in v.hourly_rain().items() if h.hour >= 19 and h.hour <= 23]) * tf
        malam += sum([r[0] for h, r in v.hourly_rain().items() if h.hour >= 0 and h.hour < 1]) * tf
        dini = sum([r[0] for h, r in v.hourly_rain().items() if h.hour >= 1 and h.hour < 7]) * tf
        hch[k]['pagi'] = pagi and "%0.1f" % pagi or '-'
        hch[k]['siang'] = siang and "%0.1f" % siang or '-'
        hch[k]['malam'] = malam and "%0.1f" % malam or '-'
        hch[k]['dini'] = dini and "%0.1f" % dini or '-'
        hch[k]['id'] = v.id

    return render_template(
        'pos/pch.html', 
        poses=hch.values(), 
        tgl=tgl, 
        _tgl=tgl - timedelta(days=1), 
        tgl_= tgl + timedelta(days=1),
        hourly_ch=hourly_ch)

@bp.route('/pda/')
@login_required
def pda():
    '''Tampilkan tentang Duga Air'''
    sampling = request.args.get('s')
    try:
        tahun,bulan,tanggal = sampling.split('/')
    except:
        tahun,bulan,tanggal = datetime.today().strftime('%Y/%m/%d').split('/')
    tgl = datetime(int(tahun), int(bulan), int(tanggal))
    pdas = Location.select().where(Location.tipe=='2', Location.tenant==current_user.tenant).order_by(Location.nama.asc())
    sns = [l.sn for l in current_user.tenant.logger_set]
    wl_pdas = dict([(l.id, 
                {'pda': l, 't6': None, 'm6': None, 't12': None, 'm12': None, 't18': None, 'm18': None}) 
               for l in pdas])

    for harian in Daily.select().where(Daily.location.in_(pdas), Daily.sampling==tgl.date()):
        for row in harian.wlevels():
            if len(row[1]):
                if row[0] == 6:
                    wl_pdas[harian.location_id].update({'t6': '%0.2f' % row[1][-1][1]})
                if row[0] == 12:
                    wl_pdas[harian.location_id].update({'t12': '%0.2f' % row[1][-1][1]})
                if row[0] == 18:
                    wl_pdas[harian.location_id].update({'t18': '%0.2f' % row[1][-1][1]})

        wl_pdas[harian.location_id].update({'m6': harian.m_wlevel_pa})
        wl_pdas[harian.location_id].update({'m12': harian.m_wlevel_si})
        wl_pdas[harian.location_id].update({'m18': harian.m_wlevel_so})
    return render_template('pos/pda.html', poses=wl_pdas.values(), tgl=tgl, _tgl=tgl - timedelta(days=1), 
                           tgl_= tgl + timedelta(days=1))

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


@bp.route('/pch/<id>/<int:tahun>/<int:bulan>', methods=['GET', 'POST'])
@login_required
def show_pch_sebulan(id, tahun, bulan):
    bulan = datetime(tahun, bulan, 1)
    sbl = bulan - timedelta(days=1)
    ssd = bulan + timedelta(days=32)
    if bulan.strftime("%Y%m") == datetime.today().strftime("%Y%m"):
        end_bl = datetime.today().day
    else:
        end_bl = (ssd.replace(day=1) - timedelta(days=1)).day
    id = int(id.split('-')[0])
    pos = get_object_or_404(Location, (Location.id == id))
    if pos.tipe not in ('1', '2', '3'):
        return "Error: Data tipe pos {}: {}".format(pos.nama, pos.tipe)

    if request.method == 'POST':
        rain_sebulan_per_jam = []
        for d in Daily.select().where(
            Daily.location_id==id, Daily.sampling.year==bulan.year, 
            Daily.sampling.month==bulan.month):
            rain_sebulan_per_jam += [(k.strftime('%Y-%m-%d %H:%M'), v[0], v[1]) for k, v in d.hourly_rain().items()]
        csv_data = 'Waktu,Hujan,Banyak Data\n'
        for r in rain_sebulan_per_jam:
            csv_data += ','.join(map(str, r))
            csv_data += '\n'
            
        resp = Response(csv_data, content_type='text/csv')
        resp.headers['Content-Disposition'] = "attachment; filename={}_{}.csv".format(pos.nama.replace(' ', '_'), bulan.strftime('%Y-%m_'))
        dl = DownloadLog.create(location=pos, 
                         sampling=bulan.strftime('%Y-%m'),
                         username=current_user.username,
                         size=len(rain_sebulan_per_jam))
        return resp

    data_sebulan = dict([((bulan + timedelta(days=i)).date(), (0, 0, 0, 0)) for i in range(0, end_bl)])
    data_sebulan.update(dict([(d.sampling, (d.rain()[0], d.rain()[1], d.m_rain, d)) for d in Daily.select().where(
        Daily.location_id==id, Daily.sampling.year==bulan.year, 
        Daily.sampling.month==bulan.month)]))
    out = [(k, v[0], v[1], v[2], v[3]) for k, v in data_sebulan.items()]
    
    return render_template('pos/show_sebulan_1.html'.format(pos.tipe), 
                           pos=pos, bln=bulan, data_sebulan=out,
                           _bln=sbl, bln_=ssd)


@bp.route('/pda/<id>/<int:tahun>/<int:bulan>', methods=['GET', 'POST'])
@login_required
def show_pda_sebulan(id, tahun, bulan):
    bulan = datetime(tahun, bulan, 1)
    sbl = bulan - timedelta(days=1)
    ssd = bulan + timedelta(days=32)
    if bulan.strftime("%Y%m") == datetime.today().strftime("%Y%m"):
        end_bl = datetime.today().day
    else:
        end_bl = (ssd.replace(day=1) - timedelta(days=1)).day
    id = int(id.split('-')[0])
    pos = get_object_or_404(Location, (Location.id == id))
    if pos.tipe not in ('1', '2', '3'):
        return "Error: Data tipe pos {}: {}".format(pos.nama, pos.tipe)

    data_sebulan = dict([((bulan + timedelta(days=i)).date(), ()) for i in range(0, end_bl)])
    data_sebulan.update(dict([(d.sampling, d) for d in Daily.select().where(
        Daily.location_id==id, Daily.sampling.year==bulan.year, 
        Daily.sampling.month==bulan.month)]))
    out = [k for k in data_sebulan]
    
    if request.method == 'POST':
        return "Ok end_bl: {}".format(end_bl)
    
    return render_template('pos/show_sebulan_2.html'.format(pos.tipe), 
                           pos=pos, bln=bulan, data_sebulan=out,
                           _bln=sbl, bln_=ssd)



@bp.route('/pda/<id>/<int:tahun>')
@login_required
def show_pda_setahun(id, tahun):
    id = int(id.split('-')[0])
    thn = datetime.today().replace(year=tahun)
    thn_ = thn + timedelta(days=366)
    _thn = thn - timedelta(days=1)
    pos = get_object_or_404(Location, (Location.id == id))
    if pos.tipe not in ('1', '2', '3'):
        return "Error: Data tipe pos {}: {}".format(pos.nama, pos.tipe)
    return render_template('pos/show_setahun_{}.html'.format(pos.tipe), 
                           pos=pos, thn=thn, _thn=_thn, thn_=thn_)


@bp.route('/pch/<id>/<int:tahun>')
@login_required
def show_pch_setahun(id, tahun):
    id = int(id.split('-')[0])
    thn = datetime.today().replace(year=tahun)
    thn_ = thn + timedelta(days=366)
    _thn = thn - timedelta(days=1)
    pos = get_object_or_404(Location, (Location.id == id))
    if pos.tipe not in ('1', '2', '3'):
        return "Error: Data tipe pos {}: {}".format(pos.nama, pos.tipe)
    return render_template('pos/show_setahun_{}.html'.format(pos.tipe), 
                           pos=pos, thn=thn, _thn=_thn, thn_=thn_)

@bp.route('/pch/<id>/', methods=['GET', 'POST'])
@login_required
def show_pch(id):
    sampling = request.args.get('s')
    if sampling:
        for sep in ['-', '/']:
            if sep in sampling:
                break
    try:
        tahun,bulan,tanggal = sampling.split(sep)
    except:
        tahun,bulan,tanggal = datetime.today().strftime('%Y/%m/%d').split('/')
    tgl = datetime(int(tahun), int(bulan), int(tanggal)).astimezone()
    _sta = tgl.replace(hour=7).astimezone()
    _end = (_sta + timedelta(days=1)).replace(hour=6, minute=55)
    if _sta > _end:
        _sta -= timedelta(days=1)
    if _end > datetime.now().astimezone():
        _end = datetime.now().astimezone()
    id = int(id.split('-')[0])
    pos = get_object_or_404(Location, (Location.id == id))
    if pos.tipe not in ('1', '2', '3'):
        return "Error: Data tipe pos {}: {}".format(pos.nama, pos.tipe)
    
    thisday_ = Daily.select().where((Daily.location_id==id) & (Daily.sampling==_sta.date())).first()

    if request.method == 'POST':
        logger = Logger.get(sn=thisday_.sn)
        data_hujan = [(datetime.fromtimestamp(c['sampling']).strftime('%Y-%m-%d %H:%M'), c['tick']*logger.tipp_fac) for c in json.loads(thisday_.content)]
        data_hujan.sort(key=lambda x: x[0])
        out = '"Tanggal Jam", Hujan\n'
        for d in data_hujan:
            out += '"{}", {}\n'.format(d[0], d[1])

        resp = Response(out, content_type='text/csv')
        resp.headers['Content-Disposition'] = "attachment; filename={}_{}.csv".format(pos.nama.replace(' ', '_'), thisday_.sampling.strftime('%Y-%m-%d_'))
        dl = DownloadLog.create(location=pos, 
                         sampling=thisday_.sampling.strftime('%Y-%m-%d'),
                         username=current_user.username,
                         size=len(data_hujan))
        return resp
    
    num_data_ = 0
    hourlyrain_  = {}
    rain_ = 0
    m_rain_ = 0
    logger = None
    if thisday_:
        hourlyrain_ = thisday_.hourly_rain()
        num_data_ = thisday_.rain()[1]
        rain_ = thisday_.rain()[0]
        m_rain_ = thisday_.m_rain
        logger = Logger.get(sn=thisday_.sn)
    note_form = NoteForm(object_type='location', object_id=pos.id)
    return render_template('pos/show_1.html'.format(pos.tipe), pos=pos, 
                           tgl=tgl, _tgl=tgl - timedelta(days=1), tgl_= tgl + timedelta(days=1), 
                           note_form=note_form, m_rain=m_rain_, 
                           hourlyrain=hourlyrain_, num_data=num_data_, rain=rain_,
                           logger=logger)

@bp.route('/pda/<id>/')
@login_required
def show_pda(id):
    sampling = request.args.get('s')
    if sampling:
        for sep in ['-', '/']:
            if sep in sampling:
                break
    try:
        tahun,bulan,tanggal = sampling.split(sep)
    except:
        tahun,bulan,tanggal = datetime.today().strftime('%Y/%m/%d').split('/')
    tgl = datetime(int(tahun), int(bulan), int(tanggal)).astimezone()
    _sta = tgl.replace(hour=7).astimezone()
    _end = (_sta + timedelta(days=1)).replace(hour=6, minute=55)
    if _sta > _end:
        _sta -= timedelta(days=1)
    if _end > datetime.now().astimezone():
        _end = datetime.now().astimezone()
    id = int(id.split('-')[0])
    pos = get_object_or_404(Location, (Location.id == id))
    if pos.tipe not in ('1', '2', '3'):
        return "Error: Data tipe pos {}: {}".format(pos.nama, pos.tipe)
    thisday_ = Daily.select().where((Daily.location_id==id) & (Daily.sampling==_sta.date())).first()
    num_data_ = 0
    hourlyrain_  = {}
    rain_ = 0
    m_rain_ = 0
    wlevels = []
    logger = None
    if thisday_:
        hourlyrain_ = thisday_.hourly_rain()
        num_data_ = thisday_.rain()[1]
        rain_ = thisday_.rain()[0]
        m_rain_ = thisday_.m_rain
        wlevels = thisday_.wlevels()
        logger = Logger.get(sn=thisday_.sn)
    note_form = NoteForm(object_type='location', object_id=pos.id)
    return render_template('pos/show_2.html'.format(pos.tipe), pos=pos, 
                           tgl=tgl, _tgl=tgl - timedelta(days=1), tgl_= tgl + timedelta(days=1), 
                           note_form=note_form, m_rain=m_rain_, 
                           hourlyrain=hourlyrain_, num_data=num_data_, rain=rain_,
                           logger=logger)


@bp.route('/<id>/pd')
@login_required
def show_with_pd(id):
    sampling = request.args.get('s')
    if sampling:
        for sep in ['-', '/']:
            if sep in sampling:
                break
    try:
        tahun,bulan,tanggal = sampling.split(sep)
    except:
        tahun,bulan,tanggal = datetime.today().strftime('%Y/%m/%d').split('/')
    tgl = datetime(int(tahun), int(bulan), int(tanggal)).astimezone()
    _sta = tgl.replace(hour=7).astimezone()
    _end = (_sta + timedelta(days=1)).replace(hour=6, minute=55)
    if _sta > _end:
        _sta -= timedelta(days=1)
    if _end > datetime.now().astimezone():
        _end = datetime.now().astimezone()
    dft = pd.DataFrame(index=pd.date_range(datetime.fromtimestamp(int(_sta.strftime('%s'))), datetime.fromtimestamp(int(_end.strftime('%s'))), freq='5T'))
    id = int(id.split('-')[0])
    pos = get_object_or_404(Location, (Location.id == id))
    if pos.tipe not in ('1', '2', '3'):
        return "Error: Data tipe pos {}: {}".format(pos.nama, pos.tipe)
    raws = []
    new_df = pd.DataFrame()
    ds_num = pd.Series()
    ds_rain = pd.Series()
    if pos.logger_set:
        logger = pos.logger_set[0]
        sql = "SELECT content from raw WHERE sn=%s AND (content->>'sampling')::INTEGER >= %s AND (content->>'sampling')::INTEGER <= %s"
        rst = db.database.execute_sql(sql, (logger.sn, _sta.strftime('%s'), _end.strftime('%s')))
        print(dir(rst))
        #raws = Raw.select(Raw.content).where(Raw.sn==logger.sn).limit(288).order_by(Raw.id)
        df = pd.DataFrame([r[0] for r in rst.fetchall()])
        print(logger.sn)
        print(_sta)
        print(_end)
        print(df.info())
        if db.database.rows_affected(rst) > 0:
            df['sampling'] = pd.to_datetime(df['sampling'], unit='s')
            df.set_index('sampling', inplace=True)
            df = dft.join(df)
            ds_rain = df.groupby(pd.Grouper(freq='1h'))['tick'].sum()
            ds_num = df.groupby(pd.Grouper(freq='1h'))['battery'].count()
            #print(ds_num.info())
            new_df = pd.DataFrame({'banyak': ds_num, 'curah_hujan': ds_rain}, index=df.index)
        
    user_form = UserForm(is_petugas=True, tenant=current_user.tenant, location=pos)
    if user_form.validate_on_submit():
        pass
    note_form = NoteForm(object_type='location', object_id=pos.id)
    return render_template('pos/show_{}.html'.format(pos.tipe), pos=pos, 
                           tgl=tgl, _tgl=tgl - timedelta(days=1), tgl_= tgl + timedelta(days=1), 
                           user_form=user_form, note_form=note_form, show=show, raws=ds_num, rains=ds_rain)


@bp.route('/', methods=['GET', 'POST'])
@bp.route('/index', methods=['GET', 'POST'])
@login_required
def index():
    if current_user.location:
        abort(404)
    poses = Location.select().where(Location.tenant == current_user.tenant).order_by(Location.nama)
    wss = Ws.select().where(Ws.tenant == current_user.tenant)
    dass = Das.select().where(Das.tenant == current_user.tenant)
    #print(current_user.tenant.id)
    return render_template('pos/index.html', poses=poses, ws_list=wss, das_list=dass)