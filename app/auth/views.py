from flask import render_template, redirect, request, url_for, flash, current_app
from flask_login import login_user, logout_user, login_required, \
    current_user
from . import auth
from .. import db
from ..models import User
from ..email import send_email
from .forms import LoginForm, RegistrationForm, ChangePasswordForm, \
    PasswordResetRequestForm, PasswordResetForm, ChangeEmailForm
import glob, os
import json
from ..models import RandomTable, Macros, Collection, Post, Tags
from ..validate import check_table_definition_validity, validate_text, validate_collection


@auth.before_app_request
def before_request():
    if current_user.is_authenticated:
        current_user.ping()
        if not current_user.confirmed \
                and request.endpoint \
                and request.endpoint[:5] != 'auth.' \
                and request.endpoint != 'static':
            return redirect(url_for('auth.unconfirmed'))


@auth.route('/unconfirmed')
def unconfirmed():
    if current_user.is_anonymous or current_user.confirmed:
        return redirect(url_for('main.index'))
    return render_template('auth/unconfirmed.html')


@auth.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user is not None and user.verify_password(form.password.data):
            login_user(user, form.remember_me.data)
            return redirect(request.args.get('next') or url_for('main.index'))
        flash('Invalid username or password.')
    return render_template('auth/login.html', form=form)


@auth.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.')
    return redirect(url_for('main.index'))


@auth.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(email=form.email.data,
                    username=form.username.data,
                    password=form.password.data)
        db.session.add(user)
        db.session.commit()
        token = user.generate_confirmation_token()
        send_email(user.email, 'Confirm Your Account',
                   'auth/email/confirm', user=user, token=token)
        flash('A confirmation email has been sent to you by email.')
        return redirect(url_for('auth.login'))
    return render_template('auth/register.html', form=form)


@auth.route('/confirm/<token>')
@login_required
def confirm(token):
    if current_user.confirmed:
        return redirect(url_for('main.index'))
    if current_user.confirm(token):
        flash('You have confirmed your account. Thanks!')
    else:
        flash('The confirmation link is invalid or has expired.')
    return redirect(url_for('main.index'))


@auth.route('/create-tutorial')
@login_required
def create_tutorial():
    # remove any existing tutorial data
    for t in ('tutorial-1-colours', 'tutorial-2-gems', 'tutorial-3-generating-numbers', 'tutorial-4-linking-tables',
              'tutorial-5-linking-tables-advanced'):
        deleted_table = db.session.query(RandomTable).filter(RandomTable.id == t). \
            filter(RandomTable.author_id == current_user.id)
        if deleted_table:
            deleted_table.delete()
    for m in ('tutorial-6-first-macro', 'tutorial-7-linking-macros-and-tables', 'tutorial-8-chance', 'tutorial-9-loops',
              'tutorial-10-if', 'tutorial-11-choice'):
        deleted_macro = db.session.query(Macros).filter(Macros.id == m). \
            filter(Macros.author_id == current_user.id)
        if deleted_macro:
            deleted_macro.delete()
    for c in ('tutorial-15-macros', 'tutorial-16-tables-and-macros'):
        deleted_coll = db.session.query(Collection).filter(Collection.id == c). \
            filter(Collection.author_id == current_user.id)
        if deleted_coll:
            deleted_coll.delete()
    for s in (-1, -2, -3):
        deleted_story = db.session.query(Post).filter(Post.id == s). \
            filter(Post.author_id == current_user.id)
        if deleted_story:
            deleted_story.delete()

    deleted_tag = db.session.query(Tags).filter(Tags.id == 'tutorial'). \
        filter(Tags.author_id == current_user.id)
    if deleted_tag:
        deleted_tag.delete()

    db.session.commit()

    # build tutorial set of data

    tag = Tags(id='tutorial',
               author_id=current_user.id)
    db.session.add(tag)

    resource_folder = os.path.dirname(current_app.instance_path) + "/resources/tutorial"
    for file in sorted(glob.glob(resource_folder + "/tables/*.json")):
        with open(file) as f:
            data = json.load(f)
            data['definition'] = "\n".join(
                [line.replace('USERNAME', current_user.username) for line in data['definition']])
        table = RandomTable(id=data['id'],
                            name=data['name'],
                            description=data['description'],
                            definition=data['definition'],
                            tags='tutorial',
                            author_id=current_user.id)
        max_rng, min_rng, validate_table_definition, table_type, error_message, row_count = check_table_definition_validity(
            table)
        if validate_table_definition:
            table.min = min_rng
            table.max = max_rng
            table.line_type = table_type
            table.row_count = row_count
            db.session.add(table)

    for file in sorted(glob.glob(resource_folder + "/macros/*.json")):
        with open(file) as f:
            data = json.load(f)
            data['definition'] = data['definition'].replace('USERNAME', current_user.username)
        macro = Macros(id=data['id'],
                       name=data['name'],
                       definition=data['definition'],
                       tags='tutorial',
                       author_id=current_user.id)
        db.session.add(macro)

    for file in sorted(glob.glob(resource_folder + "/collections/*.json")):
        with open(file) as f:
            data = json.load(f)
            data['definition'] = "\n".join(
                [line.replace('USERNAME', current_user.username) for line in data['definition']])
        collection_obj = Collection(id=data['id'],
                                    name=data['name'],
                                    description=data['description'],
                                    definition=data['definition'],
                                    tags='tutorial',
                                    author_id=current_user.id)
        db.session.add(collection_obj)

    for file in sorted(glob.glob(resource_folder + "/stories/*.json")):
        with open(file) as f:
            data = json.load(f)
            data['pins'] = data['pins'].replace('USERNAME', current_user.username)
            data['body'] = data['body'].replace('USERNAME', current_user.username)
        story = Post(id=int(data['id']),
                     body=data['body'],
                     title=data['title'],
                     pins=data['pins'],
                     author_id=current_user.id)
        db.session.add(story)

    db.session.commit()

    flash('Tutorial data created.')
    return redirect(url_for('main.index'))


@auth.route('/confirm')
@login_required
def resend_confirmation():
    token = current_user.generate_confirmation_token()
    send_email(current_user.email, 'Confirm Your Account',
               'auth/email/confirm', user=current_user, token=token)
    flash('A new confirmation email has been sent to you by email.')
    return redirect(url_for('main.index'))


@auth.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if current_user.verify_password(form.old_password.data):
            current_user.password = form.password.data
            db.session.add(current_user)
            flash('Your password has been updated.')
            return redirect(url_for('main.index'))
        else:
            flash('Invalid password.')
    return render_template("auth/change_password.html", form=form)


@auth.route('/reset', methods=['GET', 'POST'])
def password_reset_request():
    if not current_user.is_anonymous:
        return redirect(url_for('main.index'))
    form = PasswordResetRequestForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            token = user.generate_reset_token()
            send_email(user.email, 'Reset Your Password',
                       'auth/email/reset_password',
                       user=user, token=token,
                       next=request.args.get('next'))
        flash('An email with instructions to reset your password has been '
              'sent to you.')
        return redirect(url_for('auth.login'))
    return render_template('auth/reset_password.html', form=form)


@auth.route('/reset/<token>', methods=['GET', 'POST'])
def password_reset(token):
    if not current_user.is_anonymous:
        return redirect(url_for('main.index'))
    form = PasswordResetForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user is None:
            return redirect(url_for('main.index'))
        if user.reset_password(token, form.password.data):
            flash('Your password has been updated.')
            return redirect(url_for('auth.login'))
        else:
            return redirect(url_for('main.index'))
    return render_template('auth/reset_password.html', form=form)


@auth.route('/change-email', methods=['GET', 'POST'])
@login_required
def change_email_request():
    form = ChangeEmailForm()
    if form.validate_on_submit():
        if current_user.verify_password(form.password.data):
            new_email = form.email.data
            token = current_user.generate_email_change_token(new_email)
            send_email(new_email, 'Confirm your email address',
                       'auth/email/change_email',
                       user=current_user, token=token)
            flash('An email with instructions to confirm your new email '
                  'address has been sent to you.')
            return redirect(url_for('main.index'))
        else:
            flash('Invalid email or password.')
    return render_template("auth/change_email.html", form=form)


@auth.route('/change-email/<token>')
@login_required
def change_email(token):
    if current_user.change_email(token):
        flash('Your email address has been updated.')
    else:
        flash('Invalid request.')
    return redirect(url_for('main.index'))
