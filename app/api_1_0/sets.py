from flask import jsonify, request, g, url_for, current_app
from .. import db
from ..models import Set, Permission
from . import api
from .decorators import permission_required
from .errors import forbidden, bad_request
from sqlalchemy import exists, and_
from ..validate import validate_set


@api.route('/sets/')
def get_sets():
    page = request.args.get('page', 1, type=int)
    pagination = Set.query.paginate(
        page, per_page=current_app.config['RANDOMISE_IT_POSTS_PER_PAGE'],
        error_out=False)
    sets = pagination.items
    prev = None
    if pagination.has_prev:
        prev = url_for('api.get_sets', page=page - 1, _external=True)
    next = None
    if pagination.has_next:
        next = url_for('api.get_sets', page=page + 1, _external=True)
    return jsonify({
        'sets': [set.to_json() for set in sets],
        'prev': prev,
        'next': next,
        'count': pagination.total
    })


@api.route('/set/<string:id>')
def get_set(id):
    set = Set.query.get_or_404([id, g.current_user.id])
    return jsonify(set.to_json())


@api.route('/set/', methods=['POST'])
@permission_required(Permission.WRITE_ARTICLES)
def new_set():
    set = Set.from_json(request.json)
    set.author_id = g.current_user.id
    if db.session.query(exists().where(and_(Set.id == set.id,
                                            Set.author_id == g.current_user.id)
                                       )
                        ):
        Set.query.filter(Set.id == set.id,
                         Set.author_id == g.current_user.id).delete()

    validate_set_definition, error_message = validate_set(set.definition)
    if validate_set_definition:
        set.permissions = 0
        set.author_id = g.current_user.id
        db.session.add(set)
        db.session.commit()
        return jsonify(set.to_json()), 201, \
               {'Location': url_for('api.get_table', id=set.id, _external=True)}
    else:
        return bad_request(error_message)


@api.route('/sets/', methods=['POST'])
@permission_required(Permission.WRITE_ARTICLES)
def new_sets():
    count = 0
    for json in request.json:
        set_id = json.get("id")
        if db.session.query(exists().where(and_(Set.id == set_id,
                                                Set.author_id == g.current_user.id)
                                           )
                            ):
            Set.query.filter(Set.id == set_id,
                             Set.author_id == g.current_user.id).delete()

        set_obj = Set.from_json(json)
        set_obj.author_id = g.current_user.id

        validate_set_definition, error_message = validate_set(set_obj.definition)
        if validate_set_definition:
            set_obj.permissions = 0
            db.session.add(set_obj)
            count += 1
        else:
            return bad_request("set id: " + set_id + ", " + error_message)

    db.session.commit()
    return jsonify({'message': "Batch ingest successful. " + str(count) + " sets ingested."})


@api.route('/set/<string:id>', methods=['PUT'])
@permission_required(Permission.WRITE_ARTICLES)
def edit_set(id):
    set = Set.query.get_or_404([id, g.current_user.id])
    if g.current_user != set.author and \
            not g.current_user.can(Permission.ADMINISTER):
        return forbidden('Insufficient permissions')

    set.name = request.json.get('name', set.name)
    set.definition = request.json.get('definition', set.definition)
    # table.permisssions = request.json.get('permissions', table.permisssions)
    db.session.add(set)
    return jsonify(set.to_json())
