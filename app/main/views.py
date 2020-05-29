from flask import render_template, redirect, url_for, abort, flash, request, \
    current_app, make_response
from flask_login import login_required, current_user
from flask_sqlalchemy import get_debug_queries
from . import main
from .forms import EditProfileForm, EditProfileAdminForm, TableForm, StoryForm, MacroForm, \
    CollectionForm, TagForm, MarketForm, BulkTableImportForm
from .. import db
from ..models import Permission, Role, User, Post, Comment, RandomTable, Macros, ProductPermission, Collection, Tags, \
    MarketPlace, MarketCategory
from ..decorators import admin_required, permission_required
from ..validate import check_table_definition_validity, validate_text, validate_collection
from ..get_random_value import get_row_from_random_table_definition, process_text
import base64
from markdown import markdown
import bleach
import re

ALLOWED_TAGS = ['a', 'abbr', 'acronym', 'b', 'blockquote', 'code',
                'em', 'i', 'li', 'ol', 'pre', 'strong', 'ul',
                'h1', 'h2', 'h3', 'br']

non_url_safe = ['"', '#', '$', '%', '&', '+',
                ',', '/', ':', ';', '=', '?',
                '@', '[', '\\', ']', '^', '`',
                '{', '|', '}', '~', "'"]
translate_table = {ord(char): u'' for char in non_url_safe}


def slugify(text):
    text = text.translate(translate_table)
    text = u'_'.join(text.split())
    return text


@main.after_app_request
def after_request(response):
    for query in get_debug_queries():
        if query.duration >= current_app.config['RANDOMISE_IT_SLOW_DB_QUERY_TIME']:
            current_app.logger.warning(
                'Slow query: %s\nParameters: %s\nDuration: %fs\nContext: %s\n'
                % (query.statement, query.parameters, query.duration,
                   query.context))
    return response


@main.route('/', methods=['GET', 'POST'])
def index():
    tables = None
    macros = None
    collections = None
    market_products = None
    stories = None
    tags = None
    if current_user.is_authenticated:
        tables = table_query()
        macros = macro_query()
        collections = collection_query()
        market_products = MarketPlace.query.filter(MarketPlace.author_id == current_user.id).order_by(
            MarketPlace.timestamp.desc())
        stories = Post.query.filter(Post.author_id == current_user.id).order_by(Post.timestamp.desc())
        tags = tag_query()
    else:
        tables = RandomTable.query.filter_by(permissions=ProductPermission.PUBLIC) \
            .order_by(RandomTable.timestamp.desc())
        macros = Macros.query.filter_by(permissions=ProductPermission.PUBLIC) \
            .order_by(Macros.timestamp.desc())

    # Hacky DB update :)
    # update_row_count = RandomTable.query.filter_by(row_count=None)
    # if update_row_count.count() >0:
    #     for t in update_row_count:
    #         if t.line_type == 0:
    #             t.row_count = t.max
    #         else:
    #             t.row_count = len(t.definition.splitlines())
    #     db.session.commit()

    return render_template('index.html', tables=tables, macro_list=macros, collections=collections,
                           market_products=market_products, stories=stories, tags=tags)


@main.route('/user/<username>')
def user(username):
    user = User.query.filter_by(username=username).first_or_404()
    page = request.args.get('page', 1, type=int)
    pagination = user.posts.order_by(Post.timestamp.desc()).paginate(
        page, per_page=current_app.config['RANDOMISE_IT_POSTS_PER_PAGE'],
        error_out=False)
    stories = pagination.items
    tables = table_query()
    macros = macro_query()
    collection_list = collection_query()

    return render_template('user.html', user=user, stories=stories,
                           pagination=pagination, tables=tables, macro_list=macros, collections=collection_list)


@main.route('/edit-profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    form = EditProfileForm()
    if form.validate_on_submit():
        current_user.name = form.name.data
        current_user.location = form.location.data
        current_user.about_me = form.about_me.data
        db.session.add(current_user)
        flash('Your profile has been updated.')
        return redirect(url_for('.user', username=current_user.username))
    form.name.data = current_user.name
    form.location.data = current_user.location
    form.about_me.data = current_user.about_me
    return render_template('profile.html', form=form)


@main.route('/edit-profile/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_profile_admin(id):
    user = User.query.get_or_404(id)
    form = EditProfileAdminForm(user=user)
    if form.validate_on_submit():
        user.email = form.email.data
        user.username = form.username.data
        user.confirmed = form.confirmed.data
        user.role = Role.query.get(form.role.data)
        user.name = form.name.data
        user.location = form.location.data
        user.about_me = form.about_me.data
        db.session.add(user)
        flash('The profile has been updated.')
        return redirect(url_for('.user', username=user.username))
    form.email.data = user.email
    form.username.data = user.username
    form.confirmed.data = user.confirmed
    form.role.data = user.role_id
    form.name.data = user.name
    form.location.data = user.location
    form.about_me.data = user.about_me
    return render_template('profile.html', form=form, user=user)


@main.route('/follow/<username>')
@login_required
@permission_required(Permission.FOLLOW)
def follow(username):
    user = User.query.filter_by(username=username).first()
    if user is None:
        flash('Invalid user.')
        return redirect(url_for('.index'))
    if current_user.is_following(user):
        flash('You are already following this user.')
        return redirect(url_for('.user', username=username))
    current_user.follow(user)
    flash('You are now following %s.' % username)
    return redirect(url_for('.user', username=username))


@main.route('/unfollow/<username>')
@login_required
@permission_required(Permission.FOLLOW)
def unfollow(username):
    user = User.query.filter_by(username=username).first()
    if user is None:
        flash('Invalid user.')
        return redirect(url_for('.index'))
    if not current_user.is_following(user):
        flash('You are not following this user.')
        return redirect(url_for('.user', username=username))
    current_user.unfollow(user)
    flash('You are not following %s anymore.' % username)
    return redirect(url_for('.user', username=username))


@main.route('/followers/<username>')
def followers(username):
    user = User.query.filter_by(username=username).first()
    if user is None:
        flash('Invalid user.')
        return redirect(url_for('.index'))
    page = request.args.get('page', 1, type=int)
    pagination = user.followers.paginate(
        page, per_page=current_app.config['RANDOMISE_IT_FOLLOWERS_PER_PAGE'],
        error_out=False)
    follows = [{'user': item.follower, 'timestamp': item.timestamp}
               for item in pagination.items]
    return render_template('followers.html', user=user, title="Followers of",
                           endpoint='.followers', pagination=pagination,
                           follows=follows)


@main.route('/followed-by/<username>')
def followed_by(username):
    user = User.query.filter_by(username=username).first()
    if user is None:
        flash('Invalid user.')
        return redirect(url_for('.index'))
    page = request.args.get('page', 1, type=int)
    pagination = user.followed.paginate(
        page, per_page=current_app.config['RANDOMISE_IT_FOLLOWERS_PER_PAGE'],
        error_out=False)
    follows = [{'user': item.followed, 'timestamp': item.timestamp}
               for item in pagination.items]
    return render_template('followers.html', user=user, title="Followed by",
                           endpoint='.followed_by', pagination=pagination,
                           follows=follows)


@main.route('/all')
@login_required
def show_all():
    resp = make_response(redirect(url_for('.index')))
    resp.set_cookie('show_followed', '', max_age=30 * 24 * 60 * 60)
    return resp


@main.route('/followed')
@login_required
def show_followed():
    resp = make_response(redirect(url_for('.index')))
    resp.set_cookie('show_followed', '1', max_age=30 * 24 * 60 * 60)
    return resp


@main.route('/moderate')
@login_required
@permission_required(Permission.MODERATE_COMMENTS)
def moderate():
    page = request.args.get('page', 1, type=int)
    pagination = Comment.query.order_by(Comment.timestamp.desc()).paginate(
        page, per_page=current_app.config['RANDOMISE_IT_COMMENTS_PER_PAGE'],
        error_out=False)
    comments = pagination.items
    return render_template('moderate.html', comments=comments,
                           pagination=pagination, page=page)


@main.route('/moderate/enable/<int:id>')
@login_required
@permission_required(Permission.MODERATE_COMMENTS)
def moderate_enable(id):
    comment = Comment.query.get_or_404(id)
    comment.disabled = False
    db.session.add(comment)
    return redirect(url_for('.moderate',
                            page=request.args.get('page', 1, type=int)))


@main.route('/moderate/disable/<int:id>')
@login_required
@permission_required(Permission.MODERATE_COMMENTS)
def moderate_disable(id):
    comment = Comment.query.get_or_404(id)
    comment.disabled = True
    db.session.add(comment)
    return redirect(url_for('.moderate',
                            page=request.args.get('page', 1, type=int)))


@main.route('/create-table', methods=['GET', 'POST'])
@login_required
def create_table():
    form = TableForm()
    form.table_tags.choices = tag_list()
    form.table_tags.choices.insert(0, (' ', ''))

    if current_user.can(Permission.WRITE_ARTICLES) and \
            form.validate_on_submit():
        table = RandomTable(id=form.table_id.data,
                            name=form.table_name.data,
                            description=form.table_description.data,
                            definition=form.table_definition.data,
                            tags=form.table_tags.data,
                            author_id=current_user.id)

        max_rng, min_rng, validate_table_definition, table_type, error_message, row_count = check_table_definition_validity(
            table)
        if validate_table_definition:
            table.min = min_rng
            table.max = max_rng
            table.line_type = table_type
            table.row_count = row_count
            db.session.add(table)
            flash('Table Created')
            return redirect(url_for('.create_table'))
        else:
            flash(error_message)

    tables = table_query()
    macros = macro_query()
    tags = tag_query()

    return render_template('table.html', form=form, tables=tables, macro_list=macros, tags=tags)


@main.route('/edit-table/<string:id>', methods=['GET', 'POST'])
@login_required
def edit_table(id):
    # current_app.logger.warning(current_user._get_current_object().id)
    table = RandomTable.query.get_or_404([id, current_user.id])
    if current_user != table.author and \
            not current_user.can(Permission.ADMINISTER):
        abort(403)
    form = TableForm()
    form.table_tags.choices = tag_list()
    form.table_tags.choices.insert(0, (' ', ''))

    if form.validate_on_submit():
        # table.id = form.table_id.data
        table.name = form.table_name.data
        table.description = form.table_description.data
        table.definition = form.table_definition.data
        table.tags = form.table_tags.data

        max_rng, min_rng, validate_table_definition, table_type, error_message, row_count = check_table_definition_validity(
            table)
        if validate_table_definition:
            table.min = min_rng
            table.max = max_rng
            table.line_type = table_type
            table.row_count = row_count
            db.session.add(table)
            flash('Your table has been updated.')
            return redirect(url_for('.edit_table', id=table.id, page=-1))
        else:
            flash(error_message)

    # form.table_id.data = table.id
    form.table_name.data = table.name
    form.table_description.data = table.description
    form.table_definition.data = table.definition
    # form.table_permissions.data = str(table.permissions)
    form.table_tags.data = table.tags

    tables = table_query()
    macros = macro_query()
    tags = tag_query()

    del form.table_id  # remove id from edit screen form

    return render_template('table.html', tables=tables, macro_list=macros, form=form, tags=tags)


@main.route('/bulk-table-import', methods=['GET', 'POST'])
@login_required
def bulk_table_import():
    form = BulkTableImportForm()
    form.bulk_tag.choices = tag_list()
    form.bulk_tag.choices.insert(0, (' ', ''))

    if current_user.can(Permission.WRITE_ARTICLES) and form.validate_on_submit():
        new_table = ''
        new_table_id = ''
        new_table_definition = ''
        table_lines = form.tables.data.splitlines()
        table_count = 0
        error_on_import = False
        for line in table_lines:
            if not new_table:
                new_table = line
                new_table_id = slugify(line)
                if not RandomTable.query.get([new_table_id, current_user.id]):
                    continue
                else:
                    flash("Table '" + new_table + "' already exists. Bulk import cancelled.")
                    db.session.rollback()
                    error_on_import = True
                    break
            if not line:
                # Blank line denotes separator
                # write table
                table = RandomTable(id=new_table_id,
                                    name=new_table,
                                    description='',
                                    definition=new_table_definition,
                                    tags=form.bulk_tag.data,
                                    author_id=current_user.id)

                max_rng, min_rng, validate_table_definition, table_type, error_message, row_count = check_table_definition_validity(
                    table)
                if validate_table_definition:
                    table.min = min_rng
                    table.max = max_rng
                    table.line_type = table_type
                    table.row_count = row_count
                    db.session.add(table)
                    table_count += 1
                    new_table = ''
                    new_table_id = ''
                    new_table_definition = ''
                    continue
                else:
                    flash(error_message)
                    db.session.rollback()
                    error_on_import = True
                    break
            new_table_definition += line + '\n'
        if not error_on_import:
            db.session.commit()
            flash(str(table_count) + ' Tables Created')
        return redirect(url_for('.bulk_table_import'))

    return render_template('bulk_table_import.html', form=form)


@main.route('/create-story', methods=['GET', 'POST'])
@login_required
def create_story():
    form = StoryForm()
    if current_user.can(Permission.WRITE_ARTICLES) and form.validate_on_submit():
        story = Post(body=form.story.data,
                     title=form.title.data,
                     pins=form.pins.data,
                     author=current_user._get_current_object())
        db.session.add(story)
        flash('Story Created')
        return redirect(url_for('.create_story'))

    tables = table_query()
    macros = macro_query()
    collection_list = collection_query()
    tags = tag_query()
    # auth_encoded = base64.b64encode(current_user.generate_auth_token(expiration=86400) + ':')

    return render_template('story.html', form=form, tables=tables, macro_list=macros, collections=collection_list,
                           tags=tags)


@main.route('/edit-story/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_story(id):
    story = Post.query.get_or_404(id)
    if current_user != story.author and not current_user.can(Permission.ADMINISTER):
        abort(403)

    form = StoryForm()
    if current_user.can(Permission.WRITE_ARTICLES) and form.validate_on_submit():
        story.title = form.title.data
        story.body = form.story.data
        story.pins = form.pins.data
        db.session.add(story)
        flash('Story Updated')

    tables = table_query()
    macros = macro_query()
    collection_list = collection_query()
    tags = tag_query()

    # required in order to talk to API
    # auth_encoded = base64.b64encode(current_user.generate_auth_token(expiration=86400) + ':')

    form.title.data = story.title
    form.story.data = story.body
    form.pins.data = story.pins

    return render_template('story.html', form=form, tables=tables, macro_list=macros, collections=collection_list,
                           tags=tags)


@main.route('/random-value/<string:id>', methods=['GET'])
def get_random_value(id):
    if current_user.is_authenticated:
        table = RandomTable.query.get_or_404([id, current_user.id])
    else:
        table = RandomTable.query.filter_by(id=id).first()

    if table is not None:
        # return render_template('random-value.html', text=get_row_from_random_table_definition(table))
        return get_row_from_random_table_definition(table)
    else:
        flash('Table id ' + id + ' not found')
        return redirect(url_for('.index'))


@main.route('/create-macro', methods=['GET', 'POST'])
@login_required
def create_macro():
    form = MacroForm()
    form.macro_tags.choices = tag_list()
    form.macro_tags.choices.insert(0, (' ', ''))

    if current_user.can(Permission.WRITE_ARTICLES) and form.validate_on_submit():
        macro = Macros(id=form.macro_id.data,
                       name=form.macro_name.data,
                       definition=form.macro_body.data,
                       tags=form.macro_tags.data,
                       author_id=current_user.id)

        validate_macro_definition, error_message = validate_text(macro.definition, macro.id)
        if validate_macro_definition:
            db.session.add(macro)
            flash('Macro Created')
            return redirect(url_for('.create_macro'))
        else:
            flash(error_message)

    tables = table_query()
    macros = macro_query()
    tags = tag_query()

    return render_template('macro.html', form=form, macro_list=macros, tables=tables, form_type='macro', tags=tags)


@main.route('/edit-macro/<string:id>', methods=['GET', 'POST'])
@login_required
def edit_macro(id):
    # current_app.logger.warning(current_user._get_current_object().id)
    macro = Macros.query.get_or_404([id, current_user.id])
    if current_user.id != macro.author_id and not current_user.can(Permission.ADMINISTER):
        abort(403)
    form = MacroForm()
    form.macro_tags.choices = tag_list()
    form.macro_tags.choices.insert(0, ('', '---'))
    if form.validate_on_submit():
        macro.name = form.macro_name.data
        macro.definition = form.macro_body.data
        if form.macro_tags.data != '':
            macro.tags = form.macro_tags.data

        validate_macro_definition, error_message = validate_text(macro.definition, macro.id)
        if validate_macro_definition:
            db.session.add(macro)
            flash('Your macro has been updated.')
            return redirect(url_for('.edit_macro', id=macro.id, page=-1))
        else:
            flash(error_message)

    form.macro_name.data = macro.name
    form.macro_body.data = macro.definition
    # form.permissions.data = 0
    if macro.tags:
        form.macro_tags.data = macro.tags

    tables = table_query()
    macros = macro_query(id)
    tags = tag_query()

    del form.macro_id  # remove id from edit screen
    return render_template('macro.html', form=form, macro_list=macros, tables=tables, edit_macro=macro,
                           form_type='macro', tags=tags)


@main.route('/macro/<string:id>', methods=['GET'])
def get_macro(id):
    macro = Macros.query.get_or_404([id, current_user.id])

    text = bleach.linkify(bleach.clean(
        markdown(process_text(macro.definition), output_format='html'),
        tags=ALLOWED_TAGS, strip=True))

    return text


@main.route('/preview-macro', methods=['POST'])
def preview_macro():
    macro = request.form['macro'].replace('\n', '<br/>')
    if macro:
        return bleach.linkify(bleach.clean(
            markdown(process_text(macro), output_format='html'),
            tags=ALLOWED_TAGS, strip=True))
    else:
        abort(400)


@main.route('/create-collection', methods=['GET', 'POST'])
@login_required
def create_collection():
    form = CollectionForm()
    form.collection_tags.choices = tag_list()
    form.collection_tags.choices.insert(0, (' ', ''))

    if current_user.can(Permission.WRITE_ARTICLES) and form.validate_on_submit():
        collection_obj = Collection(id=form.collection_id.data,
                                    name=form.collection_name.data,
                                    definition=form.collection_definition.data,
                                    tags=form.collection_tags.data,
                                    author_id=current_user.id)

        validate, error_message = validate_collection(collection_obj.definition)
        if validate:
            db.session.add(collection_obj)
            flash('Collection Created')
            return redirect(url_for('.create_collection'))
        else:
            flash(error_message)

    tables = table_query()
    macros = macro_query()
    collection_list = collection_query()
    tags = tag_query()

    return render_template('collection.html', form=form, macro_list=macros, tables=tables, collections=collection_list,
                           tags=tags)


@main.route('/edit-collection/<string:id>', methods=['GET', 'POST'])
@login_required
def edit_collection(id):
    # current_app.logger.warning(current_user._get_current_object().id)
    collection_obj = Collection.query.get_or_404([id, current_user.id])
    if current_user.id != collection_obj.author_id and not current_user.can(Permission.ADMINISTER):
        abort(403)
    form = CollectionForm()
    form.collection_tags.choices = tag_list()
    form.collection_tags.choices.insert(0, (' ', ''))

    if form.validate_on_submit():
        collection_obj.name = form.collection_name.data
        collection_obj.description = form.collection_description.data
        collection_obj.definition = form.collection_definition.data
        collection_obj.tags = form.collection_tags.data

        validate, error_message = validate_collection(collection_obj.definition)
        if validate:
            db.session.add(collection_obj)
            flash('Your collection has been updated.')
        else:
            flash(error_message)

    form.collection_name.data = collection_obj.name
    form.collection_description.data = collection_obj.description
    form.collection_definition.data = collection_obj.definition
    # form.permissions.data = 0
    form.collection_tags.data = collection_obj.tags
    form.collection_id.data = collection_obj.id
    form.collection_id.render_kw = {'readonly': True}

    tables = table_query()
    macros = macro_query()
    collection_list = collection_query()
    tags = tag_query()

    return render_template('collection.html', form=form, macro_list=macros, tables=tables, collections=collection_list,
                           tags=tags)


@main.route('/collection/<string:id>', methods=['GET'])
def get_collection(id):
    collection_data = Collection.query.get_or_404([id, current_user.id])
    return collection_data.definition


@main.route('/create-tag', methods=['GET', 'POST'])
@login_required
def create_tag():
    form = TagForm()
    if current_user.can(Permission.WRITE_ARTICLES) and form.validate_on_submit():
        tag = Tags(id=form.tag_id.data,
                   author_id=current_user.id)

        db.session.add(tag)
        flash('Tag Created')
        return redirect(url_for('.create_tag'))

    return render_template('create_tag.html', form=form, form_type='tag')


@main.route('/create-market-product', methods=['GET', 'POST'])
@login_required
def create_market_product():
    form = MarketForm()
    form.market_tags.choices = tag_list()
    form.category1.choices = current_app.config['CATEGORIES'][:]
    form.category1.choices.insert(0, ["0", ""])
    form.category2.choices = current_app.config['CATEGORIES'][:]
    form.category2.choices.insert(0, ["0", ""])

    if current_user.can(Permission.WRITE_ARTICLES) and form.validate_on_submit():
        permission = 0
        if bool(form.commercial.data):
            permission = permission & ProductPermission.COMMERCIAL
        else:
            permission = permission & ProductPermission.PUBLIC
        if bool(form.open.data):
            permission = permission & ProductPermission.OPEN
            if bool(form.editable.data):
                permission = permission & ProductPermission.EDITABLE

        market_product = MarketPlace(name=form.name.data,
                                     description=form.description.data,
                                     permissions=permission,
                                     tags=form.market_tags.data,
                                     author_id=current_user.id)

        db.session.add(market_product)
        db.session.commit()
        # add categories
        if bool(form.category1.data):
            market_category1 = MarketCategory(author_id=current_user.id,
                                              marketplace_id=market_product.id,
                                              category_id=form.category1.data)
            db.session.add(market_category1)
        if bool(form.category2.data):
            market_category2 = MarketCategory(author_id=current_user.id,
                                              marketplace_id=market_product.id,
                                              category_id=form.category2.data)
            db.session.add(market_category2)
        db.session.commit()
        flash('Market Product Created')
        return redirect(url_for('.create_market_product'))

    tables = table_query()
    macros = macro_query()
    collection_list = collection_query()
    tags = tag_query()

    return render_template('market_product.html', form=form, macro_list=macros, tables=tables,
                           collections=collection_list, tags=tags)


@main.route('/edit-market-product/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_market_product(id):
    # current_app.logger.warning(current_user._get_current_object().id)
    market_product = MarketPlace.query.get_or_404(id)
    if current_user.id != market_product.author_id and not current_user.can(Permission.ADMINISTER):
        abort(403)
    form = MarketForm()
    form.market_tags.choices = tag_list()
    form.category1.choices = current_app.config['CATEGORIES'][:]
    form.category1.choices.insert(0, ["0", ""])
    form.category2.choices = current_app.config['CATEGORIES'][:]
    form.category2.choices.insert(0, ["0", ""])

    if form.validate_on_submit():
        market_product.name = form.name.data
        market_product.description = form.description.data
        market_product.tags = form.market_tags.data;
        permission = 0
        if form.commercial.data:
            permission = permission & ProductPermission.COMMERCIAL
        else:
            permission = permission & ProductPermission.PUBLIC
        if form.open.data:
            permission = permission & ProductPermission.OPEN
            if form.editable.data:
                permission = permission & ProductPermission.EDITABLE
        market_product.permission = permission

        db.session.add(market_product)
        flash('Your market product has been updated.')

    form.name.data = market_product.name
    form.description.data = market_product.description

    tables = table_query()
    macros = macro_query()
    collection_list = collection_query()
    tags = tag_query()

    return render_template('market_product.html', form=form, macro_list=macros, tables=tables,
                           collections=collection_list, tags=tags)


@main.route('/marketplace', methods=['GET'])
def view_marketplace():
    latest_marketproducts = MarketPlace.query.order_by(MarketPlace.timestamp.desc()).limit(50)
    popular_marketproducts = MarketPlace.query.order_by(MarketPlace.count.desc()).limit(50)

    all_categories = current_app.config['CATEGORIES'][:]

    market_categories = [pc[0] for pc in db.session.query(MarketCategory.category_id).distinct()]

    used_categories = [cat for cat in all_categories if cat[0] in market_categories]

    return render_template('view_marketplace.html',
                           all_categories=all_categories,
                           used_categories=used_categories,
                           latest_marketproducts=latest_marketproducts,
                           popular_marketproducts=popular_marketproducts)


@main.route('/id-check/<string:type>/<string:id>', methods=['GET'])
@login_required
def id_exists(type, id):
    check = "0"

    if type == 'table':
        check = db.session.query(RandomTable.id).filter_by(id=id).scalar() is not None
    elif type == 'macro':
        check = db.session.query(Macros.id).filter_by(id=id).scalar() is not None
    elif type == 'collection':
        check = db.session.query(Collection.id).filter_by(id=id).scalar() is not None
    elif type == 'tag':
        check = db.session.query(Tags.id).filter_by(id=id).scalar() is not None
    elif type == 'marketproduct':
        check = db.session.query(MarketPlace.id).filter_by(id=id).scalar() is not None

    return str(int(check == True))


def tag_list():
    return [(p.id, p.id) for p in Tags
        .query
        .filter(Tags.author_id == current_user.id)
        .order_by(Tags.id)]


def macro_query(macro_id=None):
    if macro_id:
        return Macros.query.filter(Macros.author_id == current_user.id, Macros.id != macro_id).order_by(
            Macros.timestamp.desc())
    return Macros.query.filter(Macros.author_id == current_user.id).order_by(Macros.timestamp.desc())


def table_query():
    return RandomTable.query.filter(RandomTable.author_id == current_user.id).order_by(RandomTable.timestamp.desc())


def collection_query():
    return Collection.query.filter(Collection.author_id == current_user.id).order_by(Collection.timestamp.desc())


def tag_query():
    return Tags.query.filter(Tags.author_id == current_user.id).order_by(Tags.id.asc())
