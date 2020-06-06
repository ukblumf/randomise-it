"""Add Public Announcement table

Revision ID: 66211fef0bb4
Revises: 9a84a93d0fd3
Create Date: 2020-06-06 11:29:58.607098

"""

# revision identifiers, used by Alembic.
revision = '66211fef0bb4'
down_revision = '9a84a93d0fd3'

from alembic import op
import sqlalchemy as sa


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('public_announcements',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('title', sa.Text(), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('author_id', sa.Integer(), nullable=True),
    sa.Column('timestamp', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['author_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('public_announcements', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_public_announcements_author_id'), ['author_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_public_announcements_timestamp'), ['timestamp'], unique=False)

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('public_announcements', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_public_announcements_timestamp'))
        batch_op.drop_index(batch_op.f('ix_public_announcements_author_id'))

    op.drop_table('public_announcements')
    # ### end Alembic commands ###
