"""Add last modified date columns

Revision ID: ea0bb459dec9
Revises: 1058cde5df9f
Create Date: 2020-07-07 15:33:11.305058

"""

# revision identifiers, used by Alembic.
revision = 'ea0bb459dec9'
down_revision = '1058cde5df9f'

from alembic import op
import sqlalchemy as sa


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('collection', schema=None) as batch_op:
        batch_op.add_column(sa.Column('last_modified', sa.DateTime(), nullable=True))

    with op.batch_alter_table('macros', schema=None) as batch_op:
        batch_op.add_column(sa.Column('last_modified', sa.DateTime(), nullable=True))

    with op.batch_alter_table('marketplace', schema=None) as batch_op:
        batch_op.add_column(sa.Column('last_modified', sa.DateTime(), nullable=True))

    with op.batch_alter_table('posts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('last_modified', sa.DateTime(), nullable=True))

    with op.batch_alter_table('public_collection', schema=None) as batch_op:
        batch_op.add_column(sa.Column('last_modified', sa.DateTime(), nullable=True))

    with op.batch_alter_table('public_macros', schema=None) as batch_op:
        batch_op.add_column(sa.Column('last_modified', sa.DateTime(), nullable=True))

    with op.batch_alter_table('public_random_table', schema=None) as batch_op:
        batch_op.add_column(sa.Column('last_modified', sa.DateTime(), nullable=True))

    with op.batch_alter_table('random_table', schema=None) as batch_op:
        batch_op.add_column(sa.Column('last_modified', sa.DateTime(), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('random_table', schema=None) as batch_op:
        batch_op.drop_column('last_modified')

    with op.batch_alter_table('public_random_table', schema=None) as batch_op:
        batch_op.drop_column('last_modified')

    with op.batch_alter_table('public_macros', schema=None) as batch_op:
        batch_op.drop_column('last_modified')

    with op.batch_alter_table('public_collection', schema=None) as batch_op:
        batch_op.drop_column('last_modified')

    with op.batch_alter_table('posts', schema=None) as batch_op:
        batch_op.drop_column('last_modified')

    with op.batch_alter_table('marketplace', schema=None) as batch_op:
        batch_op.drop_column('last_modified')

    with op.batch_alter_table('macros', schema=None) as batch_op:
        batch_op.drop_column('last_modified')

    with op.batch_alter_table('collection', schema=None) as batch_op:
        batch_op.drop_column('last_modified')

    # ### end Alembic commands ###
