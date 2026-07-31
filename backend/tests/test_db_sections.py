"""Tests for new database features: clone, proxy groups/members, proxy providers."""

from __future__ import annotations

from backend import database as db


# ── clone_profile ────────────────────────────────────────────────────────────


def test_clone_profile_creates_copy_with_new_seed(tmp_db):
    src = db.create_profile(name="Original", fingerprint_seed=42,
                            tags=[{"tag": "work", "color": "#ff0000"}])
    cloned = db.clone_profile(src["id"])
    assert cloned is not None
    assert cloned["id"] != src["id"]
    assert cloned["name"] == "Original (copy)"
    assert cloned["fingerprint_seed"] != 42  # new random device identity
    assert 10000 <= cloned["fingerprint_seed"] <= 99999
    assert not cloned["is_template"]  # DB stores bools as 0/1
    assert [t["tag"] for t in cloned["tags"]] == ["work"]


def test_clone_profile_custom_name(tmp_db):
    src = db.create_profile(name="Original", fingerprint_seed=1)
    cloned = db.clone_profile(src["id"], new_name="Cloned")
    assert cloned["name"] == "Cloned (copy)"


def test_clone_profile_missing_returns_none(tmp_db):
    assert db.clone_profile("nonexistent") is None


def test_clone_profile_copies_proxy_links(tmp_db):
    cred = db.create_proxy_credential(name="c", host="h", port=1080, username="u", password="p")
    src = db.create_profile(name="Orig", fingerprint_seed=1, proxy_credential_id=cred["id"])
    cloned = db.clone_profile(src["id"])
    assert cloned["proxy_credential_id"] == cred["id"]
    assert cloned["proxy_assignment"] is None  # not copied


# ── proxy groups + members ───────────────────────────────────────────────────


def _cred(name: str) -> str:
    return db.create_proxy_credential(name=name, host=f"{name}.example", port=1080)["id"]


def test_proxy_group_crud(tmp_db):
    g = db.create_proxy_group(name="g1", rotation_mode="round_robin")
    assert g["name"] == "g1"
    assert db.get_proxy_group(g["id"])["rotation_mode"] == "round_robin"
    assert len(db.list_proxy_groups()) == 1
    updated = db.update_proxy_group(g["id"], rotation_mode="random")
    assert updated["rotation_mode"] == "random"
    assert db.delete_proxy_group(g["id"]) is True
    assert db.get_proxy_group(g["id"]) is None


def test_proxy_group_members(tmp_db):
    g = db.create_proxy_group(name="g")
    a, b = _cred("a"), _cred("b")
    db.add_group_member(g["id"], a)
    db.add_group_member(g["id"], b)
    assert db.list_group_member_ids(g["id"]) == [a, b]
    # Replace ordering
    db.set_group_members(g["id"], [b, a])
    assert db.list_group_member_ids(g["id"]) == [b, a]
    assert db.remove_group_member(g["id"], a) is True
    assert db.list_group_member_ids(g["id"]) == [b]
    assert db.remove_group_member(g["id"], a) is False  # already gone


def test_round_robin_index_cycles(tmp_db):
    g = db.create_proxy_group(name="g", rotation_mode="round_robin")
    a, b = _cred("a"), _cred("b")
    db.set_group_members(g["id"], [a, b])
    idx1, n1 = db.next_round_robin_index(g["id"])
    idx2, n2 = db.next_round_robin_index(g["id"])
    idx3, n3 = db.next_round_robin_index(g["id"])
    assert (n1, n2, n3) == (2, 2, 2)
    assert (idx1, idx2, idx3) == (0, 1, 0)  # 0 -> 1 -> wraps to 0


def test_round_robin_index_empty_group(tmp_db):
    g = db.create_proxy_group(name="g")
    assert db.next_round_robin_index(g["id"]) == (-1, 0)


def test_count_profiles_using_group(tmp_db):
    g = db.create_proxy_group(name="g")
    assert db.count_profiles_using_group(g["id"]) == 0
    db.create_profile(name="p", proxy_group_id=g["id"])
    assert db.count_profiles_using_group(g["id"]) == 1


def test_remove_credential_from_groups(tmp_db):
    g = db.create_proxy_group(name="g")
    a = _cred("a")
    db.add_group_member(g["id"], a)
    assert db.remove_credential_from_groups(a) == 1
    assert db.list_group_member_ids(g["id"]) == []


# ── proxy providers ──────────────────────────────────────────────────────────


def test_proxy_provider_crud(tmp_db):
    p = db.create_proxy_provider(name="ipvanish", type="ipvanish", scheme="socks5",
                                 port=1080, username="u", password="p", options={"k": "v"})
    assert p["type"] == "ipvanish"
    assert db.get_proxy_provider(p["id"])["options"] == {"k": "v"}  # JSON parsed
    assert len(db.list_proxy_providers()) == 1
    updated = db.update_proxy_provider(p["id"], name="IPV", options={"x": 1})
    assert updated["name"] == "IPV"
    assert updated["options"] == {"x": 1}
    assert db.delete_proxy_provider(p["id"]) is True
    assert db.get_proxy_provider(p["id"]) is None


def test_count_credentials_using_provider(tmp_db):
    p = db.create_proxy_provider(name="ipvanish", type="ipvanish", port=1080,
                                 username="u", password="p")
    assert db.count_credentials_using_provider(p["id"]) == 0
    db.create_proxy_credential(name="nyc", provider_id=p["id"], provider_location="us-nyc")
    assert db.count_credentials_using_provider(p["id"]) == 1


def test_build_proxy_url_via_provider(tmp_db):
    p = db.create_proxy_provider(name="ipvanish", type="ipvanish", scheme="socks5",
                                 port=1080, username="u", password="p")
    cred = db.create_proxy_credential(name="nyc", scheme="socks5", host="", port=1080,
                                      username="", password="",
                                      provider_id=p["id"], provider_location="us-nyc")
    from backend import proxy_health
    assert proxy_health.build_proxy_url(cred) == "socks5://u:p@nyc.socks.ipvanish.com:1080"
