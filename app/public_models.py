from datetime import datetime
from . import db


class PublicRandomTable(db.Model):
    __tablename__ = 'public_random_table'
    id = db.Column(db.Text, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    name = db.Column(db.Text)
    description = db.Column(db.Text)
    definition = db.Column(db.Text)
    min = db.Column(db.Integer)
    max = db.Column(db.Integer)
    description_html = db.Column(db.Text)
    permissions = db.Column(db.Integer)
    line_type = db.Column(db.Integer)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    tags = db.Column(db.Text, index=True)
    row_count = db.Column(db.Integer)
    announcement_id = db.Column(db.Integer, db.ForeignKey('public_announcements.id'))
    modifier_name = db.Column(db.Text)
    last_modified = db.Column(db.DateTime)


class PublicMacros(db.Model):
    __tablename__ = 'public_macros'
    id = db.Column(db.Text, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    name = db.Column(db.Text)
    definition = db.Column(db.Text)
    definition_html = db.Column(db.Text)
    permissions = db.Column(db.Integer)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    tags = db.Column(db.Text, index=True)
    announcement_id = db.Column(db.Integer, db.ForeignKey('public_announcements.id'))
    last_modified = db.Column(db.DateTime)


class PublicCollection(db.Model):
    __tablename__ = 'public_collection'
    id = db.Column(db.Text, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    name = db.Column(db.Text)
    description = db.Column(db.Text)
    definition = db.Column(db.Text)
    permissions = db.Column(db.Integer)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    tags = db.Column(db.Text, index=True)
    announcement_id = db.Column(db.Integer, db.ForeignKey('public_announcements.id'))
    last_modified = db.Column(db.DateTime)


class PublicLinkedTables(db.Model):
    __tablename__ = 'public_linked_tables'
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    table_id = db.Column(db.Text, primary_key=True)
    original_author_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    announcement_id = db.Column(db.Integer, db.ForeignKey('public_announcements.id'))
    public_table = db.relationship('PublicRandomTable',
                                   backref=db.backref('public_table'),
                                   foreign_keys=[table_id, original_author_id],
                                   primaryjoin='and_(PublicRandomTable.id == PublicLinkedTables.table_id,' +
                                               'PublicRandomTable.author_id == PublicLinkedTables.original_author_id)')


class PublicLinkedMacros(db.Model):
    __tablename__ = 'public_linked_macros'
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    macro_id = db.Column(db.Text, primary_key=True)
    original_author_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    announcement_id = db.Column(db.Integer, db.ForeignKey('public_announcements.id'))
    public_macro = db.relationship('PublicMacros',
                                   backref=db.backref('public_macro'),
                                   foreign_keys=[macro_id, original_author_id],
                                   primaryjoin='and_(PublicMacros.id == PublicLinkedMacros.macro_id,' +
                                               'PublicMacros.author_id == PublicLinkedMacros.original_author_id)')


class PublicLinkedCollections(db.Model):
    __tablename__ = 'public_linked_collections'
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    collection_id = db.Column(db.Text, primary_key=True)
    original_author_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    announcement_id = db.Column(db.Integer, db.ForeignKey('public_announcements.id'))
    public_collection = db.relationship('PublicCollection',
                                        backref=db.backref('public_collection'),
                                        foreign_keys=[collection_id, original_author_id],
                                        primaryjoin='and_(PublicCollection.id == PublicLinkedCollections.collection_id,' +
                                                    'PublicCollection.author_id == PublicLinkedCollections.original_author_id)')


class PublicAnnouncements(db.Model):
    __tablename__ = 'public_announcements'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    title = db.Column(db.Text)
    description = db.Column(db.Text)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)


class UserPublicContent(db.Model):
    __tablename__ = 'user_public_content'
    announcement_id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    public_announcement = db.relationship('PublicAnnouncements',
                                          backref=db.backref('public_announcements'),
                                          foreign_keys=announcement_id,
                                          primaryjoin='PublicAnnouncements.id == UserPublicContent.announcement_id')
