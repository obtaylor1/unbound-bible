"""Add per-work scripture source metadata."""

from alembic import op
import sqlalchemy as sa


revision = '0009_composite_edition_sources'
down_revision = '0008_commentary_library'
branch_labels = None
depends_on = None


_WORK_ID = 'prayer-of-manasseh'


def _replace_edition_status_check(statuses: tuple[str, ...]) -> None:
    allowed = ', '.join(repr(status) for status in statuses)
    connection = op.get_bind()
    migration_context = op.get_context()
    sqlite_foreign_keys = False
    if connection.dialect.name == 'sqlite':
        sqlite_foreign_keys = bool(
            connection.exec_driver_sql('PRAGMA foreign_keys').scalar()
        )
        if sqlite_foreign_keys:
            with migration_context.autocommit_block():
                op.get_bind().exec_driver_sql('PRAGMA foreign_keys=OFF')
    try:
        with op.batch_alter_table('text_editions') as batch_op:
            batch_op.drop_constraint(
                'ck_text_editions_verification_status',
                type_='check',
            )
            batch_op.create_check_constraint(
                'ck_text_editions_verification_status',
                f'verification_status IN ({allowed})',
            )
    finally:
        if sqlite_foreign_keys:
            with migration_context.autocommit_block():
                op.get_bind().exec_driver_sql('PRAGMA foreign_keys=ON')


def _insert_supplemental_work() -> None:
    library_works = sa.table(
        'library_works',
        sa.column('id', sa.String(length=100)),
        sa.column('title', sa.String(length=200)),
    )
    select_work = sa.select(
        sa.literal(_WORK_ID),
        sa.literal('Prayer of Manasseh'),
    ).where(
        ~sa.exists(sa.select(1).where(library_works.c.id == _WORK_ID))
    )
    op.execute(
        sa.insert(library_works).from_select(('id', 'title'), select_work)
    )


def _refuse_provisional_edition_downgrade() -> None:
    migration_context = op.get_context()
    if migration_context.as_sql:
        return
    text_editions = sa.table(
        'text_editions',
        sa.column('edition_code', sa.String(length=100)),
        sa.column('verification_status', sa.String(length=16)),
    )
    provisional_edition = op.get_bind().scalar(
        sa.select(text_editions.c.edition_code)
        .where(text_editions.c.verification_status == 'provisional')
        .limit(1)
    )
    if provisional_edition is not None:
        raise RuntimeError(
            'Cannot downgrade 0009_composite_edition_sources while text_editions '
            'contains provisional verification_status values. Change every provisional '
            'edition to queued, staged, verified, or withdrawn before downgrading.'
        )


def upgrade() -> None:
    _replace_edition_status_check(
        ('queued', 'staged', 'provisional', 'verified', 'withdrawn')
    )
    op.create_table(
        'edition_work_sources',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('edition_code', sa.String(length=100), nullable=False),
        sa.Column('work_id', sa.String(length=100), nullable=False),
        sa.Column('source_key', sa.String(length=100), nullable=False),
        sa.Column('source_label', sa.String(length=200), nullable=False),
        sa.Column('translator', sa.String(length=200), nullable=True),
        sa.Column('source_language', sa.String(length=100), nullable=False),
        sa.Column('source_tradition', sa.String(length=200), nullable=False),
        sa.Column('published_year', sa.Integer(), nullable=True),
        sa.Column('license_spdx', sa.String(length=100), nullable=False),
        sa.Column('attribution', sa.Text(), nullable=False),
        sa.Column('provenance_url', sa.String(length=2048), nullable=True),
        sa.Column('fallback', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('modified', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('modification_note', sa.Text(), nullable=True),
        sa.Column('verification_status', sa.String(length=16), nullable=False),
        sa.Column('canon_scope', sa.String(length=16), nullable=False),
        sa.CheckConstraint(
            "verification_status IN ('provisional', 'verified')",
            name='ck_edition_work_sources_verification_status',
        ),
        sa.CheckConstraint(
            "canon_scope IN ('ethio81', 'supplemental')",
            name='ck_edition_work_sources_canon_scope',
        ),
        sa.ForeignKeyConstraint(
            ['edition_code'],
            ['text_editions.edition_code'],
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['work_id'],
            ['library_works.id'],
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'edition_code',
            'work_id',
            name='uq_edition_work_sources_edition_work',
        ),
    )
    op.create_index(
        'ix_edition_work_sources_work_id',
        'edition_work_sources',
        ['work_id'],
    )
    _insert_supplemental_work()


def downgrade() -> None:
    _refuse_provisional_edition_downgrade()
    op.drop_index(
        'ix_edition_work_sources_work_id',
        table_name='edition_work_sources',
    )
    op.drop_table('edition_work_sources')
    _replace_edition_status_check(('queued', 'staged', 'verified', 'withdrawn'))
    # Keep the supplemental catalog row: upgrade may have found a pre-existing,
    # user-owned row, and this revision stores no durable migration ownership marker.
