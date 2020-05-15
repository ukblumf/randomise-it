from flask import jsonify, request, g, url_for, current_app
from .. import db
from ..models import RandomTable, Permission
from . import api
from .decorators import permission_required
from .errors import forbidden, bad_request
from ..validate import check_table_definition_validity
from sqlalchemy import exists, and_

from ..get_random_value import get_row_from_random_table_definition


@api.route('/tables/')
def get_tables():
    page = request.args.get('page', 1, type=int)
    pagination = RandomTable.query.paginate(
        page, per_page=current_app.config['RANDOMISE_IT_POSTS_PER_PAGE'],
        error_out=False)
    tables = pagination.items
    prev = None
    if pagination.has_prev:
        prev = url_for('api.get_tables', page=page - 1, _external=True)
    next = None
    if pagination.has_next:
        next = url_for('api.get_tables', page=page + 1, _external=True)
    return jsonify({
        'tables': [table.to_json() for table in tables],
        'prev': prev,
        'next': next,
        'count': pagination.total
    })


@api.route('/table/<string:id>')
def get_table(id):
    table = RandomTable.query.get_or_404([id, g.current_user.id])
    return jsonify(table.to_json())


@api.route('/table/', methods=['POST'])
@permission_required(Permission.WRITE_ARTICLES)
def new_table():
    table_id = request.json.get("id")
    if db.session.query(exists().where(and_(RandomTable.id == table_id,
                                            RandomTable.author_id == g.current_user.id)
                                       )):
        RandomTable.query.filter(RandomTable.id == table_id,
                                 RandomTable.author_id == g.current_user.id).delete()

    table = RandomTable.from_json(request.json)
    table.author = g.current_user

    max_rng, min_rng, validate_table_definition, table_type, error_message = check_table_definition_validity(table)
    if validate_table_definition:
        table.min = min_rng
        table.max = max_rng
        table.line_type = table_type
        table.permissions = 0
        db.session.add(table)
        db.session.commit()
        return jsonify(table.to_json()), 201, \
               {'Location': url_for('api.get_table', id=table.id, _external=True)}
    else:
        return bad_request(error_message)


@api.route('/tables/', methods=['POST'])
@permission_required(Permission.WRITE_ARTICLES)
def new_tables():
    table_count = 0
    for json_table in request.json:
        table_id = json_table.get("id")
        if db.session.query(exists().where(and_(RandomTable.id == table_id,
                                                RandomTable.author_id == g.current_user.id)
                                           )
                            ):
            RandomTable.query.filter(RandomTable.id == table_id,
                                     RandomTable.author_id == g.current_user.id).delete()

        table = RandomTable.from_json(json_table)
        table.author = g.current_user

        max_rng, min_rng, validate_table_definition, table_type, error_message = check_table_definition_validity(table)
        if validate_table_definition:
            table.min = min_rng
            table.max = max_rng
            table.line_type = table_type
            table.permissions = 0
            db.session.add(table)
            table_count += 1
        else:
            return bad_request("table id: " + table_id + ", " + error_message)

    db.session.commit()
    return jsonify({'message': "Batch ingest successful. " + str(table_count) + " tables ingested."})


@api.route('/table/<string:id>', methods=['PUT'])
@permission_required(Permission.WRITE_ARTICLES)
def edit_table(id):
    table = RandomTable.query.get_or_404([id, g.current_user.id])
    if g.current_user != table.author and \
            not g.current_user.can(Permission.ADMINISTER):
        return forbidden('Insufficient permissions')

    table.name = request.json.get('name', table.name)
    table.description = request.json.get('description', table.description)
    table.definition = request.json.get('definition', table.definition)
    # table.permisssions = request.json.get('permissions', table.permisssions)
    db.session.add(table)
    return jsonify(table.to_json())


@api.route('/random-value/<string:id>', methods=['GET'])
def get_random_value(id):

    # for k, v in request.headers.items():
    #     current_app.logger.warning(k + ":" + v)

    table = RandomTable.query.get_or_404([id, g.current_user.id])

    return jsonify({'random_value': get_row_from_random_table_definition(table)})

