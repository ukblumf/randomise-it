"""Adding support to make table/macro contents viewable after sharing

Revision ID: 04e56013761f
Revises: 63c5fe144a13
Create Date: 2020-09-15 11:11:46.571413

"""

# revision identifiers, used by Alembic.
revision = '04e56013761f'
down_revision = '63c5fe144a13'

from alembic import op
import sqlalchemy as sa


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('macros', schema=None) as batch_op:
        batch_op.add_column(sa.Column('visible_contents', sa.Boolean(), nullable=True))

    with op.batch_alter_table('public_macros', schema=None) as batch_op:
        batch_op.add_column(sa.Column('visible_contents', sa.Boolean(), nullable=True))

    with op.batch_alter_table('public_random_table', schema=None) as batch_op:
        batch_op.add_column(sa.Column('visible_contents', sa.Boolean(), nullable=True))

    with op.batch_alter_table('random_table', schema=None) as batch_op:
        batch_op.add_column(sa.Column('visible_contents', sa.Boolean(), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('random_table', schema=None) as batch_op:
        batch_op.drop_column('visible_contents')

    with op.batch_alter_table('public_random_table', schema=None) as batch_op:
        batch_op.drop_column('visible_contents')

    with op.batch_alter_table('public_macros', schema=None) as batch_op:
        batch_op.drop_column('visible_contents')

    with op.batch_alter_table('macros', schema=None) as batch_op:
        batch_op.drop_column('visible_contents')

    # ### end Alembic commands ###
