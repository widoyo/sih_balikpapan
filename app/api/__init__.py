from flask import Blueprint, request
from app.models import db

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

from app.api import users, errors, tokens, tenants