"""Persist owner-scoped scripture research trails."""

from alembic import op
import sqlalchemy as sa


revision = '0011_research_trail'
down_revision = '0010_merge_platform_composite'
branch_labels = None
depends_on = None


_RESEARCH_MODES = (
    'what-happened-between',
    'research-question',
    'topic-research',
    'person-study',
    'place-study',
    'timeline',
    'people-and-places',
)
_RESEARCH_DEPTHS = ('quick', 'study', 'deep-research', 'scholar')


def _sql_values(values: tuple[str, ...]) -> str:
    return ', '.join(repr(value) for value in values)


def upgrade() -> None:
    op.create_table(
        'research_nodes',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('owner_id', sa.Uuid(), nullable=False),
        sa.Column('study_id', sa.Uuid(), nullable=True),
        sa.Column('parent_id', sa.Uuid(), nullable=True),
        sa.Column('question', sa.String(length=10_000), nullable=False),
        sa.Column('mode', sa.String(length=40), nullable=False),
        sa.Column('source_scopes', sa.JSON(), nullable=False),
        sa.Column('depth', sa.String(length=30), nullable=False),
        sa.Column('response_snapshot', sa.JSON(), nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            'length(question) BETWEEN 1 AND 10000',
            name='ck_research_nodes_question_length',
        ),
        sa.CheckConstraint(
            f'mode IN ({_sql_values(_RESEARCH_MODES)})',
            name='ck_research_nodes_mode',
        ),
        sa.CheckConstraint(
            f'depth IN ({_sql_values(_RESEARCH_DEPTHS)})',
            name='ck_research_nodes_depth',
        ),
        sa.ForeignKeyConstraint(
            ['owner_id'],
            ['users.id'],
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['study_id'],
            ['study_sessions.id'],
            ondelete='SET NULL',
        ),
        sa.ForeignKeyConstraint(
            ['parent_id'],
            ['research_nodes.id'],
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_research_nodes_owner_updated',
        'research_nodes',
        ['owner_id', 'updated_at'],
    )
    op.create_index(
        'ix_research_nodes_parent_id',
        'research_nodes',
        ['parent_id'],
    )


def downgrade() -> None:
    op.drop_index('ix_research_nodes_parent_id', table_name='research_nodes')
    op.drop_index('ix_research_nodes_owner_updated', table_name='research_nodes')
    op.drop_table('research_nodes')
