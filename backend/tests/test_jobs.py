"""
Job Matching Service Tests

Tests for:
- Job search functionality
- Hybrid search (vector + keyword)
- Job filtering
- Job bookmarking
"""
import pytest
import pytest_asyncio


class TestJobSearch:
    """Test job search endpoints"""
    
    @pytest.mark.asyncio
    async def test_search_jobs_basic(self, authenticated_client):
        """Test basic job search"""
        response = await authenticated_client.post(
            "/api/v1/jobs/match",
            json={
                "user_query_preference": {
                    "keywords": "产品经理"
                },
                "search_mode": "hybrid",
                "top_k": 10
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "status" in data
        assert data["status"] == "success"
        assert "data" in data
        assert isinstance(data["data"], list)
    
    @pytest.mark.asyncio
    async def test_search_with_filters(self, authenticated_client):
        """Test job search with filters"""
        response = await authenticated_client.post(
            "/api/v1/jobs/match",
            json={
                "user_query_preference": {
                    "keywords": "工程师"
                },
                "hard_filters": {
                    "city": ["北京", "上海"]
                },
                "search_mode": "vector",
                "top_k": 5
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "status" in data
        assert data["status"] == "success"
    
    @pytest.mark.asyncio
    async def test_search_keyword_mode(self, authenticated_client):
        """Test keyword-based search mode"""
        response = await authenticated_client.post(
            "/api/v1/jobs/match",
            json={
                "user_query_preference": {
                    "keywords": "Java开发"
                },
                "search_mode": "keyword",
                "top_k": 10
            }
        )
        
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_search_vector_mode(self, authenticated_client):
        """Test vector-based search mode"""
        response = await authenticated_client.post(
            "/api/v1/jobs/match",
            json={
                "user_query_preference": {
                    "keywords": "数据科学家"
                },
                "search_mode": "vector",
                "top_k": 10
            }
        )
        
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_search_without_auth(self, client):
        """Test job search without authentication"""
        response = await client.post(
            "/api/v1/jobs/match",
            json={
                "user_query_preference": {
                    "keywords": "测试"
                }
            }
        )
        
        assert response.status_code == 401


class TestJobBookmarking:
    """Test job bookmark functionality"""
    
    @pytest.mark.asyncio
    async def test_bookmark_job(self, authenticated_client):
        """Test bookmarking a job"""
        # First search for a job
        search_response = await authenticated_client.post(
            "/api/v1/jobs/match",
            json={
                "user_query_preference": {"keywords": "测试"},
                "top_k": 1
            }
        )
        
        if search_response.status_code == 200:
            results = search_response.json()["data"]
            if results:
                job_id = results[0]["id"]
                
                # Bookmark the job (endpoint may not exist yet)
                # This is a placeholder for future implementation
                pass
    
    @pytest.mark.asyncio
    async def test_get_bookmarked_jobs(self, authenticated_client):
        """Test getting bookmarked jobs"""
        # Endpoint may not be implemented yet
        # This is a placeholder for future implementation
        pass
    
    @pytest.mark.asyncio
    async def test_unbookmark_job(self, authenticated_client):
        """Test removing a bookmark"""
        # Endpoint may not be implemented yet
        # This is a placeholder for future implementation
        pass


class TestJobDetails:
    """Test job detail endpoints"""
    
    @pytest.mark.asyncio
    async def test_get_job_details(self, authenticated_client):
        """Test getting job details"""
        # Search for a job first
        search_response = await authenticated_client.post(
            "/api/v1/jobs/match",
            json={
                "user_query_preference": {"keywords": "测试"},
                "top_k": 1
            }
        )
        
        if search_response.status_code == 200:
            results = search_response.json()["data"]
            if results:
                job_id = results[0]["id"]
                
                # Get job details
                details_response = await authenticated_client.get(f"/api/v1/jobs/{job_id}")
                
                assert details_response.status_code == 200
                data = details_response.json()
                
                assert "id" in data
                assert "company" in data or "title" in data


class TestJobExport:
    """Test job export functionality"""
    
    @pytest.mark.asyncio
    async def test_export_jobs_csv(self, authenticated_client):
        """Test exporting jobs to CSV"""
        response = await authenticated_client.post(
            "/api/v1/jobs/export",
            json={
                "format": "csv",
                "job_ids": []  # Empty means export all matched jobs
            }
        )
        
        # Should return file download or success
        assert response.status_code in [200, 202]
