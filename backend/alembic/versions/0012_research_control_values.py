"""Align persisted research modes with the approved controls."""

from alembic import op


revision = '0012_research_control_values'
down_revision = '0011_research_trail'
branch_labels = None
depends_on = None


_PRIOR_MODES = (
    'what-happened-between',
    'research-question',
    'topic-research',
    'person-study',
    'place-study',
    'timeline',
    'people-and-places',
)

_APPROVED_MODES = (
    'what-happened-between',
    'explain-a-book',
    'compare-accounts',
    'people-and-places',
    'original-languages',
    'genealogy',
)

_UPGRADE_MODE_MAP = {
    'research-question': 'explain-a-book',
    'topic-research': 'compare-accounts',
    'person-study': 'people-and-places',
    'place-study': 'people-and-places',
    'timeline': 'what-happened-between',
}

_DOWNGRADE_MODE_MAP = {
    'explain-a-book': 'research-question',
    'compare-accounts': 'topic-research',
    'original-languages': 'research-question',
    'genealogy': 'person-study',
}


def _sql_values(values: tuple[str, ...]) -> str:
    return ', '.join(repr(value) for value in values)


def _replace_mode_constraint(
    values: tuple[str, ...],
    replacements: dict[str, str],
) -> None:
    # Dropping first lets existing rows be translated before the exact new
    # constraint is applied. Batch operations keep this SQLite-compatible.
    with op.batch_alter_table('research_nodes') as batch_op:
        batch_op.drop_constraint('ck_research_nodes_mode', type_='check')

    cases = ' '.join(
        f"WHEN {old!r} THEN {new!r}"
        for old, new in replacements.items()
    )
    op.execute(
        f'UPDATE research_nodes SET mode = CASE mode {cases} ELSE mode END'
    )

    with op.batch_alter_table('research_nodes') as batch_op:
        batch_op.create_check_constraint(
            'ck_research_nodes_mode',
            f'mode IN ({_sql_values(values)})',
        )


def upgrade() -> None:
    _replace_mode_constraint(_APPROVED_MODES, _UPGRADE_MODE_MAP)


def downgrade() -> None:
    _replace_mode_constraint(_PRIOR_MODES, _DOWNGRADE_MODE_MAP)
