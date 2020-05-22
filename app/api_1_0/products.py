# from flask import jsonify, request, g, url_for, current_app
# from .. import db
# from ..models import Products, RandomTable, Macros, Set, Permission
# from . import api
# from .decorators import permission_required
# from .errors import forbidden, bad_request
# from sqlalchemy import exists, and_
# from ..validate import validate_set, validate_text, check_table_definition_validity
#
#
# @api.route('/products/')
# def get_products():
#     page = request.args.get('page', 1, type=int)
#     pagination = Products.query.paginate(
#         page, per_page=current_app.config['RANDOMISE_IT_POSTS_PER_PAGE'],
#         error_out=False)
#     products = pagination.items
#     prev = None
#     if pagination.has_prev:
#         prev = url_for('api.get_products', page=page - 1, _external=True)
#     next = None
#     if pagination.has_next:
#         next = url_for('api.get_products', page=page + 1, _external=True)
#     return jsonify({
#         'products': [product.to_json() for product in products],
#         'prev': prev,
#         'next': next,
#         'count': pagination.total
#     })
#
#
# @api.route('/product/<string:id>')
# def get_product(id):
#     product = Products.query.get_or_404([id, g.current_user.id])
#     return jsonify(product.to_json())
#
#
# @api.route('/product/', methods=['POST'])
# @permission_required(Permission.WRITE_ARTICLES)
# def new_product():
#     table_count = 0
#     macro_count = 0
#     set_count = 0
#
#     for json in request.json.get("tables"):
#         table_id = json.get("id")
#         if db.session.query(exists().where(and_(RandomTable.id == table_id, RandomTable.author_id == g.current_user.id))):
#             RandomTable.query.filter(RandomTable.id == table_id, RandomTable.author_id == g.current_user.id).delete()
#
#         table = RandomTable.from_json(json)
#         table.author = g.current_user
#
#         max_rng, min_rng, validate_table_definition, table_type, error_message = check_table_definition_validity(table)
#         if validate_table_definition:
#             table.min = min_rng
#             table.max = max_rng
#             table.line_type = table_type
#             table.permissions = 0
#             db.session.add(table)
#             table_count += 1
#         else:
#             return bad_request("table id: " + table_id + ", " + error_message)
#
#     for json in request.json.get("macros"):
#         macro_id = json.get("id")
#         if db.session.query(exists().where(and_(Macros.id == macro_id, Macros.author_id == g.current_user.id))):
#             Macros.query.filter(Macros.id == macro_id, Macros.author_id == g.current_user.id).delete()
#
#         macro = Macros.from_json(json)
#         macro.author = g.current_user
#
#         validate_macro_definition, error_message = validate_text(macro.definition)
#         if validate_macro_definition:
#             macro.permissions = 0
#             db.session.add(macro)
#             macro_count += 1
#         else:
#             return bad_request("macro id: " + macro_id + ", " + error_message)
#
#     for json in request.json.get("sets"):
#         set_id = json.get("id")
#         if db.session.query(exists().where(and_(Set.id == set_id, Set.author_id == g.current_user.id))):
#             Set.query.filter(Set.id == set_id, Set.author_id == g.current_user.id).delete()
#
#         set_obj = Set.from_json(json)
#         set_obj.author_id = g.current_user.id
#
#         validate_set_definition, error_message = validate_set(set_obj.definition)
#         if validate_set_definition:
#             set_obj.permissions = 0
#             db.session.add(set_obj)
#             set_count += 1
#         else:
#             return bad_request("set id: " + set_id + ", " + error_message)
#
#     product_id = request.json.get("id")
#     if db.session.query(exists().where(and_(Products.id == product_id,
#                                             Products.author_id == g.current_user.id)
#                                        )
#                         ):
#         Products.query.filter(Products.id == product_id,
#                               Products.author_id == g.current_user.id).delete()
#
#     product = Products.from_json(request.json)
#     product.author_id = g.current_user.id
#
#     db.session.add(product)
#     db.session.commit()
#
#     return jsonify({'message': "Product ingest successful. Tables:" + str(table_count) + ", Macros:" + str(macro_count) + ", Sets:" + str(set_count) + " ingested."})
#
#
# @api.route('/product/<string:id>', methods=['PUT'])
# @permission_required(Permission.WRITE_ARTICLES)
# def edit_product(id):
#     product = Products.query.get_or_404([id, g.current_user.id])
#     if g.current_user != product.author and not g.current_user.can(Permission.ADMINISTER):
#         return forbidden('Insufficient permissions')
#
#     product.name = request.json.get('name', product.name)
#     product.definition = request.json.get('definition', product.definition)
#     # table.permisssions = request.json.get('permissions', table.permisssions)
#     db.session.add(product)
#     return jsonify(product.to_json())
