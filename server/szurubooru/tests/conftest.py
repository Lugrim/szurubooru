import contextlib
import os
import random
import string
from datetime import datetime
from unittest.mock import patch

import freezegun
import pytest
import sqlalchemy as sa
import sqlalchemy.orm as sa_orm
import testing.postgresql
from sqlalchemy import event

from szurubooru import config, db, model, rest

_PG_ARGS = (
    "-c TimeZone=UTC "
    "-c fsync=off "
    "-c synchronous_commit=off "
    "-c full_page_writes=off "
)


@pytest.fixture(scope="session")
def _pg_server():
    with testing.postgresql.Postgresql(postgres_args=_PG_ARGS) as pg:
        yield pg


@pytest.fixture(scope="session")
def _pg_engine(_pg_server):
    engine = sa.create_engine(_pg_server.url())
    yield engine
    engine.dispose()


class _TransactedTestDB:
    """Test DB fixture that rolls back the entire transaction on reset_db().

    DDL (CREATE TABLE) and DML both live inside an outer connection-level
    transaction.  session.commit() only releases a SAVEPOINT; the outer
    transaction is never committed, so trans.rollback() undoes everything.
    """

    def __init__(self, connection, session, transaction):
        self._connection = connection
        self._transaction = transaction
        self.session = session

    def create_table(self, *tables):
        for table in tables:
            table.create(bind=self._connection, checkfirst=True)

    def reset_db(self):
        self.session.close()
        if self._transaction.is_active:
            self._transaction.rollback()


class _CommittingTestDB:
    """Test DB fixture for tests that need real commits.

    reset_db() drops and recreates the public schema.
    """

    def __init__(self, session, engine):
        self.session = session
        self._engine = engine

    def create_table(self, *tables):
        with self._engine.begin() as conn:
            for table in tables:
                table.create(bind=conn, checkfirst=True)

    def reset_db(self):
        self.session.close()
        with self._engine.connect() as conn:
            conn.execute(sa.text("DROP SCHEMA public CASCADE"))
            conn.execute(sa.text("CREATE SCHEMA public"))
            conn.commit()


@pytest.fixture
def transacted_postgresql_db(_pg_engine):
    """Override pytest_pgsql's fixture with an SA 2.0-compatible version."""
    conn = _pg_engine.connect()
    trans = conn.begin()
    # bind= is deprecated in SA 2.0 but still functional; removed in SA 3.0
    session = sa_orm.Session(bind=conn)  # noqa: SA-legacy
    # A savepoint makes session.commit() release the savepoint rather than
    # committing the outer connection-level transaction.
    session.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def _restart_savepoint(session, transaction):
        if transaction.nested and not transaction._parent.nested:
            session.begin_nested()

    try:
        yield _TransactedTestDB(conn, session, trans)
    finally:
        session.close()
        if trans.is_active:
            trans.rollback()
        conn.close()


@pytest.fixture
def postgresql_db(_pg_engine):
    """Override pytest_pgsql's fixture with an SA 2.0-compatible version."""
    session = sa_orm.Session(_pg_engine)
    try:
        yield _CommittingTestDB(session, _pg_engine)
    finally:
        session.close()
        with _pg_engine.connect() as conn:
            conn.execute(sa.text("DROP SCHEMA public CASCADE"))
            conn.execute(sa.text("CREATE SCHEMA public"))
            conn.commit()


def get_unique_name():
    alphabet = string.ascii_letters + string.digits
    return "".join(random.choice(alphabet) for _ in range(8))


@pytest.fixture
def fake_datetime():
    @contextlib.contextmanager
    def injector(now):
        freezer = freezegun.freeze_time(now)
        freezer.start()
        yield
        freezer.stop()

    return injector


@pytest.fixture(scope="session")
def query_logger(pytestconfig):
    if pytestconfig.option.verbose > 0:
        import logging

        import coloredlogs

        coloredlogs.install(
            fmt="[%(asctime)-15s] %(name)s %(message)s", isatty=True
        )
        logging.basicConfig()
        logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)


@pytest.fixture(scope="function", autouse=True)
def session(query_logger, transacted_postgresql_db):
    db.session = transacted_postgresql_db.session
    transacted_postgresql_db.create_table(*model.Base.metadata.sorted_tables)
    try:
        yield transacted_postgresql_db.session
    finally:
        transacted_postgresql_db.reset_db()


@pytest.fixture(scope="function")
def nontransacted_session(query_logger, postgresql_db):
    old_db_session = db.session
    db.session = postgresql_db.session
    postgresql_db.create_table(*model.Base.metadata.sorted_tables)
    try:
        yield postgresql_db.session
    finally:
        postgresql_db.reset_db()
        db.session = old_db_session


@pytest.fixture
def context_factory(session):
    def factory(params=None, files=None, user=None, headers=None):
        ctx = rest.Context(
            env={"HTTP_ORIGIN": "http://example.com"},
            method=None,
            url=None,
            headers=headers or {},
            params=params or {},
            files=files or {},
        )
        ctx.session = session
        ctx.user = user or model.User()
        return ctx

    return factory


@pytest.fixture
def config_injector():
    def injector(new_config_content):
        config.config = new_config_content

    return injector


@pytest.fixture
def user_factory():
    def factory(
        name=None,
        rank=model.User.RANK_REGULAR,
        email="dummy",
        password_salt=None,
        password_hash=None,
    ):
        user = model.User()
        user.name = name or get_unique_name()
        user.password_salt = password_salt or "dummy"
        user.password_hash = password_hash or "dummy"
        user.email = email
        user.rank = rank
        user.creation_time = datetime(1997, 1, 1)
        user.avatar_style = model.User.AVATAR_GRAVATAR
        return user

    return factory


@pytest.fixture
def user_token_factory(user_factory):
    def factory(
        user=None,
        token=None,
        expiration_time=None,
        enabled=None,
        creation_time=None,
    ):
        if user is None:
            user = user_factory()
            db.session.add(user)
        user_token = model.UserToken()
        user_token.user = user
        user_token.token = token or "dummy"
        user_token.expiration_time = expiration_time
        user_token.enabled = enabled if enabled is not None else True
        user_token.creation_time = creation_time or datetime(1997, 1, 1)
        return user_token

    return factory


@pytest.fixture
def tag_category_factory():
    def factory(name=None, color="dummy", order=1, default=False):
        category = model.TagCategory()
        category.name = name or get_unique_name()
        category.color = color
        category.order = order
        category.default = default
        return category

    return factory


@pytest.fixture
def tag_factory():
    def factory(names=None, category=None):
        if not category:
            category = model.TagCategory(get_unique_name())
            db.session.add(category)
        tag = model.Tag()
        tag.names = []
        for i, name in enumerate(names or [get_unique_name()]):
            tag.names.append(model.TagName(name, i))
        tag.category = category
        tag.creation_time = datetime(1996, 1, 1)
        return tag

    return factory


@pytest.fixture
def post_factory():
    def factory(
        id=None,
        safety=model.Post.SAFETY_SAFE,
        type=model.Post.TYPE_IMAGE,
        tags=[],
        checksum="...",
    ):
        post = model.Post()
        post.post_id = id
        post.safety = safety
        post.type = type
        post.checksum = checksum
        post.flags = []
        post.mime_type = "application/octet-stream"
        post.creation_time = datetime(1996, 1, 1)
        post.tags = tags
        return post

    return factory


@pytest.fixture
def comment_factory(user_factory, post_factory):
    def factory(user=None, post=None, text="dummy", time=None):
        if not user:
            user = user_factory()
            db.session.add(user)
        if not post:
            post = post_factory()
            db.session.add(post)
        comment = model.Comment()
        comment.user = user
        comment.post = post
        comment.text = text
        comment.creation_time = time or datetime(1996, 1, 1)
        return comment

    return factory


@pytest.fixture
def post_score_factory(user_factory, post_factory):
    def factory(post=None, user=None, score=1):
        if user is None:
            user = user_factory()
        if post is None:
            post = post_factory()
        return model.PostScore(
            post=post, user=user, score=score, time=datetime(1999, 1, 1)
        )

    return factory


@pytest.fixture
def post_favorite_factory(user_factory, post_factory):
    def factory(post=None, user=None):
        if user is None:
            user = user_factory()
        if post is None:
            post = post_factory()
        return model.PostFavorite(
            post=post, user=user, time=datetime(1999, 1, 1)
        )

    return factory


@pytest.fixture
def pool_category_factory():
    def factory(name=None, color="dummy", default=False):
        category = model.PoolCategory()
        category.name = name or get_unique_name()
        category.color = color
        category.default = default
        return category

    return factory


@pytest.fixture
def pool_factory():
    def factory(
        id=None, names=None, description=None, category=None, time=None
    ):
        if not category:
            category = model.PoolCategory(get_unique_name())
            db.session.add(category)
        pool = model.Pool()
        pool.pool_id = id
        pool.names = []
        for i, name in enumerate(names or [get_unique_name()]):
            pool.names.append(model.PoolName(name, i))
        pool.description = description
        pool.category = category
        pool.creation_time = time or datetime(1996, 1, 1)
        return pool

    return factory


@pytest.fixture
def pool_post_factory(pool_factory, post_factory):
    def factory(pool=None, post=None, order=None):
        if not pool:
            pool = pool_factory()
            db.session.add(pool)
        if not post:
            post = post_factory()
            db.session.add(post)
        pool_post = model.PoolPost(post)
        pool_post.pool = pool
        pool_post.post = post
        pool_post.order = order or 0
        return pool_post

    return factory


@pytest.fixture
def read_asset():
    def get(path):
        path = os.path.join(os.path.dirname(__file__), "assets", path)
        with open(path, "rb") as handle:
            return handle.read()

    return get
