from flask import jsonify, request, g, url_for, current_app
from .. import db
from ..models import Collection, Permission
from . import api
from .decorators import permission_required
from .errors import forbidden, bad_request
from sqlalchemy import exists, and_
from ..validate import validate_collection


@api.route('/collections/')
def get_collections():
    page = request.args.get('page', 1, type=int)
    pagination = Collection.query.paginate(
        page, per_page=current_app.config['RANDOMIST_POSTS_PER_PAGE'],
        error_out=False)
    collections = pagination.items
    prev = None
    if pagination.has_prev:
        prev = url_for('api.get_collections', page=page - 1, _external=True)
    next = None
    if pagination.has_next:
        next = url_for('api.get_collections', page=page + 1, _external=True)
    return jsonify({
        'collections': [collection.to_json() for collection in collections],
        'prev': prev,
        'next': next,
        'count': pagination.total
    })


@api.route('/collection/<string:id>')
def get_collection(id):
    collection = Collection.query.get_or_404([id, g.current_user.id])
    return jsonify(collection.to_json())


@api.route('/collection/', methods=['POST'])
@permission_required(Permission.WRITE_ARTICLES)
def new_collection():
    collection = Collection.from_json(request.json)
    collection.author_id = g.current_user.id
    if db.session.query(exists().where(and_(Collection.id == collection.id,
                                            Collection.author_id == g.current_user.id)
                                       )
                        ):
        Collection.query.filter(Collection.id == collection.id,
                                Collection.author_id == g.current_user.id).delete()

    validate_collection_definition, error_message = validate_collection(collection.definition)
    if validate_collection_definition:
        collection.permissions = 0
        collection.author_id = g.current_user.id
        db.session.add(collection)
        db.session.commit()
        return jsonify(collection.to_json()), 201, \
               {'Location': url_for('api.get_table', id=collection.id, _external=True)}
    else:
        return bad_request(error_message)


@api.route('/collections/', methods=['POST'])
@permission_required(Permission.WRITE_ARTICLES)
def new_collections():
    count = 0
    for json in request.json:
        collection_id = json.get("id")
        if db.session.query(exists().where(and_(Collection.id == collection_id,
                                                Collection.author_id == g.current_user.id)
                                           )
                            ):
            Collection.query.filter(Collection.id == collection_id,
                                    Collection.author_id == g.current_user.id).delete()

        collection_obj = Collection.from_json(json)
        collection_obj.author_id = g.current_user.id

        validate_collection_definition, error_message = validate_collection(collection_obj.definition)
        if validate_collection_definition:
            collection_obj.permissions = 0
            db.session.add(collection_obj)
            count += 1
        else:
            return bad_request("set id: " + collection_id + ", " + error_message)

    db.session.commit()
    return jsonify({'message': "Batch ingest successful. " + str(count) + " sets ingested."})


@api.route('/collection/<string:id>', methods=['PUT'])
@permission_required(Permission.WRITE_ARTICLES)
def edit_collection(id):
    collection = Collection.query.get_or_404([id, g.current_user.id])
    if g.current_user != collection.author and \
            not g.current_user.can(Permission.ADMINISTER):
        return forbidden('Insufficient permissions')

    collection.name = request.json.get('name', collection.name)
    collection.definition = request.json.get('definition', collection.definition)
    # table.permisssions = request.json.get('permissions', table.permisssions)
    db.session.add(collection)
    return jsonify(collection.to_json())
