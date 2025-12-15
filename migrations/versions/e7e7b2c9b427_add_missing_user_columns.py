"""add missing user columns

Revision ID: e7e7b2c9b427
Revises: 4f0c7f3501c4
Create Date: 2025-12-13 20:55:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'e7e7b2c9b427'
down_revision = '4f0c7f3501c4'
branch_labels = None
depends_on = None


def upgrade():
    # Add missing columns to user table
    # Note: batch_alter_table doesn't work well with PostgreSQL, use direct column addition
    op.add_column('user', sa.Column('email', sa.String(length=120), nullable=True))
    op.add_column('user', sa.Column('phone', sa.String(length=20), nullable=True))
    op.add_column('user', sa.Column('created_at', sa.DateTime(), nullable=True))
    op.add_column('user', sa.Column('last_login', sa.DateTime(), nullable=True))
    op.add_column('user', sa.Column('is_active', sa.Boolean(), nullable=True))
    op.add_column('user', sa.Column('role', sa.String(length=20), nullable=True))
    
    # Set default values for existing rows
    op.execute("UPDATE \"user\" SET is_active = true WHERE is_active IS NULL")
    op.execute("UPDATE \"user\" SET role = 'user' WHERE role IS NULL")
    op.execute("UPDATE \"user\" SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL")
    
    # Set server defaults for future rows (optional, but helps)
    # Note: We can't easily add server defaults after the fact in PostgreSQL without recreating the column
    # So we'll just ensure existing rows have values


def downgrade():
    # Remove the columns
    op.drop_column('user', 'role')
    op.drop_column('user', 'is_active')
    op.drop_column('user', 'last_login')
    op.drop_column('user', 'created_at')
    op.drop_column('user', 'phone')
    op.drop_column('user', 'email')
