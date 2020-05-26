from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, BooleanField, SelectField, SubmitField, RadioField, FieldList, HiddenField, IntegerField
from wtforms.validators import Length, Email, Regexp, DataRequired, NumberRange
from wtforms import ValidationError
from flask_pagedown.fields import PageDownField
from wtforms.widgets import HiddenInput
from ..models import Role, User


class NameForm(FlaskForm):
    name = StringField('What is your name?', validators=[DataRequired()])
    submit = SubmitField('Submit')


class EditProfileForm(FlaskForm):
    name = StringField('Real name', validators=[Length(0, 64)])
    location = StringField('Location', validators=[Length(0, 64)])
    about_me = TextAreaField('About me')
    submit = SubmitField('Submit')


class EditProfileAdminForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Length(1, 64), Email()])
    username = StringField('Username', validators=[
        DataRequired(), Length(1, 64), Regexp('^[A-Za-z][A-Za-z0-9_.]*$', 0,
                                              'UserNames must have only letters, numbers, dots or underscores')])
    confirmed = BooleanField('Confirmed')
    role = SelectField('Role', coerce=int)
    name = StringField('Real name', validators=[Length(0, 64)])
    location = StringField('Location', validators=[Length(0, 64)])
    about_me = TextAreaField('About me')
    submit = SubmitField('Submit')

    def __init__(self, user, *args, **kwargs):
        super(EditProfileAdminForm, self).__init__(*args, **kwargs)
        self.role.choices = [(role.id, role.name)
                             for role in Role.query.order_by(Role.name).all()]
        self.user = user

    def validate_email(self, field):
        if field.data != self.user.email and \
                User.query.filter_by(email=field.data).first():
            raise ValidationError('Email already registered.')

    def validate_username(self, field):
        if field.data != self.user.username and \
                User.query.filter_by(username=field.data).first():
            raise ValidationError('Username already in use.')


class PostForm(FlaskForm):
    body = PageDownField("What's on your mind?", validators=[DataRequired()])
    submit = SubmitField('Submit')


class CommentForm(FlaskForm):
    body = StringField('Enter your comment', validators=[DataRequired()])
    submit = SubmitField('Submit')


class TableForm(FlaskForm):
    table_name = StringField('Table name', validators=[Length(0, 255)])
    table_id = StringField('Identifier', validators=[Length(0, 255)])
    table_description = TextAreaField('Description')
    table_definition = TextAreaField('Random Table Definition', render_kw={"rows": 10, "cols": 70})
    # table_permissions = RadioField('Table Type',
    #                                choices=[('0', 'Private'), ('1', 'Public Open'), ('5', 'Public Closed'),
    #                                         ('2', 'Commercial Open'), ('6', 'Commercial Closed')])
    table_tags = SelectField('Tags')
    submit = SubmitField('Save')


class StoryForm(FlaskForm):
    title = StringField('Title', validators=[Length(0, 255)])
    story = TextAreaField("Story", validators=[DataRequired()], render_kw={"rows": 24, "cols": 60})
    pins = HiddenField("Pins", validators=None)
    submit = SubmitField('Save')


class MacroForm(FlaskForm):
    macro_name = StringField('Macro Name', validators=[Length(0, 255)])
    macro_id = StringField('Identifier', validators=[Length(0, 255)])
    macro_body = TextAreaField("Create Macro", validators=[DataRequired()], render_kw={"rows": 15, "cols": 60})
    macro_tags = SelectField('Tags')
    submit = SubmitField('Save')


class CollectionForm(FlaskForm):
    collection_name = StringField('Collection Name', validators=[Length(0, 255)])
    collection_id = StringField('Identifier', validators=[Length(0, 255)])
    collection_description = TextAreaField('Description')
    collection_definition = TextAreaField("Collection Items", validators=[DataRequired()], render_kw={"rows": 15, "cols": 60})
    collection_tags = SelectField('Tags')
    submit = SubmitField('Save')


class TagForm(FlaskForm):
    tag_id = StringField('Tag ID', validators=[Length(0, 64)])
    submit = SubmitField('Save')


class MarketForm(FlaskForm):
    name = StringField('Marketplace Name', validators=[Length(0, 255)])
    description = TextAreaField('Description')
    commercial = BooleanField('Commercial Product', render_kw={"title": "Is this Product for sale, tick box if so. Leave unticked to be publicly available"})
    open = BooleanField('Open', render_kw={"title": "If ticked the contents of the product are viewable, if unticked users can only get the results of selecting the table/macro."})
    editable = BooleanField('Editable', render_kw={"title": "Only used if Product is Open, if so check this box if you want to allow users ability to edit the tables/macros."})
    market_tags = SelectField('Tags')
    category1 = SelectField('Market Place Category 1')
    category2 = SelectField('Market Place Category 2')
    submit = SubmitField('Save')


class BulkTableImportForm(FlaskForm):
    tables = TextAreaField('Bulk Table Definitions', validators=[DataRequired()], render_kw={"rows": 15, "cols": 60})
    bulk_tag = SelectField('Tag')
    submit = SubmitField('Save')
