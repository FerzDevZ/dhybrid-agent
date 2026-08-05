"""Code generation from specifications (OpenAPI, GraphQL, Protobuf)."""

from __future__ import annotations

import re
from typing import Any


def generate_from_openapi(spec: dict[str, Any], framework: str = "fastapi") -> str:
    """Generate code from OpenAPI specification.

    Args:
        spec: OpenAPI specification dict
        framework: Target framework (fastapi, flask, etc.)

    Returns:
        Generated code as string
    """
    if framework != "fastapi":
        raise ValueError(f"Unsupported framework: {framework}")

    lines = [
        "from fastapi import FastAPI",
        "from pydantic import BaseModel",
        "from typing import Optional, List",
        "",
        "app = FastAPI()",
        "",
    ]

    # Generate Pydantic models from components/schemas
    schemas = spec.get("components", {}).get("schemas", {})
    for schema_name, schema in schemas.items():
        lines.append(f"class {schema_name}(BaseModel):")
        props = schema.get("properties", {})
        required = set(schema.get("required", []))
        for prop_name, prop_spec in props.items():
            prop_type = _openapi_type_to_python(prop_spec)
            if prop_name not in required:
                prop_type = f"Optional[{prop_type}]"
            lines.append(f"    {prop_name}: {prop_type}")
        lines.append("")

    # Generate routes from paths
    paths = spec.get("paths", {})
    for path, methods in paths.items():
        for method, details in methods.items():
            if method.lower() not in ("get", "post", "put", "patch", "delete"):
                continue

            func_name = _generate_func_name(path, method)
            path_params = _extract_path_params(path)

            # Build function signature
            params = []
            for p in path_params:
                params.append(f"{p}: int")

            # Add query/body params if needed
            if method.lower() in ("post", "put", "patch"):
                # Try to find request body schema
                req_body = details.get("requestBody", {})
                content = req_body.get("content", {})
                if "application/json" in content:
                    schema_ref = content["application/json"].get("schema", {}).get("$ref", "")
                    if schema_ref:
                        model_name = schema_ref.split("/")[-1]
                        params.append(f"data: {model_name}")

            param_str = ", ".join(params)
            lines.append(f"@app.{method.lower()}('{path}')")
            lines.append(f"async def {func_name}({param_str}):")
            lines.append(f"    \"\"\"{details.get('summary', '')}\"\"\"")
            lines.append("    # TODO: implement")
            lines.append("    pass")
            lines.append("")

    return "\n".join(lines)


def _openapi_type_to_python(prop_spec: dict) -> str:
    """Convert OpenAPI type to Python type annotation."""
    type_map = {
        "string": "str",
        "integer": "int",
        "number": "float",
        "boolean": "bool",
        "array": "List",
        "object": "dict",
    }
    openapi_type = prop_spec.get("type", "string")
    return type_map.get(openapi_type, "Any")


def _extract_path_params(path: str) -> list[str]:
    """Extract path parameters from URL path."""
    return re.findall(r"\{(\w+)\}", path)


def _generate_func_name(path: str, method: str) -> str:
    """Generate function name from path and method."""
    # Clean path
    clean = re.sub(r"[{}]", "", path)
    clean = clean.strip("/").replace("/", "_").replace("-", "_")
    return f"{method.lower()}_{clean or 'root'}"


def generate_from_graphql(schema: str, framework: str = "strawberry") -> str:
    """Generate code from GraphQL schema.

    Args:
        schema: GraphQL schema string
        framework: Target framework (strawberry, ariadne, etc.)

    Returns:
        Generated code as string
    """
    if framework != "strawberry":
        raise ValueError(f"Unsupported framework: {framework}")

    lines = [
        "import strawberry",
        "from typing import Optional, List",
        "",
    ]

    # Parse schema for type definitions
    # Simple regex-based parsing for common patterns
    type_pattern = r"type\s+(\w+)\s*\{([^}]+)\}"
    for match in re.finditer(type_pattern, schema):
        type_name = match.group(1)
        fields_text = match.group(2)

        lines.append("@strawberry.type")
        lines.append(f"class {type_name}:")
        for field_line in fields_text.strip().split("\n"):
            field_line = field_line.strip()
            if not field_line:
                continue
            # Parse field: name: Type!
            field_match = re.match(r"(\w+):\s*([\w\[\]!]+)", field_line)
            if field_match:
                field_name = field_match.group(1)
                field_type = field_match.group(2)
                py_type = _graphql_type_to_python(field_type)
                lines.append(f"    {field_name}: {py_type}")
        lines.append("")

    # Parse Query type
    query_pattern = r"type\s+Query\s*\{([^}]+)\}"
    match = re.search(query_pattern, schema)
    if match:
        lines.append("@strawberry.type")
        lines.append("class Query:")
        fields_text = match.group(1)
        for field_line in fields_text.strip().split("\n"):
            field_line = field_line.strip()
            if not field_line:
                continue
            field_match = re.match(r"(\w+)\((.*?)\):\s*([\w\[\]!]+)", field_line)
            if field_match:
                field_name = field_match.group(1)
                args_text = field_match.group(2)
                return_type = field_match.group(3)
                py_return = _graphql_type_to_python(return_type)

                args = []
                for arg in args_text.split(","):
                    arg = arg.strip()
                    if not arg:
                        continue
                    arg_match = re.match(r"(\w+):\s*([\w\[\]!]+)", arg)
                    if arg_match:
                        arg_name = arg_match.group(1)
                        arg_type = arg_match.group(2)
                        py_type = _graphql_type_to_python(arg_type)
                        args.append(f"{arg_name}: {py_type}")

                args_str = ", ".join(args)
                lines.append("    @strawberry.field")
                lines.append(f"    def {field_name}(self, {args_str}) -> {py_return}:")
                lines.append("        # TODO: implement")
                lines.append("        pass")
        lines.append("")

    return "\n".join(lines)


def _graphql_type_to_python(gql_type: str) -> str:
    """Convert GraphQL type to Python type."""
    # Handle List: [Type!]!
    list_match = re.match(r"\[(.+)\]", gql_type)
    if list_match:
        inner = _graphql_type_to_python(list_match.group(1))
        return f"List[{inner}]"

    # Handle non-null: Type!
    if gql_type.endswith("!"):
        return _graphql_type_to_python(gql_type[:-1])

    type_map = {
        "ID": "strawberry.ID",
        "String": "str",
        "Int": "int",
        "Float": "float",
        "Boolean": "bool",
    }
    return type_map.get(gql_type, "Any")


def generate_from_protobuf(proto: str, framework: str = "grpc") -> str:
    """Generate code from Protobuf definition.

    Args:
        proto: Protobuf schema string
        framework: Target framework (grpc, grpclib, etc.)

    Returns:
        Generated code as string
    """
    lines = [
        "from abc import ABC, abstractmethod",
        "from typing import Optional, List",
        "",
    ]

    # Parse package
    _ = re.search(r"package\s+(\w+);", proto)  # package name parsed but not used
    # Parse messages
    message_pattern = r"message\s+(\w+)\s*\{([^}]+)\}"
    for match in re.finditer(message_pattern, proto):
        msg_name = match.group(1)
        fields_text = match.group(2)

        lines.append(f"class {msg_name}:")
        lines.append("    def __init__(")
        fields = []
        for field_line in fields_text.strip().split("\n"):
            field_line = field_line.strip()
            if not field_line or field_line.startswith("//"):
                continue
            # Parse: type name = number;
            field_match = re.match(r"(\w+)\s+(\w+)\s*=\s*\d+;", field_line)
            if field_match:
                field_type = field_match.group(1)
                field_name = field_match.group(2)
                py_type = _protobuf_type_to_python(field_type)
                fields.append(f"        {field_name}: {py_type} = None,")
        lines.extend(fields)
        lines.append("    ):")
        for field_line in fields_text.strip().split("\n"):
            field_line = field_line.strip()
            if not field_line or field_line.startswith("//"):
                continue
            field_match = re.match(r"(\w+)\s+(\w+)\s*=\s*\d+;", field_line)
            if field_match:
                field_name = field_match.group(2)
                lines.append(f"        self.{field_name} = {field_name}")
        lines.append("")

    # Parse services
    service_pattern = r"service\s+(\w+)\s*\{([^}]+)\}"
    for match in re.finditer(service_pattern, proto):
        svc_name = match.group(1)
        methods_text = match.group(2)

        lines.append(f"class {svc_name}(ABC):")
        for method_line in methods_text.strip().split("\n"):
            method_line = method_line.strip()
            if not method_line or method_line.startswith("//"):
                continue
            # Parse: rpc MethodName(Request) returns (Response);
            method_match = re.match(r"rpc\s+(\w+)\s*\((\w+)\)\s*returns\s*\((\w+)\);", method_line)
            if method_match:
                method_name = method_match.group(1)
                req_type = method_match.group(2)
                resp_type = method_match.group(3)
                lines.append("    @abstractmethod")
                lines.append(f"    async def {method_name}(self, request: {req_type}) -> {resp_type}:")
                lines.append("        pass")
        lines.append("")

    return "\n".join(lines)


def _protobuf_type_to_python(proto_type: str) -> str:
    """Convert Protobuf type to Python type."""
    type_map = {
        "int32": "int",
        "int64": "int",
        "uint32": "int",
        "uint64": "int",
        "sint32": "int",
        "sint64": "int",
        "fixed32": "int",
        "fixed64": "int",
        "sfixed32": "int",
        "sfixed64": "int",
        "float": "float",
        "double": "float",
        "bool": "bool",
        "string": "str",
        "bytes": "bytes",
    }
    return type_map.get(proto_type, "Any")