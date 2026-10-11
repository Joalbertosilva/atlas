"""Identidade de comparecimento observada nos arquivos 2026: aptos = comparecimento + abstenções
+ eleitores de seções não instaladas (ex.: seções do exterior não instaladas).

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-11
"""
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    ALTER TABLE fact.turnout_munzona DROP CONSTRAINT IF EXISTS turnout_munzona_check;
    ALTER TABLE fact.turnout_munzona ADD CONSTRAINT turnout_munzona_identity
        CHECK (qt_comparecimento + qt_abstencoes + qt_eleitores_secoes_nao_instaladas = qt_aptos);
    ALTER TABLE agg.turnout_municipality ADD COLUMN qt_eleitores_secoes_nao_instaladas bigint NOT NULL DEFAULT 0;
    ALTER TABLE agg.turnout_state ADD COLUMN qt_eleitores_secoes_nao_instaladas bigint NOT NULL DEFAULT 0;
    """)


def downgrade() -> None:
    op.execute("""
    ALTER TABLE agg.turnout_state DROP COLUMN qt_eleitores_secoes_nao_instaladas;
    ALTER TABLE agg.turnout_municipality DROP COLUMN qt_eleitores_secoes_nao_instaladas;
    ALTER TABLE fact.turnout_munzona DROP CONSTRAINT IF EXISTS turnout_munzona_identity;
    ALTER TABLE fact.turnout_munzona ADD CONSTRAINT turnout_munzona_check
        CHECK (qt_comparecimento + qt_abstencoes = qt_aptos);
    """)
