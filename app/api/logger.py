import datetime
import pandas as pd
from flask import jsonify, request, json
from playhouse.flask_utils import get_object_or_404
from app.api import bp
from app.api.auth import basic_auth
from app.models import Logger, Raw

@bp.route('/logger/<sn>/raw', methods=['GET'])
#@basic_auth.login_required
def get_logger_raw(sn):
    sampling = request.args.get('s', '')
    num = 288
    if sampling == '':
        sampling = datetime.datetime.now()
    else:
        try:
            sampling = datetime.datetime.strptime(sampling, '%Y-%m-%d')
        except ValueError:
            try:
                sampling = datetime.datetime.strptime(sampling, '%Y-%m')
                num = 288 * 31
            except ValueError:
                try:
                    sampling = datetime.datetime.strptime(sampling, '%Y')
                    num = 288 * 31 * 12
                except ValueError:
                    pass
    sampling = sampling.replace(hour=6, minute=55)
    rst = Raw.select().where((Raw.sn==sn) & (Raw.received > sampling)).limit(num).order_by(Raw.id)
    if not rst.count():
        return jsonify({})
    raw = [r.content for r in rst]
    dft = pd.DataFrame(index=pd.date_range(sampling, periods=num, freq='5T'))
    df = pd.DataFrame([json.loads(r.content) for r in rst])
    
    df['sampling'] = pd.to_datetime(df['sampling'], unit='s')
    df.set_index('sampling', inplace=True)
    df = dft.join(df)
    ds_rain = None
    ds_num = df.groupby(pd.Grouper(freq='1h'))['battery'].count()
    ds_rain = df.groupby(pd.Grouper(freq='1h'))['tick'].sum()
    end = datetime.datetime.now()
    start = end.replace(hour=7, minute=0)
    if (end.hour < 7):
        start = (end - datetime.timedelta(days=1)).replace(hour=7, minute=0)
    out = get_object_or_404(Logger, Logger.sn==sn).to_dict()
    out.update({ 'data': {
                        #'num': rst.count(),
                        'end': df.index.to_list(),
                        #'start': df.index.to_list()[0],
                        #'dsnum': ds_num.to_list(),
                        'tick': df.tick.to_list()
                    }})
    return jsonify(out)


@bp.route('/logger/<sn>', methods=['GET'])
#@basic_auth.login_required
def get_logger(sn):
    logger = Logger.get(Logger.sn==sn)
    return jsonify(logger.to_dict())

@bp.route('/loggers', methods=['GET'])
def get_loggers():
    pass
