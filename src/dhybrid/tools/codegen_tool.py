"""Tool codegen — generate code from specifications (OpenAPI, GraphQL, Protobuf)."""

from __future__ import annotations

from dhybrid.tools.codegen import (
    generate_from_graphql,
    generate_from_openapi,
    generate_from_protobuf,
)
from dhybrid.tools.registry import ToolRegistry


def register(reg: ToolRegistry, max_chars: int = 8000) -> None:
    def codegen_openapi(spec: str, framework: str = "fastapi") -> str:
        """Generate code from OpenAPI specification.

        Args:
            spec: JSON string of OpenAPI specification
            framework: Target framework (fastapi)
        """
        import json
        try:
            spec_dict = json.loads(spec)
        except json.JSONDecodeError as e:
            return f"ERROR: Invalid JSON spec: {e}"
        return generate_from_openapi(spec_dict, framework)

    def codegen_graphql(schema: str, framework: str = "strawberry") -> str:
        """Generate code from GraphQL schema.

        Args:
            schema: GraphQL schema string
            framework: Target framework (strawberry)
        """
        return generate_from_graphql(schema, framework)

    def codegen_protobuf(proto: str, framework: str = "grpc") -> str:
        """Generate code from Protobuf definition.

        Args:
            proto: Protobuf schema string
            framework: Target framework (grpc)
        """
        return generate_from_protobuf(proto, framework)

    reg.register(
        "codegen_openapi",
        "Generate FastAPI code from OpenAPI 3.0 spec (JSON).",
        {"spec": {"type": "string", "required": True}, "framework": {"type": "string"}},
        codegen_openapi,
    )
    reg.register(
        "codegen_graphql",
        "Generate Strawberry GraphQL code from schema.",
        {"schema": {"type": "string", "required": True}, "framework": {"type": "string"}},
        codegen_graphql,
    )
    reg.register(
        "codegen_protobuf",
        "Generate gRPC service code from Protobuf definition.",
        {"proto": {"type": "string", "required": True}, "framework": {"type": "string"}},
        codegen_protobuf,
    )