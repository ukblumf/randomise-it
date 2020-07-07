from flask import jsonify, request, g, url_for, current_app
from .. import db
from ..models import Macros, Permission
from . import api
from .decorators import permission_required
from .errors import forbidden, bad_request
from sqlalchemy import exists, and_
from ..validate import validate_text
from ..get_random_value import process_text_extended


@api.route('/macros/')
def get_macros():
    page = request.args.get('page', 1, type=int)
    pagination = Macros.query.paginate(
        page, per_page=current_app.config['RANDOMIST_POSTS_PER_PAGE'],
        error_out=False)
    macros = pagination.items
    prev_page = None
    if pagination.has_prev:
        prev_page = url_for('api.get_macros', page=page - 1, _external=True)
    next_page = None
    if pagination.has_next:
        next_page = url_for('api.get_macros', page=page + 1, _external=True)
    return jsonify({
        'macros': [macro.to_json() for macro in macros],
        'prev': prev_page,
        'next': next_page,
        'count': pagination.total
    })


@api.route('/macro/<string:id>')
def get_macro(id):
    macro = Macros.query.get_or_404([id, g.current_user.id])
    return jsonify(macro.to_json())


@api.route('/macro/', methods=['POST'])
@permission_required(Permission.WRITE_ARTICLES)
def new_macro():
    macro = Macros.from_json(request.json)
    macro.author_id = g.current_user.id

    validate_macro_definition, error_message = validate_text(macro.definition, macro.id)
    if validate_macro_definition:
        macro.permissions = 0
        db.session.add(macro)
        db.session.commit()
        return jsonify(macro.to_json()), 201, \
               {'Location': url_for('api.get_table', id=macro.id, _external=True)}
    else:
        return bad_request(error_message)


@api.route('/macros/', methods=['POST'])
@permission_required(Permission.WRITE_ARTICLES)
def new_macros():
    count = 0
    for json in request.json:
        macro_id = json.get("id")
        if db.session.query(exists().where(and_(Macros.id == macro_id, Macros.author_id == g.current_user.id))):
            Macros.query.filter(Macros.id == macro_id,
                                     Macros.author_id == g.current_user.id).delete()

        macro = Macros.from_json(json)
        macro.author = g.current_user

        validate_macro_definition, error_message = validate_text(macro.definition, macro.id)
        if validate_macro_definition:
            macro.permissions = 0
            db.session.add(macro)
            count += 1
        else:
            return bad_request("macro id: " + macro_id + ", " + error_message)

    db.session.commit()
    return jsonify({'message': "Batch ingest successful. " + str(count) + " macros ingested."})


@api.route('/macro/<string:id>', methods=['PUT'])
@permission_required(Permission.WRITE_ARTICLES)
def edit_macro(id):
    macro = Macros.query.get_or_404([id, g.current_user.id])
    if g.current_user != macro.author and \
            not g.current_user.can(Permission.ADMINISTER):
        return forbidden('Insufficient permissions')

    macro.name = request.json.get('name', macro.name)
    macro.description = request.json.get('description', macro.description)
    macro.definition = request.json.get('definition', macro.definition)
    # table.permisssions = request.json.get('permissions', table.permisssions)
    db.session.add(macro)
    return jsonify(macro.to_json())


@api.route('/process-macro/<string:id>', methods=['GET'])
def process_macro(id):

    # for k, v in request.headers.items():
    #     current_app.logger.warning(k + ":" + v)
    # current_app.logger.warning("macro id:" + id + ", user id:" + str(g.current_user.id))
    macro = Macros.query.get_or_404([id, g.current_user.id])

    return jsonify({'macro_text': process_text_extended(macro.definition)})

