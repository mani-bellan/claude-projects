"""ossie-duck: compile Apache Ossie semantic models to SQL and run them on DuckDB."""

from .compiler import CompiledQuery, QueryRequest, compile_query
from .engine import Engine, QueryResult
from .errors import QueryError
from .service import SemanticService
from .model import (
    SPEC_VERSION,
    Issue,
    ModelValidationError,
    OssieError,
    SemanticModel,
    load_model,
    parse_model,
)

__all__ = [
    "SPEC_VERSION",
    "CompiledQuery",
    "Engine",
    "Issue",
    "ModelValidationError",
    "OssieError",
    "QueryError",
    "QueryRequest",
    "QueryResult",
    "SemanticModel",
    "SemanticService",
    "compile_query",
    "load_model",
    "parse_model",
]
__version__ = "0.2.0"
