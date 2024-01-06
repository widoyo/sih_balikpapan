from flask import Blueprint, request, jsonify
from flask_login import current_user
from app.models import db, Ws, Das
from app.api.errors import bad_request

bp = Blueprint('api', __name__)

@bp.route('update', methods=['POST'])
def update():
    data = request.form
    if data.get('obj') not in ['logger', 'location']:
        return "obj tidak valid", 400
    table = data.get('obj')
    field = data.get('name')
    oid = data.get('pk')
    val = data.get('value')
    if field == 'tipp_fac':
        sql = "UPDATE {table} set {nama}={nilai} WHERE id={oid}".format(table=table, 
                                                                    nama=field, 
                                                                    nilai=val, 
                                                                    oid=oid)
    else:
        sql = "UPDATE {table} set {nama}='{nilai}' WHERE id={oid}".format(table=table, 
                                                                    nama=field, 
                                                                    nilai=val, 
                                                                    oid=oid)
    db.database.execute_sql(sql)    
    return sql, 200

'''
@bp.route('/ws', methods=['POST'])
def create_ws():
    if not current_user.tenant:
        return bad_request('Anda bukan tenant')
    data = request.get_json() or {}
    data.update({'tenant': current_user.tenant})
    if 'nama' not in data:
        return bad_request('Harus ada nama')
    ws = Ws()
    ws.from_dict(data)
    ws.save()
    response = jsonify(ws.to_dict())
    response.status_code = 201
    return response
'''

@bp.route('/das', methods=['POST'])
def create_das():
    if not current_user.tenant:
        return bad_request('Anda bukan tenant')
    data = request.get_json() or {}
    data.update({'tenant': current_user.tenant})
    if 'nama' not in data:
        return bad_request('Harus ada nama')
    das = Das()
    das.from_dict(data)
    das.save()
    response = jsonify(das.to_dict())
    response.status_code = 201
    return response

from app.api import users, errors, tokens, tenants, logger