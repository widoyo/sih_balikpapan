from datetime import datetime, timedelta
import pytz, json
from flask import Blueprint, request, render_template, redirect, flash, abort
from flask_login import current_user, login_required
from playhouse.flask_utils import get_object_or_404
from peewee import Cast
import pandas as pd
from .models import Location, Das, Ws, db
from .forms import PosForm, UserForm, NoteForm

bp = Blueprint('pos', __name__)


@bp.before_request
def before_request():
    if current_user.is_authenticated:
        current_user.last_seen = datetime.utcnow()
        current_user.save()

@bp.route('/pch/')
def pch():
    '''Tampilkan tentang curah hujan'''
    sampling = request.args.get('s')
    try:
        tahun,bulan,tanggal = sampling.split('/')
    except:
        tahun,bulan,tanggal = datetime.today().strftime('%Y/%m/%d').split('/')
    tgl = datetime(int(tahun), int(bulan), int(tanggal))
    pch = Location.select().where(Location.tipe=='1', Location.tenant==current_user.tenant)
    sql = "SELECT * from hourly WHERE location_id IN () AND sampling BETWEEN AND GROUP BY location_id"
    return render_template('pos/pch.html', poses=pch, tgl=tgl, _tgl=tgl - timedelta(days=1), tgl_= tgl + timedelta(days=1))

@bp.route('/pda/')
def pda():
    '''Tampilkan tentang Duga Air'''
    sampling = request.args.get('s')
    try:
        tahun,bulan,tanggal = sampling.split('/')
    except:
        tahun,bulan,tanggal = datetime.today().strftime('%Y/%m/%d').split('/')
    tgl = datetime(int(tahun), int(bulan), int(tanggal))
    pda = Location.select().where(Location.tipe=='2', Location.tenant==current_user.tenant)
    return render_template('pos/pda.html', poses=pda, tgl=tgl, _tgl=tgl - timedelta(days=1), tgl_= tgl + timedelta(days=1))

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


@bp.route('/<id>/<int:tahun>/<int:bulan>')
@login_required
def show_sebulan(id, tahun, bulan):
    bulan = datetime(tahun, bulan, 1)
    sbl = bulan - timedelta(days=1)
    ssd = bulan + timedelta(days=32)
    id = int(id.split('-')[0])
    pos = get_object_or_404(Location, (Location.id == id))
    if pos.tipe not in ('1', '2', '3'):
        return "Error: Data tipe pos {}: {}".format(pos.nama, pos.tipe)
    return render_template('pos/show_sebulan_{}.html'.format(pos.tipe), 
                           pos=pos, bln=bulan, _bln=sbl, bln_=ssd)


@bp.route('/<id>/<int:tahun>')
@login_required
def show_setahun(id, tahun):
    id = int(id.split('-')[0])
    thn = datetime.today().replace(year=tahun)
    thn_ = thn + timedelta(days=366)
    _thn = thn - timedelta(days=1)
    pos = get_object_or_404(Location, (Location.id == id))
    if pos.tipe not in ('1', '2', '3'):
        return "Error: Data tipe pos {}: {}".format(pos.nama, pos.tipe)
    return render_template('pos/show_setahun_{}.html'.format(pos.tipe), 
                           pos=pos, thn=thn, _thn=_thn, thn_=thn_)

@bp.route('/<id>/')
@login_required
def show(id):
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
        sql = "SELECT content from raw WHERE sn = ? AND (content->>'sampling')::INTEGER >= ? AND (content->>'sampling')::INTEGER <= ?"
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
    poses = Location.select().where(Location.tenant == current_user.tenant)
    wss = Ws.select().where(Ws.tenant == current_user.tenant)
    dass = Das.select().where(Das.tenant == current_user.tenant)
    #print(current_user.tenant.id)
    return render_template('pos/index.html', poses=poses, ws_list=wss, das_list=dass)