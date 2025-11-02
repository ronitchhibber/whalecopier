"""add market resolutions table

Revision ID: 002
Revises: 001
Create Date: 2025-11-02 14:50:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade():
    # Create market_resolutions table
    op.create_table(
        'market_resolutions',
        sa.Column('market_id', sa.String(), nullable=False),
        sa.Column('question', sa.String(), nullable=True),
        sa.Column('category', sa.String(), nullable=True),
        sa.Column('end_date', sa.DateTime(), nullable=True),
        sa.Column('resolution_date', sa.DateTime(), nullable=True),
        sa.Column('resolved', sa.Boolean(), nullable=True, default=False),
        sa.Column('outcome', sa.String(), nullable=True),
        sa.Column('outcome_prices', sa.String(), nullable=True),
        sa.Column('resolved_by', sa.String(), nullable=True),
        sa.Column('resolution_source', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('volume_24h', sa.Float(), nullable=True),
        sa.Column('liquidity', sa.Float(), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=True, default=True),
        sa.PrimaryKeyConstraint('market_id')
    )

    # Create indexes for common queries
    op.create_index('idx_market_resolutions_resolved', 'market_resolutions', ['resolved'])
    op.create_index('idx_market_resolutions_category', 'market_resolutions', ['category'])
    op.create_index('idx_market_resolutions_end_date', 'market_resolutions', ['end_date'])

    # Add columns to trades table for P&L tracking
    op.add_column('trades', sa.Column('realized_pnl', sa.Float(), nullable=True))
    op.add_column('trades', sa.Column('is_resolved', sa.Boolean(), nullable=True, default=False))
    op.add_column('trades', sa.Column('resolution_checked_at', sa.DateTime(), nullable=True))

    # Create index for faster whale P&L queries
    op.create_index('idx_trades_whale_resolved', 'trades', ['whale_address', 'is_resolved'])


def downgrade():
    # Drop indexes
    op.drop_index('idx_trades_whale_resolved', table_name='trades')
    op.drop_index('idx_market_resolutions_end_date', table_name='market_resolutions')
    op.drop_index('idx_market_resolutions_category', table_name='market_resolutions')
    op.drop_index('idx_market_resolutions_resolved', table_name='market_resolutions')

    # Drop columns from trades
    op.drop_column('trades', 'resolution_checked_at')
    op.drop_column('trades', 'is_resolved')
    op.drop_column('trades', 'realized_pnl')

    # Drop market_resolutions table
    op.drop_table('market_resolutions')
