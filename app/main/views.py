import collections

from flask import render_template, redirect, url_for, abort, flash, request, \
    current_app, make_response, jsonify
from flask_login import login_required, current_user
from sqlalchemy import and_, text, func
from flask_sqlalchemy import get_debug_queries
from . import main
from .forms import EditProfileForm, EditProfileAdminForm, TableForm, StoryForm, MacroForm, \
    CollectionForm, TagForm, MarketForm, BulkTableImportForm, Share
from .. import db
from ..models import Permission, Role, User, Post, RandomTable, Macros, ProductPermission, Collection, Tags, \
    MarketPlace, MarketCategory
from ..public_models import *
from ..decorators import admin_required, permission_required
from ..validate import check_table_definition_validity, validate_text, validate_collection
from ..randomise_utils import *
from ..get_random_value import get_row_from_random_table_definition, process_text_extended
from markdown import markdown
import bleach
import re

ALLOWED_TAGS = ['a', 'abbr', 'acronym', 'b', 'blockquote', 'code',
                'em', 'i', 'li', 'ol', 'pre', 'strong', 'ul',
                'h1', 'h2', 'h3', 'br']
non_url_safe = ['"', '#', '$', '%', '&', '+',
                ',', '/', ':', ';', '=', '?',
                '@', '[', '\\', ']', '^', '`',
                '{', '|', '}', '~', "'", "."]
translate_table = {ord(char): u'' for char in non_url_safe}


def slugify(slug_text):
    slug_text = slug_text.translate(translate_table)
    slug_text = u'-'.join(slug_text.split())
    slug_text = re.sub('--+', '-', slug_text)
    return slug_text


@main.after_app_request
def after_request(response):
    for query in get_debug_queries():
        if query.duration >= current_app.config['RANDOMIST_SLOW_DB_QUERY_TIME']:
            current_app.logger.warning(
                'Slow query: %s\nParameters: %s\nDuration: %fs\nContext: %s\n'
                % (query.statement, query.parameters, query.duration,
                   query.context))
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response


@main.route('/', methods=['GET'])
def index():
    collection_list, macros, tables, tags, public_collections, public_macros, public_tables = required_data()
    stories = None
    if current_user.is_anonymous:
        public_tables = PublicRandomTable.query.filter(PublicRandomTable.supporting == False).order_by(func.random()).limit(10)
        public_macros = PublicMacros.query.filter(PublicMacros.supporting == False).order_by(func.random()).limit(10)
    else:
        stories = Post.query.filter(Post.author_id == current_user.id).order_by(Post.timestamp.desc())

    return render_template('index.html', tables=tables, macro_list=macros, collections=collection_list,
                           public_collections=public_collections, public_macros=public_macros,
                           public_tables=public_tables, stories=stories, tags=tags)


@main.route('/about', methods=['GET'])
def about():
    return render_template('about.html')


@main.route('/user/<username>')
def user(username):
    user = User.query.filter_by(username=username).first_or_404()
    # page = request.args.get('page', 1, type=int)
    # pagination = user.posts.order_by(Post.timestamp.desc()).paginate(
    #     page, per_page=current_app.config['RANDOMIST_POSTS_PER_PAGE'],
    #     error_out=False)
    story_count = Post.query.filter(Post.author_id == current_user.id).count()
    table_count = RandomTable.query.filter(RandomTable.author_id == current_user.id).count()
    macro_count = Macros.query.filter(Macros.author_id == current_user.id).count()
    collection_count = Collection.query.filter(Collection.author_id == current_user.id).count()

    stats = {
        "story_count": story_count,
        "table_count": table_count,
        "macro_count": macro_count,
        "collection_count": collection_count
    }

    shared_content = PublicAnnouncements.query.filter(PublicAnnouncements.author_id == current_user.id)
    shared_content_owned = UserPublicContent.query.filter(UserPublicContent.author_id == current_user.id)

    sql = text(
        'SELECT * FROM random_table JOIN public_random_table ON public_random_table.id = random_table.id AND '
        'public_random_table.author_id = random_table.author_id '
        'WHERE random_table.author_id = ' + str(
            current_user.id) + ' and public_random_table.last_modified != random_table.last_modified')
    updated_tables = db.engine.execute(sql)

    sql = text('SELECT * FROM macros JOIN public_macros ON public_macros.id = macros.id AND '
               'public_macros.author_id = macros.author_id '
               'WHERE macros.author_id = ' + str(
        current_user.id) + ' and public_macros.last_modified != macros.last_modified')
    updated_macros = db.engine.execute(sql)

    sql = text(
        'SELECT * FROM collection JOIN public_collection ON public_collection.id = collection.id AND '
        'public_collection.author_id = collection.author_id '
        'WHERE collection.author_id = ' + str(
            current_user.id) + ' and public_collection.last_modified != collection.last_modified')
    updated_collections = db.engine.execute(sql)

    tags = tag_query()

    return render_template('user.html', user=user, stats=stats,
                           shared_content=shared_content, shared_content_owned=shared_content_owned,
                           updated_tables=updated_tables, updated_macros=updated_macros,
                           updated_collections=updated_collections, tags=tags)


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


@main.route('/administ', methods=['GET'])
@login_required
@admin_required
def admin_view():
    stats = {}
    user_count = db.session.query(User).count()
    stats["User_Count"] = user_count
    announcement_count = db.session.query(PublicAnnouncements).count()
    stats["Announcement_Count"] = announcement_count

    users = User.query.order_by(User.member_since.desc()).limit(10)

    return render_template('administ.html', stats=stats.items(), users=users)


# @main.route('/follow/<username>')
# @login_required
# @permission_required(Permission.FOLLOW)
# def follow(username):
#     user = User.query.filter_by(username=username).first()
#     if user is None:
#         flash('Invalid user.')
#         return redirect(url_for('.index'))
#     if current_user.is_following(user):
#         flash('You are already following this user.')
#         return redirect(url_for('.user', username=username))
#     current_user.follow(user)
#     flash('You are now following %s.' % username)
#     return redirect(url_for('.user', username=username))


# @main.route('/unfollow/<username>')
# @login_required
# @permission_required(Permission.FOLLOW)
# def unfollow(username):
#     user = User.query.filter_by(username=username).first()
#     if user is None:
#         flash('Invalid user.')
#         return redirect(url_for('.index'))
#     if not current_user.is_following(user):
#         flash('You are not following this user.')
#         return redirect(url_for('.user', username=username))
#     current_user.unfollow(user)
#     flash('You are not following %s anymore.' % username)
#     return redirect(url_for('.user', username=username))


# @main.route('/followers/<username>')
# def followers(username):
#     user = User.query.filter_by(username=username).first()
#     if user is None:
#         flash('Invalid user.')
#         return redirect(url_for('.index'))
#     page = request.args.get('page', 1, type=int)
#     pagination = user.followers.paginate(
#         page, per_page=current_app.config['RANDOMIST_FOLLOWERS_PER_PAGE'],
#         error_out=False)
#     follows = [{'user': item.follower, 'timestamp': item.timestamp}
#                for item in pagination.items]
#     return render_template('followers.html', user=user, title="Followers of",
#                            endpoint='.followers', pagination=pagination,
#                            follows=follows)


# @main.route('/followed-by/<username>')
# def followed_by(username):
#     user = User.query.filter_by(username=username).first()
#     if user is None:
#         flash('Invalid user.')
#         return redirect(url_for('.index'))
#     page = request.args.get('page', 1, type=int)
#     pagination = user.followed.paginate(
#         page, per_page=current_app.config['RANDOMIST_FOLLOWERS_PER_PAGE'],
#         error_out=False)
#     follows = [{'user': item.followed, 'timestamp': item.timestamp}
#                for item in pagination.items]
#     return render_template('followers.html', user=user, title="Followed by",
#                            endpoint='.followed_by', pagination=pagination,
#                            follows=follows)


# @main.route('/all')
# @login_required
# def show_all():
#     resp = make_response(redirect(url_for('.index')))
#     resp.set_cookie('show_followed', '', max_age=30 * 24 * 60 * 60)
#     return resp


# @main.route('/followed')
# @login_required
# def show_followed():
#     resp = make_response(redirect(url_for('.index')))
#     resp.set_cookie('show_followed', '1', max_age=30 * 24 * 60 * 60)
#     return resp


# @main.route('/moderate')
# @login_required
# @permission_required(Permission.MODERATE_COMMENTS)
# def moderate():
#     page = request.args.get('page', 1, type=int)
#     pagination = Comment.query.order_by(Comment.timestamp.desc()).paginate(
#         page, per_page=current_app.config['RANDOMIST_COMMENTS_PER_PAGE'],
#         error_out=False)
#     comments = pagination.items
#     return render_template('moderate.html', comments=comments,
#                            pagination=pagination, page=page)


# @main.route('/moderate/enable/<int:id>')
# @login_required
# @permission_required(Permission.MODERATE_COMMENTS)
# def moderate_enable(id):
#     comment = Comment.query.get_or_404(id)
#     comment.disabled = False
#     db.session.add(comment)
#     return redirect(url_for('.moderate',
#                             page=request.args.get('page', 1, type=int)))


# @main.route('/moderate/disable/<int:id>')
# @login_required
# @permission_required(Permission.MODERATE_COMMENTS)
# def moderate_disable(id):
#     comment = Comment.query.get_or_404(id)
#     comment.disabled = True
#     db.session.add(comment)
#     return redirect(url_for('.moderate',
#                             page=request.args.get('page', 1, type=int)))

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
                            definition=remove_blank_lines(form.table_definition.data),
                            tags=form.table_tags.data,
                            author_id=current_user.id,
                            modifier_name=form.modifier_name.data,
                            supporting=form.supporting.data)

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

    return render_template('table.html', form=form, tables=tables, macro_list=macros, tags=tags,
                           public_tables=public_tables, public_macros=public_macros,
                           public_collections=public_collections)


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
        table.name = form.table_name.data
        table.description = form.table_description.data
        table.definition = remove_blank_lines(form.table_definition.data)
        table.tags = form.table_tags.data
        table.modifier_name = form.modifier_name.data
        table.supporting = form.supporting.data

        max_rng, min_rng, validate_table_definition, table_type, error_message, row_count = \
            check_table_definition_validity(table)
        if validate_table_definition:
            table.min = min_rng
            table.max = max_rng
            table.line_type = table_type
            table.row_count = row_count
            db.session.add(table)
            flash('Your table has been updated.')
            return redirect(url_for('.edit_table', username=username, id=id))
        else:
            flash(error_message)

    form.table_name.data = table.name
    form.table_description.data = table.description
    form.table_definition.data = table.definition
    if (table.tags, table.tags) in form.table_tags.choices:
        form.table_tags.data = table.tags
    form.table_id.data = table.id
    form.table_id.render_kw = {'readonly': True}
    form.modifier_name.data = table.modifier_name
    form.supporting.data = table.supporting

    collection_list, macros, tables, tags, public_collections, public_macros, public_tables = required_data()

    is_public = db.session.query(PublicRandomTable).filter(PublicRandomTable.author_id == current_user.id).filter(
        PublicRandomTable.id == id).first() is not None

    return render_template('table.html', tables=tables, macro_list=macros, form=form, tags=tags,
                           public_tables=public_tables, public_macros=public_macros,
                           public_collections=public_collections, username=username, table_id=id, is_public=is_public)


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
                if len(new_table) > 160:
                    flash(
                        "Table name '" + new_table_id + "' too long. Max Length 160 characters. Bulk import cancelled.")
                    db.session.rollback()
                    error_on_import = True
                    break
                new_table_id = slugify(line.lower())
                if len(new_table_id) > 128:
                    flash("Table id '" + new_table_id + "' too long. Max Length 128 characters. Bulk import cancelled.")
                    db.session.rollback()
                    error_on_import = True
                    break
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

                max_rng, min_rng, validate_table_definition, table_type, error_message, row_count = \
                    check_table_definition_validity(table)
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
                    flash(error_message + ', Table id : ' + new_table_id + ', Table name : ' + new_table)
                    db.session.rollback()
                    error_on_import = True
                    break
            new_table_definition += line + '\n'

        if new_table_definition and new_table_id:
            table = RandomTable(id=new_table_id,
                                name=new_table,
                                description='',
                                definition=new_table_definition,
                                tags=form.bulk_tag.data,
                                author_id=current_user.id)

            max_rng, min_rng, validate_table_definition, table_type, error_message, row_count = \
                check_table_definition_validity(table)
            if validate_table_definition:
                table.min = min_rng
                table.max = max_rng
                table.line_type = table_type
                table.row_count = row_count
                db.session.add(table)
                table_count += 1
            else:
                flash(error_message + ', Table id : ' + new_table_id + ', Table name : ' + new_table)
                db.session.rollback()
                error_on_import = True

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

    collection_list, macros, tables, tags, public_collections, public_macros, public_tables = required_data(
        remove_supporting=True)

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
        return redirect(url_for('.edit_story', username=username, id=id))

    collection_list, macros, tables, tags, public_collections, public_macros, public_tables = required_data(
        remove_supporting=True)

    form.title.data = story.title
    form.story.data = story.body
    form.pins.data = story.pins

    return render_template('story.html', form=form, tables=tables, macro_list=macros, collections=collection_list,
                           tags=tags, public_collections=public_collections,
                           public_macros=public_macros, public_tables=public_tables, username=username, story_id=id)


@main.route('/random-value/<string:username>/<string:id>', methods=['GET'])
def get_random_value(username, id):
    table = get_random_table_record(username, id)
    if table is not None:
        modifier = 0
        if request.args.get('modifier'):
            modifier_param = request.args.get('modifier')
            try:
                modifier = int(float(modifier_param))
            except Exception as e:
                pass
        return get_row_from_random_table_definition(table, modifier)

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
                       author_id=current_user.id,
                       supporting=form.supporting.data)

        validate_macro_definition, error_message = validate_text(macro.definition, macro.id)
        if validate_macro_definition:
            db.session.add(macro)
            flash('Macro Created')
            return redirect(url_for('.create_macro'))
        else:
            flash(error_message)

    collection_list, macros, tables, tags, public_collections, public_macros, public_tables = required_data()

    return render_template('macro.html', form=form, macro_list=macros, tables=tables, form_type='macro', tags=tags,
                           public_tables=public_tables, public_macros=public_macros,
                           public_collections=public_collections)


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
        macro.supporting = form.supporting.data

        validate_macro_definition, error_message = validate_text(macro.definition, macro.id)
        if validate_macro_definition:
            db.session.add(macro)
            flash('Your macro has been updated.')
            return redirect(url_for('.edit_macro', username=username, id=id))
        else:
            flash(error_message)

    form.macro_name.data = macro.name
    form.macro_body.data = macro.definition
    form.macro_id.data = macro.id
    form.macro_id.render_kw = {'readonly': True}
    form.supporting.data = macro.supporting
    if (macro.tags, macro.tags) in form.macro_tags.choices:
        form.macro_tags.data = macro.tags

    collection_list, macros, tables, tags, public_collections, public_macros, public_tables = required_data()

    is_public = db.session.query(PublicMacros).filter(PublicMacros.author_id == current_user.id).filter(
        PublicMacros.id == id).first() is not None

    return render_template('macro.html', form=form, macro_list=macros, tables=tables, edit_macro=macro,
                           form_type='macro', tags=tags,
                           public_tables=public_tables, public_macros=public_macros,
                           public_collections=public_collections, username=username, macro_id=id, is_public=is_public)


@main.route('/macro/<string:username>/<string:id>', methods=['GET'])
def get_macro(username, id):
    macro = get_macro_record(username, id)
    if macro is not None:
        macro_text = process_text_extended(macro.definition)
        return bleach.linkify(bleach.clean(markdown(macro_text, output_format='html'), tags=ALLOWED_TAGS, strip=True))
    else:
        return 'Error finding macro id: ' + username + '.macro.' + id


@main.route('/preview-macro', methods=['POST'])
@login_required
def preview_macro():
    macro = request.form['macro'].replace('\n', '<br/>')
    if macro:
        return bleach.linkify(
            bleach.clean(markdown(process_text_extended(macro), output_format='html'), tags=ALLOWED_TAGS, strip=True))
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
                                    definition=remove_blank_lines(form.collection_definition.data),
                                    tags=form.collection_tags.data,
                                    author_id=current_user.id,
                                    supporting=form.supporting.data)

        validate, error_message = validate_collection(collection_obj.definition)
        if validate:
            db.session.add(collection_obj)
            flash('Collection Created')
            return redirect(url_for('.create_collection'))
        else:
            flash(error_message)

    collection_list, macros, tables, tags, public_collections, public_macros, public_tables = required_data()

    return render_template('collection.html', form=form, macro_list=macros, tables=tables, collections=collection_list,
                           tags=tags,
                           public_tables=public_tables, public_macros=public_macros,
                           public_collections=public_collections)


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
        collection_obj.definition = remove_blank_lines(form.collection_definition.data)
        collection_obj.tags = form.collection_tags.data
        collection_obj.supporting = form.supporting.data

        validate, error_message = validate_collection(collection_obj.definition)
        if validate:
            db.session.add(collection_obj)
            flash('Your collection has been updated.')
            return redirect(url_for('.edit_collection', username=username, id=id))
        else:
            flash(error_message)

    form.collection_name.data = collection_obj.name
    form.collection_description.data = collection_obj.description
    form.collection_definition.data = collection_obj.definition
    if (collection_obj.tags, collection_obj.tags) in form.collection_tags.choices:
        form.collection_tags.data = collection_obj.tags
    form.collection_id.data = collection_obj.id
    form.collection_id.render_kw = {'readonly': True}
    form.supporting.data = collection_obj.supporting

    collection_list, macros, tables, tags, public_collections, public_macros, public_tables = required_data()

    return render_template('collection.html', form=form, macro_list=macros, tables=tables, collections=collection_list,
                           tags=tags,
                           public_tables=public_tables, public_macros=public_macros,
                           public_collections=public_collections, username=username, collection_id=id)


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
    users_selected_products = db.session.query(UserPublicContent.announcement_id).filter(
        UserPublicContent.author_id == current_user.id)
    free_products = PublicAnnouncements.query \
        .filter(PublicAnnouncements.author_id != current_user.id) \
        .filter(PublicAnnouncements.id.notin_(users_selected_products)) \
        .order_by(PublicAnnouncements.timestamp.desc()).limit(100);
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
        tags = set()
        public_collections = PublicCollection.query.filter(PublicCollection.announcement_id == public_id)
        public_macros = PublicMacros.query.filter(PublicMacros.announcement_id == public_id)
        public_tables = PublicRandomTable.query.filter(PublicRandomTable.announcement_id == public_id)
        collection_count = macro_count = table_count = 0
        for c in public_collections:
            if db.session.query(PublicLinkedCollections) \
                    .filter(PublicLinkedCollections.author_id == current_user.id) \
                    .filter(PublicLinkedCollections.collection_id == c.id) \
                    .filter(PublicLinkedCollections.original_author_id == c.author_id) \
                    .first() is None:
                new_collection = PublicLinkedCollections(author_id=current_user.id,
                                                         collection_id=c.id,
                                                         original_author_id=c.author_id,
                                                         announcement_id=c.announcement_id)
                db.session.add(new_collection)
                collection_count += 1
                if c.tags.strip():
                    tags.add(c.tags)

        for m in public_macros:
            if db.session.query(PublicLinkedMacros) \
                    .filter(PublicLinkedMacros.author_id == current_user.id) \
                    .filter(PublicLinkedMacros.macro_id == m.id) \
                    .filter(PublicLinkedMacros.original_author_id == m.author_id) \
                    .first() is None:
                new_macro = PublicLinkedMacros(author_id=current_user.id,
                                               macro_id=m.id,
                                               original_author_id=m.author_id,
                                               announcement_id=m.announcement_id)
                db.session.add(new_macro)
                macro_count += 1
                if m.tags.strip():
                    tags.add(m.tags)

        for t in public_tables:
            if db.session.query(PublicLinkedTables) \
                    .filter(PublicLinkedTables.author_id == current_user.id) \
                    .filter(PublicLinkedTables.table_id == t.id) \
                    .filter(PublicLinkedTables.original_author_id == t.author_id) \
                    .first() is None:
                new_table = PublicLinkedTables(author_id=current_user.id,
                                               table_id=t.id,
                                               original_author_id=t.author_id,
                                               announcement_id=t.announcement_id)
                db.session.add(new_table)
                table_count += 1
                if t.tags.strip():
                    tags.add(t.tags)

        for tag in tags:
            if db.session.query(Tags).filter(Tags.id == tag).filter(Tags.author_id == current_user.id).first() is None:
                new_tag = Tags(id=tag,
                               author_id=current_user.id)
                db.session.add(new_tag)

        db.session.commit()
        return make_response(jsonify({'success': True,
                                      'collection_count': str(collection_count),
                                      'macro_count': str(macro_count),
                                      'table_count': str(table_count)
                                      }))
    return make_response(jsonify({'success': False}))


@main.route('/public-content/<string:public_id>', methods=['GET'])
@login_required
def get_public_content(public_id):
    public_id = public_id[5:]
    public_collections = PublicCollection.query.with_entities(PublicCollection.id).filter_by(announcement_id=public_id)
    public_macros = PublicMacros.query.with_entities(PublicMacros.id).filter_by(announcement_id=public_id)
    public_tables = PublicRandomTable.query.with_entities(PublicRandomTable.id).filter_by(announcement_id=public_id)
    results = {"collections": [i[0] for i in public_collections], "macros": [i[0] for i in public_macros],
               "tables": [i[0] for i in public_tables]}
    return results


@main.route('/delete-public-announcement/<string:public_id>', methods=['DELETE'])
@login_required
def delete_public_announcement(public_id):
    if db.session.query(PublicAnnouncements) \
            .filter(PublicAnnouncements.id == public_id) \
            .filter(PublicAnnouncements.author_id == current_user.id) \
            .first() is None:
        abort(400)

    table_count = PublicRandomTable.query.filter(PublicRandomTable.announcement_id == public_id).count()
    macro_count = PublicMacros.query.filter(PublicMacros.announcement_id == public_id).count()
    collection_count = PublicCollection.query.filter(PublicCollection.announcement_id == public_id).count()

    tables = db.session.query(PublicRandomTable).filter(PublicRandomTable.announcement_id == public_id)
    tables.delete()
    macros = db.session.query(PublicMacros).filter(PublicMacros.announcement_id == public_id)
    macros.delete()
    collection = db.session.query(PublicCollection).filter(PublicCollection.announcement_id == public_id)
    collection.delete()
    announcement = db.session.query(PublicAnnouncements).filter(PublicAnnouncements.id == public_id)
    announcement.delete()

    return make_response(jsonify({'success': True,
                                  'collection_count': str(collection_count),
                                  'macro_count': str(macro_count),
                                  'table_count': str(table_count)
                                  }))


@main.route('/delete-table/<string:username>/<string:id>', methods=['DELETE'])
@login_required
def delete_table(username, id):
    if username != current_user.username:
        abort(403)

    deleted_table = db.session.query(RandomTable).filter(RandomTable.id == id). \
        filter(RandomTable.author_id == current_user.id)
    deleted_table.delete()

    return {'success': True}


@main.route('/delete-macro/<string:username>/<string:id>', methods=['DELETE'])
@login_required
def delete_macro(username, id):
    if username != current_user.username:
        abort(403)

    deleted_macro = db.session.query(Macros).filter(Macros.id == id). \
        filter(Macros.author_id == current_user.id)
    deleted_macro.delete()

    return {'success': True}


@main.route('/delete-collection/<string:username>/<string:id>', methods=['DELETE'])
@login_required
def delete_collection(username, id):
    if username != current_user.username:
        abort(403)

    deleted_collection = db.session.query(Collection).filter(Collection.id == id). \
        filter(Collection.author_id == current_user.id)
    deleted_collection.delete()

    return {'success': True}


@main.route('/delete-story/<string:username>/<string:id>', methods=['DELETE'])
@login_required
def delete_story(username, id):
    if username != current_user.username:
        abort(403)

    deleted_story = db.session.query(Post).filter(Post.id == id). \
        filter(Post.author_id == current_user.id)
    deleted_story.delete()

    return {'success': True}


@main.route('/delete-shared-content/<string:public_id>', methods=['DELETE'])
@login_required
def delete_shared_content(public_id):
    if db.session.query(UserPublicContent) \
            .filter(UserPublicContent.announcement_id == public_id) \
            .filter(UserPublicContent.author_id == current_user.id) \
            .first() is None:
        abort(400)

    tables = db.session.query(PublicLinkedTables).filter(PublicLinkedTables.announcement_id == public_id). \
        filter(PublicLinkedTables.author_id == current_user.id)
    tables.delete()
    macros = db.session.query(PublicLinkedMacros).filter(PublicLinkedMacros.announcement_id == public_id). \
        filter(PublicLinkedMacros.author_id == current_user.id)
    macros.delete()
    collection = db.session.query(PublicLinkedCollections).filter(PublicLinkedCollections.announcement_id == public_id). \
        filter(PublicLinkedCollections.author_id == current_user.id)
    collection.delete()
    announcement = db.session.query(UserPublicContent).filter(UserPublicContent.announcement_id == public_id). \
        filter(UserPublicContent.author_id == current_user.id)
    announcement.delete()

    return make_response(jsonify({'success': True}))


@main.route('/delete-tag/<string:id>', methods=['DELETE'])
@login_required
def delete_tag(id):
    if db.session.query(Tags) \
            .filter(Tags.id == id) \
            .filter(Tags.author_id == current_user.id) \
            .first() is None:
        abort(400)

    tag = db.session.query(Tags).filter(Tags.id == id). \
        filter(Tags.author_id == current_user.id)
    tag.delete()

    return make_response(jsonify({'success': True}))


@main.route('/refresh-shared-content/<string:id>', methods=['POST'])
@login_required
def refresh_shared_content(id):
    username, id_type, reference_id = split_id(id)
    if username != current_user.username:
        abort(403)

    if id_type == 'table':
        if db.session.query(RandomTable) \
                .filter(RandomTable.id == reference_id) \
                .filter(RandomTable.author_id == current_user.id) \
                .first() is None:
            abort(403)
        table = RandomTable.query.get_or_404([reference_id, current_user.id])
        public_table = PublicRandomTable.query.get_or_404([reference_id, current_user.id])
        public_table.name = table.name
        public_table.description = table.description
        public_table.definition = table.definition
        public_table.min = table.min
        public_table.max = table.max
        public_table.description_html = table.description_html
        public_table.line_type = table.line_type
        public_table.tags = table.tags
        public_table.row_count = table.row_count
        public_table.modifier_name = table.modifier_name
        public_table.last_modified = table.last_modified
        public_table.supporting = table.supporting
        db.session.add(public_table)
        db.session.commit()

    elif id_type == 'macro':
        if db.session.query(Macros) \
                .filter(Macros.id == reference_id) \
                .filter(Macros.author_id == current_user.id) \
                .first() is None:
            abort(403)
        macro = Macros.query.get_or_404([reference_id, current_user.id])
        public_macro = PublicMacros.query.get_or_404([reference_id, current_user.id])
        public_macro.name = macro.name
        public_macro.definition = macro.definition
        public_macro.definition_html = macro.definition
        public_macro.tags = macro.tags
        public_macro.last_modified = macro.last_modified
        public_macro.supporting = macro.supporting
        db.session.add(public_macro)
        db.session.commit()

    elif id_type == 'collection':
        if db.session.query(Collection) \
                .filter(Collection.id == reference_id) \
                .filter(Collection.author_id == current_user.id) \
                .first() is None:
            abort(403)
        collection_obj = Collection.query.get_or_404([reference_id, current_user.id])
        public_collection_obj = PublicCollection.query.get_or_404([reference_id, current_user.id])
        public_collection_obj.name = collection_obj.name
        public_collection_obj.description = collection_obj.description
        public_collection_obj.definition = collection_obj.definition
        public_collection_obj.tags = collection_obj.tags
        public_collection_obj.last_modified = collection_obj.last_modified
        public_collection_obj.supporting = collection_obj.supporting
        db.session.add(public_collection_obj)
        db.session.commit()

    else:
        abort(400)

    return make_response(jsonify({'success': True}))


@main.route('/id-check/<string:type>/<string:id>', methods=['GET'])
@login_required
def id_exists(type, id):
    check = "0"
    if type == 'table':
        check = db.session.query(RandomTable) \
            .filter(RandomTable.id == id) \
            .filter(RandomTable.author_id == current_user.id) \
            .first() is not None
    elif type == 'macro':
        check = db.session.query(Macros) \
            .filter(Macros.id == id) \
            .filter(Macros.author_id == current_user.id) \
            .first() is not None
    elif type == 'collection':
        check = db.session.query(Collection) \
            .filter(Collection.id == id) \
            .filter(Collection.author_id == current_user.id) \
            .first() is not None
    elif type == 'tag':
        check = db.session.query(Tags) \
            .filter(Tags.id == id) \
            .filter(Tags.author_id == current_user.id) \
            .first() is not None

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
                    c = Collection.query.get([c_id, current_user.id])
                    if not c:
                        db.session.rollback()
                        return render_template('error_page.html', description='Error finding Collection ' + c_id)
                    else:
                        if db.session.query(PublicCollection). \
                                filter(PublicCollection.author_id == current_user.id). \
                                filter(PublicCollection.id == c.id).first() is None:
                            pc = PublicCollection(id=c.id,
                                                  name=c.name,
                                                  definition=c.definition,
                                                  tags=c.tags,
                                                  author_id=current_user.id,
                                                  permissions=ProductPermission.PUBLIC,
                                                  announcement_id=announcement.id,
                                                  last_modified=c.last_modified,
                                                  supporting=c.supporting)
                            db.session.add(pc)
            if public_macros != ['']:
                for m_id in public_macros:
                    m = Macros.query.get([m_id, current_user.id])
                    if not m:
                        db.session.rollback()
                        return render_template('error_page.html', description='Error finding Macro ' + m_id)
                    else:
                        if db.session.query(PublicMacros). \
                                filter(PublicMacros.author_id == current_user.id). \
                                filter(PublicMacros.id == m.id).first() is None:
                            pm = PublicMacros(id=m.id,
                                              name=m.name,
                                              definition=m.definition,
                                              tags=m.tags,
                                              author_id=current_user.id,
                                              permissions=ProductPermission.PUBLIC,
                                              announcement_id=announcement.id,
                                              last_modified=m.last_modified,
                                              supporting=m.supporting)
                            db.session.add(pm)
            if public_tables != ['']:
                for t_id in public_tables:
                    t = RandomTable.query.get([t_id, current_user.id])
                    if not t:
                        db.session.rollback()
                        return render_template('error_page.html', description='Error finding Random Table ' + t_id)
                    else:
                        if db.session.query(PublicRandomTable). \
                                filter(PublicRandomTable.author_id == current_user.id). \
                                filter(PublicRandomTable.id == t.id).first() is None:
                            prt = PublicRandomTable(id=t.id,
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
                                                    announcement_id=announcement.id,
                                                    modifier_name=t.modifier_name,
                                                    last_modified=t.last_modified,
                                                    supporting=t.supporting)
                            db.session.add(prt)
            db.session.commit()
            flash('Content Shared')
            return redirect(url_for('.share_public'))

    collection_list = Collection.query. \
        filter(Collection.author_id == current_user.id). \
        filter(Collection.id.notin_(('tutorial-15-macros', 'tutorial-16-tables-and-macros'))). \
        order_by(Collection.timestamp.desc())
    macros = Macros.query. \
        filter(Macros.author_id == current_user.id). \
        filter(Macros.id.notin_(('tutorial-6-first-macro', 'tutorial-7-linking-macros-and-tables', 'tutorial-8-chance',
                                 'tutorial-9-loops', 'tutorial-10-if', 'tutorial-11-choice'))). \
        order_by(Macros.timestamp.desc())
    tables = RandomTable.query. \
        filter(RandomTable.author_id == current_user.id). \
        filter(RandomTable.id.notin_(('tutorial-1-colours', 'tutorial-2-gems', 'tutorial-3-generating-numbers',
                                      'tutorial-4-linking-tables', 'tutorial-5-linking-tables-advanced'))). \
        order_by(RandomTable.timestamp.desc())

    tags = tag_query()
    shared_public_tables = db.session.query(PublicRandomTable.id).filter(
        PublicRandomTable.author_id == current_user.id)
    shared_tables = [i.id for i in shared_public_tables]

    shared_public_macros = db.session.query(PublicMacros.id).filter(
        PublicMacros.author_id == current_user.id)
    shared_macros = [i.id for i in shared_public_macros]

    shared_public_collections = db.session.query(PublicCollection.id).filter(
        PublicCollection.author_id == current_user.id)
    shared_collections = [i.id for i in shared_public_collections]

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
                           table_references=table_references, macro_references=macro_references,
                           shared_collections=shared_collections,
                           shared_macros=shared_macros,
                           shared_tables=shared_tables)


def build_collection_references(coll_obj):
    coll_dict = collections.OrderedDict()
    coll_definition = coll_obj.definition.splitlines()

    for coll_item in coll_definition:
        coll_item = coll_item[2:len(coll_item) - 2]
        username, id_type, reference_id = split_id(coll_item)
        if id_type == 'table':
            table = get_random_table_record(username, reference_id)
            if table is not None:
                try:
                    coll_dict[coll_item] = find_references(coll_item, table.definition, [coll_item + '::0'], 0)
                except Exception as inst:
                    raise inst
            else:
                raise Exception('Table not found', coll_item + ' not found. Referenced in ' + coll_obj.name)
        elif id_type == 'macro':
            macro = get_macro_record(username, reference_id)
            if macro is not None:
                try:
                    coll_dict[coll_item] = find_references(coll_item, macro.definition, [coll_item + '::0'], 0)
                except Exception as inst:
                    raise inst
            else:
                raise Exception('Macro not found', coll_item + ' not found. Referenced in ' + coll_obj.name)
        elif id_type == 'collection':
            sub_coll = get_collection_record(username, reference_id)
            if sub_coll is not None:
                coll_dict[coll_item] = build_collection_references(sub_coll)
            else:
                raise Exception('Collection Not Found', coll_item + ' not found . Referenced in ' + coll_obj.name)
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
                raise Exception('Table not found', external_id + ' not found referenced from ' + obj_id)
        elif id_type == 'macro':
            macro = get_macro_record(username, reference_id)
            if macro is not None:
                references.append(external_id + '::' + str(depth))
                find_references(external_id, macro.definition, references, depth)
            else:
                raise Exception('Macro not found', external_id + ' not found  referenced from ' + obj_id)
        open_angle_brackets = definition.find("<<", close_angle_brackets)
    return references


def tag_list():
    return [(p.id, p.id) for p in Tags.query.filter(Tags.author_id == current_user.id).order_by(Tags.id)]


def macro_query(macro_id=None, remove_supporting=False):
    if macro_id:
        return Macros.query.filter(Macros.author_id == current_user.id, Macros.id != macro_id).order_by(
            Macros.timestamp.desc())
    macro_list = None
    if remove_supporting:
        macro_list = Macros.query.filter(Macros.author_id == current_user.id).filter(
            Macros.supporting == False).order_by(Macros.timestamp.desc())
    else:
        macro_list = Macros.query.filter(Macros.author_id == current_user.id).order_by(Macros.timestamp.desc())

    return macro_list


def table_query(remove_supporting=False):
    table_list = None
    if remove_supporting:
        table_list = RandomTable.query.filter(RandomTable.author_id == current_user.id).filter(
            RandomTable.supporting == False).order_by(RandomTable.timestamp.desc())
    else:
        table_list = RandomTable.query.filter(RandomTable.author_id == current_user.id).order_by(
            RandomTable.timestamp.desc())

    return table_list


def collection_query(remove_supporting=False):
    collection_list = None
    if remove_supporting:
        collection_list = Collection.query.filter(Collection.author_id == current_user.id).filter(
            Collection.supporting == False).order_by(Collection.timestamp.desc())
    else:
        collection_list = Collection.query.filter(Collection.author_id == current_user.id).order_by(
            Collection.timestamp.desc())

    return collection_list


def tag_query():
    return Tags.query.filter(Tags.author_id == current_user.id).order_by(Tags.id.asc())


def required_data(remove_supporting=False):
    if current_user.is_anonymous:
        return None, None, None, None, None, None, None

    tables = table_query(remove_supporting=remove_supporting)
    macros = macro_query(remove_supporting=remove_supporting)
    collection_list = collection_query(remove_supporting=remove_supporting)
    tags = tag_query()
    # public_tables = None
    # public_macros = None
    # public_collections = None
    # if remove_supporting:
    public_tables = PublicLinkedTables.query.filter(PublicLinkedTables.author_id == current_user.id).filter(
        PublicLinkedTables.public_table.has(PublicRandomTable.supporting == False))
    public_macros = PublicLinkedMacros.query.filter(PublicLinkedMacros.author_id == current_user.id).filter(
        PublicLinkedMacros.public_macro.has(PublicMacros.supporting == False))
    public_collections = PublicLinkedCollections.query.filter(
        PublicLinkedCollections.author_id == current_user.id).filter(
        PublicLinkedCollections.public_collection.has(PublicCollection.supporting == False))
    # else:
    #    public_tables = PublicLinkedTables.query.filter(PublicLinkedTables.author_id == current_user.id)
    #    public_macros = PublicLinkedMacros.query.filter(PublicLinkedMacros.author_id == current_user.id)
    #   public_collections = PublicLinkedCollections.query.filter(PublicLinkedCollections.author_id == current_user.id)

    return collection_list, macros, tables, tags, public_collections, public_macros, public_tables
