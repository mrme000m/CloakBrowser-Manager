"""SQLite database operations for browser profiles."""

from __future__ import annotations

import datetime
import json
import random
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any

DATA_DIR = Path("/data")
DB_PATH = DATA_DIR / "profiles.db"


@contextmanager
def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS profiles (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                fingerprint_seed INTEGER NOT NULL,
                proxy TEXT,
                timezone TEXT,
                locale TEXT,
                platform TEXT DEFAULT 'windows',
                user_agent TEXT,
                screen_width INTEGER DEFAULT 1920,
                screen_height INTEGER DEFAULT 1080,
                gpu_vendor TEXT,
                gpu_renderer TEXT,
                hardware_concurrency INTEGER,
                humanize BOOLEAN DEFAULT 0,
                human_preset TEXT DEFAULT 'default',
                headless BOOLEAN DEFAULT 0,
                geoip BOOLEAN DEFAULT 0,
                clipboard_sync BOOLEAN DEFAULT 1,
                auto_launch BOOLEAN DEFAULT 0,
                color_scheme TEXT,
                notes TEXT,
                proxy_credential_id TEXT,
                is_template BOOLEAN DEFAULT 0,
                restart_on_crash BOOLEAN DEFAULT 0,
                max_restarts INTEGER DEFAULT 5,
                proxy_group_id TEXT,
                proxy_assignment TEXT,
                user_data_dir TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS profile_tags (
                profile_id TEXT REFERENCES profiles(id) ON DELETE CASCADE,
                tag TEXT NOT NULL,
                color TEXT,
                PRIMARY KEY (profile_id, tag)
            );

            CREATE TABLE IF NOT EXISTS proxy_credentials (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                scheme TEXT NOT NULL DEFAULT 'socks5',
                host TEXT NOT NULL DEFAULT '',
                port INTEGER NOT NULL DEFAULT 1080,
                username TEXT NOT NULL DEFAULT '',
                password TEXT NOT NULL DEFAULT '',
                provider_id TEXT,
                provider_location TEXT,
                last_status TEXT,
                last_exit_ip TEXT,
                last_country TEXT,
                last_checked_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS proxy_providers (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                type TEXT NOT NULL DEFAULT 'custom',
                scheme TEXT NOT NULL DEFAULT 'socks5',
                host_template TEXT,
                port INTEGER NOT NULL DEFAULT 1080,
                username TEXT NOT NULL DEFAULT '',
                password TEXT NOT NULL DEFAULT '',
                options TEXT DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS proxy_groups (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                rotation_mode TEXT NOT NULL DEFAULT 'round_robin',
                round_robin_index INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS proxy_group_members (
                group_id TEXT NOT NULL,
                credential_id TEXT NOT NULL,
                position INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (group_id, credential_id)
            );
        """)
        conn.commit()

        # Migrations for existing databases
        cols = {row[1] for row in conn.execute("PRAGMA table_info(profiles)").fetchall()}
        if "clipboard_sync" not in cols:
            conn.execute("ALTER TABLE profiles ADD COLUMN clipboard_sync BOOLEAN DEFAULT 1")
            conn.commit()
        if "launch_args" not in cols:
            conn.execute("ALTER TABLE profiles ADD COLUMN launch_args TEXT DEFAULT '[]'")
            conn.commit()
        if "auto_launch" not in cols:
            conn.execute("ALTER TABLE profiles ADD COLUMN auto_launch BOOLEAN DEFAULT 0")
            conn.commit()
        if "proxy_credential_id" not in cols:
            conn.execute("ALTER TABLE profiles ADD COLUMN proxy_credential_id TEXT")
            conn.commit()

        # Section 2/3/4 migrations
        for col, ddl in (
            ("is_template", "BOOLEAN DEFAULT 0"),
            ("restart_on_crash", "BOOLEAN DEFAULT 0"),
            ("max_restarts", "INTEGER DEFAULT 5"),
            ("proxy_group_id", "TEXT"),
            ("proxy_assignment", "TEXT"),
        ):
            if col not in cols:
                conn.execute(f"ALTER TABLE profiles ADD COLUMN {col} {ddl}")
                conn.commit()

        cred_cols = {row[1] for row in conn.execute("PRAGMA table_info(proxy_credentials)").fetchall()}
        for col, ddl in (
            ("provider_id", "TEXT"),
            ("provider_location", "TEXT"),
            ("last_status", "TEXT"),
            ("last_exit_ip", "TEXT"),
            ("last_country", "TEXT"),
            ("last_checked_at", "TEXT"),
        ):
            if col not in cred_cols:
                conn.execute(f"ALTER TABLE proxy_credentials ADD COLUMN {col} {ddl}")
                conn.commit()


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def create_profile(
    name: str,
    fingerprint_seed: int | None = None,
    **fields: Any,
) -> dict[str, Any]:
    profile_id = str(uuid.uuid4())
    seed = fingerprint_seed if fingerprint_seed is not None else random.randint(10000, 99999)
    user_data_dir = str(DATA_DIR / "profiles" / profile_id)
    now = _now()
    tags = fields.pop("tags", None) or []

    with get_db() as conn:
        conn.execute(
            """INSERT INTO profiles (
                id, name, fingerprint_seed, proxy, timezone, locale, platform,
                user_agent, screen_width, screen_height, gpu_vendor, gpu_renderer,
                hardware_concurrency, humanize, human_preset, headless, geoip,
                clipboard_sync, auto_launch, color_scheme, launch_args, notes,
                proxy_credential_id, is_template, restart_on_crash, max_restarts,
                proxy_group_id, proxy_assignment,
                user_data_dir, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                profile_id, name, seed,
                fields.get("proxy"),
                fields.get("timezone"),
                fields.get("locale"),
                fields.get("platform", "windows"),
                fields.get("user_agent"),
                fields.get("screen_width", 1920),
                fields.get("screen_height", 1080),
                fields.get("gpu_vendor"),
                fields.get("gpu_renderer"),
                fields.get("hardware_concurrency"),
                fields.get("humanize", False),
                fields.get("human_preset", "default"),
                fields.get("headless", False),
                fields.get("geoip", False),
                fields.get("clipboard_sync", True),
                fields.get("auto_launch", False),
                fields.get("color_scheme"),
                json.dumps(fields.get("launch_args") or []),
                fields.get("notes"),
                fields.get("proxy_credential_id"),
                bool(fields.get("is_template", False)),
                bool(fields.get("restart_on_crash", False)),
                int(fields.get("max_restarts", 5)),
                fields.get("proxy_group_id"),
                fields.get("proxy_assignment"),
                user_data_dir, now, now,
            ),
        )
        for t in tags:
            conn.execute(
                "INSERT INTO profile_tags (profile_id, tag, color) VALUES (?, ?, ?)",
                (profile_id, t["tag"], t.get("color")),
            )
        conn.commit()

    return get_profile(profile_id)  # type: ignore[return-value]


def get_profile(profile_id: str) -> dict[str, Any] | None:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM profiles WHERE id = ?", (profile_id,)).fetchone()
        if not row:
            return None
        profile = dict(row)
        profile["launch_args"] = json.loads(profile.get("launch_args") or "[]")
        tags = conn.execute(
            "SELECT tag, color FROM profile_tags WHERE profile_id = ?",
            (profile_id,),
        ).fetchall()
        profile["tags"] = [dict(t) for t in tags]
        return profile


def list_profiles() -> list[dict[str, Any]]:
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM profiles ORDER BY created_at DESC").fetchall()
        profiles = []
        for row in rows:
            profile = dict(row)
            profile["launch_args"] = json.loads(profile.get("launch_args") or "[]")
            tags = conn.execute(
                "SELECT tag, color FROM profile_tags WHERE profile_id = ?",
                (profile["id"],),
            ).fetchall()
            profile["tags"] = [dict(t) for t in tags]
            profiles.append(profile)
        return profiles


def update_profile(profile_id: str, **fields: Any) -> dict[str, Any] | None:
    existing = get_profile(profile_id)
    if not existing:
        return None

    tags = fields.pop("tags", None)

    # Only update fields that were explicitly provided
    update_cols = []
    update_vals = []
    # Pre-serialize launch_args to JSON before the generic update loop
    if "launch_args" in fields:
        fields["launch_args"] = json.dumps(fields["launch_args"] or [])

    for col in (
        "name", "fingerprint_seed", "proxy", "timezone", "locale", "platform",
        "user_agent", "screen_width", "screen_height", "gpu_vendor", "gpu_renderer",
        "hardware_concurrency", "humanize", "human_preset", "headless", "geoip",
        "clipboard_sync", "auto_launch", "color_scheme", "launch_args", "notes",
        "proxy_credential_id", "is_template", "restart_on_crash", "max_restarts",
        "proxy_group_id", "proxy_assignment",
    ):
        if col in fields:
            update_cols.append(f"{col} = ?")
            update_vals.append(fields[col])

    if update_cols:
        update_cols.append("updated_at = ?")
        update_vals.append(_now())
        update_vals.append(profile_id)
        with get_db() as conn:
            conn.execute(
                f"UPDATE profiles SET {', '.join(update_cols)} WHERE id = ?",
                update_vals,
            )
            conn.commit()

    if tags is not None:
        with get_db() as conn:
            conn.execute("DELETE FROM profile_tags WHERE profile_id = ?", (profile_id,))
            for t in tags:
                conn.execute(
                    "INSERT INTO profile_tags (profile_id, tag, color) VALUES (?, ?, ?)",
                    (profile_id, t["tag"], t.get("color")),
                )
            conn.commit()

    return get_profile(profile_id)


def delete_profile(profile_id: str) -> bool:
    with get_db() as conn:
        cursor = conn.execute("DELETE FROM profiles WHERE id = ?", (profile_id,))
        conn.commit()
        return cursor.rowcount > 0


# ── Proxy Credentials ─────────────────────────────────────────────────────


def create_proxy_credential(
    name: str,
    scheme: str = "socks5",
    host: str = "",
    port: int = 1080,
    username: str = "",
    password: str = "",
    provider_id: str | None = None,
    provider_location: str | None = None,
) -> dict[str, Any]:
    cred_id = str(uuid.uuid4())
    now = _now()
    with get_db() as conn:
        conn.execute(
            """INSERT INTO proxy_credentials (
                id, name, scheme, host, port, username, password,
                provider_id, provider_location,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (cred_id, name, scheme, host, port, username, password,
             provider_id, provider_location, now, now),
        )
        conn.commit()
    return get_proxy_credential(cred_id)  # type: ignore[return-value]


def get_proxy_credential(cred_id: str) -> dict[str, Any] | None:
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM proxy_credentials WHERE id = ?", (cred_id,)
        ).fetchone()
        if not row:
            return None
        return dict(row)


def list_proxy_credentials() -> list[dict[str, Any]]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM proxy_credentials ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def update_proxy_credential(cred_id: str, **fields: Any) -> dict[str, Any] | None:
    existing = get_proxy_credential(cred_id)
    if not existing:
        return None

    update_cols = []
    update_vals = []
    for col in (
        "name", "scheme", "host", "port", "username", "password",
        "provider_id", "provider_location",
        "last_status", "last_exit_ip", "last_country", "last_checked_at",
    ):
        if col in fields:
            update_cols.append(f"{col} = ?")
            update_vals.append(fields[col])

    if update_cols:
        update_cols.append("updated_at = ?")
        update_vals.append(_now())
        update_vals.append(cred_id)
        with get_db() as conn:
            conn.execute(
                f"UPDATE proxy_credentials SET {', '.join(update_cols)} WHERE id = ?",
                update_vals,
            )
            conn.commit()

    return get_proxy_credential(cred_id)


def delete_proxy_credential(cred_id: str) -> bool:
    with get_db() as conn:
        cursor = conn.execute(
            "DELETE FROM proxy_credentials WHERE id = ?", (cred_id,)
        )
        conn.commit()
        return cursor.rowcount > 0


def count_profiles_using_credential(cred_id: str) -> int:
    with get_db() as conn:
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM profiles WHERE proxy_credential_id = ?",
            (cred_id,),
        ).fetchone()
        return row["cnt"] if row else 0


def build_proxy_url_from_credential(cred: dict[str, Any]) -> str:
    """Build a full proxy URL from a proxy credential dict.

    Uses the credential's OWN fields. For provider-linked credentials (where
    host/user/pass may be empty), resolve via proxy_health.materialize_credential
    before calling this.
    """
    scheme = cred.get("scheme", "socks5")
    host = cred.get("host", "")
    port = cred.get("port", 1080)
    username = cred.get("username", "")
    password = cred.get("password", "")
    if username and password:
        return f"{scheme}://{username}:{password}@{host}:{port}"
    elif username:
        return f"{scheme}://{username}@{host}:{port}"
    return f"{scheme}://{host}:{port}"


# ── Proxy Providers ───────────────────────────────────────────────────────


def create_proxy_provider(
    name: str,
    type: str = "custom",
    scheme: str = "socks5",
    host_template: str = "",
    port: int = 1080,
    username: str = "",
    password: str = "",
    options: dict | None = None,
) -> dict[str, Any]:
    provider_id = str(uuid.uuid4())
    now = _now()
    with get_db() as conn:
        conn.execute(
            """INSERT INTO proxy_providers (
                id, name, type, scheme, host_template, port, username,
                password, options, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (provider_id, name, type, scheme, host_template, port,
             username, password, json.dumps(options or {}), now, now),
        )
        conn.commit()
    return get_proxy_provider(provider_id)  # type: ignore[return-value]


def get_proxy_provider(provider_id: str) -> dict[str, Any] | None:
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM proxy_providers WHERE id = ?", (provider_id,)
        ).fetchone()
        if not row:
            return None
        p = dict(row)
        p["options"] = json.loads(p.get("options") or "{}")
        return p


def list_proxy_providers() -> list[dict[str, Any]]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM proxy_providers ORDER BY created_at DESC"
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["options"] = json.loads(d.get("options") or "{}")
            out.append(d)
        return out


def update_proxy_provider(provider_id: str, **fields: Any) -> dict[str, Any] | None:
    if not get_proxy_provider(provider_id):
        return None
    if "options" in fields and isinstance(fields["options"], (dict, list)):
        fields["options"] = json.dumps(fields["options"])
    update_cols = []
    update_vals = []
    for col in ("name", "type", "scheme", "host_template", "port",
                "username", "password", "options"):
        if col in fields:
            update_cols.append(f"{col} = ?")
            update_vals.append(fields[col])
    if update_cols:
        update_cols.append("updated_at = ?")
        update_vals.append(_now())
        update_vals.append(provider_id)
        with get_db() as conn:
            conn.execute(
                f"UPDATE proxy_providers SET {', '.join(update_cols)} WHERE id = ?",
                update_vals,
            )
            conn.commit()
    return get_proxy_provider(provider_id)


def delete_proxy_provider(provider_id: str) -> bool:
    with get_db() as conn:
        cursor = conn.execute(
            "DELETE FROM proxy_providers WHERE id = ?", (provider_id,)
        )
        conn.commit()
        return cursor.rowcount > 0


def count_credentials_using_provider(provider_id: str) -> int:
    with get_db() as conn:
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM proxy_credentials WHERE provider_id = ?",
            (provider_id,),
        ).fetchone()
        return row["cnt"] if row else 0


# ── Proxy Groups ───────────────────────────────────────────────────────────


def create_proxy_group(name: str, rotation_mode: str = "round_robin") -> dict[str, Any]:
    group_id = str(uuid.uuid4())
    now = _now()
    with get_db() as conn:
        conn.execute(
            "INSERT INTO proxy_groups (id, name, rotation_mode, round_robin_index, "
            "created_at, updated_at) VALUES (?, ?, ?, 0, ?, ?)",
            (group_id, name, rotation_mode, now, now),
        )
        conn.commit()
    return get_proxy_group(group_id)  # type: ignore[return-value]


def get_proxy_group(group_id: str) -> dict[str, Any] | None:
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM proxy_groups WHERE id = ?", (group_id,)
        ).fetchone()
        return dict(row) if row else None


def list_proxy_groups() -> list[dict[str, Any]]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM proxy_groups ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def update_proxy_group(group_id: str, **fields: Any) -> dict[str, Any] | None:
    if not get_proxy_group(group_id):
        return None
    update_cols = []
    update_vals = []
    for col in ("name", "rotation_mode", "round_robin_index"):
        if col in fields:
            update_cols.append(f"{col} = ?")
            update_vals.append(fields[col])
    if update_cols:
        update_cols.append("updated_at = ?")
        update_vals.append(_now())
        update_vals.append(group_id)
        with get_db() as conn:
            conn.execute(
                f"UPDATE proxy_groups SET {', '.join(update_cols)} WHERE id = ?",
                update_vals,
            )
            conn.commit()
    return get_proxy_group(group_id)


def delete_proxy_group(group_id: str) -> bool:
    with get_db() as conn:
        conn.execute("DELETE FROM proxy_group_members WHERE group_id = ?", (group_id,))
        cursor = conn.execute("DELETE FROM proxy_groups WHERE id = ?", (group_id,))
        conn.commit()
        return cursor.rowcount > 0


def count_profiles_using_group(group_id: str) -> int:
    with get_db() as conn:
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM profiles WHERE proxy_group_id = ?",
            (group_id,),
        ).fetchone()
        return row["cnt"] if row else 0


# ── Proxy Group Members ────────────────────────────────────────────────────


def list_group_members(group_id: str) -> list[dict[str, Any]]:
    """Return members with a snapshot of each credential's identity fields."""
    with get_db() as conn:
        rows = conn.execute(
            """SELECT m.credential_id, m.position, c.name, c.host, c.port,
                      c.username, c.scheme, c.provider_id, c.provider_location,
                      c.last_status, c.last_exit_ip, c.last_country
               FROM proxy_group_members m
               JOIN proxy_credentials c ON c.id = m.credential_id
               WHERE m.group_id = ?
               ORDER BY m.position ASC""",
            (group_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def list_group_member_ids(group_id: str) -> list[str]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT credential_id FROM proxy_group_members "
            "WHERE group_id = ? ORDER BY position ASC",
            (group_id,),
        ).fetchall()
        return [r["credential_id"] for r in rows]


def set_group_members(group_id: str, credential_ids: list[str]) -> None:
    """Replace all members of a group with the given ordered list."""
    with get_db() as conn:
        conn.execute("DELETE FROM proxy_group_members WHERE group_id = ?", (group_id,))
        for pos, cred_id in enumerate(credential_ids):
            conn.execute(
                "INSERT OR IGNORE INTO proxy_group_members "
                "(group_id, credential_id, position) VALUES (?, ?, ?)",
                (group_id, cred_id, pos),
            )
        conn.commit()


def add_group_member(group_id: str, credential_id: str, position: int | None = None) -> None:
    with get_db() as conn:
        if position is None:
            row = conn.execute(
                "SELECT COALESCE(MAX(position), -1) + 1 AS np "
                "FROM proxy_group_members WHERE group_id = ?",
                (group_id,),
            ).fetchone()
            position = row["np"] if row else 0
        conn.execute(
            "INSERT OR IGNORE INTO proxy_group_members "
            "(group_id, credential_id, position) VALUES (?, ?, ?)",
            (group_id, credential_id, position),
        )
        conn.commit()


def remove_group_member(group_id: str, credential_id: str) -> bool:
    with get_db() as conn:
        cursor = conn.execute(
            "DELETE FROM proxy_group_members WHERE group_id = ? AND credential_id = ?",
            (group_id, credential_id),
        )
        conn.commit()
        return cursor.rowcount > 0


def remove_credential_from_groups(credential_id: str) -> int:
    """Remove a credential from every group it belongs to. Returns count removed."""
    with get_db() as conn:
        cursor = conn.execute(
            "DELETE FROM proxy_group_members WHERE credential_id = ?",
            (credential_id,),
        )
        conn.commit()
        return cursor.rowcount


def next_round_robin_index(group_id: str) -> tuple[int, int]:
    """Atomically advance and return (current_index, member_count).

    Returns (-1, 0) if the group has no members.
    """
    with get_db() as conn:
        n = conn.execute(
            "SELECT COUNT(*) AS cnt FROM proxy_group_members WHERE group_id = ?",
            (group_id,),
        ).fetchone()["cnt"]
        if n == 0:
            return (-1, 0)
        row = conn.execute(
            "SELECT round_robin_index FROM proxy_groups WHERE id = ?",
            (group_id,),
        ).fetchone()
        if not row:
            return (-1, 0)
        idx = row["round_robin_index"] % n
        conn.execute(
            "UPDATE proxy_groups SET round_robin_index = ? WHERE id = ?",
            ((idx + 1) % n, group_id),
        )
        conn.commit()
        return (idx, n)


# ── Profile Clone ───────────────────────────────────────────────────────────

_CLONE_FIELDS = (
    "platform", "user_agent", "screen_width", "screen_height", "gpu_vendor",
    "gpu_renderer", "hardware_concurrency", "humanize", "human_preset",
    "headless", "geoip", "clipboard_sync", "auto_launch", "color_scheme",
    "launch_args", "notes", "timezone", "locale",
)


def clone_profile(profile_id: str, new_name: str | None = None) -> dict[str, Any] | None:
    """Clone a profile into a new one with a fresh random fingerprint seed.

    Copies fingerprint/network/hardware/behavior fields + tags + proxy links,
    but gives the clone a new id, empty user_data_dir, a NEW random seed
    (different device identity), and is_template=False. proxy_assignment is
    not copied — the clone selects its own sticky pick on first launch.
    """
    source = get_profile(profile_id)
    if not source:
        return None
    fields: dict[str, Any] = {}
    for k in _CLONE_FIELDS:
        if k in source and source[k] is not None:
            fields[k] = source[k]
    fields["proxy"] = source.get("proxy")
    fields["proxy_credential_id"] = source.get("proxy_credential_id")
    fields["proxy_group_id"] = source.get("proxy_group_id")
    fields["restart_on_crash"] = bool(source.get("restart_on_crash", False))
    fields["max_restarts"] = int(source.get("max_restarts", 5))
    fields["is_template"] = False
    tags = source.get("tags") or []
    fields["tags"] = [{"tag": t["tag"], "color": t.get("color")} for t in tags]
    name = (new_name or source.get("name", "Profile")) + " (copy)"
    return create_profile(name=name, fingerprint_seed=None, **fields)
