"""create ma strategy cross tab model

Revision ID: 392bcb3b35c5
Revises: 99275f7f0073
Create Date: 2024-10-09 14:52:30.139832

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '392bcb3b35c5'
down_revision: Union[str, None] = '99275f7f0073'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('market_asset_type',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    op.create_table('ma_cross_tab',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('symbol', sa.String(), nullable=False),
    sa.Column('market_assets_type', sa.Integer(), nullable=False),
    sa.Column('timeframe_type', sa.Integer(), nullable=False),
    sa.Column('ma_cross_resistance', sa.Float(), nullable=True),
    sa.Column('ma_cross_support', sa.Float(), nullable=True),
    sa.Column('liquidity_status', sa.String(), nullable=True),
    sa.ForeignKeyConstraint(['market_assets_type'], ['market_asset_type.id'], ),
    sa.ForeignKeyConstraint(['timeframe_type'], ['timeframe_type.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('symbol', 'market_assets_type', 'timeframe_type')
    )


def downgrade() -> None:
    pass
    # op.drop_table('ma_cross_tab')
    # op.drop_table('market_asset_type')