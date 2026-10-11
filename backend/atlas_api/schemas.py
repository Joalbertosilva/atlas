"""Validação de entrada (marshmallow). Todos os parâmetros de rota passam por aqui."""
from marshmallow import Schema, ValidationError, fields, validate, validates_schema

UF_RE = r"^[A-Z]{2}$"
MUN_RE = r"^[0-9]{5}$"
CARGOS = ["1", "3", "5", "6", "7", "8"]


class Paging(Schema):
    page = fields.Integer(load_default=1, validate=validate.Range(min=1, max=10000))
    page_size = fields.Integer(load_default=50, validate=validate.Range(min=1, max=200))


class ScopeArgs(Schema):
    cargo = fields.String(load_default="1", validate=validate.OneOf(CARGOS))
    turno = fields.Integer(load_default=1, validate=validate.OneOf([1, 2]))
    uf = fields.String(load_default=None, validate=validate.Regexp(UF_RE))
    municipio = fields.String(load_default=None, validate=validate.Regexp(MUN_RE))


class RankingArgs(ScopeArgs, Paging):
    kind = fields.String(load_default="candidatura", validate=validate.OneOf(["candidatura", "todas"]))
    format = fields.String(load_default="json", validate=validate.OneOf(["json", "csv"]))


class MunicipalityResultsArgs(ScopeArgs):
    mode = fields.String(load_default="leader", validate=validate.OneOf(["leader", "candidate"]))
    option_id = fields.Integer(load_default=None, validate=validate.Range(min=1))
    format = fields.String(load_default="json", validate=validate.OneOf(["json", "csv"]))

    @validates_schema
    def _need_option(self, data, **_):
        if data["mode"] == "candidate" and not data.get("option_id"):
            raise ValidationError("option_id é obrigatório em mode=candidate", "option_id")


class CompareArgs(ScopeArgs):
    option_ids = fields.String(required=True, validate=validate.Regexp(r"^[0-9]{1,9}(,[0-9]{1,9}){0,2}$"))


class TurnoCargoArgs(Schema):
    cargo = fields.String(load_default="1", validate=validate.OneOf(CARGOS))
    turno = fields.Integer(load_default=1, validate=validate.OneOf([1, 2]))


class MunicipalitiesArgs(Paging):
    uf = fields.String(load_default=None, validate=validate.Regexp(UF_RE))
    q = fields.String(load_default=None, validate=validate.Length(min=2, max=80))


class CandidaciesArgs(Paging):
    cargo = fields.String(load_default=None, validate=validate.OneOf(CARGOS))
    uf = fields.String(load_default=None, validate=validate.Regexp(r"^([A-Z]{2})$"))
    q = fields.String(load_default=None, validate=validate.Length(min=2, max=80))


class PlacesArgs(Paging):
    zona = fields.String(load_default=None, validate=validate.Regexp(r"^[0-9]{1,4}$"))
    q = fields.String(load_default=None, validate=validate.Length(min=2, max=80))


class SectionsArgs(Paging):
    municipio = fields.String(required=True, validate=validate.Regexp(MUN_RE))
    zona = fields.String(load_default=None, validate=validate.Regexp(r"^[0-9]{1,4}$"))
    local = fields.Integer(load_default=None, validate=validate.Range(min=1))


class GeometryArgs(Schema):
    level = fields.String(load_default="municipio", validate=validate.OneOf(["municipio", "uf"]))
    uf = fields.String(load_default=None, validate=validate.Regexp(UF_RE))


class SearchArgs(Schema):
    q = fields.String(required=True, validate=validate.Length(min=2, max=200))
    page = fields.Integer(load_default=1, validate=validate.Range(min=1, max=5))
    uf = fields.String(load_default=None, validate=validate.Regexp(UF_RE))
    municipio = fields.String(load_default=None, validate=validate.Regexp(MUN_RE))
    candidato = fields.String(load_default=None, validate=validate.Length(min=2, max=80))


class PollSearchArgs(SearchArgs):
    q = fields.String(load_default="", validate=validate.Length(max=200))
    cargo = fields.String(load_default=None, validate=validate.Length(min=2, max=40))
    empresa = fields.String(load_default=None, validate=validate.Length(min=2, max=80))
    de = fields.Date(load_default=None)
    ate = fields.Date(load_default=None)
    page_size = fields.Integer(load_default=20, validate=validate.Range(min=1, max=100))
