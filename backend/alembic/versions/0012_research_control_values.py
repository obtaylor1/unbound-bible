"""Align persisted research modes and scopes with approved controls."""

import json

from alembic import op
import sqlalchemy as sa


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

_UPGRADE_SCOPE_MAP = {
    'ancient-accounts': 'ancient-sources',
    'historical-sources': 'ancient-sources',
    'commentaries': 'commentary',
    'language-resources': 'biblical-canon',
    'user-library': 'biblical-canon',
}

_DOWNGRADE_SCOPE_MAP = {
    'apocrypha': 'ancient-accounts',
    '1-enoch': 'ancient-accounts',
    'jubilees': 'ancient-accounts',
    'ancient-sources': 'ancient-accounts',
    'commentary': 'commentaries',
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


def _decoded_json(value: object) -> object:
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return None


def _mapped_scopes(value: object, replacements: dict[str, str]) -> list[str] | None:
    scopes = _decoded_json(value)
    if not isinstance(scopes, list) or any(
        not isinstance(scope, str) for scope in scopes
    ):
        return None
    mapped = [replacements.get(scope, scope) for scope in scopes]
    if 'all-sources' in mapped:
        return ['all-sources']
    result: list[str] = []
    seen: set[str] = set()
    for scope in mapped:
        if scope not in seen:
            seen.add(scope)
            result.append(scope)
    return result


def _migrate_source_scopes(replacements: dict[str, str]) -> None:
    connection = op.get_bind()
    rows = list(connection.execute(sa.text(
        'SELECT id, source_scopes, response_snapshot FROM research_nodes'
    )).mappings())
    update_scopes = sa.text('''
        UPDATE research_nodes SET source_scopes = :source_scopes WHERE id = :id
    ''').bindparams(sa.bindparam('source_scopes', type_=sa.JSON()))
    update_snapshot = sa.text('''
        UPDATE research_nodes
        SET response_snapshot = :response_snapshot
        WHERE id = :id
    ''').bindparams(sa.bindparam('response_snapshot', type_=sa.JSON()))

    for row in rows:
        mapped = _mapped_scopes(row['source_scopes'], replacements)
        if mapped is not None:
            connection.execute(
                update_scopes,
                {'id': row['id'], 'source_scopes': mapped},
            )

        snapshot = _decoded_json(row['response_snapshot'])
        if not isinstance(snapshot, dict):
            continue
        settings = snapshot.get('settings')
        if not isinstance(settings, dict):
            continue
        snapshot_scopes = _mapped_scopes(settings.get('source_scopes'), replacements)
        if snapshot_scopes is None:
            continue
        settings['source_scopes'] = snapshot_scopes
        connection.execute(update_snapshot, {
            'id': row['id'],
            'response_snapshot': snapshot,
        })


def upgrade() -> None:
    _migrate_source_scopes(_UPGRADE_SCOPE_MAP)
    _replace_mode_constraint(_APPROVED_MODES, _UPGRADE_MODE_MAP)


def downgrade() -> None:
    _migrate_source_scopes(_DOWNGRADE_SCOPE_MAP)
    _replace_mode_constraint(_PRIOR_MODES, _DOWNGRADE_MODE_MAP)
