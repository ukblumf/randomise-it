from flask import jsonify, request, g, url_for, current_app
from .. import db
from ..models import MarketPlace, ProductCategory
from . import api
from .decorators import permission_required
from .errors import forbidden, bad_request, not_found
from sqlalchemy import exists, and_
from ..validate import validate_set, validate_text, check_table_definition_validity


@api.route('/market-products/<string:cat_id>', methods=['GET'])
def get_market_products(cat_id):

    # check if category exists
    if ProductCategory.query.filter(ProductCategory.category_id == cat_id).count() == 0:
        return not_found("No market place products match category")

    latest_marketproducts = MarketPlace.query.join(ProductCategory)\
        .filter(ProductCategory.category_id == cat_id).order_by(MarketPlace.timestamp.desc())
    popular_marketproducts = MarketPlace.query.join(ProductCategory)\
        .filter(ProductCategory.category_id == cat_id).order_by(MarketPlace.count.desc())

    return jsonify({
        'latest_products': [market_product.to_json() for market_product in latest_marketproducts],
        'popular_products': [market_product.to_json() for market_product in popular_marketproducts]
    })


@api.route('/market-products/all', methods=['GET'])
def get_all_market_products():

    latest_marketproducts = MarketPlace.query.order_by(MarketPlace.timestamp.desc())
    popular_marketproducts = MarketPlace.query.order_by(MarketPlace.count.desc())

    return jsonify({
        'latest_products': [market_product.to_json() for market_product in latest_marketproducts],
        'popular_products': [market_product.to_json() for market_product in popular_marketproducts]
    })