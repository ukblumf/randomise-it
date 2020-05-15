from flask import Blueprint

api = Blueprint('api', __name__)

from . import authentication, posts, users, comments, errors, tables, macros, sets, products, marketplace
