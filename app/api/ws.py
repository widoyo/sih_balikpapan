from flask import jsonify
from playhouse.flask_utils import get_object_or_404
from app.api import bp
from app.models import Ws

@bp.route('/ws')