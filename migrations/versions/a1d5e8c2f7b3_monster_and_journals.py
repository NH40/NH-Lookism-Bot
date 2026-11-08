"""67 MONSTER, журнал имущества с триггерами, история боёв, журнал ошибок. Существующие данные не меняются.

Revision ID: a1d5e8c2f7b3
Revises: f3c9a1d7e2b4
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a1d5e8c2f7b3"
down_revision: Union[str, None] = "f3c9a1d7e2b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Числовые колонки users: (колонка, код в журнале).
_NUMERIC = (
    ("nh_coins", "nh"), ("donate_coins", "donate"), ("tickets_count", "tickets"), ("dev_points", "dev_points"),
    ("potential_points", "potential_points"), ("path_points", "path_points"), ("path_fragments", "path_fragments"),
    ("technique_fragments", "technique_fragments"), ("genius_fragments", "genius_fragments"), ("blood_drops", "blood_drops"),
    ("skip_scrolls", "skip_scrolls"),
)
_PROFILE = (
    "phase", "country_code", "city_id", "potential", "monster_potential", "bloodline", "bloodline_level", "bloodline2", "bloodline2_level",
    "active_path", "active_path2", "active_technique", "active_genius", "path_stage", "awakening_level", "second_body", "is_banned", "admin_role",
    "stat_strength", "stat_speed", "stat_endurance", "stat_agility", "mastery_strength", "mastery_speed", "mastery_endurance", "mastery_technique",
    "business_level", "business_capacity",
)
_MERGED = "'statists','tickets','dev_points','potential_points','path_points','path_fragments','technique_fragments','genius_fragments','blood_drops','skip_scrolls','district'"

_WRITE = f"""
CREATE FUNCTION ledger_write(uid bigint, a text, it text, d bigint, bal bigint, nt text) RETURNS void AS $$
DECLARE
    src text := left(coalesce(nullif(current_setting('app.log_src', true), ''), 'system'), 64);
    rsn text := left(coalesce(current_setting('app.log_reason', true), ''), 24);
    win interval := NULL;
    last_id bigint;
BEGIN
    IF rsn IN ('income', 'emperor_tax') THEN
        win := interval '1 hour';
    ELSIF a IN ({_MERGED}) THEN
        win := interval '5 minutes';
    END IF;
    IF win IS NOT NULL THEN
        SELECT id INTO last_id FROM player_ledger
        WHERE user_id = uid AND asset = a AND item = it AND reason = rsn
          AND (source = src OR rsn IN ('income', 'emperor_tax')) AND created_at > now() - win
        ORDER BY id DESC LIMIT 1;
        IF last_id IS NOT NULL THEN
            UPDATE player_ledger SET delta = delta + d, balance = bal, hits = hits + 1 WHERE id = last_id;
            RETURN;
        END IF;
    END IF;
    INSERT INTO player_ledger (user_id, asset, item, delta, balance, note, reason, source) VALUES (uid, a, it, d, bal, left(nt, 128), rsn, src);
END;
$$ LANGUAGE plpgsql;
"""

_numeric_blocks = "\n".join(
    f"    IF NEW.{col} IS DISTINCT FROM OLD.{col} THEN PERFORM ledger_write(NEW.id, '{code}', '', (NEW.{col} - OLD.{col})::bigint, NEW.{col}::bigint, ''); END IF;"
    for col, code in _NUMERIC
)
_USERS_NUMERIC = f"""
CREATE FUNCTION ledger_users_numeric() RETURNS trigger AS $$
BEGIN
{_numeric_blocks}
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;
"""
_fields = ",".join(f"'{f}'" for f in _PROFILE)
_USERS_PROFILE = f"""
CREATE FUNCTION ledger_users_profile() RETURNS trigger AS $$
DECLARE
    f text;
    o jsonb := to_jsonb(OLD);
    n jsonb := to_jsonb(NEW);
BEGIN
    FOREACH f IN ARRAY ARRAY[{_fields}] LOOP
        IF o->f IS DISTINCT FROM n->f THEN
            PERFORM ledger_write(NEW.id, 'profile', f, 0, NULL, coalesce(o->>f, '—') || ' → ' || coalesce(n->>f, '—'));
        END IF;
    END LOOP;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;
"""
_EXTRAS = """
CREATE FUNCTION ledger_extras() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        PERFORM ledger_write(NEW.user_id, 'statists', '', NEW.quantity::bigint, NULL, '');
    ELSIF TG_OP = 'DELETE' THEN
        PERFORM ledger_write(OLD.user_id, 'statists', '', -OLD.quantity::bigint, NULL, '');
    ELSIF NEW.quantity IS DISTINCT FROM OLD.quantity THEN
        PERFORM ledger_write(NEW.user_id, 'statists', '', (NEW.quantity - OLD.quantity)::bigint, NULL, '');
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;
"""
_CARDS = """
CREATE FUNCTION ledger_cards() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        PERFORM ledger_write(NEW.user_id, 'card', NEW.card_code, NEW.quantity::bigint, NEW.quantity::bigint, '');
    ELSIF TG_OP = 'DELETE' THEN
        PERFORM ledger_write(OLD.user_id, 'card', OLD.card_code, -OLD.quantity::bigint, 0, '');
    ELSIF NEW.quantity IS DISTINCT FROM OLD.quantity THEN
        PERFORM ledger_write(NEW.user_id, 'card', NEW.card_code, (NEW.quantity - OLD.quantity)::bigint, NEW.quantity::bigint, '');
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;
"""
_DISTRICTS = """
CREATE FUNCTION ledger_districts() RETURNS trigger AS $$
BEGIN
    IF OLD.owner_id IS NOT DISTINCT FROM NEW.owner_id THEN
        RETURN NULL;
    END IF;
    IF OLD.owner_id IS NOT NULL THEN
        PERFORM ledger_write(OLD.owner_id, 'district', '', -1, NULL, '');
    END IF;
    IF NEW.owner_id IS NOT NULL THEN
        PERFORM ledger_write(NEW.owner_id, 'district', '', 1, NULL, '');
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;
"""
_BUILDINGS = """
CREATE FUNCTION ledger_buildings() RETURNS trigger AS $$
DECLARE
    b businesses;
    uid bigint;
BEGIN
    IF TG_OP = 'INSERT' THEN b := NEW; ELSE b := OLD; END IF;
    uid := b.holder_id;
    IF uid IS NULL AND b.district_id IS NOT NULL THEN
        SELECT owner_id INTO uid FROM districts WHERE id = b.district_id;
    END IF;
    IF uid IS NOT NULL THEN
        PERFORM ledger_write(uid, 'building', b.type, CASE WHEN TG_OP = 'INSERT' THEN 1 ELSE -1 END, NULL, '');
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;
"""
_TRIGGERS = (
    f"CREATE TRIGGER ledger_users_numeric AFTER UPDATE OF {', '.join(c for c, _ in _NUMERIC)} ON users FOR EACH ROW EXECUTE FUNCTION ledger_users_numeric();",
    f"CREATE TRIGGER ledger_users_profile AFTER UPDATE OF {', '.join(_PROFILE)} ON users FOR EACH ROW EXECUTE FUNCTION ledger_users_profile();",
    "CREATE TRIGGER ledger_extras AFTER INSERT OR DELETE OR UPDATE OF quantity ON extras FOR EACH ROW EXECUTE FUNCTION ledger_extras();",
    "CREATE TRIGGER ledger_cards AFTER INSERT OR DELETE OR UPDATE OF quantity ON card_stacks FOR EACH ROW EXECUTE FUNCTION ledger_cards();",
    "CREATE TRIGGER ledger_districts AFTER UPDATE OF owner_id ON districts FOR EACH ROW EXECUTE FUNCTION ledger_districts();",
    "CREATE TRIGGER ledger_buildings AFTER INSERT OR DELETE ON businesses FOR EACH ROW EXECUTE FUNCTION ledger_buildings();",
)


def upgrade() -> None:
    op.add_column("users", sa.Column("monster_potential", sa.Boolean(), nullable=False, server_default="false"))
    op.create_table(
        "player_ledger",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("asset", sa.String(length=24), nullable=False),
        sa.Column("item", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("delta", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("balance", sa.BigInteger(), nullable=True),
        sa.Column("note", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("reason", sa.String(length=24), nullable=False, server_default=""),
        sa.Column("source", sa.String(length=64), nullable=False, server_default="system"),
        sa.Column("hits", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_player_ledger_user_id_desc", "player_ledger", ["user_id", "id"])
    op.create_index("ix_player_ledger_created_at", "player_ledger", ["created_at"])
    op.create_table(
        "battle_log",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("kind", sa.String(length=12), nullable=False),
        sa.Column("attacker_id", sa.BigInteger(), nullable=False),
        sa.Column("defender_id", sa.BigInteger(), nullable=True),
        sa.Column("attacker_won", sa.Boolean(), nullable=False),
        sa.Column("rounds", sa.Integer(), nullable=False, server_default="0"),
        *[sa.Column(c, sa.BigInteger(), nullable=False, server_default="0") for c in ("a_quantity", "a_power", "a_dead", "a_fled", "d_quantity", "d_power", "d_dead", "d_fled")],
        sa.Column("notes", sa.String(length=1000), nullable=False, server_default=""),
        sa.Column("details", postgresql.JSONB(), nullable=True),
        sa.Column("source", sa.String(length=64), nullable=False, server_default="system"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_battle_log_attacker", "battle_log", ["attacker_id", "id"])
    op.create_index("ix_battle_log_defender", "battle_log", ["defender_id", "id"])
    op.create_index("ix_battle_log_created_at", "battle_log", ["created_at"])
    op.create_table(
        "error_log",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("fingerprint", sa.String(length=24), nullable=False),
        sa.Column("kind", sa.String(length=8), nullable=False),
        sa.Column("process", sa.String(length=8), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False, server_default=""),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("source", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("hits", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("max_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("first_seen", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("uq_error_log_fingerprint", "error_log", ["fingerprint"], unique=True)
    op.create_index("ix_error_log_kind_seen", "error_log", ["kind", "last_seen"])
    for sql in (_WRITE, _USERS_NUMERIC, _USERS_PROFILE, _EXTRAS, _CARDS, _DISTRICTS, _BUILDINGS, *_TRIGGERS):
        op.execute(sql)


def downgrade() -> None:
    for name, table in (
        ("ledger_users_numeric", "users"), ("ledger_users_profile", "users"), ("ledger_extras", "extras"),
        ("ledger_cards", "card_stacks"), ("ledger_districts", "districts"), ("ledger_buildings", "businesses"),
    ):
        op.execute(f"DROP TRIGGER {name} ON {table}")
        op.execute(f"DROP FUNCTION {name}()")
    op.execute("DROP FUNCTION ledger_write(bigint, text, text, bigint, bigint, text)")
    op.drop_table("error_log")
    op.drop_table("battle_log")
    op.drop_table("player_ledger")
    op.drop_column("users", "monster_potential")
