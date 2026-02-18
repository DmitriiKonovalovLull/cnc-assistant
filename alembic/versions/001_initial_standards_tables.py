"""Initial standards tables

Revision ID: 001
Revises: 
Create Date: 2026-02-16

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Создаем таблицу standards
    op.create_table(
        'standards',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('family', sa.String(20), nullable=False),
        sa.Column('code', sa.String(100), nullable=False),
        sa.Column('full_code', sa.String(200), nullable=False),
        sa.Column('title', sa.Text()),
        sa.Column('country', sa.String(50)),
        sa.Column('revision', sa.String(20)),
        sa.Column('version_hash', sa.String(64), nullable=False),
        sa.Column('source', sa.String(50), default='user_upload'),
        sa.Column('last_checked', sa.DateTime(), default=sa.func.now()),
        sa.Column('last_updated', sa.DateTime(), default=sa.func.now()),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('needs_review', sa.Boolean(), default=False),
    )
    
    # Индексы для standards
    op.create_index('idx_standard_family', 'standards', ['family'])
    op.create_index('idx_standard_code', 'standards', ['code'])
    op.create_index('idx_standard_full_code', 'standards', ['full_code'])
    op.create_index('idx_standard_version_hash', 'standards', ['version_hash'])
    op.create_index('idx_standard_needs_review', 'standards', ['needs_review'])
    op.create_index('idx_standard_last_checked', 'standards', ['last_checked'])
    op.create_index('idx_standard_family_code', 'standards', ['family', 'code'])
    op.create_index('idx_standard_needs_review_checked', 'standards', ['needs_review', 'last_checked'])
    
    # Создаем таблицу standard_versions
    op.create_table(
        'standard_versions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('standard_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('version_hash', sa.String(64), nullable=False),
        sa.Column('file_path', sa.Text(), nullable=False),
        sa.Column('file_size', sa.Integer()),
        sa.Column('version_metadata', postgresql.JSONB()),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['standard_id'], ['standards.id'], ondelete='CASCADE'),
    )
    
    # Индексы для standard_versions
    op.create_index('idx_version_standard_id', 'standard_versions', ['standard_id'])
    op.create_index('idx_version_hash', 'standard_versions', ['version_hash'])
    op.create_index('idx_version_created_at', 'standard_versions', ['created_at'])
    
    # Создаем таблицу standard_data
    op.create_table(
        'standard_data',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('standard_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('section_name', sa.String(200), nullable=False),
        sa.Column('data', postgresql.JSONB(), nullable=False),
        sa.Column('data_type', sa.String(50)),
        sa.Column('page_number', sa.Integer()),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.ForeignKeyConstraint(['standard_id'], ['standards.id'], ondelete='CASCADE'),
    )
    
    # Индексы для standard_data
    op.create_index('idx_data_standard_id', 'standard_data', ['standard_id'])
    op.create_index('idx_data_section', 'standard_data', ['section_name'])
    op.create_index('idx_data_standard_section', 'standard_data', ['standard_id', 'section_name'])


def downgrade() -> None:
    op.drop_index('idx_data_standard_section', table_name='standard_data')
    op.drop_index('idx_data_section', table_name='standard_data')
    op.drop_index('idx_data_standard_id', table_name='standard_data')
    op.drop_table('standard_data')
    
    op.drop_index('idx_version_created_at', table_name='standard_versions')
    op.drop_index('idx_version_hash', table_name='standard_versions')
    op.drop_index('idx_version_standard_id', table_name='standard_versions')
    op.drop_table('standard_versions')
    
    op.drop_index('idx_standard_needs_review_checked', table_name='standards')
    op.drop_index('idx_standard_family_code', table_name='standards')
    op.drop_index('idx_standard_last_checked', table_name='standards')
    op.drop_index('idx_standard_needs_review', table_name='standards')
    op.drop_index('idx_standard_version_hash', table_name='standards')
    op.drop_index('idx_standard_full_code', table_name='standards')
    op.drop_index('idx_standard_code', table_name='standards')
    op.drop_index('idx_standard_family', table_name='standards')
    op.drop_table('standards')
