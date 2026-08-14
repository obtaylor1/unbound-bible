from __future__ import annotations

import uuid
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import delete, event, inspect, select
from sqlalchemy.exc import IntegrityError

from app.application import create_application
from app.auth.service import AuthService
from app.research.models import (
    MAX_TRAIL_DEPTH,
    ResearchNode,
    ResearchTrailError,
    build_trail_snapshot,
    create_research_node,
    get_owned_research_node,
)
from app.research.schemas import ResearchQueryRequest
from app.studies.models import StudySession


def _register(session, settings, *, email: str, username: str):
    user, _access, _refresh = AuthService(session, settings).register(
        email,
        username,
        'correct-horse-battery-staple',
    )
    return user


def _request(
    question: str,
    *,
    session_id: uuid.UUID | None = None,
    parent_node_id: uuid.UUID | None = None,
) -> ResearchQueryRequest:
    return ResearchQueryRequest(
        question=question,
        session_id=session_id,
        parent_node_id=parent_node_id,
        mode='what-happened-between',
        source_scopes=['biblical-canon', 'historical-sources'],
        depth='deep-research',
    )


def _snapshot(question: str) -> dict[str, object]:
    return {
        'query': question,
        'settings': {
            'source_scopes': ['biblical-canon', 'historical-sources'],
            'depth': 'deep-research',
            'mode_parameters': {'from': 'Eden', 'to': 'Abel'},
        },
        'summary': {
            'title': 'A grounded summary',
            'claims': [
                {
                    'id': 'claim-1',
                    'statement': 'The snapshot is presentation history.',
                    'classification': 'ai-synthesis',
                    'confidence': 'medium',
                    'source_ids': ['genesis-4'],
                }
            ],
        },
        'sources': [
            {
                'id': 'genesis-4',
                'title': 'Genesis',
                'reference': 'Genesis 4:1',
                'source_type': 'canonical-scripture',
            }
        ],
    }


def test_application_metadata_registers_exact_research_node_schema(test_settings):
    application = create_application(test_settings)
    inspector = inspect(application.state.database_engine)

    columns = {column['name']: column for column in inspector.get_columns('research_nodes')}
    assert set(columns) == {
        'id',
        'owner_id',
        'study_id',
        'parent_id',
        'question',
        'mode',
        'source_scopes',
        'depth',
        'response_snapshot',
        'created_at',
        'updated_at',
    }
    assert columns['owner_id']['nullable'] is False
    assert columns['study_id']['nullable'] is True
    assert columns['parent_id']['nullable'] is True
    assert columns['question']['nullable'] is False
    assert columns['source_scopes']['nullable'] is False
    assert columns['response_snapshot']['nullable'] is False

    foreign_keys = {
        tuple(foreign_key['constrained_columns']): foreign_key
        for foreign_key in inspector.get_foreign_keys('research_nodes')
    }
    assert foreign_keys[('owner_id',)]['referred_table'] == 'users'
    assert foreign_keys[('owner_id',)]['options']['ondelete'] == 'CASCADE'
    assert foreign_keys[('study_id',)]['referred_table'] == 'study_sessions'
    assert foreign_keys[('study_id',)]['options']['ondelete'] == 'SET NULL'
    assert foreign_keys[('parent_id',)]['referred_table'] == 'research_nodes'
    assert foreign_keys[('parent_id',)]['options']['ondelete'] == 'CASCADE'

    indexes = {index['name']: index for index in inspector.get_indexes('research_nodes')}
    assert indexes['ix_research_nodes_owner_updated']['column_names'] == [
        'owner_id',
        'updated_at',
    ]
    assert indexes['ix_research_nodes_parent_id']['column_names'] == ['parent_id']
    assert {constraint['name'] for constraint in inspector.get_check_constraints('research_nodes')} == {
        'ck_research_nodes_depth',
        'ck_research_nodes_mode',
        'ck_research_nodes_question_length',
    }


def test_authenticated_owner_creates_root_and_same_study_child_with_json_roundtrip(
    test_settings,
):
    application = create_application(test_settings)
    snapshot = _snapshot('What happened between Eden and Abel?')
    original_snapshot = deepcopy(snapshot)

    with application.state.session_factory() as session:
        owner = _register(
            session,
            test_settings,
            email='owner@example.com',
            username='owner',
        )
        study = StudySession(owner_id=owner.id, title='Genesis research')
        session.add(study)
        session.flush()

        root = create_research_node(
            session,
            owner.id,
            _request(snapshot['query'], session_id=study.id),
            snapshot,
        )
        child_snapshot = _snapshot('How does the genealogy continue?')
        child = create_research_node(
            session,
            owner.id,
            _request(
                child_snapshot['query'],
                session_id=study.id,
                parent_node_id=root.id,
            ),
            child_snapshot,
            parent=root,
        )
        session.commit()
        session.expire_all()

        stored_root = session.get(ResearchNode, root.id)
        stored_child = session.get(ResearchNode, child.id)

        assert stored_root is not None
        assert stored_root.response_snapshot == original_snapshot
        assert stored_root.source_scopes == ['biblical-canon', 'historical-sources']
        assert stored_root.mode == 'what-happened-between'
        assert stored_root.depth == 'deep-research'
        assert stored_child is not None
        assert stored_child.owner_id == owner.id
        assert stored_child.study_id == study.id
        assert stored_child.parent_id == root.id
        assert snapshot == original_snapshot


def test_owned_lookup_hides_another_users_node(test_settings):
    application = create_application(test_settings)
    with application.state.session_factory() as session:
        owner = _register(
            session,
            test_settings,
            email='owner@example.com',
            username='owner',
        )
        stranger = _register(
            session,
            test_settings,
            email='stranger@example.com',
            username='stranger',
        )
        node = create_research_node(
            session,
            owner.id,
            _request('Who was Abel?'),
            _snapshot('Who was Abel?'),
        )
        session.commit()

        assert get_owned_research_node(session, node.id, owner.id).id == node.id
        assert get_owned_research_node(session, node.id, stranger.id) is None


def test_create_rejects_parent_or_study_owned_by_another_user_before_insert(
    test_settings,
):
    application = create_application(test_settings)
    with application.state.session_factory() as session:
        owner = _register(
            session,
            test_settings,
            email='owner@example.com',
            username='owner',
        )
        stranger = _register(
            session,
            test_settings,
            email='stranger@example.com',
            username='stranger',
        )
        foreign_study = StudySession(owner_id=stranger.id, title='Private')
        session.add(foreign_study)
        session.flush()
        foreign_parent = create_research_node(
            session,
            stranger.id,
            _request('Private root', session_id=foreign_study.id),
            _snapshot('Private root'),
        )
        session.flush()

        with pytest.raises(ValueError, match='parent'):
            create_research_node(
                session,
                owner.id,
                _request('Cross-owner child', parent_node_id=foreign_parent.id),
                _snapshot('Cross-owner child'),
                parent=foreign_parent,
            )
        with pytest.raises(ValueError, match='study'):
            create_research_node(
                session,
                owner.id,
                _request('Cross-owner study', session_id=foreign_study.id),
                _snapshot('Cross-owner study'),
            )

        assert session.scalar(
            select(ResearchNode).where(ResearchNode.question == 'Cross-owner child')
        ) is None


def test_create_re_resolves_detached_parent_under_requesting_owner(test_settings):
    application = create_application(test_settings)
    with application.state.session_factory() as session:
        owner = _register(
            session,
            test_settings,
            email='owner@example.com',
            username='owner',
        )
        stranger = _register(
            session,
            test_settings,
            email='stranger@example.com',
            username='stranger',
        )
        real_parent = create_research_node(
            session,
            owner.id,
            _request('Owner-only root'),
            _snapshot('Owner-only root'),
        )
        session.commit()
        spoofed_parent = ResearchNode(id=real_parent.id, owner_id=stranger.id)

        with pytest.raises(ResearchTrailError) as error:
            create_research_node(
                session,
                stranger.id,
                _request('Spoofed child', parent_node_id=real_parent.id),
                _snapshot('Spoofed child'),
                parent=spoofed_parent,
            )

        assert error.value.code == 'parent_not_found'
        assert session.scalar(
            select(ResearchNode).where(ResearchNode.question == 'Spoofed child')
        ) is None


def test_create_rejects_stale_deleted_parent_before_insert(test_settings):
    application = create_application(test_settings)
    with application.state.session_factory() as session:
        owner = _register(
            session,
            test_settings,
            email='owner@example.com',
            username='owner',
        )
        parent = create_research_node(
            session,
            owner.id,
            _request('Soon deleted'),
            _snapshot('Soon deleted'),
        )
        session.commit()
        parent_id = parent.id
        session.expunge(parent)
        session.execute(delete(ResearchNode).where(ResearchNode.id == parent_id))
        session.commit()

        with pytest.raises(ResearchTrailError) as error:
            create_research_node(
                session,
                owner.id,
                _request('Stale child', parent_node_id=parent_id),
                _snapshot('Stale child'),
                parent=parent,
            )

        assert error.value.code == 'parent_not_found'
        assert session.scalar(
            select(ResearchNode).where(ResearchNode.question == 'Stale child')
        ) is None


def test_parent_study_mismatch_is_rejected(test_settings):
    application = create_application(test_settings)
    with application.state.session_factory() as session:
        owner = _register(
            session,
            test_settings,
            email='owner@example.com',
            username='owner',
        )
        studies = [
            StudySession(owner_id=owner.id, title='First'),
            StudySession(owner_id=owner.id, title='Second'),
        ]
        session.add_all(studies)
        session.flush()
        parent = create_research_node(
            session,
            owner.id,
            _request('Root', session_id=studies[0].id),
            _snapshot('Root'),
        )
        session.flush()

        with pytest.raises(ValueError, match='same study'):
            create_research_node(
                session,
                owner.id,
                _request(
                    'Child',
                    session_id=studies[1].id,
                    parent_node_id=parent.id,
                ),
                _snapshot('Child'),
                parent=parent,
            )


def test_foreign_key_delete_actions_are_enforced(test_settings):
    application = create_application(test_settings)
    with application.state.session_factory() as session:
        owner = _register(
            session,
            test_settings,
            email='owner@example.com',
            username='owner',
        )
        study = StudySession(owner_id=owner.id, title='Trail study')
        session.add(study)
        session.flush()
        root = create_research_node(
            session,
            owner.id,
            _request('Root', session_id=study.id),
            _snapshot('Root'),
        )
        child = create_research_node(
            session,
            owner.id,
            _request('Child', session_id=study.id, parent_node_id=root.id),
            _snapshot('Child'),
            parent=root,
        )
        session.commit()
        root_id, child_id, study_id, owner_id = root.id, child.id, study.id, owner.id

        session.execute(delete(ResearchNode).where(ResearchNode.id == root_id))
        session.commit()
        session.expire_all()
        assert session.get(ResearchNode, child_id) is None

        linked = create_research_node(
            session,
            owner_id,
            _request('Linked', session_id=study_id),
            _snapshot('Linked'),
        )
        session.commit()
        session.execute(delete(StudySession).where(StudySession.id == study_id))
        session.commit()
        session.refresh(linked)
        assert linked.study_id is None

        linked_id = linked.id
        session.execute(delete(type(owner)).where(type(owner).id == owner_id))
        session.commit()
        session.expire_all()
        assert session.get(ResearchNode, linked_id) is None


def test_trail_snapshot_is_deterministic_and_cycle_safe(test_settings):
    application = create_application(test_settings)
    with application.state.session_factory() as session:
        owner = _register(
            session,
            test_settings,
            email='owner@example.com',
            username='owner',
        )
        root = create_research_node(
            session, owner.id, _request('Root'), _snapshot('Root')
        )
        session.flush()
        current = create_research_node(
            session,
            owner.id,
            _request('Current', parent_node_id=root.id),
            _snapshot('Current'),
            parent=root,
        )
        session.flush()
        children = [
            create_research_node(
                session,
                owner.id,
                _request(question, parent_node_id=current.id),
                _snapshot(question),
                parent=current,
            )
            for question in ('Zulu branch', 'Alpha branch')
        ]
        session.flush()
        fixed_time = datetime(2026, 8, 12, tzinfo=UTC)
        root.updated_at = fixed_time - timedelta(days=1)
        current.updated_at = fixed_time
        for child in children:
            child.updated_at = fixed_time
        session.commit()

        trail = build_trail_snapshot(session, current.id, owner.id)
        assert [node['question'] for node in trail['ancestry']] == ['Root', 'Current']
        assert [node['question'] for node in trail['children']] == [
            child.question for child in sorted(children, key=lambda item: str(item.id))
        ]

        root.parent_id = current.id
        session.commit()
        cyclic = build_trail_snapshot(session, current.id, owner.id)
        assert [node['id'] for node in cyclic['ancestry']] == [
            str(root.id),
            str(current.id),
        ]


def test_trail_snapshot_limits_children_in_database_and_reports_truncation(
    test_settings,
):
    application = create_application(test_settings)
    with application.state.session_factory() as session:
        owner = _register(
            session,
            test_settings,
            email='owner@example.com',
            username='owner',
        )
        root = create_research_node(
            session, owner.id, _request('Root'), _snapshot('Root')
        )
        session.flush()
        session.add_all(
            ResearchNode(
                owner_id=owner.id,
                parent_id=root.id,
                question=f'Child {index:03}',
                mode='research-question',
                source_scopes=['biblical-canon'],
                depth='quick',
                response_snapshot=_snapshot(f'Child {index:03}'),
            )
            for index in range(MAX_TRAIL_DEPTH + 2)
        )
        session.commit()

        child_selects = []

        def capture_child_select(_conn, _cursor, statement, parameters, *_args):
            if 'research_nodes.parent_id =' in statement and 'ORDER BY' in statement:
                child_selects.append((statement, parameters))

        event.listen(
            application.state.database_engine,
            'before_cursor_execute',
            capture_child_select,
        )
        try:
            trail = build_trail_snapshot(session, root.id, owner.id)
        finally:
            event.remove(
                application.state.database_engine,
                'before_cursor_execute',
                capture_child_select,
            )

        assert len(trail['children']) == MAX_TRAIL_DEPTH
        assert trail['children_truncated'] is True
        assert len(child_selects) == 1
        assert 'LIMIT' in child_selects[0][0].upper()


def test_trail_snapshot_rejects_overlong_ancestry_with_bounded_queries(test_settings):
    application = create_application(test_settings)
    with application.state.session_factory() as session:
        owner = _register(
            session,
            test_settings,
            email='owner@example.com',
            username='owner',
        )
        node_ids = [uuid.uuid4() for _ in range(MAX_TRAIL_DEPTH + 1)]
        session.add_all(
            ResearchNode(
                id=node_id,
                owner_id=owner.id,
                parent_id=node_ids[index - 1] if index else None,
                question=f'Node {index}',
                mode='research-question',
                source_scopes=['biblical-canon'],
                depth='quick',
                response_snapshot=_snapshot(f'Node {index}'),
            )
            for index, node_id in enumerate(node_ids)
        )
        session.commit()
        session.expire_all()

        research_selects = 0

        def count_research_selects(_conn, _cursor, statement, *_args):
            nonlocal research_selects
            if (
                statement.lstrip().upper().startswith('SELECT')
                and 'research_nodes' in statement
            ):
                research_selects += 1

        event.listen(
            application.state.database_engine,
            'before_cursor_execute',
            count_research_selects,
        )
        try:
            with pytest.raises(ResearchTrailError) as error:
                build_trail_snapshot(session, node_ids[-1], owner.id)
        finally:
            event.remove(
                application.state.database_engine,
                'before_cursor_execute',
                count_research_selects,
            )

        assert error.value.code == 'trail_too_deep'
        assert research_selects <= MAX_TRAIL_DEPTH


def test_database_constraints_reject_invalid_values(test_settings):
    application = create_application(test_settings)
    with application.state.session_factory() as session:
        owner = _register(
            session,
            test_settings,
            email='owner@example.com',
            username='owner',
        )
        session.add(
            ResearchNode(
                owner_id=owner.id,
                question='x' * 10_001,
                mode='invalid',
                source_scopes=[],
                depth='invalid',
                response_snapshot={},
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()


def _alembic_config(database_url: str) -> Config:
    backend_root = Path(__file__).resolve().parents[2]
    config = Config(str(backend_root / 'alembic.ini'))
    config.set_main_option('script_location', str(backend_root / 'alembic'))
    config.set_main_option('sqlalchemy.url', database_url)
    return config


def test_research_trail_migration_upgrade_downgrade_upgrade_cycle(
    tmp_path,
    monkeypatch,
):
    monkeypatch.delenv('DATABASE_URL', raising=False)
    database_url = f"sqlite:///{tmp_path / 'trail-migration.db'}"
    config = _alembic_config(database_url)

    command.upgrade(config, 'head')
    from sqlalchemy import create_engine

    application_engine = create_engine(database_url)
    assert 'research_nodes' in inspect(application_engine).get_table_names()

    command.downgrade(config, '0010_merge_platform_composite')
    assert 'research_nodes' not in inspect(application_engine).get_table_names()

    command.upgrade(config, 'head')
    assert 'research_nodes' in inspect(application_engine).get_table_names()
    application_engine.dispose()
