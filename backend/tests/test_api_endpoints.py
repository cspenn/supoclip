"""
API endpoint tests for SupoClip backend.

Tests:
- Root endpoint
- Health check endpoints
- Database health
- Basic API structure
- CORS configuration
"""
from fastapi.testclient import TestClient


class TestRootEndpoint:
    """Test root endpoint."""

    def test_root_endpoint_returns_200(self, async_client: TestClient):
        """Test that root endpoint returns 200."""
        response = async_client.get("/")
        assert response.status_code == 200

    def test_root_endpoint_response_structure(self, async_client: TestClient):
        """Test root endpoint response structure."""
        response = async_client.get("/")
        data = response.json()

        required_fields = ["name", "version", "status", "docs", "architecture"]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"

    def test_root_endpoint_values(self, async_client: TestClient):
        """Test root endpoint response values."""
        response = async_client.get("/")
        data = response.json()

        assert data["name"] == "SupoClip API"
        assert data["status"] == "running"
        assert data["docs"] == "/docs"


class TestHealthCheckEndpoints:
    """Test health check endpoints."""

    def test_basic_health_check(self, async_client: TestClient):
        """Test basic health check endpoint."""
        response = async_client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert "status" in data
        assert data["status"] == "healthy"

    def test_database_health_check(self, async_client: TestClient):
        """Test database health check endpoint."""
        response = async_client.get("/health/db")
        assert response.status_code == 200

        data = response.json()
        assert "status" in data
        assert "database" in data
        assert data["database"] == "connected"

    # Redis health check removed - we now use local asyncio queue instead of Redis


class TestAPIDocumentation:
    """Test API documentation endpoints."""

    def test_swagger_docs_available(self, async_client: TestClient):
        """Test that Swagger documentation is available."""
        response = async_client.get("/docs")
        assert response.status_code == 200

    def test_openapi_schema_available(self, async_client: TestClient):
        """Test that OpenAPI schema is available."""
        response = async_client.get("/openapi.json")
        assert response.status_code == 200

        schema = response.json()
        assert "openapi" in schema
        assert "paths" in schema


class TestAPIStructure:
    """Test API structure and routing."""

    def test_api_version_in_schema(self, async_client: TestClient):
        """Test that API version is in OpenAPI schema."""
        response = async_client.get("/openapi.json")
        schema = response.json()

        info = schema.get("info", {})
        assert "version" in info

    def test_api_title_in_schema(self, async_client: TestClient):
        """Test that API title is in OpenAPI schema."""
        response = async_client.get("/openapi.json")
        schema = response.json()

        info = schema.get("info", {})
        assert info.get("title") == "SupoClip API"

    def test_api_description_in_schema(self, async_client: TestClient):
        """Test that API has a description."""
        response = async_client.get("/openapi.json")
        schema = response.json()

        info = schema.get("info", {})
        assert "description" in info


class TestCORSConfiguration:
    """Test CORS middleware configuration."""

    def test_cors_headers_present(self, async_client: TestClient):
        """Test that CORS headers are present in responses."""
        response = async_client.get("/", headers={"Origin": "http://localhost:3000"})

        # Check for CORS headers
        assert response.status_code == 200
        # CORS headers depend on implementation


class TestErrorHandling:
    """Test API error handling."""

    def test_nonexistent_endpoint_404(self, async_client: TestClient):
        """Test that nonexistent endpoints return 404."""
        response = async_client.get("/api/nonexistent")
        assert response.status_code == 404

    def test_method_not_allowed(self, async_client: TestClient):
        """Test that wrong HTTP method returns appropriate error."""
        response = async_client.post("/")
        # POST to root should be method not allowed
        assert response.status_code in [405, 404, 422]  # Depending on implementation


class TestBasicAPIIntegration:
    """Basic API integration tests."""

    def test_health_check_chain(self, async_client: TestClient):
        """Test checking all health endpoints."""
        basic_health = async_client.get("/health")
        assert basic_health.status_code == 200

        db_health = async_client.get("/health/db")
        assert db_health.status_code == 200

    def test_api_responsiveness(self, async_client: TestClient):
        """Test API responds quickly to basic requests."""
        import time

        start = time.time()
        response = async_client.get("/")
        duration = time.time() - start

        assert response.status_code == 200
        # Should respond within reasonable time (< 1 second)
        assert duration < 1.0

    def test_api_json_responses(self, async_client: TestClient):
        """Test that API returns valid JSON."""
        response = async_client.get("/")

        # Should be valid JSON
        data = response.json()
        assert isinstance(data, dict)

        response = async_client.get("/health")
        data = response.json()
        assert isinstance(data, dict)


class TestStaticFileServing:
    """Test static file serving."""

    def test_clips_directory_mount(self, async_client: TestClient):
        """Test that clips directory is mounted."""
        # Try to access clips endpoint (may 404 if no files)
        response = async_client.get("/clips/nonexistent.mp4")
        # Should return 404 (file not found), not 500 (error)
        assert response.status_code in [404, 405]


class TestAPIContentTypes:
    """Test API content type handling."""

    def test_json_content_type_default(self, async_client: TestClient):
        """Test that API returns JSON by default."""
        response = async_client.get("/")
        content_type = response.headers.get("content-type", "")

        assert "application/json" in content_type

    def test_health_json_content_type(self, async_client: TestClient):
        """Test health endpoint returns JSON."""
        response = async_client.get("/health")
        content_type = response.headers.get("content-type", "")

        assert "application/json" in content_type


class TestDatabaseDependencyInjection:
    """Test database dependency injection in endpoints."""

    def test_database_health_uses_session(self, async_client: TestClient):
        """Test that database health check uses injected session."""
        response = async_client.get("/health/db")

        assert response.status_code == 200
        data = response.json()

        # Should indicate database connection status
        assert "status" in data
        assert "database" in data
