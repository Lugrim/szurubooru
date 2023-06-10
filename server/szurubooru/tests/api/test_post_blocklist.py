from datetime import datetime
from unittest.mock import patch

import pytest

from szurubooru import api, db, errors, model
from szurubooru.func import posts


@pytest.fixture(autouse=True)
def inject_config(config_injector):
    config_injector(
        {
            "privileges": {
                "posts:list": model.User.RANK_REGULAR,
                "posts:view": model.User.RANK_REGULAR,
            },
        }
    )


def test_retrieving_blocklist(user_factory, post_factory, context_factory, tag_factory):
    tag1 = tag_factory(names=['tag1'])
    tag2 = tag_factory(names=['tag2'])
    tag3 = tag_factory(names=['tag3'])
    post1 = post_factory(id=1, tags=[tag1, tag2])
    post2 = post_factory(id=2, tags=[tag1])
    post3 = post_factory(id=3, tags=[tag2])
    post4 = post_factory(id=4, tags=[tag3])
    post5 = post_factory(id=5)
    db.session.add_all([post1, post2, post3, post4, post5])
    db.session.flush()
    # We can't check that the posts we retrieve are the ones we want
    with patch("szurubooru.func.posts.serialize_post"):
        posts.serialize_post.return_value = "serialized post"
        result = api.post_api.get_posts(
            context_factory(
                params={"query": "", "offset": 0},
                user=user_factory(rank=model.User.RANK_REGULAR, blocklist="tag1"),
            )
        )
        assert result == {
            "query": "",
            "offset": 0,
            "limit": 100,
            "total": 3,
            "results": ["serialized post", "serialized post", "serialized post"],
        }

