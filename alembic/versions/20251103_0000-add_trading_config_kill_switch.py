"""add_trading_config_table_with_kill_switch

Revision ID: 4f8a3b2c1d5e
Revises: 2a0720202a01
Create Date: 2025-11-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = '4f8a3b2c1d5e'
down_revision: Union[str, Sequence[str], None] = '2a0720202a01'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create trading_config table and insert initial row."""
    # Create trading_config table
    op.create_table(
        'trading_config',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('copy_trading_enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('max_position_size', sa.Numeric(precision=20, scale=2), server_default='1000.0'),
        sa.Column('max_total_exposure', sa.Numeric(precision=20, scale=2), server_default='10000.0'),
        sa.Column('max_positions', sa.Integer(), server_default='1000'),
        sa.Column('last_modified_at', sa.TIMESTAMP(), nullable=False, server_default=text('NOW()')),
        sa.Column('modified_by', sa.String(100)),
        sa.CheckConstraint('id = 1', name='single_row_only')
    )

    # Insert initial configuration row
    op.execute("""
        INSERT INTO trading_config (
            id,
            copy_trading_enabled,
            max_position_size,
            max_total_exposure,
            max_positions,
            last_modified_at,
            modified_by
        ) VALUES (
            1,
            true,
            1000.0,
            10000.0,
            1000,
            NOW(),
            'system_init'
        )
    """)


def downgrade() -> None:
    """Drop trading_config table."""
    op.drop_table('trading_config')
