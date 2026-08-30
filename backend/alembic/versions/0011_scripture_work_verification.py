"""Add work-level scripture source verification evidence."""

from collections.abc import Iterator
from contextlib import contextmanager

from alembic import op
import sqlalchemy as sa


revision = '0011_scripture_work_verification'
down_revision = '0010_merge_platform_composite'
branch_labels = None
depends_on = None


_NEW_STATUSES = (
    'in_progress',
    'verified_exact',
    'verified_formatting',
    'verified_rebuilt',
    'review_required',
)
_OLD_STATUSES = ('provisional', 'verified')
_COUNT_COLUMNS = (
    'comparison_exact',
    'comparison_formatting',
    'comparison_missing',
    'comparison_extra',
    'comparison_wording',
)


@contextmanager
def _sqlite_foreign_keys_disabled() -> Iterator[None]:
    connection = op.get_bind()
    migration_context = op.get_context()
    foreign_keys_enabled = False
    if connection.dialect.name == 'sqlite':
        foreign_keys_enabled = bool(
            connection.exec_driver_sql('PRAGMA foreign_keys').scalar()
        )
        if foreign_keys_enabled:
            with migration_context.autocommit_block():
                op.get_bind().exec_driver_sql('PRAGMA foreign_keys=OFF')
    try:
        yield
    finally:
        if foreign_keys_enabled:
            with migration_context.autocommit_block():
                op.get_bind().exec_driver_sql('PRAGMA foreign_keys=ON')


def _status_check(statuses: tuple[str, ...]) -> str:
    allowed = ', '.join(repr(status) for status in statuses)
    return f'verification_status IN ({allowed})'


def _drop_status_check() -> None:
    with op.batch_alter_table('edition_work_sources') as batch_op:
        batch_op.drop_constraint(
            'ck_edition_work_sources_verification_status',
            type_='check',
        )


def upgrade() -> None:
    with _sqlite_foreign_keys_disabled():
        _drop_status_check()
        op.execute(sa.text("""
            UPDATE edition_work_sources
            SET verification_status = CASE verification_status
                WHEN 'provisional' THEN 'in_progress'
                WHEN 'verified' THEN 'verified_exact'
            END
        """))
        with op.batch_alter_table('edition_work_sources') as batch_op:
            batch_op.alter_column(
                'verification_status',
                existing_type=sa.String(length=16),
                type_=sa.String(length=32),
                existing_nullable=False,
            )
            batch_op.add_column(sa.Column('source_edition', sa.String(length=200)))
            batch_op.add_column(sa.Column('source_revision', sa.String(length=200)))
            batch_op.add_column(sa.Column('rights_url', sa.String(length=2048)))
            batch_op.add_column(sa.Column('rights_jurisdiction', sa.String(length=100)))
            batch_op.add_column(sa.Column('artifact_filename', sa.String(length=512)))
            batch_op.add_column(sa.Column(
                'artifact_retrieved_at', sa.DateTime(timezone=True)
            ))
            batch_op.add_column(sa.Column('artifact_size', sa.Integer()))
            batch_op.add_column(sa.Column('artifact_sha256', sa.String(length=64)))
            batch_op.add_column(sa.Column('parser_version', sa.String(length=64)))
            batch_op.add_column(sa.Column(
                'transformations',
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'[]'"),
            ))
            for column_name in _COUNT_COLUMNS:
                batch_op.add_column(sa.Column(
                    column_name,
                    sa.Integer(),
                    nullable=False,
                    server_default=sa.text('0'),
                ))
            batch_op.add_column(sa.Column(
                'comparison_report_sha256', sa.String(length=64)
            ))
            batch_op.add_column(sa.Column('reviewer', sa.String(length=200)))
            batch_op.add_column(sa.Column('reviewed_at', sa.DateTime(timezone=True)))
            batch_op.add_column(sa.Column('review_note', sa.Text()))
            batch_op.create_check_constraint(
                'ck_edition_work_sources_verification_status',
                _status_check(_NEW_STATUSES),
            )
            for column_name in _COUNT_COLUMNS:
                batch_op.create_check_constraint(
                    f'ck_edition_work_sources_{column_name}_nonnegative',
                    f'{column_name} >= 0',
                )
            batch_op.create_check_constraint(
                'ck_edition_work_sources_artifact_size_nonnegative',
                'artifact_size IS NULL OR artifact_size >= 0',
            )
            batch_op.create_check_constraint(
                'ck_edition_work_sources_artifact_sha256_length',
                'artifact_sha256 IS NULL OR length(artifact_sha256) = 64',
            )
            batch_op.create_check_constraint(
                'ck_edition_work_sources_comparison_report_sha256_length',
                'comparison_report_sha256 IS NULL OR '
                'length(comparison_report_sha256) = 64',
            )


def downgrade() -> None:
    with _sqlite_foreign_keys_disabled():
        _drop_status_check()
        op.execute(sa.text("""
            UPDATE edition_work_sources
            SET verification_status = CASE
                WHEN verification_status IN (
                    'verified_exact', 'verified_formatting', 'verified_rebuilt'
                ) THEN 'verified'
                WHEN verification_status IN (
                    'in_progress', 'review_required'
                ) THEN 'provisional'
            END
        """))
        with op.batch_alter_table('edition_work_sources') as batch_op:
            for column_name in _COUNT_COLUMNS:
                batch_op.drop_constraint(
                    f'ck_edition_work_sources_{column_name}_nonnegative',
                    type_='check',
                )
            batch_op.drop_constraint(
                'ck_edition_work_sources_artifact_size_nonnegative',
                type_='check',
            )
            batch_op.drop_constraint(
                'ck_edition_work_sources_artifact_sha256_length',
                type_='check',
            )
            batch_op.drop_constraint(
                'ck_edition_work_sources_comparison_report_sha256_length',
                type_='check',
            )
            for column_name in (
                'review_note',
                'reviewed_at',
                'reviewer',
                'comparison_report_sha256',
                *_COUNT_COLUMNS,
                'transformations',
                'parser_version',
                'artifact_sha256',
                'artifact_size',
                'artifact_retrieved_at',
                'artifact_filename',
                'rights_jurisdiction',
                'rights_url',
                'source_revision',
                'source_edition',
            ):
                batch_op.drop_column(column_name)
            batch_op.alter_column(
                'verification_status',
                existing_type=sa.String(length=32),
                type_=sa.String(length=16),
                existing_nullable=False,
            )
            batch_op.create_check_constraint(
                'ck_edition_work_sources_verification_status',
                _status_check(_OLD_STATUSES),
            )
