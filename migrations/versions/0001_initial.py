"""Modelo inicial: metadados de importação, staging, dados publicados, agregados, pesquisas e cache.

Granularidades e chaves foram definidas após inspecionar os arquivos reais de 2026
(ver docs/DATA_DICTIONARY.md).

Revision ID: 0001
Revises:
Create Date: 2026-10-11
"""
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

UFS = [
    "AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS", "MT", "PA",
    "PB", "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO", "ZZ",
]

DDL = r"""
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS unaccent;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE SCHEMA IF NOT EXISTS meta;
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS fact;
CREATE SCHEMA IF NOT EXISTS agg;
CREATE SCHEMA IF NOT EXISTS polls;
CREATE SCHEMA IF NOT EXISTS app;

-- unaccent() não é IMMUTABLE; wrapper para uso em índices/colunas geradas.
CREATE OR REPLACE FUNCTION core.normalize_text(t text) RETURNS text
LANGUAGE sql IMMUTABLE PARALLEL SAFE STRICT
AS $$ SELECT lower(public.unaccent('public.unaccent'::regdictionary, t)) $$;

------------------------------------------------------------------------------
-- META: recursos, importações e publicações por recorte
------------------------------------------------------------------------------
CREATE TABLE meta.resource (
    resource_key        text PRIMARY KEY,
    dataset             text NOT NULL,
    kind                text NOT NULL,
    url                 text NOT NULL CHECK (url LIKE 'https://%'),
    listed_in_catalog   boolean NOT NULL,
    license             text NOT NULL,
    description         text,
    http_last_modified  timestamptz,
    content_length      bigint,
    checked_at          timestamptz
);

CREATE TABLE meta.import_run (
    id                   bigserial PRIMARY KEY,
    resource_key         text NOT NULL REFERENCES meta.resource(resource_key),
    member_name          text NOT NULL,
    scope_key            text NOT NULL,
    zip_sha256           text NOT NULL,
    member_crc32         text NOT NULL,
    member_size          bigint NOT NULL,
    fingerprint          text GENERATED ALWAYS AS (member_name || ':' || member_crc32 || ':' || member_size::text) STORED,
    source_generated_at  timestamp,
    http_last_modified   timestamptz,
    status               text NOT NULL CHECK (status IN ('running','failed','published','superseded')),
    rows_read            bigint,
    rows_loaded          bigint,
    validation           jsonb,
    error                text,
    started_at           timestamptz NOT NULL DEFAULT now(),
    finished_at          timestamptz
);
CREATE INDEX import_run_scope_idx ON meta.import_run (scope_key, status);

-- Um registro por recorte publicado: aponta para a importação vigente.
CREATE TABLE meta.publication (
    scope_key      text PRIMARY KEY,
    kind           text NOT NULL,
    sg_uf          text,
    import_run_id  bigint NOT NULL REFERENCES meta.import_run(id),
    rows_published bigint NOT NULL,
    published_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE meta.reconciliation (
    id            bigserial PRIMARY KEY,
    check_name    text NOT NULL,
    scope         text NOT NULL,
    expected      bigint,
    observed      bigint,
    ok            boolean NOT NULL,
    details       jsonb,
    checked_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX reconciliation_check_idx ON meta.reconciliation (check_name, scope, checked_at DESC);

------------------------------------------------------------------------------
-- CORE: entidades publicadas (códigos preservados como texto)
------------------------------------------------------------------------------
CREATE TABLE core.state (
    sg_uf        text PRIMARY KEY CHECK (sg_uf ~ '^[A-Z]{2}$'),
    nm_uf        text NOT NULL,
    cd_uf_ibge   text CHECK (cd_uf_ibge ~ '^[0-9]{2}$'),
    cd_uf_tse    text,
    is_exterior  boolean NOT NULL DEFAULT false
);

CREATE TABLE core.municipality (
    cd_municipio_tse   text PRIMARY KEY CHECK (cd_municipio_tse ~ '^[0-9]{5}$'),
    sg_uf              text NOT NULL REFERENCES core.state(sg_uf),
    nm_municipio       text NOT NULL,
    cd_municipio_ibge  text UNIQUE CHECK (cd_municipio_ibge ~ '^[0-9]{7}$'),
    nm_municipio_ibge  text,
    is_exterior        boolean NOT NULL DEFAULT false,
    name_norm          text GENERATED ALWAYS AS (core.normalize_text(nm_municipio)) STORED
);
CREATE INDEX municipality_uf_idx ON core.municipality (sg_uf);
CREATE INDEX municipality_name_trgm ON core.municipality USING gin (name_norm gin_trgm_ops);

CREATE TABLE core.election (
    cd_eleicao       text PRIMARY KEY,
    ano_eleicao      smallint NOT NULL,
    cd_tipo_eleicao  text,
    ds_eleicao       text NOT NULL,
    dt_eleicao       date NOT NULL,
    tp_abrangencia   text NOT NULL
);

CREATE TABLE core.office (
    cd_cargo   text PRIMARY KEY,
    ds_cargo   text NOT NULL,
    system     text NOT NULL CHECK (system IN ('majoritario','proporcional')),
    scope      text NOT NULL CHECK (scope IN ('nacional','estadual')),
    sort_order smallint NOT NULL
);

-- Vagas por circunscrição (consulta_vagas). Senador 2026 = 2 vagas por UF.
CREATE TABLE core.seat (
    cd_eleicao  text NOT NULL REFERENCES core.election(cd_eleicao),
    sg_ue       text NOT NULL,
    cd_cargo    text NOT NULL REFERENCES core.office(cd_cargo),
    qt_vaga     integer NOT NULL CHECK (qt_vaga >= 0),
    PRIMARY KEY (cd_eleicao, sg_ue, cd_cargo)
);

-- Disputa = eleição + turno + cargo + unidade eleitoral (BR para Presidente, UF para os demais).
CREATE TABLE core.contest (
    id          serial PRIMARY KEY,
    cd_eleicao  text NOT NULL REFERENCES core.election(cd_eleicao),
    nr_turno    smallint NOT NULL CHECK (nr_turno IN (1,2)),
    cd_cargo    text NOT NULL REFERENCES core.office(cd_cargo),
    sg_ue       text NOT NULL,
    UNIQUE (cd_eleicao, nr_turno, cd_cargo, sg_ue)
);

-- Candidatura: SQ_CANDIDATO é único por eleição; número NÃO é chave.
-- Campos pessoais desnecessários (CPF, e-mail, título, nascimento, gênero, raça,
-- instrução, estado civil, ocupação) não são importados.
CREATE TABLE core.candidacy (
    id                        serial PRIMARY KEY,
    cd_eleicao                text NOT NULL REFERENCES core.election(cd_eleicao),
    sq_candidato              text NOT NULL,
    cd_cargo                  text NOT NULL REFERENCES core.office(cd_cargo),
    sg_ue                     text NOT NULL,
    nr_candidato              text NOT NULL,
    nm_candidato              text NOT NULL,
    nm_urna_candidato         text NOT NULL,
    nr_partido                text,
    sg_partido                text,
    nm_partido                text,
    sg_federacao              text,
    nm_federacao              text,
    nm_coligacao              text,
    ds_composicao_coligacao   text,
    cd_situacao_candidatura   text,
    ds_situacao_candidatura   text,
    ds_detalhe_situacao_cand  text,
    name_norm                 text GENERATED ALWAYS AS (core.normalize_text(nm_urna_candidato || ' ' || nm_candidato)) STORED,
    UNIQUE (cd_eleicao, sq_candidato)
);
CREATE INDEX candidacy_contest_idx ON core.candidacy (cd_eleicao, cd_cargo, sg_ue);
CREATE INDEX candidacy_name_trgm ON core.candidacy USING gin (name_norm gin_trgm_ops);

-- Situação da candidatura no turno, conforme arquivo oficial de totalização.
CREATE TABLE core.candidacy_round (
    candidacy_id              integer NOT NULL REFERENCES core.candidacy(id),
    nr_turno                  smallint NOT NULL,
    nm_tipo_destinacao_votos  text,
    cd_sit_tot_turno          text,
    ds_sit_tot_turno          text,
    PRIMARY KEY (candidacy_id, nr_turno)
);

-- Opções de voto de uma disputa: candidatura, legenda, branco ou nulo.
-- Branco/nulo/legenda NÃO são candidaturas.
CREATE TABLE core.vote_option (
    id            serial PRIMARY KEY,
    cd_eleicao    text NOT NULL REFERENCES core.election(cd_eleicao),
    cd_cargo      text NOT NULL REFERENCES core.office(cd_cargo),
    sg_ue         text NOT NULL,
    kind          text NOT NULL CHECK (kind IN ('candidatura','legenda','branco','nulo')),
    nr_votavel    text NOT NULL,
    sq_candidato  text NOT NULL DEFAULT '',
    candidacy_id  integer REFERENCES core.candidacy(id),
    nr_partido    text,
    label         text NOT NULL,
    CHECK ((kind = 'candidatura') = (candidacy_id IS NOT NULL)),
    UNIQUE (cd_eleicao, cd_cargo, sg_ue, kind, nr_votavel, sq_candidato)
);

CREATE TABLE core.zone (
    sg_uf    text NOT NULL REFERENCES core.state(sg_uf),
    nr_zona  text NOT NULL CHECK (nr_zona ~ '^[0-9]+$'),
    PRIMARY KEY (sg_uf, nr_zona)
);

-- Local de votação: chave (município TSE, zona, número do local). Nome não é identificador.
CREATE TABLE core.polling_place (
    id                 serial PRIMARY KEY,
    cd_municipio_tse   text NOT NULL REFERENCES core.municipality(cd_municipio_tse),
    nr_zona            text NOT NULL,
    nr_local_votacao   text NOT NULL,
    nm_local_votacao   text NOT NULL,
    cd_tipo_local      text,
    ds_tipo_local      text,
    ds_endereco        text,
    nm_bairro          text,
    nr_cep             text,
    ds_situ_local      text,
    latitude           double precision,
    longitude          double precision,
    coord_status       text NOT NULL CHECK (coord_status IN ('valida','ausente','invalida')),
    geom               geometry(Point, 4326),
    UNIQUE (cd_municipio_tse, nr_zona, nr_local_votacao)
);
CREATE INDEX polling_place_mun_idx ON core.polling_place (cd_municipio_tse, nr_zona);

-- Seção: chave nacional (município TSE, zona, seção). Número de seção isolado não é chave.
CREATE TABLE core.section (
    id                     serial PRIMARY KEY,
    cd_municipio_tse       text NOT NULL REFERENCES core.municipality(cd_municipio_tse),
    nr_zona                text NOT NULL,
    nr_secao               text NOT NULL,
    polling_place_id       integer REFERENCES core.polling_place(id),
    link_status            text NOT NULL DEFAULT 'sem_vinculo'
                           CHECK (link_status IN ('confirmado','somente_cadastro','somente_resultado','divergente','sem_vinculo')),
    result_nr_local        text,
    cd_tipo_secao_agregada text,
    ds_tipo_secao_agregada text,
    nr_secao_principal     text,
    qt_eleitor_secao       integer CHECK (qt_eleitor_secao >= 0),
    UNIQUE (cd_municipio_tse, nr_zona, nr_secao)
);
CREATE INDEX section_place_idx ON core.section (polling_place_id);

------------------------------------------------------------------------------
-- FACT: votos e comparecimento
------------------------------------------------------------------------------
-- Grão: disputa x município x zona x opção x voto em trânsito (arquivos *_munzona).
CREATE TABLE fact.vote_munzona (
    contest_id           integer NOT NULL REFERENCES core.contest(id),
    sg_uf                text NOT NULL,
    cd_municipio_tse     text NOT NULL,
    nr_zona              text NOT NULL,
    option_id            integer NOT NULL REFERENCES core.vote_option(id),
    st_voto_em_transito  boolean NOT NULL,
    qt_votos             integer NOT NULL CHECK (qt_votos >= 0),
    qt_votos_validos     integer NOT NULL CHECK (qt_votos_validos >= 0 AND qt_votos_validos <= qt_votos),
    PRIMARY KEY (contest_id, cd_municipio_tse, nr_zona, option_id, st_voto_em_transito)
);
CREATE INDEX vote_munzona_option_idx ON fact.vote_munzona (option_id);
CREATE INDEX vote_munzona_uf_idx ON fact.vote_munzona (sg_uf);

-- Grão: disputa x município x zona x trânsito (detalhe_votacao_munzona). Uma linha por cargo:
-- aptos/comparecimento repetem entre cargos e NUNCA devem ser somados entre cargos.
CREATE TABLE fact.turnout_munzona (
    contest_id                         integer NOT NULL REFERENCES core.contest(id),
    sg_uf                              text NOT NULL,
    cd_municipio_tse                   text NOT NULL,
    nr_zona                            text NOT NULL,
    st_voto_em_transito                boolean NOT NULL,
    qt_aptos                           integer NOT NULL,
    qt_secoes_principais               integer NOT NULL,
    qt_secoes_agregadas                integer NOT NULL,
    qt_secoes_nao_instaladas           integer NOT NULL,
    qt_total_secoes                    integer NOT NULL,
    qt_comparecimento                  integer NOT NULL,
    qt_eleitores_secoes_nao_instaladas integer NOT NULL,
    qt_abstencoes                      integer NOT NULL,
    qt_votos                           integer NOT NULL,
    qt_votos_concorrentes              integer NOT NULL,
    qt_total_votos_validos             integer NOT NULL,
    qt_votos_nominais_validos          integer NOT NULL,
    qt_total_votos_leg_validos         integer NOT NULL,
    qt_votos_leg_validos               integer NOT NULL,
    qt_votos_nom_convr_leg_validos     integer NOT NULL,
    qt_total_votos_anulados            integer NOT NULL,
    qt_total_votos_anul_subjud         integer NOT NULL,
    qt_votos_brancos                   integer NOT NULL,
    qt_total_votos_nulos               integer NOT NULL,
    qt_votos_nulos                     integer NOT NULL,
    qt_votos_nulos_tecnicos            integer NOT NULL,
    qt_votos_anulados_apu_sep          integer NOT NULL,
    dt_ultima_totalizacao              timestamp,
    PRIMARY KEY (contest_id, cd_municipio_tse, nr_zona, st_voto_em_transito),
    CHECK (qt_comparecimento + qt_abstencoes = qt_aptos)
);

-- Grão: disputa x seção x opção (votacao_secao). Particionado pela unidade eleitoral do
-- arquivo de origem (BR = Presidente em todas as UFs e exterior; UF = cargos estaduais):
-- publicar um recorte = substituir a partição dentro de uma transação.
CREATE TABLE fact.vote_section (
    sg_ue       text NOT NULL,
    contest_id  integer NOT NULL,
    section_id  integer NOT NULL,
    option_id   integer NOT NULL,
    qt_votos    integer NOT NULL CHECK (qt_votos >= 0),
    PRIMARY KEY (sg_ue, section_id, contest_id, option_id)
) PARTITION BY LIST (sg_ue);

-- Grão: disputa x seção (detalhe_votacao_secao).
CREATE TABLE fact.turnout_section (
    contest_id                 integer NOT NULL REFERENCES core.contest(id),
    section_id                 integer NOT NULL REFERENCES core.section(id),
    sg_uf                      text NOT NULL,
    qt_aptos                   integer NOT NULL,
    qt_comparecimento          integer NOT NULL,
    qt_abstencoes              integer NOT NULL,
    qt_votos_nominais          integer NOT NULL,
    qt_votos_brancos           integer NOT NULL,
    qt_votos_nulos             integer NOT NULL,
    qt_votos_legenda           integer NOT NULL,
    qt_votos_anulados_apu_sep  integer NOT NULL,
    ds_origem_voto             text,
    st_secao_instalada         boolean,
    st_secao_anulada           boolean,
    PRIMARY KEY (contest_id, section_id)
);
CREATE INDEX turnout_section_uf_idx ON fact.turnout_section (sg_uf);

------------------------------------------------------------------------------
-- AGG: agregados reconstruídos a partir de fact.*_munzona (grão oficial de totalização)
------------------------------------------------------------------------------
CREATE TABLE agg.result_municipality (
    contest_id        integer NOT NULL,
    cd_municipio_tse  text NOT NULL,
    sg_uf             text NOT NULL,
    option_id         integer NOT NULL,
    qt_votos          bigint NOT NULL,
    qt_votos_validos  bigint NOT NULL,
    PRIMARY KEY (contest_id, cd_municipio_tse, option_id)
);
CREATE INDEX result_municipality_option_idx ON agg.result_municipality (option_id, contest_id);

CREATE TABLE agg.result_state (
    contest_id        integer NOT NULL,
    sg_uf             text NOT NULL,
    option_id         integer NOT NULL,
    qt_votos          bigint NOT NULL,
    qt_votos_validos  bigint NOT NULL,
    PRIMARY KEY (contest_id, sg_uf, option_id)
);

CREATE TABLE agg.turnout_municipality (
    contest_id                 integer NOT NULL,
    cd_municipio_tse           text NOT NULL,
    sg_uf                      text NOT NULL,
    qt_aptos                   bigint NOT NULL,
    qt_comparecimento          bigint NOT NULL,
    qt_abstencoes              bigint NOT NULL,
    qt_votos                   bigint NOT NULL,
    qt_total_votos_validos     bigint NOT NULL,
    qt_votos_nominais_validos  bigint NOT NULL,
    qt_total_votos_leg_validos bigint NOT NULL,
    qt_votos_brancos           bigint NOT NULL,
    qt_total_votos_nulos       bigint NOT NULL,
    qt_total_votos_anul_subjud bigint NOT NULL,
    qt_total_votos_anulados    bigint NOT NULL,
    qt_total_secoes            bigint NOT NULL,
    dt_ultima_totalizacao      timestamp,
    PRIMARY KEY (contest_id, cd_municipio_tse)
);

CREATE TABLE agg.turnout_state (
    contest_id                 integer NOT NULL,
    sg_uf                      text NOT NULL,
    qt_aptos                   bigint NOT NULL,
    qt_comparecimento          bigint NOT NULL,
    qt_abstencoes              bigint NOT NULL,
    qt_votos                   bigint NOT NULL,
    qt_total_votos_validos     bigint NOT NULL,
    qt_votos_nominais_validos  bigint NOT NULL,
    qt_total_votos_leg_validos bigint NOT NULL,
    qt_votos_brancos           bigint NOT NULL,
    qt_total_votos_nulos       bigint NOT NULL,
    qt_total_votos_anul_subjud bigint NOT NULL,
    qt_total_votos_anulados    bigint NOT NULL,
    qt_total_secoes            bigint NOT NULL,
    dt_ultima_totalizacao      timestamp,
    PRIMARY KEY (contest_id, sg_uf)
);

-- Geometrias IBGE (simplificadas pela própria API de malhas, qualidade "minima").
CREATE TABLE core.municipality_geometry (
    cd_municipio_ibge  text PRIMARY KEY CHECK (cd_municipio_ibge ~ '^[0-9]{7}$'),
    sg_uf              text NOT NULL,
    geom               geometry(MultiPolygon, 4326) NOT NULL,
    source_import_id   bigint REFERENCES meta.import_run(id)
);
CREATE INDEX municipality_geometry_uf_idx ON core.municipality_geometry (sg_uf);
CREATE INDEX municipality_geometry_gix ON core.municipality_geometry USING gist (geom);

CREATE TABLE core.state_geometry (
    cd_uf_ibge  text PRIMARY KEY,
    geom        geometry(MultiPolygon, 4326) NOT NULL
);

------------------------------------------------------------------------------
-- POLLS: pesquisas registradas (cadastro oficial, sem resultados percentuais)
------------------------------------------------------------------------------
CREATE TABLE polls.registered_poll (
    nr_protocolo_registro    text PRIMARY KEY,
    cd_eleicao               text,
    nm_eleicao               text,
    sg_uf                    text,
    sg_ue                    text,
    nm_ue                    text,
    dt_registro              timestamp,
    st_pesquisa_propria      text,
    nr_cnpj_empresa          text,
    nm_empresa               text,
    nm_empresa_fantasia      text,
    ds_cargo                 text,
    dt_inicio_pesquisa       date,
    dt_fim_pesquisa          date,
    dt_divulgacao            date,
    qt_entrevistado          integer,
    vr_pesquisa              numeric(14,2),
    ds_metodologia_pesquisa  text,
    ds_plano_amostral        text,
    ds_dado_municipio        text,
    source_import_id         bigint REFERENCES meta.import_run(id),
    search_document          tsvector GENERATED ALWAYS AS (
        setweight(to_tsvector('portuguese', coalesce(core.normalize_text(nm_empresa), '') || ' ' ||
                                           coalesce(core.normalize_text(nm_empresa_fantasia), '')), 'A') ||
        setweight(to_tsvector('portuguese', coalesce(core.normalize_text(nm_ue), '') || ' ' ||
                                           coalesce(core.normalize_text(ds_cargo), '') || ' ' ||
                                           coalesce(nr_protocolo_registro, '')), 'B') ||
        setweight(to_tsvector('portuguese', coalesce(core.normalize_text(left(ds_metodologia_pesquisa, 4000)), '')), 'D')
    ) STORED
);
CREATE INDEX registered_poll_fts ON polls.registered_poll USING gin (search_document);
CREATE INDEX registered_poll_uf_idx ON polls.registered_poll (sg_uf, dt_divulgacao DESC);

------------------------------------------------------------------------------
-- APP: cache de busca de curta duração. A chave é HMAC da consulta (texto da
-- consulta não é armazenado); entradas expiradas são removidas.
------------------------------------------------------------------------------
CREATE TABLE app.search_cache (
    cache_key   text PRIMARY KEY,
    mode        text NOT NULL,
    payload     jsonb NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now(),
    expires_at  timestamptz NOT NULL
);
CREATE INDEX search_cache_expires_idx ON app.search_cache (expires_at);

------------------------------------------------------------------------------
-- STAGING: tabelas UNLOGGED criadas por importação (staging.run_<id>_<tipo>),
-- todas as colunas como texto, exatamente como no CSV. Removidas após publicar;
-- mantidas após falha para diagnóstico (atlas-etl cleanup remove).
------------------------------------------------------------------------------
"""


def upgrade() -> None:
    op.execute(DDL)
    for ue in UFS + ["BR"]:
        op.execute(
            f"CREATE TABLE fact.vote_section_{ue.lower()} PARTITION OF fact.vote_section FOR VALUES IN ('{ue}')"
        )


def downgrade() -> None:
    for schema in ("staging", "app", "polls", "agg", "fact", "core", "meta"):
        op.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
