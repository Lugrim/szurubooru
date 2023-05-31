'''
add-wishlist

Revision ID: 93650effbf5a
Created at: 2023-05-31 12:58:09.048808
'''

import sqlalchemy as sa
from alembic import op



revision = '93650effbf5a'
down_revision = '9ba5e3a6ee7c'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('user', sa.Column('wishlist', sa.Text, nullable=True))


def downgrade():
    op.drop_column('user', 'wishlist')
