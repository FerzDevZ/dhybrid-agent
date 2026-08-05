"""Tests for code generation from specs."""
from dhybrid.tools.codegen import (
    generate_from_graphql,
    generate_from_openapi,
    generate_from_protobuf,
)


def test_codegen_openapi_creates_fastapi_routes():
    spec = {
        "openapi": "3.0.0",
        "paths": {
            "/users": {
                "get": {
                    "summary": "List users",
                    "responses": {"200": {"description": "Success"}},
                },
                "post": {
                    "summary": "Create user",
                    "responses": {"201": {"description": "Created"}},
                },
            },
            "/users/{id}": {
                "get": {
                    "summary": "Get user",
                    "parameters": [{"name": "id", "in": "path", "required": True, "schema": {"type": "integer"}}],
                    "responses": {"200": {"description": "Success"}},
                },
            },
        },
    }
    code = generate_from_openapi(spec, "fastapi")
    assert "@app.get('/users')" in code
    assert "@app.post('/users')" in code
    assert "@app.get('/users/{id}')" in code
    assert "async def get_users" in code  # Generated name based on method + path
    assert "async def post_users" in code
    assert "async def get_users_id" in code


def test_codegen_openapi_creates_pydantic_models():
    spec = {
        "openapi": "3.0.0",
        "components": {
            "schemas": {
                "User": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "name": {"type": "string"},
                        "email": {"type": "string", "format": "email"},
                    },
                    "required": ["id", "name"],
                },
            },
        },
        "paths": {},
    }
    code = generate_from_openapi(spec, "fastapi")
    assert "class User" in code
    assert "BaseModel" in code
    assert "id: int" in code
    assert "name: str" in code


def test_codegen_graphql_creates_types():
    schema = """
    type User {
        id: ID!
        name: String!
        email: String!
    }
    type Query {
        user(id: ID!): User
        users: [User!]!
    }
    type Mutation {
        createUser(name: String!, email: String!): User!
    }
    """
    code = generate_from_graphql(schema, "strawberry")
    assert "class User" in code
    assert "strawberry.type" in code
    assert "id: strawberry.ID" in code
    assert "name: str" in code
    assert "def user" in code or "async def user" in code


def test_codegen_protobuf_creates_grpc_service():
    proto = """
    syntax = "proto3";
    package user;
    
    message User {
        int32 id = 1;
        string name = 2;
        string email = 3;
    }
    
    service UserService {
        rpc GetUser(GetUserRequest) returns (User);
        rpc ListUsers(ListUsersRequest) returns (ListUsersResponse);
    }
    """
    code = generate_from_protobuf(proto, "grpc")
    assert "class UserService" in code
    assert "async def GetUser" in code
    assert "async def ListUsers" in code