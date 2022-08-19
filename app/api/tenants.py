from flask import jsonify
from playhouse.flask_utils import get_object_or_404
from app.api import bp
from app.models import Tenant

@bp.route('/tenants/<int:id>', methods=['GET'])
def get_tenant(id):
    return jsonify(get_object_or_404(Tenant, Tenant.id==id).to_dict())
