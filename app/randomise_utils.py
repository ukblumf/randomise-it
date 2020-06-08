from flask_login import current_user
from .models import RandomTable, Macros, User, Collection
from .public_models import PublicRandomTable, PublicMacros, PublicCollection, PublicLinkedTables, PublicLinkedMacros, \
    PublicLinkedCollections
import re

regex = r"(\d+%\s)?(.*)\.(.*)\.(.*$)"


def get_random_table_record(username, reference_id):
    if username != current_user.username:
        # get user to get user id
        external_user = User.query.filter_by(username=username).first()
        # see if table is in public linked table
        public_link_table = PublicLinkedTables.query.get([current_user.id, reference_id, external_user.id])
        if public_link_table is not None:
            return PublicRandomTable.query.get([reference_id, external_user.id])
        else:
            return None
    else:
        return RandomTable.query.get([reference_id, current_user.id])


def get_macro_record(username, reference_id):
    if username != current_user.username:
        external_user = User.query.filter_by(username=username).first()
        public_link_macro = PublicLinkedMacros.query.get([current_user.id, reference_id, external_user.id])
        if public_link_macro is not None:
            return PublicMacros.query.get([reference_id, external_user.id])
        else:
            return None
    else:
        return Macros.query.get([reference_id, current_user.id])


def get_collection_record(username, reference_id):
    if username != current_user.username:
        external_user = User.query.filter_by(username=username).first()
        public_link_collection = PublicLinkedCollections.query.get([current_user.id, reference_id, external_user.id])
        if public_link_collection is not None:
            return PublicCollection.query.get([reference_id, external_user.id])
        else:
            return None
    else:
        return Collection.query.get([reference_id, current_user.id])


def split_id(id):
    username, id_type, reference_id = id.split('.')
    if '%' in username:  # user contains chance
        chance, username = username.split(' ')
    return username, id_type, reference_id
