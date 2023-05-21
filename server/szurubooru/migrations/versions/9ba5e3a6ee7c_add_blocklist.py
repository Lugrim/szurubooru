'''
Add blocklist related fields

add_blocklist

Revision ID: 9ba5e3a6ee7c
Created at: 2023-05-20 22:28:10.824954
'''

import sqlalchemy as sa
from alembic import op

revision = '9ba5e3a6ee7c'
down_revision = 'adcd63ff76a2'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('user', sa.Column('blocklist', sa.Text, nullable=True))


def downgrade():
    op.drop_column('user', 'blocklist')
