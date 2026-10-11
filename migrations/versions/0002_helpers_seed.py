"""Funções de normalização usadas pelo ETL e cargos/UF exterior de referência.

Cargos 2 (vice-presidente), 4 (vice-governador), 9 e 10 (suplentes de senador) não são
disputas independentes e não recebem votos próprios nos arquivos de resultado.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-11
"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(r"""
    -- '#NULO', '#NE' e vazio do TSE -> NULL
    CREATE OR REPLACE FUNCTION staging.nn(t text) RETURNS text
    LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
      SELECT CASE WHEN t IS NULL OR btrim(t) IN ('', '#NULO', '#NE', '#NULO#') THEN NULL ELSE btrim(t) END $$;

    -- Inteiro estrito: falha a transação se o texto não for numérico (validação de layout).
    CREATE OR REPLACE FUNCTION staging.to_int(t text) RETURNS integer
    LANGUAGE sql IMMUTABLE PARALLEL SAFE STRICT AS $$ SELECT btrim(t)::integer $$;

    -- Código numérico como texto canônico sem zeros à esquerda (zona, seção, local, cargo...).
    CREATE OR REPLACE FUNCTION staging.code(t text) RETURNS text
    LANGUAGE sql IMMUTABLE PARALLEL SAFE STRICT AS $$ SELECT (btrim(t)::bigint)::text $$;

    -- Município TSE: sempre 5 dígitos (os arquivos trazem "01007" ou 1457).
    CREATE OR REPLACE FUNCTION staging.mun(t text) RETURNS text
    LANGUAGE sql IMMUTABLE PARALLEL SAFE STRICT AS $$ SELECT lpad((btrim(t)::integer)::text, 5, '0') $$;

    CREATE OR REPLACE FUNCTION staging.br_date(t text) RETURNS date
    LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
      SELECT CASE WHEN staging.nn(t) IS NULL THEN NULL ELSE to_date(btrim(t), 'DD/MM/YYYY') END $$;

    INSERT INTO core.office (cd_cargo, ds_cargo, system, scope, sort_order) VALUES
      ('1', 'Presidente', 'majoritario', 'nacional', 1),
      ('3', 'Governador', 'majoritario', 'estadual', 2),
      ('5', 'Senador', 'majoritario', 'estadual', 3),
      ('6', 'Deputado Federal', 'proporcional', 'estadual', 4),
      ('7', 'Deputado Estadual', 'proporcional', 'estadual', 5),
      ('8', 'Deputado Distrital', 'proporcional', 'estadual', 6)
    ON CONFLICT DO NOTHING;

    INSERT INTO core.state (sg_uf, nm_uf, cd_uf_ibge, cd_uf_tse, is_exterior)
    VALUES ('ZZ', 'Exterior', NULL, NULL, true) ON CONFLICT DO NOTHING;
    """)


def downgrade() -> None:
    op.execute("""
    DELETE FROM core.state WHERE sg_uf = 'ZZ';
    DELETE FROM core.office;
    DROP FUNCTION IF EXISTS staging.br_date(text), staging.mun(text), staging.code(text),
                            staging.to_int(text), staging.nn(text);
    """)
