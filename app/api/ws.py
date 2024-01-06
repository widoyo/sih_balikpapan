from flask_login import current_user
from playhouse.flask_utils import get_object_or_404
from apifairy import body, other_responses, response
from app.api import bp
from app.schema import EntryWs, NewEntryWs

entry_ws = EntryWs()
new_entry_ws = NewEntryWs()
entries_ws = EntryWs(many=True)

@bp.route('/ws', methods=['GET'])
@response(entry_ws)
def index():
    """Return all Ws"""
    