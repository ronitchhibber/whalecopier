"""add_24h_metrics_and_recent_trade_columns

Revision ID: 2a0720202a01
Revises: 3254c910aa28
Create Date: 2025-10-31 16:19:58.317210

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2a0720202a01'
down_revision: Union[str, Sequence[str], None] = '3254c910aa28'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add 24h metrics columns
    op.add_column('whales', sa.Column('trades_24h', sa.Integer(), nullable=True))
    op.add_column('whales', sa.Column('volume_24h', sa.Numeric(precision=20, scale=2), nullable=True))

    # Add active trades count (replacing/complementing active_positions)
    op.add_column('whales', sa.Column('active_trades', sa.Integer(), nullable=True))

    # Add timestamp tracking for recent trades
    op.add_column('whales', sa.Column('most_recent_trade_at', sa.TIMESTAMP(timezone=True), nullable=True))
    op.add_column('whales', sa.Column('last_trade_check_at', sa.TIMESTAMP(timezone=True), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    # Remove timestamp tracking columns
    op.drop_column('whales', 'last_trade_check_at')
    op.drop_column('whales', 'most_recent_trade_at')

    # Remove active trades count
    op.drop_column('whales', 'active_trades')

    # Remove 24h metrics columns
    op.drop_column('whales', 'volume_24h')
    op.drop_column('whales', 'trades_24h')
