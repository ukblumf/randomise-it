from datetime import datetime
import hashlib
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer
from markdown import markdown
import bleach
from flask import current_app, request, url_for
from flask_login import UserMixin, AnonymousUserMixin
from app.exceptions import ValidationError
from . import db, login_manager
from app.public_models import *


class Permission:
    FOLLOW = 0x01
    COMMENT = 0x02
    WRITE_ARTICLES = 0x04
    MODERATE_COMMENTS = 0x08
    ADMINISTER = 0x80


class ProductPermission:
    PUBLIC = 1
    COMMERCIAL = 2
    OPEN = 4
    EDITABLE = 8
    PRIVATE = 0
    PUBLIC_OPEN = 5
    PUBLIC_OPEN_EDITABLE = 13
    COMMERCIAL_OPEN = 6
    COMMERCIAL_OPEN_EDITABLE = 14


class Role(db.Model):
    __tablename__ = 'roles'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True)
    default = db.Column(db.Boolean, default=False, index=True)
    permissions = db.Column(db.Integer)
    users = db.relationship('User', backref='role', lazy='dynamic')

    @staticmethod
    def insert_roles():
        roles = {
            'User': (Permission.FOLLOW |
                     Permission.COMMENT |
                     Permission.WRITE_ARTICLES, True),
            'Moderator': (Permission.FOLLOW |
                          Permission.COMMENT |
                          Permission.WRITE_ARTICLES |
                          Permission.MODERATE_COMMENTS, False),
            'Administrator': (0xff, False)
        }
        for r in roles:
            role = Role.query.filter_by(name=r).first()
            if role is None:
                role = Role(name=r)
            role.permissions = roles[r][0]
            role.default = roles[r][1]
            db.session.add(role)
        db.session.commit()

    def __repr__(self):
        return '<Role %r>' % self.name


class Follow(db.Model):
    __tablename__ = 'follows'
    follower_id = db.Column(db.Integer, db.ForeignKey('users.id'),
                            primary_key=True)
    followed_id = db.Column(db.Integer, db.ForeignKey('users.id'),
                            primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(64), unique=True, index=True)
    username = db.Column(db.String(64), unique=True, index=True)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'))
    password_hash = db.Column(db.String(128))
    confirmed = db.Column(db.Boolean, default=False)
    name = db.Column(db.String(64))
    location = db.Column(db.String(64))
    about_me = db.Column(db.Text())
    member_since = db.Column(db.DateTime(), default=datetime.utcnow)
    last_seen = db.Column(db.DateTime(), default=datetime.utcnow)
    avatar_hash = db.Column(db.String(32))
    posts = db.relationship('Post', backref='author', lazy='dynamic')
    tables = db.relationship('RandomTable', backref='author', lazy='dynamic')
    macros = db.relationship('Macros', backref='author', lazy='dynamic')
    collections = db.relationship('Collection', backref='author', lazy='dynamic')
    public_tables = db.relationship('PublicRandomTable', backref='author', lazy='dynamic')
    public_macros = db.relationship('PublicMacros', backref='author', lazy='dynamic')
    public_collections = db.relationship('PublicCollection', backref='author', lazy='dynamic')
    public_linked_tables = db.relationship('PublicLinkedTables',
                                           foreign_keys=[PublicLinkedTables.original_author_id],
                                           backref=db.backref('original_author', lazy='joined'),
                                           lazy='dynamic',
                                           cascade='all, delete-orphan')
    public_linked_macros = db.relationship('PublicLinkedMacros',
                                           foreign_keys=[PublicLinkedMacros.original_author_id],
                                           backref=db.backref('original_author', lazy='joined'),
                                           lazy='dynamic',
                                           cascade='all, delete-orphan')
    public_linked_collections = db.relationship('PublicLinkedCollections',
                                                foreign_keys=[PublicLinkedCollections.original_author_id],
                                                backref=db.backref('original_author', lazy='joined'),
                                                lazy='dynamic',
                                                cascade='all, delete-orphan')
    followed = db.relationship('Follow',
                               foreign_keys=[Follow.follower_id],
                               backref=db.backref('follower', lazy='joined'),
                               lazy='dynamic',
                               cascade='all, delete-orphan')
    followers = db.relationship('Follow',
                                foreign_keys=[Follow.followed_id],
                                backref=db.backref('followed', lazy='joined'),
                                lazy='dynamic',
                                cascade='all, delete-orphan')
    comments = db.relationship('Comment', backref='author', lazy='dynamic')

    @staticmethod
    def generate_fake(count=100):
        from sqlalchemy.exc import IntegrityError
        from random import seed
        import forgery_py

        seed()
        for i in range(count):
            u = User(email=forgery_py.internet.email_address(),
                     username=forgery_py.internet.user_name(True),
                     password=forgery_py.lorem_ipsum.word(),
                     confirmed=True,
                     name=forgery_py.name.full_name(),
                     location=forgery_py.address.city(),
                     about_me=forgery_py.lorem_ipsum.sentence(),
                     member_since=forgery_py.date.date(True))
            db.session.add(u)
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()

    @staticmethod
    def add_self_follows():
        for user in User.query.all():
            if not user.is_following(user):
                user.follow(user)
                db.session.add(user)
                db.session.commit()

    def __init__(self, **kwargs):
        super(User, self).__init__(**kwargs)
        if self.role is None:
            if self.email == current_app.config['RANDOMISE_IT_ADMIN']:
                self.role = Role.query.filter_by(permissions=0xff).first()
            if self.role is None:
                self.role = Role.query.filter_by(default=True).first()
        if self.email is not None and self.avatar_hash is None:
            self.avatar_hash = hashlib.md5(
                self.email.encode('utf-8')).hexdigest()
        self.followed.append(Follow(followed=self))

    @property
    def password(self):
        raise AttributeError('password is not a readable attribute')

    @password.setter
    def password(self, password):
        self.password_hash = generate_password_hash(password)

    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)

    def generate_confirmation_token(self, expiration=3600):
        s = Serializer(current_app.config['SECRET_KEY'], expiration)
        return s.dumps({'confirm': self.id})

    def confirm(self, token):
        s = Serializer(current_app.config['SECRET_KEY'])
        try:
            data = s.loads(token)
        except:
            return False
        if data.get('confirm') != self.id:
            return False
        self.confirmed = True
        db.session.add(self)
        return True

    def generate_reset_token(self, expiration=3600):
        s = Serializer(current_app.config['SECRET_KEY'], expiration)
        return s.dumps({'reset': self.id})

    def reset_password(self, token, new_password):
        s = Serializer(current_app.config['SECRET_KEY'])
        try:
            data = s.loads(token)
        except:
            return False
        if data.get('reset') != self.id:
            return False
        self.password = new_password
        db.session.add(self)
        return True

    def generate_email_change_token(self, new_email, expiration=3600):
        s = Serializer(current_app.config['SECRET_KEY'], expiration)
        return s.dumps({'change_email': self.id, 'new_email': new_email})

    def change_email(self, token):
        s = Serializer(current_app.config['SECRET_KEY'])
        try:
            data = s.loads(token)
        except:
            return False
        if data.get('change_email') != self.id:
            return False
        new_email = data.get('new_email')
        if new_email is None:
            return False
        if self.query.filter_by(email=new_email).first() is not None:
            return False
        self.email = new_email
        self.avatar_hash = hashlib.md5(
            self.email.encode('utf-8')).hexdigest()
        db.session.add(self)
        return True

    def can(self, permissions):
        return self.role is not None and \
               (self.role.permissions & permissions) == permissions

    def is_administrator(self):
        return self.can(Permission.ADMINISTER)

    def ping(self):
        self.last_seen = datetime.utcnow()
        db.session.add(self)

    def gravatar(self, size=100, default='identicon', rating='g'):
        if request.is_secure:
            url = 'https://secure.gravatar.com/avatar'
        else:
            url = 'http://www.gravatar.com/avatar'
        hash = self.avatar_hash or hashlib.md5(
            self.email.encode('utf-8')).hexdigest()
        return '{url}/{hash}?s={size}&d={default}&r={rating}'.format(
            url=url, hash=hash, size=size, default=default, rating=rating)

    def follow(self, user):
        if not self.is_following(user):
            f = Follow(follower=self, followed=user)
            db.session.add(f)

    def unfollow(self, user):
        f = self.followed.filter_by(followed_id=user.id).first()
        if f:
            db.session.delete(f)

    def is_following(self, user):
        return self.followed.filter_by(
            followed_id=user.id).first() is not None

    def is_followed_by(self, user):
        return self.followers.filter_by(
            follower_id=user.id).first() is not None

    @property
    def followed_posts(self):
        return Post.query.join(Follow, Follow.followed_id == Post.author_id) \
            .filter(Follow.follower_id == self.id)

    def to_json(self):
        json_user = {
            'url': url_for('api.get_user', id=self.id, _external=True),
            'username': self.username,
            'member_since': self.member_since,
            'last_seen': self.last_seen,
            'posts': url_for('api.get_user_posts', id=self.id, _external=True),
            'followed_posts': url_for('api.get_user_followed_posts',
                                      id=self.id, _external=True),
            'post_count': self.posts.count()
        }
        return json_user

    def generate_auth_token(self, expiration):
        s = Serializer(current_app.config['SECRET_KEY'],
                       expires_in=expiration)
        return s.dumps({'id': self.id}).decode('ascii')

    @staticmethod
    def verify_auth_token(token):
        s = Serializer(current_app.config['SECRET_KEY'])
        try:
            data = s.loads(token)
        except:
            return None
        return User.query.get(data['id'])

    def __repr__(self):
        return '<User %r>' % self.username


class AnonymousUser(AnonymousUserMixin):
    def can(self, permissions):
        return False

    def is_administrator(self):
        return False


login_manager.anonymous_user = AnonymousUser


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class Post(db.Model):
    __tablename__ = 'posts'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.Text)
    body = db.Column(db.Text)
    body_html = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    pins = db.Column(db.Text)

    # comments = db.relationship('Comment', backref='post', lazy='dynamic')

    @staticmethod
    def on_changed_body(target, value, oldvalue, initiator):
        allowed_tags = ['a', 'abbr', 'acronym', 'b', 'blockquote', 'code',
                        'em', 'i', 'li', 'ol', 'pre', 'strong', 'ul',
                        'h1', 'h2', 'h3', 'p']
        target.body_html = bleach.linkify(bleach.clean(
            markdown(value, output_format='html'),
            tags=allowed_tags, strip=True))

    def to_json(self):
        json_post = {
            'url': url_for('api.get_post', id=self.id, _external=True),
            'title': self.title,
            'body': self.body,
            'body_html': self.body_html,
            'pins': self.pins,
            'timestamp': self.timestamp,
            'author': url_for('api.get_user', id=self.author_id,
                              _external=True)
        }
        return json_post

    @staticmethod
    def from_json(json_post):
        body = json_post.get('body')
        if body is None or body == '':
            raise ValidationError('post does not have a body')
        title = json_post.get('title')
        return Post(body=body, title=title)


db.event.listen(Post.body, 'set', Post.on_changed_body)


class Comment(db.Model):
    __tablename__ = 'comments'
    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.Text)
    body_html = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    disabled = db.Column(db.Boolean)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'))

    @staticmethod
    def on_changed_body(target, value, oldvalue, initiator):
        allowed_tags = ['a', 'abbr', 'acronym', 'b', 'code', 'em', 'i',
                        'strong']
        target.body_html = bleach.linkify(bleach.clean(
            markdown(value, output_format='html'),
            tags=allowed_tags, strip=True))

    def to_json(self):
        json_comment = {
            'url': url_for('api.get_comment', id=self.id, _external=True),
            'body': self.body,
            'body_html': self.body_html,
            'timestamp': self.timestamp,
            'author': url_for('api.get_user', id=self.author_id,
                              _external=True),
        }
        return json_comment

    @staticmethod
    def from_json(json_comment):
        body = json_comment.get('body')
        if body is None or body == '':
            raise ValidationError('comment does not have a body')
        return Comment(body=body)


db.event.listen(Comment.body, 'set', Comment.on_changed_body)


class RandomTable(db.Model):
    __tablename__ = 'random_table'
    id = db.Column(db.Text, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    name = db.Column(db.Text)
    description = db.Column(db.Text)
    definition = db.Column(db.Text)
    min = db.Column(db.Integer)
    max = db.Column(db.Integer)
    description_html = db.Column(db.Text)
    permissions = db.Column(db.Integer, index=True)
    line_type = db.Column(db.Integer)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    tags = db.Column(db.Text, index=True)
    original_author_id = db.Column(db.Integer)
    row_count = db.Column(db.Integer)
    modifier_name = db.Column(db.Text)

    @staticmethod
    def on_changed_table(target, value, oldvalue, initiator):
        allowed_tags = ['a', 'abbr', 'acronym', 'b', 'blockquote', 'code',
                        'em', 'i', 'li', 'ol', 'pre', 'strong', 'ul',
                        'h1', 'h2', 'h3', 'p']
        target.description_html = bleach.linkify(bleach.clean(
            markdown(value, output_format='html'),
            tags=allowed_tags, strip=True))

    def to_json(self):

        definition = self.definition.splitlines()

        json_post = {
            'url': url_for('api.get_table', id=self.id, _external=True),
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'definition': definition,
            'permissions': self.permissions,
            'timestamp': self.timestamp,
            'author': url_for('api.get_user', id=self.author_id,
                              _external=True),
            'tags': self.tags,
            'original_author_id': self.original_author_id
        }
        return json_post

    @staticmethod
    def from_json(json_post):
        # check required fields
        for field in ('id', 'name', 'definition'):
            value = json_post.get(field)
            if value is None or value == '':
                raise ValidationError('Missing Field: ' + field)

        id = json_post.get('id')
        name = json_post.get('name')
        description = json_post.get('description')
        definition_lines = json_post.get('definition')
        definition = ""
        for idx, line in enumerate(definition_lines):
            definition += line
            if idx < len(definition_lines) - 1:
                definition += "\n"
        # permisssions = json_post.get('permissions')
        return RandomTable(id=id, name=name, description=description, definition=definition)


db.event.listen(RandomTable.description, 'set', RandomTable.on_changed_table)


class Macros(db.Model):
    __tablename__ = 'macros'
    id = db.Column(db.Text, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    name = db.Column(db.Text)
    definition = db.Column(db.Text)
    definition_html = db.Column(db.Text)
    permissions = db.Column(db.Integer, index=True)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    tags = db.Column(db.Text, index=True)
    original_author_id = db.Column(db.Integer)

    @staticmethod
    def on_changed_table(target, value, oldvalue, initiator):
        allowed_tags = ['a', 'abbr', 'acronym', 'b', 'blockquote', 'code',
                        'em', 'i', 'li', 'ol', 'pre', 'strong', 'ul',
                        'h1', 'h2', 'h3', 'p']
        target.definition_html = bleach.linkify(bleach.clean(
            markdown(value, output_format='html'),
            tags=allowed_tags, strip=True))

    def to_json(self):

        definition = self.definition.splitlines()

        json_post = {
            'url': url_for('api.get_macro', id=self.id, _external=True),
            'id': self.id,
            'name': self.name,
            'definition': definition,
            'permissions': self.permissions,
            'timestamp': self.timestamp,
            'author': url_for('api.get_user', id=self.author_id,
                              _external=True),
            'tags': self.tags,
            'original_author_id': self.original_author_id

        }
        return json_post

    @staticmethod
    def from_json(json_post):
        # check required fields
        for field in ('id', 'name', 'definition'):
            value = json_post.get(field)
            if value is None or value == '':
                raise ValidationError('Missing Field: ' + field)

        id = json_post.get('id')
        name = json_post.get('name')
        definition_lines = json_post.get('definition')
        definition = ""
        for idx, line in enumerate(definition_lines):
            definition += line
            if idx < len(definition_lines) - 1:
                definition += "\n"
        # permissions = json_post.get('permissions')
        return Macros(id=id, name=name, definition=definition)


db.event.listen(Macros.definition, 'set', Macros.on_changed_table)


class Collection(db.Model):
    __tablename__ = 'collection'
    id = db.Column(db.Text, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    name = db.Column(db.Text)
    description = db.Column(db.Text)
    definition = db.Column(db.Text)
    permissions = db.Column(db.Integer, index=True)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    tags = db.Column(db.Text, index=True)
    original_author_id = db.Column(db.Integer)

    def to_json(self):
        items = self.items.splitlines()
        json_post = {
            'url': url_for('api.get_collection', id=self.id, _external=True),
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'definition': items,
            'parent': self.parent,
            'permissions': self.permissions,
            'timestamp': self.timestamp,
            'author': url_for('api.get_user', id=self.author_id,
                              _external=True),
            'tags': self.tags,
            'original_author_id': self.original_author_id
        }
        return json_post

    @staticmethod
    def from_json(json_post):
        # check required fields
        for field in ('id', 'name', 'definition', 'parent'):
            value = json_post.get(field)
            if value is None or value == '':
                raise ValidationError('Missing Field: ' + field)

        id = json_post.get('id')
        name = json_post.get('name')
        definition_lines = json_post.get('definition')
        parent = json_post.get('parent')
        description = json_post.get('description')
        definition = ""
        for idx, line in enumerate(definition_lines):
            definition += line
            if idx < len(definition_lines) - 1:
                definition += "\n"
        # permissions = json_post.get('permissions')
        return Collection(id=id, name=name, definition=definition, parent=parent, description=description)


class Tags(db.Model):
    __tablename__ = 'tags'
    id = db.Column(db.Text, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)

    def to_json(self):
        json_post = {
            'url': url_for('api.get_macro', id=self.id, _external=True),
            'id': self.id,
            'timestamp': self.timestamp,
            'author': url_for('api.get_user', id=self.author_id,
                              _external=True)
        }
        return json_post

    @staticmethod
    def from_json(json_post):
        # check required fields
        for field in ('id'):
            value = json_post.get(field)
            if value is None or value == '':
                raise ValidationError('Missing Field: ' + field)

        id = json_post.get('id')
        return Tags(id=id)


class MarketPlace(db.Model):
    __tablename__ = 'marketplace'
    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    name = db.Column(db.Text)
    description = db.Column(db.Text)
    description_html = db.Column(db.Text)
    tags = db.Column(db.Text, index=True)
    permissions = db.Column(db.Integer)
    count = db.Column(db.Integer, default=0)
    price = db.Column(db.Float, default=0)
    on_sale = db.Column(db.Boolean, default=False)
    sale_price = db.Column(db.Float, default=0)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    categories = db.relationship('MarketCategory', backref='market_product', lazy='dynamic')

    @staticmethod
    def on_changed_body(target, value, oldvalue, initiator):
        allowed_tags = ['a', 'abbr', 'acronym', 'b', 'blockquote', 'code',
                        'em', 'i', 'li', 'ol', 'pre', 'strong', 'ul',
                        'h1', 'h2', 'h3', 'p']
        target.description_html = bleach.linkify(bleach.clean(
            markdown(value, output_format='html'),
            tags=allowed_tags, strip=True))

    def to_json(self):
        json_post = {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'description_html': self.description_html,
            'tags': self.tags,
            'permissions': self.permissions,
            'timestamp': self.timestamp,
            'author': url_for('api.get_user', id=self.author_id,
                              _external=True)
        }
        return json_post

    @staticmethod
    def from_json(json_post):
        # check required fields
        for field in ('name', 'description', 'product_id'):
            value = json_post.get(field)
            if value is None or value == '':
                raise ValidationError('Missing Field: ' + field)

        name = json_post.get('name')
        description = json_post.get('description')
        tags = str(json_post.get('tags'))
        permissions = 0

        return MarketPlace(name=name, description=description, product_id=product_id, permissions=permissions)


db.event.listen(MarketPlace.description, 'set', MarketPlace.on_changed_body)


class MarketCategory(db.Model):
    __tablename__ = 'market_category'
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    marketplace_id = db.Column(db.Integer, db.ForeignKey('marketplace.id'), primary_key=True)
    category_id = db.Column(db.Text, primary_key=True)

    def to_json(self):

        json_post = {
            'author': url_for('api.get_user', id=self.author_id,
                              _external=True),
            'marketplace_id': self.marketplace_id,
            'category_id': self.category_id
        }
        return json_post

    @staticmethod
    def from_json(json_post):
        # check required fields
        for field in ('marketplace_id', 'category_id'):
            value = json_post.get(field)
            if value is None or value == '':
                raise ValidationError('Missing Field: ' + field)

        marketplace_id = json_post.get('marketplace_id')
        category_id = json_post.get('category_id')
        return MarketCategory(marketplace_id=marketplace_id, category_id=category_id)
