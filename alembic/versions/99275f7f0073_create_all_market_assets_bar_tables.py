"""create all market assets bar tables

Revision ID: 99275f7f0073
Revises: 
Create Date: 2024-10-09 13:45:21.626845

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '99275f7f0073'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('timeframe_type',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    op.create_table('bond_mtf_bar',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('symbol', sa.String(), nullable=False),
    sa.Column('timestamp', sa.DateTime(), nullable=False),
    sa.Column('open', sa.Float(), nullable=True),
    sa.Column('high', sa.Float(), nullable=True),
    sa.Column('low', sa.Float(), nullable=True),
    sa.Column('close', sa.Float(), nullable=True),
    sa.Column('volume', sa.Float(), nullable=True),
    sa.Column('timeframe_type', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['timeframe_type'], ['timeframe_type.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('symbol', 'timestamp', 'timeframe_type')
    )
    op.create_table('cfd_mtf_bar',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('symbol', sa.String(), nullable=False),
    sa.Column('timestamp', sa.DateTime(), nullable=False),
    sa.Column('open', sa.Float(), nullable=True),
    sa.Column('high', sa.Float(), nullable=True),
    sa.Column('low', sa.Float(), nullable=True),
    sa.Column('close', sa.Float(), nullable=True),
    sa.Column('volume', sa.Float(), nullable=True),
    sa.Column('timeframe_type', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['timeframe_type'], ['timeframe_type.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('symbol', 'timestamp', 'timeframe_type')
    )
    op.create_table('commodity_mtf_bar',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('symbol', sa.String(), nullable=False),
    sa.Column('timestamp', sa.DateTime(), nullable=False),
    sa.Column('open', sa.Float(), nullable=True),
    sa.Column('high', sa.Float(), nullable=True),
    sa.Column('low', sa.Float(), nullable=True),
    sa.Column('close', sa.Float(), nullable=True),
    sa.Column('volume', sa.Float(), nullable=True),
    sa.Column('timeframe_type', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['timeframe_type'], ['timeframe_type.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('symbol', 'timestamp', 'timeframe_type')
    )
    op.create_table('crypto_mtf_bar',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('symbol', sa.String(), nullable=False),
    sa.Column('timestamp', sa.DateTime(), nullable=False),
    sa.Column('open', sa.Float(), nullable=True),
    sa.Column('high', sa.Float(), nullable=True),
    sa.Column('low', sa.Float(), nullable=True),
    sa.Column('close', sa.Float(), nullable=True),
    sa.Column('volume', sa.Float(), nullable=True),
    sa.Column('timeframe_type', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['timeframe_type'], ['timeframe_type.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('symbol', 'timestamp', 'timeframe_type')
    )
    op.create_table('forex_mtf_bar',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('symbol', sa.String(), nullable=False),
    sa.Column('timestamp', sa.DateTime(), nullable=False),
    sa.Column('open', sa.Float(), nullable=True),
    sa.Column('high', sa.Float(), nullable=True),
    sa.Column('low', sa.Float(), nullable=True),
    sa.Column('close', sa.Float(), nullable=True),
    sa.Column('volume', sa.Float(), nullable=True),
    sa.Column('timeframe_type', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['timeframe_type'], ['timeframe_type.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('symbol', 'timestamp', 'timeframe_type')
    )
    op.create_table('future_mtf_bar',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('symbol', sa.String(), nullable=False),
    sa.Column('timestamp', sa.DateTime(), nullable=False),
    sa.Column('open', sa.Float(), nullable=True),
    sa.Column('high', sa.Float(), nullable=True),
    sa.Column('low', sa.Float(), nullable=True),
    sa.Column('close', sa.Float(), nullable=True),
    sa.Column('volume', sa.Float(), nullable=True),
    sa.Column('timeframe_type', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['timeframe_type'], ['timeframe_type.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('symbol', 'timestamp', 'timeframe_type')
    )
    op.create_table('index_mtf_bar',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('symbol', sa.String(), nullable=False),
    sa.Column('timestamp', sa.DateTime(), nullable=False),
    sa.Column('open', sa.Float(), nullable=True),
    sa.Column('high', sa.Float(), nullable=True),
    sa.Column('low', sa.Float(), nullable=True),
    sa.Column('close', sa.Float(), nullable=True),
    sa.Column('volume', sa.Float(), nullable=True),
    sa.Column('timeframe_type', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['timeframe_type'], ['timeframe_type.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('symbol', 'timestamp', 'timeframe_type')
    )
    op.create_table('option_mtf_bar',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('symbol', sa.String(), nullable=False),
    sa.Column('timestamp', sa.DateTime(), nullable=False),
    sa.Column('open', sa.Float(), nullable=True),
    sa.Column('high', sa.Float(), nullable=True),
    sa.Column('low', sa.Float(), nullable=True),
    sa.Column('close', sa.Float(), nullable=True),
    sa.Column('volume', sa.Float(), nullable=True),
    sa.Column('timeframe_type', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['timeframe_type'], ['timeframe_type.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('symbol', 'timestamp', 'timeframe_type')
    )
    op.create_table('stock_mtf_bar',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('symbol', sa.String(), nullable=False),
    sa.Column('timestamp', sa.DateTime(), nullable=False),
    sa.Column('open', sa.Float(), nullable=True),
    sa.Column('high', sa.Float(), nullable=True),
    sa.Column('low', sa.Float(), nullable=True),
    sa.Column('close', sa.Float(), nullable=True),
    sa.Column('volume', sa.Float(), nullable=True),
    sa.Column('timeframe_type', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['timeframe_type'], ['timeframe_type.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('symbol', 'timestamp', 'timeframe_type')
    )


def downgrade() -> None:
    pass
    # op.drop_table('stock_mtf_bar')
    # op.drop_table('option_mtf_bar')
    # op.drop_table('index_mtf_bar')
    # op.drop_table('future_mtf_bar')
    # op.drop_table('forex_mtf_bar')
    # op.drop_table('crypto_mtf_bar')
    # op.drop_table('commodity_mtf_bar')
    # op.drop_table('cfd_mtf_bar')
    # op.drop_table('bond_mtf_bar')
    # op.drop_table('timeframe_type')
