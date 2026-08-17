"""Replace legacy member/admin roles with reader/administrator.

Downgrade cannot reconstruct the former moderator distinction; readers become
members and administrators become admins.
"""

from alembic import context, op
import sqlalchemy as sa


revision = '0015_administrator_role'
down_revision = '0014_research_library_core'
branch_labels = None
depends_on = None

def _validate_roles(bind) -> None:
    if context.is_offline_mode():
        op.execute(sa.text("""
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM users WHERE role IS NOT NULL AND role NOT IN
    ('member','admin','moderator','reader','administrator')) THEN
    RAISE EXCEPTION 'Unsupported user roles remain before administrator migration';
  END IF;
END $$
"""))
        return
    rows = bind.execute(sa.text(
        "SELECT role, count(*) FROM users WHERE role IS NOT NULL "
        "AND role NOT IN ('member','admin','moderator','reader','administrator') "
        "GROUP BY role ORDER BY role"
    )).all()
    if rows:
        detail = ', '.join(f'{role} ({count})' for role, count in rows)
        raise RuntimeError(f'Unsupported user roles ({sum(count for _, count in rows)}): {detail}')


def upgrade() -> None:
    bind = op.get_bind()
    _validate_roles(bind)
    op.execute(sa.text("UPDATE users SET role = 'reader' WHERE role IN ('member', 'moderator')"))
    op.execute(sa.text("UPDATE users SET role = 'administrator' WHERE role = 'admin'"))
    if bind.dialect.name == 'sqlite':
        with op.batch_alter_table('users', recreate='always') as batch:
            batch.alter_column('role', existing_type=sa.String(20), nullable=False, server_default='reader')
            batch.create_check_constraint(
                'ck_users_role', "role IN ('reader', 'administrator')"
            )
    else:
        op.alter_column('users', 'role', existing_type=sa.String(20), nullable=False, server_default='reader')
        op.create_check_constraint('ck_users_role', 'users', "role IN ('reader', 'administrator')")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == 'sqlite':
        with op.batch_alter_table('users', recreate='always') as batch:
            batch.drop_constraint('ck_users_role', type_='check')
            batch.alter_column('role', existing_type=sa.String(20), nullable=False, server_default='member')
    else:
        op.drop_constraint('ck_users_role', 'users', type_='check')
        op.alter_column('users', 'role', existing_type=sa.String(20), nullable=False, server_default='member')
    op.execute(sa.text("UPDATE users SET role = 'member' WHERE role = 'reader'"))
    op.execute(sa.text("UPDATE users SET role = 'admin' WHERE role = 'administrator'"))
