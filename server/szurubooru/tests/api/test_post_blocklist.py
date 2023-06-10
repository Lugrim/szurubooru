from datetime import datetime
from unittest.mock import patch

import pytest

from szurubooru import api, db, errors, model
from szurubooru.func import posts


def test_blocklist(user_factory, post_factory, context_factory, config_injector, tag_factory):
    tag1 = tag_factory(names=['tag1'])
    tag2 = tag_factory(names=['tag2'])
    tag3 = tag_factory(names=['tag3'])
    post1 = post_factory(id=11, tags=[tag1, tag2])
    post2 = post_factory(id=12, tags=[tag1])
    post3 = post_factory(id=13, tags=[tag2])
    post4 = post_factory(id=14, tags=[tag3])
    post5 = post_factory(id=15)
    config_injector({
        "privileges": {
            "posts:list": model.User.RANK_REGULAR,
        }
    })
    db.session.add_all([post1, post2, post3, post4, post5])
    db.session.flush()
    # We can't check that the posts we retrieve are the ones we want
    with patch("szurubooru.func.posts.serialize_post"):
        posts.serialize_post.side_effect = (
            lambda post, *_args, **_kwargs: "serialized post %d" % post.post_id
        )
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
            "results": ["serialized post 15", "serialized post 14", "serialized post 13"],
        }

