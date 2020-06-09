import collections

from flask import render_template, redirect, url_for, abort, flash, request, \
    current_app, make_response, jsonify
from flask_login import login_required, current_user
from flask_sqlalchemy import get_debug_queries
from . import main
from .forms import EditProfileForm, EditProfileAdminForm, TableForm, StoryForm, MacroForm, \
    CollectionForm, TagForm, MarketForm, BulkTableImportForm, Share
from .. import db
from ..models import Permission, Role, User, Post, Comment, RandomTable, Macros, ProductPermission, Collection, Tags, \
    MarketPlace, MarketCategory
from ..public_models import *
from ..decorators import admin_required, permission_required
from ..validate import check_table_definition_validity, validate_text, validate_collection
from ..randomise_utils import *
from ..get_random_value import get_row_from_random_table_definition, process_text
from markdown import markdown
import bleach

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
    collection_list, macros, tables, tags, public_collections, public_macros, public_tables = required_data()
    stories = None
    if current_user.is_anonymous:
        public_tables = PublicRandomTable.query.order_by(PublicRandomTable.timestamp.desc()).limit(100)
        public_macros = PublicMacros.query.order_by(PublicMacros.timestamp.desc()).limit(100)
    else:
        stories = Post.query.filter(Post.author_id == current_user.id).order_by(Post.timestamp.desc())

    return render_template('index.html', tables=tables, macro_list=macros, collections=collection_list,
                           public_collections=public_collections, public_macros=public_macros,
                           public_tables=public_tables, stories=stories, tags=tags)


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

    collection_list, macros, tables, tags, public_collections, public_macros, public_tables = required_data()

    return render_template('table.html', form=form, tables=tables, macro_list=macros, tags=tags)


@main.route('/edit-table/<string:username>/<string:id>', methods=['GET', 'POST'])
@login_required
def edit_table(username, id):
    if current_user.username != username:
        abort(400)

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

    form.table_name.data = table.name
    form.table_description.data = table.description
    form.table_definition.data = table.definition
    form.table_tags.data = table.tags
    form.table_id.data = table.id
    form.table_id.render_kw = {'readonly': True}

    collection_list, macros, tables, tags, public_collections, public_macros, public_tables = required_data()

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

    collection_list, macros, tables, tags, public_collections, public_macros, public_tables = required_data()

    return render_template('story.html', form=form, tables=tables, macro_list=macros, collections=collection_list,
                           tags=tags, public_collections=public_collections,
                           public_macros=public_macros, public_tables=public_tables)


@main.route('/edit-story/<string:username>/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_story(username, id):
    if current_user.username != username:
        abort(400)

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

    collection_list, macros, tables, tags, public_collections, public_macros, public_tables = required_data()

    form.title.data = story.title
    form.story.data = story.body
    form.pins.data = story.pins

    return render_template('story.html', form=form, tables=tables, macro_list=macros, collections=collection_list,
                           tags=tags, public_collections=public_collections,
                           public_macros=public_macros, public_tables=public_tables)


@main.route('/random-value/<string:username>/<string:id>', methods=['GET'])
def get_random_value(username, id):
    table = get_random_table_record(username, id)
    if table is not None:
        return get_row_from_random_table_definition(table)

    return 'Error finding random table id: ' + username + '.table.' + id


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

    collection_list, macros, tables, tags, public_collections, public_macros, public_tables = required_data()

    return render_template('macro.html', form=form, macro_list=macros, tables=tables, form_type='macro', tags=tags)


@main.route('/edit-macro/<string:username>/<string:id>', methods=['GET', 'POST'])
@login_required
def edit_macro(username, id):
    if current_user.username != username:
        abort(400)

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
    form.macro_id.data = macro.id
    form.macro_id.render_kw = {'readonly': True}
    if macro.tags:
        form.macro_tags.data = macro.tags

    collection_list, macros, tables, tags, public_collections, public_macros, public_tables = required_data()

    return render_template('macro.html', form=form, macro_list=macros, tables=tables, edit_macro=macro,
                           form_type='macro', tags=tags)


@main.route('/macro/<string:username>/<string:id>', methods=['GET'])
def get_macro(username, id):
    macro = get_macro_record(username, id)
    if macro is not None:
        macro_text = process_text(macro.definition)
        return bleach.linkify(bleach.clean(markdown(macro_text, output_format='html'), tags=ALLOWED_TAGS, strip=True))
    else:
        return 'Error finding macro id: ' + username + '.macro.' + id


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

    collection_list, macros, tables, tags, public_collections, public_macros, public_tables = required_data()

    return render_template('collection.html', form=form, macro_list=macros, tables=tables, collections=collection_list,
                           tags=tags)


@main.route('/edit-collection/<string:username>/<string:id>', methods=['GET', 'POST'])
@login_required
def edit_collection(username, id):
    if current_user.username != username:
        abort(400)
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
    form.collection_tags.data = collection_obj.tags
    form.collection_id.data = collection_obj.id
    form.collection_id.render_kw = {'readonly': True}

    collection_list, macros, tables, tags, public_collections, public_macros, public_tables = required_data()

    return render_template('collection.html', form=form, macro_list=macros, tables=tables, collections=collection_list,
                           tags=tags)


@main.route('/collection/<string:username>/<string:id>', methods=['GET'])
def get_collection(username, id):
    collection = get_collection_record(username, id)
    if collection is not None:
        return collection.definition

    return 'Error finding collection id: ' + username + '.collection.' + id


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

    collection_list, macros, tables, tags, public_collections, public_macros, public_tables = required_data()

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

    collection_list, macros, tables, tags, public_collections, public_macros, public_tables = required_data()

    return render_template('market_product.html', form=form, macro_list=macros, tables=tables,
                           collections=collection_list, tags=tags)


@main.route('/discover', methods=['GET'])
def discover():
    free_products = PublicAnnouncements.query.filter(PublicAnnouncements.author_id != current_user.id).order_by(
        PublicAnnouncements.timestamp.desc()).limit(100);
    latest_marketproducts = MarketPlace.query.order_by(MarketPlace.timestamp.desc()).limit(50)
    popular_marketproducts = MarketPlace.query.order_by(MarketPlace.count.desc()).limit(50)
    all_categories = current_app.config['CATEGORIES'][:]
    market_categories = [pc[0] for pc in db.session.query(MarketCategory.category_id).distinct()]
    used_categories = [cat for cat in all_categories if cat[0] in market_categories]

    return render_template('discover.html',
                           all_categories=all_categories,
                           used_categories=used_categories,
                           latest_marketproducts=latest_marketproducts,
                           popular_marketproducts=popular_marketproducts,
                           free_products=free_products)


@main.route('/transfer-public-content/<string:public_id>', methods=['POST'])
@login_required
def transfer_public_content(public_id):
    if db.session.query(PublicAnnouncements) \
            .filter(PublicAnnouncements.id == public_id) \
            .filter(PublicAnnouncements.author_id == current_user.id) \
            .first() is None:
        new_content = UserPublicContent(announcement_id=public_id,
                                        author_id=current_user.id)
        db.session.add(new_content)

        public_collections = PublicCollection.query.filter(PublicCollection.announcement_id == public_id)
        public_macros = PublicMacros.query.filter(PublicMacros.announcement_id == public_id)
        public_tables = PublicRandomTable.query.filter(PublicRandomTable.announcement_id == public_id)

        for c in public_collections:
            if db.session.query(PublicLinkedCollections) \
                    .filter(PublicLinkedCollections.author_id == current_user.id) \
                    .filter(PublicLinkedCollections.collection_id == c.id) \
                    .filter(PublicLinkedCollections.original_author_id == c.author_id) \
                    .first() is None:
                new_collection = PublicLinkedCollections(author_id=current_user.id,
                                                         collection_id=c.id,
                                                         original_author_id=c.author_id)
                db.session.add(new_collection)

        for m in public_macros:
            if db.session.query(PublicLinkedMacros) \
                    .filter(PublicLinkedMacros.author_id == current_user.id) \
                    .filter(PublicLinkedMacros.macro_id == m.id) \
                    .filter(PublicLinkedMacros.original_author_id == m.author_id) \
                    .first() is None:
                new_macro = PublicLinkedMacros(author_id=current_user.id,
                                               macro_id=m.id,
                                               original_author_id=m.author_id)
                db.session.add(new_macro)

        for t in public_tables:
            if db.session.query(PublicLinkedTables) \
                    .filter(PublicLinkedTables.author_id == current_user.id) \
                    .filter(PublicLinkedTables.table_id == t.id) \
                    .filter(PublicLinkedTables.original_author_id == t.author_id) \
                    .first() is None:
                new_table = PublicLinkedTables(author_id=current_user.id,
                                               table_id=t.id,
                                               original_author_id=t.author_id)
                db.session.add(new_table)
        db.session.commit()
        return make_response(jsonify({'success': True}))
    return make_response(jsonify({'success': False}))


@main.route('/public-content/<string:public_id>', methods=['GET'])
def get_public_content(public_id):
    public_id = public_id[5:]
    public_collections = PublicCollection.query.with_entities(PublicCollection.id).filter_by(announcement_id=public_id)
    public_macros = PublicMacros.query.with_entities(PublicMacros.id).filter_by(announcement_id=public_id)
    public_tables = PublicRandomTable.query.with_entities(PublicRandomTable.id).filter_by(announcement_id=public_id)
    results = {"collections": [i[0] for i in public_collections], "macros": [i[0] for i in public_macros],
               "tables": [i[0] for i in public_tables]}
    return results


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


@main.route('/share-public', methods=['GET', 'POST'])
@login_required
def share_public():
    form = Share()
    if current_user.can(Permission.WRITE_ARTICLES) and form.validate_on_submit():
        with db.session.no_autoflush:
            public_collections = form.collections_shared.data.strip().split(' ')
            public_macros = form.macros_shared.data.strip().split(' ')
            public_tables = form.tables_shared.data.strip().split(' ')
            announcement = PublicAnnouncements(title=form.title.data,
                                               description=form.description.data,
                                               author_id=current_user.id)
            db.session.add(announcement)
            db.session.flush()
            if public_collections != ['']:
                for c_id in public_collections:
                    c = Collection.query.get([c_id[11:], current_user.id])
                    if not c:
                        db.session.rollback()
                        return render_template('error_page.html', description='Error finding Collection ' + c_id)
                    else:
                        pc = PublicCollection(id=c.id,
                                              name=c.name,
                                              definition=c.definition,
                                              tags=c.tags,
                                              author_id=current_user.id,
                                              permissions=ProductPermission.PUBLIC,
                                              announcement_id=announcement.id)
                        db.session.add(pc)
            if public_macros != ['']:
                for m_id in public_macros:
                    m = Macros.query.get([m_id[6:], current_user.id])
                    if not m:
                        db.session.rollback()
                        return render_template('error_page.html', description='Error finding Macro ' + m_id)
                    else:
                        pm = PublicMacros(id=m.id,
                                          name=m.name,
                                          definition=m.definition,
                                          tags=m.tags,
                                          author_id=current_user.id,
                                          permissions=ProductPermission.PUBLIC,
                                          announcement_id=announcement.id)
                        db.session.add(pm)
            if public_tables != ['']:
                for t_id in public_tables:
                    t = RandomTable.query.get([t_id[6:], current_user.id])
                    if not t:
                        db.session.rollback()
                        return render_template('error_page.html', description='Error finding Random Table ' + t_id)
                    else:
                        pt = PublicRandomTable(id=t.id,
                                               name=t.name,
                                               description=t.description,
                                               definition=t.definition,
                                               tags=t.tags,
                                               author_id=current_user.id,
                                               min=t.min,
                                               max=t.max,
                                               description_html=t.description_html,
                                               line_type=t.line_type,
                                               row_count=t.row_count,
                                               announcement_id=announcement.id)
                        db.session.add(pt)
            db.session.commit()
            flash('Content Shared')
            return redirect(url_for('.share_public'))

    collection_list, macros, tables, tags, public_collections, public_macros, public_tables = required_data()
    collection_references = collections.OrderedDict()
    table_references = collections.OrderedDict()
    macro_references = collections.OrderedDict()
    try:
        if collection_list.count():
            for c in collection_list:
                collection_references[current_user.username + '.collection.' + c.id] = build_collection_references(c)
        if tables.count():
            for t in tables:
                table_references[current_user.username + '.table.' + t.id] = find_references(
                    current_user.username + '.table.' + t.id, t.definition,
                    [current_user.username + '.table.' + t.id + '::0'], 0)
        if macros.count():
            for m in macros:
                macro_references[current_user.username + '.macro.' + m.id] = find_references(
                    current_user.username + '.macro.' + m.id, m.definition,
                    [current_user.username + '.macro.' + m.id + '::0'], 0)
    except Exception as inst:
        return render_template('error_page.html', description=inst)

    return render_template('share_public.html', form=form, tables=tables, macro_list=macros,
                           collections=collection_list, tags=tags, collection_references=collection_references,
                           table_references=table_references, macro_references=macro_references)


def build_collection_references(coll_obj):
    coll_dict = collections.OrderedDict()
    coll_definition = coll_obj.definition.splitlines()

    for coll_item in coll_definition:
        username, id_type, reference_id = split_id(coll_item)
        if id_type == 'table':
            table = get_random_table_record(username, reference_id)
            if table is not None:
                try:
                    coll_dict[coll_item] = find_references(coll_item, table.definition, [coll_item + '::0'], 0)
                except Exception as inst:
                    raise inst
            else:
                raise Exception('Table not found', coll_item + ' not found.')
        elif id_type == 'macro':
            macro = get_macro_record(username, reference_id)
            if macro is not None:
                try:
                    coll_dict[coll_item] = find_references(coll_item, macro.definition, [coll_item + '::0'], 0)
                except Exception as inst:
                    raise inst
            else:
                raise Exception('Macro not found', coll_item + ' not found')
        elif id_type == 'collection':
            sub_coll = get_collection_record(username, reference_id)
            if sub_coll is not None:
                coll_dict[coll_item] = build_collection_references(sub_coll)
            else:
                raise Exception('Collection Not Found', coll_item + ' not found in db for user ' + str(current_user.id))
    return coll_dict


def find_references(obj_id, definition, references, depth):
    depth += 1
    open_angle_brackets = definition.find("<<")
    while open_angle_brackets >= 0:
        close_angle_brackets = definition.find(">>", open_angle_brackets)
        external_id = definition[open_angle_brackets + 2:close_angle_brackets]
        if external_id + '::' + str(depth) in references:
            # already processed this id at this level
            open_angle_brackets = definition.find("<<", close_angle_brackets)
            continue
        # find if reference exists up the chain
        for d in range(0, depth - 1):
            if external_id + '::' + str(d) in references:
                raise Exception('CircularReference',
                                external_id + ' already used in chain. Found in ' + obj_id + '. Depth = ' + str(depth))
        username, id_type, reference_id = split_id(external_id)
        if id_type == 'table':
            table = get_random_table_record(username, reference_id)
            if table is not None:
                references.append(external_id + '::' + str(depth))
                find_references(external_id, table.definition, references, depth)
            else:
                raise Exception('Table not found', external_id + ' not found in db for user:' + str(current_user.id))
        elif id_type == 'macro':
            macro = get_macro_record(username, reference_id)
            if macro is not None:
                references.append(external_id + '::' + str(depth))
                find_references(external_id, macro.definition, references, depth)
            else:
                raise Exception('Macro not found', external_id + ' not found in db for user:' + str(current_user.id))
        open_angle_brackets = definition.find("<<", close_angle_brackets)
    return references


def tag_list():
    return [(p.id, p.id) for p in Tags.query.filter(Tags.author_id == current_user.id).order_by(Tags.id)]


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


def required_data():
    if current_user.is_anonymous:
        return None, None, None, None, None, None, None

    tables = table_query()
    macros = macro_query()
    collection_list = collection_query()
    tags = tag_query()
    public_tables = PublicLinkedTables.query.filter(PublicLinkedTables.author_id == current_user.id)
    public_macros = PublicLinkedMacros.query.filter(PublicLinkedMacros.author_id == current_user.id)
    public_collections = PublicLinkedCollections.query.filter(PublicLinkedCollections.author_id == current_user.id)
    return collection_list, macros, tables, tags, public_collections, public_macros, public_tables
