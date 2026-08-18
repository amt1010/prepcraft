from app.backend.core.ids import generate_ulid, new_id


def test_generate_ulid_is_26_characters():
    assert len(generate_ulid()) == 26


def test_generate_ulid_uses_only_crockford_base32_characters():
    allowed = set("0123456789ABCDEFGHJKMNPQRSTVWXYZ")
    assert set(generate_ulid()) <= allowed


def test_generate_ulid_sorts_lexicographically_by_timestamp():
    earlier = generate_ulid(timestamp_ms=1_700_000_000_000)
    later = generate_ulid(timestamp_ms=1_700_000_000_001)
    assert earlier < later


def test_generate_ulid_is_unique_across_calls():
    ids = {generate_ulid() for _ in range(1000)}
    assert len(ids) == 1000


def test_new_id_prefixes_with_given_prefix():
    id_ = new_id("RUN")
    assert id_.startswith("RUN-")


def test_new_id_appends_a_valid_ulid_after_the_prefix():
    id_ = new_id("PAPER")
    _, ulid_part = id_.split("-", 1)
    assert len(ulid_part) == 26
