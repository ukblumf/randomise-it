from flask_login import current_user
from .models import RandomTable, Macros, User, Collection
from .public_models import PublicRandomTable, PublicMacros, PublicCollection, PublicLinkedTables, PublicLinkedMacros, \
    PublicLinkedCollections


def get_random_table_record(username, reference_id):
    return retrieve_data(username, reference_id, RandomTable, PublicLinkedTables, PublicRandomTable)


def get_macro_record(username, reference_id):
    return retrieve_data(username, reference_id, Macros, PublicLinkedMacros, PublicMacros)


def get_collection_record(username, reference_id):
    return retrieve_data(username, reference_id, Collection, PublicLinkedCollections, PublicCollection)


def retrieve_data(username, reference_id, private_table, link_table, public_table):
    if current_user.is_anonymous:
        external_user = User.query.filter_by(username=username).first()
        return public_table.query.get([reference_id, external_user.id])
    elif username != current_user.username:
        external_user = User.query.filter_by(username=username).first()
        # public_link_collection = link_table.query.get([current_user.id, reference_id, external_user.id])
        # if public_link_collection is not None:
        return public_table.query.get([reference_id, external_user.id])
        # else:
        #    return None
    else:
        return private_table.query.get([reference_id, current_user.id])


def split_id(id):
    username, id_type, reference_id = id.split('.')
    if '%' in username:  # ignore chance percentage
        chance, username = username.split(' ')
    return username, id_type, reference_id


def remove_blank_lines(data):
    clean_data = ""
    for line in data.splitlines(True):
        if line.strip().rstrip():
            clean_data += line
    return clean_data
