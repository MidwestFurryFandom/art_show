"""Add buyers for pieces and payment tracking

Revision ID: 676530c66ee7
Revises: 54227ab70c17
Create Date: 2018-10-26 19:14:27.685763

"""


# revision identifiers, used by Alembic.
revision = '676530c66ee7'
down_revision = '54227ab70c17'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa
import residue


try:
    is_sqlite = op.get_context().dialect.name == 'sqlite'
except Exception:
    is_sqlite = False

if is_sqlite:
    op.get_context().connection.execute('PRAGMA foreign_keys=ON;')
    utcnow_server_default = "(datetime('now', 'utc'))"
else:
    utcnow_server_default = "timezone('utc', current_timestamp)"

def sqlite_column_reflect_listener(inspector, table, column_info):
    """Adds parenthesis around SQLite datetime defaults for utcnow."""
    if column_info['default'] == "datetime('now', 'utc')":
        column_info['default'] = utcnow_server_default

sqlite_reflect_kwargs = {
    'listeners': [('column_reflect', sqlite_column_reflect_listener)]
}

# ===========================================================================
# HOWTO: Handle alter statements in SQLite
#
# def upgrade():
#     if is_sqlite:
#         with op.batch_alter_table('table_name', reflect_kwargs=sqlite_reflect_kwargs) as batch_op:
#             batch_op.alter_column('column_name', type_=sa.Unicode(), server_default='', nullable=False)
#     else:
#         op.alter_column('table_name', 'column_name', type_=sa.Unicode(), server_default='', nullable=False)
#
# ===========================================================================


def upgrade():
    op.create_table('art_show_payment',
    sa.Column('id', residue.UUID(), nullable=False),
    sa.Column('attendee_id', residue.UUID(), nullable=True),
    sa.Column('amount', sa.Integer(), server_default='0', nullable=False),
    sa.Column('type', sa.Integer(), server_default='180350097', nullable=False),
    sa.Column('when', residue.UTCDateTime(), nullable=False),
    sa.ForeignKeyConstraint(['attendee_id'], ['attendee.id'], name=op.f('fk_art_show_payment_attendee_id_attendee'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_art_show_payment'))
    )
    op.add_column('art_show_piece', sa.Column('buyer_id', residue.UUID(), nullable=True))
    op.add_column('art_show_piece', sa.Column('winning_bid', sa.Integer(), server_default='0', nullable=True))
    op.create_foreign_key(op.f('fk_art_show_piece_buyer_id_attendee'), 'art_show_piece', 'attendee', ['buyer_id'], ['id'], ondelete='SET NULL')


def downgrade():
    op.drop_constraint(op.f('fk_art_show_piece_buyer_id_attendee'), 'art_show_piece', type_='foreignkey')
    op.drop_column('art_show_piece', 'winning_bid')
    op.drop_column('art_show_piece', 'buyer_id')
    op.drop_table('art_show_payment')
