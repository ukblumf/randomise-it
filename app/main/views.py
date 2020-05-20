from flask import render_template, redirect, url_for, abort, flash, request, \
    current_app, make_response
from flask_login import login_required, current_user
from flask_sqlalchemy import get_debug_queries
from . import main
from .forms import EditProfileForm, EditProfileAdminForm, PostForm, CommentForm, TableForm, StoryForm, MacroForm, \
    SetForm, ProductForm, MarketForm
from .. import db
from ..models import Permission, Role, User, Post, Comment, RandomTable, Macros, ProductPermission, Set, Products, \
    MarketPlace, ProductCategory
from ..decorators import admin_required, permission_required
from ..validate import check_table_definition_validity, validate_text, validate_set
from ..get_random_value import get_row_from_random_table_definition, process_text
import base64
from markdown import markdown
import bleach
import collections
import re


ALLOWED_TAGS = ['a', 'abbr', 'acronym', 'b', 'blockquote', 'code',
                'em', 'i', 'li', 'ol', 'pre', 'strong', 'ul',
                'h1', 'h2', 'h3']


@main.after_app_request
def after_request(response):
    for query in get_debug_queries():
        if query.duration >= current_app.config['RANDOMISE_IT_SLOW_DB_QUERY_TIME']:
            current_app.logger.warning(
                'Slow query: %s\nParameters: %s\nDuration: %fs\nContext: %s\n'
                % (query.statement, query.parameters, query.duration,
                   query.context))
    return response


@main.route('/shutdown')
def server_shutdown():
    if not current_app.testing:
        abort(404)
    shutdown = request.environ.get('werkzeug.server.shutdown')
    if not shutdown:
        abort(500)
    shutdown()
    return 'Shutting down...'


@main.route('/', methods=['GET', 'POST'])
def index():
    tables = None
    macros = None
    if current_user.is_authenticated:
        tables = RandomTable.query.filter_by(author_id=current_user.id) \
            .order_by(RandomTable.timestamp.desc()).paginate(1, per_page=1000, error_out=False)
        macros = Macros.query.filter_by(author_id=current_user.id) \
            .order_by(Macros.timestamp.desc()).paginate(1, per_page=1000, error_out=False)
    else:
        tables = RandomTable.query.filter_by(permissions=ProductPermission.PUBLIC) \
            .order_by(RandomTable.timestamp.desc()).paginate(1, per_page=1000, error_out=False)
        macros = Macros.query.filter_by(permissions=ProductPermission.PUBLIC) \
            .order_by(Macros.timestamp.desc()).paginate(1, per_page=1000, error_out=False)

    return render_template('index.html', tables=tables.items, macro_list=macros.items)


@main.route('/user/<username>')
def user(username):
    user = User.query.filter_by(username=username).first_or_404()
    page = request.args.get('page', 1, type=int)
    pagination = user.posts.order_by(Post.timestamp.desc()).paginate(
        page, per_page=current_app.config['RANDOMISE_IT_POSTS_PER_PAGE'],
        error_out=False)
    stories = pagination.items

    tables = RandomTable.query.filter(RandomTable.author_id == current_user.id).order_by(RandomTable.timestamp.desc())
    macros = Macros.query.filter(Macros.author_id == current_user.id).order_by(Macros.timestamp.desc())
    sets = Set.query.filter(Set.author_id == current_user.id).order_by(Set.timestamp.desc())

    return render_template('user.html', user=user, stories=stories,
                           pagination=pagination, tables=tables, macro_list=macros, sets=sets)


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
    return render_template('edit_profile.html', form=form)


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
    return render_template('edit_profile.html', form=form, user=user)


@main.route('/post/<int:id>', methods=['GET', 'POST'])
def post(id):
    post = Post.query.get_or_404(id)
    form = CommentForm()
    if form.validate_on_submit():
        comment = Comment(body=form.body.data,
                          post=post,
                          author=current_user._get_current_object())
        db.session.add(comment)
        flash('Your comment has been published.')
        return redirect(url_for('.post', id=post.id, page=-1))
    page = request.args.get('page', 1, type=int)
    if page == -1:
        page = (post.comments.count() - 1) // \
               current_app.config['RANDOMISE_IT_COMMENTS_PER_PAGE'] + 1
    pagination = post.comments.order_by(Comment.timestamp.asc()).paginate(
        page, per_page=current_app.config['RANDOMISE_IT_COMMENTS_PER_PAGE'],
        error_out=False)
    comments = pagination.items
    return render_template('post.html', posts=[post], form=form,
                           comments=comments, pagination=pagination)


@main.route('/edit-post/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_post(id):
    post = Post.query.get_or_404(id)
    if current_user != post.author and \
            not current_user.can(Permission.ADMINISTER):
        abort(403)
    form = PostForm()
    if form.validate_on_submit():
        post.body = form.body.data
        db.session.add(post)
        flash('The post has been updated.')
        return redirect(url_for('.post', id=post.id))
    form.body.data = post.body
    return render_template('edit_post.html', form=form)


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
    form.products.choices = [(p.id, p.name) for p in Products
        .query
        .filter(Products.author_id == current_user.id, Products.permissions == 0)
        .order_by(Products.name)]
    form.products.choices.insert(0, (' ', ''))

    if current_user.can(Permission.WRITE_ARTICLES) and \
            form.validate_on_submit():
        table = RandomTable(id=form.table_id.data,
                            name=form.table_name.data,
                            description=form.table_description.data,
                            definition=form.table_definition.data,
                            product_id=form.products.data,
                            author_id=current_user.id)

        max_rng, min_rng, validate_table_definition, table_type, error_message = check_table_definition_validity(table)
        if validate_table_definition:
            table.min = min_rng
            table.max = max_rng
            table.line_type = table_type
            db.session.add(table)
            flash('Table Created')
            return redirect(url_for('.create_table'))
        else:
            flash(error_message)

    tables = RandomTable.query.filter(RandomTable.author_id == current_user.id).order_by(RandomTable.timestamp.desc())
    macros = Macros.query.filter(Macros.author_id == current_user.id).order_by(Macros.timestamp.desc())

    return render_template('create_table.html', form=form, tables=tables, macro_list=macros, form_type='table')


@main.route('/edit-table/<string:id>', methods=['GET', 'POST'])
@login_required
def edit_table(id):
    # current_app.logger.warning(current_user._get_current_object().id)
    table = RandomTable.query.get_or_404([id, current_user.id])
    if current_user != table.author and \
            not current_user.can(Permission.ADMINISTER):
        abort(403)
    form = TableForm()
    form.products.choices = [(p.id, p.name) for p in Products
        .query
        .filter(Products.author_id == current_user.id, Products.permissions == 0)
        .order_by(Products.name)]
    form.products.choices.insert(0, (' ', ''))

    if form.validate_on_submit():
        # table.id = form.table_id.data
        table.name = form.table_name.data
        table.description = form.table_description.data
        table.definition = form.table_definition.data
        table.product_id = form.products.data

        max_rng, min_rng, validate_table_definition, table_type, error_message = check_table_definition_validity(table)
        if validate_table_definition:
            table.min = min_rng
            table.max = max_rng
            table.line_type = table_type
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
    form.products.data = table.product_id

    tables = RandomTable.query.filter(RandomTable.author_id == current_user.id).order_by(RandomTable.timestamp.desc())
    macros = Macros.query.filter(Macros.author_id == current_user.id).order_by(Macros.timestamp.desc())

    del form.table_id  # remove id from edit screen form

    return render_template('edit_table.html', tables=tables, macro_list=macros, form=form, form_type='table')


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

    tables = RandomTable.query.filter(RandomTable.author_id == current_user.id).order_by(RandomTable.timestamp.desc())
    macros = Macros.query.filter(Macros.author_id == current_user.id).order_by(Macros.timestamp.desc())
    parent_sets = Set.query.filter(Set.author_id == current_user.id, Set.parent == True).order_by(Set.timestamp.desc())
    sets = Set.query.filter(Set.author_id == current_user.id).order_by(Set.timestamp.desc())
    menus = collections.OrderedDict()
    for parent_set in parent_sets:
        menus[parent_set.name] = build_menu(parent_set, 0)

    # auth_encoded = base64.b64encode(current_user.generate_auth_token(expiration=86400) + ':')

    return render_template('create_story.html', form=form, tables=tables, macro_list=macros, menus=menus, sets=sets)


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

    tables = RandomTable.query.filter(RandomTable.author_id == current_user.id).order_by(RandomTable.timestamp.desc())
    macros = Macros.query.filter(Macros.author_id == current_user.id).order_by(Macros.timestamp.desc())
    parents_sets = Set.query.filter(Set.author_id == current_user.id, Set.parent == True).order_by(Set.timestamp.desc())
    sets = Set.query.filter(Set.author_id == current_user.id).order_by(Set.timestamp.desc())
    menus = collections.OrderedDict()

    for parent_set in parents_sets:
        menus[parent_set.name] = build_menu(parent_set, 0)

    # required in order to talk to API
    # auth_encoded = base64.b64encode(current_user.generate_auth_token(expiration=86400) + ':')

    form.title.data = story.title
    form.story.data = story.body
    form.pins.data = story.pins

    return render_template('create_story.html', form=form, tables=tables, macro_list=macros, menus=menus, sets=sets)


def build_menu(set_obj, recur):
    if recur > 5:
        flash('Recursion limit in build_menu exceeded, possibly a set referencing an earlier set.')
        return collections.OrderedDict()

    # current_app.logger.warning('process set:' + set_obj.name)
    set_dict = collections.OrderedDict()
    set_definition = set_obj.definition.splitlines()

    for set_item in set_definition:
        if set_item.startswith('table.'):
            table = RandomTable.query.get([set_item[6:], current_user.id])
            if table is not None:
                set_dict[table.name] = set_item
        elif set_item.startswith('macro.'):
            macro = Macros.query.get([set_item[6:], current_user.id])
            if macro is not None:
                set_dict[macro.name] = set_item
        elif set_item.startswith('set.'):
            sub_set = Set.query.get([set_item[4:], current_user.id])
            if sub_set is not None:
                set_dict[sub_set.name] = build_menu(sub_set, recur + 1)
    return set_dict


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
    form.macro_products.choices = [(p.id, p.name) for p in Products
        .query
        .filter(Products.author_id == current_user.id, Products.permissions == 0)
        .order_by(Products.name)]
    form.macro_products.choices.insert(0, (' ', ''))

    if current_user.can(Permission.WRITE_ARTICLES) and form.validate_on_submit():
        macro = Macros(id=form.macro_id.data,
                       name=form.macro_name.data,
                       definition=form.macro_body.data,
                       product_id=form.macro_products.data,
                       author_id=current_user.id)

        validate_macro_definition, error_message = validate_text(macro.definition, macro.id)
        if validate_macro_definition:
            db.session.add(macro)
            flash('Macro Created')
            return redirect(url_for('.create_macro'))
        else:
            flash(error_message)

    tables = RandomTable.query.filter(RandomTable.author_id == current_user.id).order_by(RandomTable.timestamp.desc())
    macros = Macros.query.filter(Macros.author_id == current_user.id).order_by(Macros.timestamp.desc())

    return render_template('create_macro.html', form=form, macro_list=macros, tables=tables, form_type='macro')


@main.route('/edit-macro/<string:id>', methods=['GET', 'POST'])
@login_required
def edit_macro(id):
    # current_app.logger.warning(current_user._get_current_object().id)
    macro = Macros.query.get_or_404([id, current_user.id])
    if current_user.id != macro.author_id and not current_user.can(Permission.ADMINISTER):
        abort(403)
    form = MacroForm()
    form.macro_products.choices = [(p.id, p.name) for p in Products
        .query
        .filter(Products.author_id == current_user.id, Products.permissions == 0)
        .order_by(Products.name)]
    form.macro_products.choices.insert(0, ('', '---'))
    if form.validate_on_submit():
        macro.name = form.macro_name.data
        macro.definition = form.macro_body.data
        if form.macro_products.data != '':
            macro.product_id = form.macro_products.data

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
    if macro.product_id:
        form.macro_products.data = macro.product_id

    tables = RandomTable.query.filter(RandomTable.author_id == current_user.id).order_by(RandomTable.timestamp.desc())
    macros = Macros.query.filter(Macros.author_id == current_user.id, Macros.id != id).order_by(Macros.timestamp.desc())

    del form.macro_id  # remove id from edit screen
    return render_template('edit_macro.html', form=form, macro_list=macros, tables=tables, edit_macro=macro, form_type='macro')


@main.route('/macro/<string:id>', methods=['GET'])
def get_macro(id):
    macro = Macros.query.get_or_404([id, current_user.id])

    text = bleach.linkify(bleach.clean(
        markdown(process_text(macro.definition), output_format='html'),
        tags=ALLOWED_TAGS, strip=True))

    return text


@main.route('/create-set', methods=['GET', 'POST'])
@login_required
def create_set():
    form = SetForm()
    form.set_products.choices = [(p.id, p.name) for p in Products
        .query
        .filter(Products.author_id == current_user.id, Products.permissions == 0)
        .order_by(Products.name)]

    form.set_products.choices.insert(0, (' ', ''))

    if current_user.can(Permission.WRITE_ARTICLES) and form.validate_on_submit():
        set_obj = Set(id=form.set_id.data,
                      name=form.set_name.data,
                      definition=form.set_definition.data,
                      product_id=form.set_products.data,
                      parent=form.set_is_parent.data,
                      author_id=current_user.id)

        validate, error_message = validate_set(set_obj.definition)
        if validate:
            db.session.add(set_obj)
            flash('Set Created')
            return redirect(url_for('.create_set'))
        else:
            flash(error_message)

    tables = RandomTable.query.filter(RandomTable.author_id == current_user.id).order_by(RandomTable.timestamp.desc())
    macros = Macros.query.filter(Macros.author_id == current_user.id).order_by(Macros.timestamp.desc())
    sets = Set.query.filter(Set.author_id == current_user.id).order_by(Set.timestamp.desc())

    return render_template('create_set.html', form=form, macro_list=macros, tables=tables, sets=sets, form_type='set')


@main.route('/edit-set/<string:id>', methods=['GET', 'POST'])
@login_required
def edit_set(id):
    # current_app.logger.warning(current_user._get_current_object().id)
    set_obj = Set.query.get_or_404([id, current_user.id])
    if current_user.id != set_obj.author_id and not current_user.can(Permission.ADMINISTER):
        abort(403)
    form = SetForm()
    form.set_products.choices = [(p.id, p.name) for p in Products
        .query
        .filter(Products.author_id == current_user.id, Products.permissions == 0)
        .order_by(Products.name)]

    form.set_products.choices.insert(0, (' ', ''))

    if form.validate_on_submit():
        set_obj.name = form.set_name.data
        set_obj.description = form.set_description.data
        set_obj.definition = form.set_definition.data
        set_obj.parent = form.set_is_parent.data
        set_obj.product_id = form.set_products.data

        validate, error_message = validate_set(set_obj.definition)
        if validate:
            db.session.add(set_obj)
            flash('Your set has been updated.')
        else:
            flash(error_message)

    form.set_name.data = set_obj.name
    form.set_description.data = set_obj.description
    form.set_definition.data = set_obj.definition
    form.set_is_parent.data = set_obj.parent
    # form.permissions.data = 0
    form.set_products.data = set_obj.product_id

    tables = RandomTable.query.filter(RandomTable.author_id == current_user.id).order_by(RandomTable.timestamp.desc())
    macros = Macros.query.filter(Macros.author_id == current_user.id).order_by(Macros.timestamp.desc())
    sets = Set.query.filter(Set.author_id == current_user.id).order_by(Set.timestamp.desc())

    del form.set_id  # remove id from edit screen

    return render_template('edit_set.html', form=form, macro_list=macros, tables=tables, sets=sets, form_type='set')


@main.route('/set/<string:id>', methods=['GET'])
def get_set(id):
    set_data = Set.query.get_or_404([id, current_user.id])
    return set_data.definition

@main.route('/create-product', methods=['GET', 'POST'])
@login_required
def create_product():
    form = ProductForm()
    if current_user.can(Permission.WRITE_ARTICLES) and form.validate_on_submit():
        product = Products(id=form.id.data,
                           name=form.name.data,
                           description=form.description.data,
                           permissions=0,
                           author_id=current_user.id)

        db.session.add(product)
        flash('Product Created')
        return redirect(url_for('.create_product'))

    return render_template('create_product.html', form=form, form_type='product')


@main.route('/edit-product/<string:id>', methods=['GET', 'POST'])
@login_required
def edit_product(id):
    # current_app.logger.warning(current_user._get_current_object().id)
    product = Products.query.get_or_404([id, current_user.id])
    if current_user.id != product.author_id and not current_user.can(Permission.ADMINISTER):
        abort(403)
    form = ProductForm()
    if form.validate_on_submit():
        product.name = form.name.data
        product.description = form.description.data

        db.session.add(product)
        flash('Your product has been updated.')

    # form.id.data = set_obj.id
    form.name.data = product.name
    form.description.data = product.description

    tables = RandomTable.query.filter(RandomTable.author_id == current_user.id, RandomTable.product_id == id).order_by(
        RandomTable.timestamp.desc())
    macros = Macros.query.filter(Macros.author_id == current_user.id, Macros.product_id == id).order_by(
        Macros.timestamp.desc())
    sets = Set.query.filter(Set.author_id == current_user.id, Set.product_id == id).order_by(Set.timestamp.desc())

    del form.id  # remove id from edit screen

    return render_template('edit_product.html', form=form, macro_list=macros, tables=tables, sets=sets, form_type='product')


@main.route('/create-market-product', methods=['GET', 'POST'])
@login_required
def create_market_product():
    form = MarketForm()
    form.product.choices = [(p.id, p.name) for p in Products
        .query
        .filter(Products.author_id == current_user.id, Products.permissions == 0)
        .order_by(Products.name)]
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
                                     product_id=form.product.data,
                                     author_id=current_user.id)

        db.session.add(market_product)
        db.session.commit()
        # add categories
        if bool(form.category1.data):
            product_category1 = ProductCategory(author_id=current_user.id,
                                                product_id=market_product.id,
                                                category_id=form.category1.data)
            db.session.add(product_category1)
        if bool(form.category2.data):
            product_category2 = ProductCategory(author_id=current_user.id,
                                                product_id=market_product.id,
                                                category_id=form.category2.data)
            db.session.add(product_category2)
        db.session.commit()
        flash('Market Product Created')
        return redirect(url_for('.create_market_product'))

    return render_template('create_market_product.html', form=form)


@main.route('/edit-market-product/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_market_product(id):
    # current_app.logger.warning(current_user._get_current_object().id)
    market_product = MarketPlace.query.get_or_404(id)
    if current_user.id != market_product.author_id and not current_user.can(Permission.ADMINISTER):
        abort(403)
    form = MarketForm()
    form.product.choices = [(p.id, p.name) for p in Products
        .query
        .filter(Products.author_id == current_user.id, Products.permissions == 0)
        .order_by(Products.name)]
    form.category1.choices = current_app.config['CATEGORIES'][:]
    form.category1.choices.insert(0, ["0", ""])
    form.category2.choices = current_app.config['CATEGORIES'][:]
    form.category2.choices.insert(0, ["0", ""])

    if form.validate_on_submit():
        market_product.name = form.name.data
        market_product.description = form.description.data

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

    # form.id.data = set_obj.id
    form.name.data = market_product.name
    form.description.data = market_product.description

    tables = RandomTable.query.filter(RandomTable.author_id == current_user.id, RandomTable.product_id == id).order_by(
        RandomTable.timestamp.desc())
    macros = Macros.query.filter(Macros.author_id == current_user.id, Macros.product_id == id).order_by(
        Macros.timestamp.desc())
    sets = Set.query.filter(Set.author_id == current_user.id, Set.product_id == id).order_by(Set.timestamp.desc())

    return render_template('edit_market_product.html', form=form, macro_list=macros, tables=tables, sets=sets)


@main.route('/edit', methods=['GET'])
@login_required
def edit_screen():
    tables = RandomTable.query.filter(RandomTable.author_id == current_user.id).order_by(RandomTable.timestamp.desc())
    macros = Macros.query.filter(Macros.author_id == current_user.id).order_by(Macros.timestamp.desc())
    sets = Set.query.filter(Set.author_id == current_user.id).order_by(Set.timestamp.desc())
    products = Products.query.filter(Products.author_id == current_user.id).order_by(Products.timestamp.desc())
    market_products = MarketPlace.query.filter(MarketPlace.author_id == current_user.id).order_by(
        MarketPlace.timestamp.desc())
    stories = Post.query.filter(Post.author_id == current_user.id).order_by(Post.timestamp.desc())

    return render_template('edit_screen.html', macro_list=macros, tables=tables, sets=sets,
                           products=products, market_products=market_products, stories=stories)


@main.route('/marketplace', methods=['GET'])
def view_marketplace():
    latest_marketproducts = MarketPlace.query.order_by(MarketPlace.timestamp.desc()).limit(50)
    popular_marketproducts = MarketPlace.query.order_by(MarketPlace.count.desc()).limit(50)

    all_categories = current_app.config['CATEGORIES'][:]

    product_categories = [pc[0] for pc in db.session.query(ProductCategory.category_id).distinct()]

    used_categories = [cat for cat in all_categories if cat[0] in product_categories]

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
    elif type == 'set':
        check = db.session.query(Set.id).filter_by(id=id).scalar() is not None
    elif type == 'product':
        check = db.session.query(Products.id).filter_by(id=id).scalar() is not None
    elif type == 'marketproduct':
        check = db.session.query(MarketPlace.id).filter_by(id=id).scalar() is not None

    return str(int(check == True))
