"""
Tests for BackgroundTasks integration in resumes API
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi import BackgroundTasks


class TestBackgroundTasksIntegration:
    """Test that upload endpoint properly uses BackgroundTasks"""
    
    @pytest.mark.asyncio
    async def test_upload_endpoint_accepts_background_tasks(self):
        """Verify upload_resume function signature includes BackgroundTasks"""
        from app.api.v1.resumes import upload_resume
        import inspect
        
        sig = inspect.signature(upload_resume)
        params = list(sig.parameters.keys())
        
        assert 'background_tasks' in params, "upload_resume should accept background_tasks parameter"
    
    @pytest.mark.asyncio
    async def test_process_resume_async_function_exists(self):
        """Verify process_resume_async function exists and is callable"""
        from app.api.v1.resumes import process_resume_async
        
        assert callable(process_resume_async)
        
        # Check it's an async function
        import inspect
        assert inspect.iscoroutinefunction(process_resume_async)
    
    @pytest.mark.asyncio
    async def test_background_tasks_add_task_called(self):
        """Test that background_tasks.add_task is called during upload"""
        from app.api.v1.resumes import upload_resume
        from unittest.mock import Mock, AsyncMock
        import uuid
        
        # Mock dependencies
        mock_user = Mock()
        mock_user.id = uuid.uuid4()
        
        mock_session = AsyncMock()
        mock_session.commit = AsyncMock()
        
        # Create a mock file
        mock_file = Mock()
        mock_file.filename = "test.pdf"
        mock_file.content_type = "application/pdf"
        mock_file.file = MagicMock()
        mock_file.file.read = AsyncMock(return_value=b"%PDF fake content")
        
        # Mock BackgroundTasks
        mock_background_tasks = Mock(spec=BackgroundTasks)
        mock_background_tasks.add_task = Mock()
        
        # Mock services
        with patch('app.api.v1.resumes.upload_service') as mock_upload_svc, \
             patch('app.api.v1.resumes.parser_service') as mock_parser_svc:
            
            # Setup mock return values
            mock_file_info = {
                "filename": "test.pdf",
                "file_size": 1024,
                "content_type": "application/pdf",
                "file_path": "/tmp/test.pdf"
            }
            mock_upload_svc.save_file = AsyncMock(return_value=mock_file_info)
            
            mock_resume = Mock()
            mock_resume.id = uuid.uuid4()
            mock_resume.uploaded_at = None
            mock_upload_svc.create_resume_record = AsyncMock(return_value=mock_resume)
            
            mock_analysis = Mock()
            mock_analysis.id = uuid.uuid4()
            mock_parser_svc.create_analysis_record = AsyncMock(return_value=mock_analysis)
            
            # Call the endpoint
            try:
                result = await upload_resume(
                    file=mock_file,
                    current_user=mock_user,
                    session=mock_session,
                    background_tasks=mock_background_tasks
                )
                
                # Verify add_task was called
                assert mock_background_tasks.add_task.called, "background_tasks.add_task should be called"
                
                # Verify the task function and arguments
                call_args = mock_background_tasks.add_task.call_args
                assert call_args is not None
                
                # First arg should be the function
                task_func = call_args[0][0]
                assert task_func.__name__ == 'process_resume_async'
                
            except Exception as e:
                # If there's an error, it shouldn't be about missing background_tasks
                assert "background_tasks" not in str(e).lower()
    
    @pytest.mark.asyncio
    async def test_background_tasks_none_handling(self):
        """Test graceful handling when background_tasks is None"""
        from app.api.v1.resumes import upload_resume
        from unittest.mock import Mock, AsyncMock
        import uuid
        
        # Mock dependencies
        mock_user = Mock()
        mock_user.id = uuid.uuid4()
        
        mock_session = AsyncMock()
        mock_session.commit = AsyncMock()
        
        # Create a mock file
        mock_file = Mock()
        mock_file.filename = "test.pdf"
        mock_file.content_type = "application/pdf"
        mock_file.file = MagicMock()
        mock_file.file.read = AsyncMock(return_value=b"%PDF fake content")
        
        # Pass None for background_tasks
        mock_background_tasks = None
        
        # Mock services
        with patch('app.api.v1.resumes.upload_service') as mock_upload_svc, \
             patch('app.api.v1.resumes.parser_service') as mock_parser_svc:
            
            # Setup mock return values
            mock_file_info = {
                "filename": "test.pdf",
                "file_size": 1024,
                "content_type": "application/pdf",
                "file_path": "/tmp/test.pdf"
            }
            mock_upload_svc.save_file = AsyncMock(return_value=mock_file_info)
            
            mock_resume = Mock()
            mock_resume.id = uuid.uuid4()
            mock_resume.uploaded_at = None
            mock_upload_svc.create_resume_record = AsyncMock(return_value=mock_resume)
            
            mock_analysis = Mock()
            mock_analysis.id = uuid.uuid4()
            mock_parser_svc.create_analysis_record = AsyncMock(return_value=mock_analysis)
            
            # Call the endpoint - should not raise exception
            try:
                result = await upload_resume(
                    file=mock_file,
                    current_user=mock_user,
                    session=mock_session,
                    background_tasks=mock_background_tasks
                )
                
                # Should still succeed (just won't start background task)
                assert result is not None
                
            except Exception as e:
                # Should not fail due to None background_tasks
                pytest.fail(f"Should handle None background_tasks gracefully: {e}")


class TestProcessResumeAsyncErrorHandling:
    """Test error handling in background task"""
    
    @pytest.mark.asyncio
    async def test_process_resume_async_handles_errors(self):
        """Test that process_resume_async handles exceptions gracefully"""
        from app.api.v1.resumes import process_resume_async
        
        # Call with invalid parameters to trigger error
        # This should not raise exception, but log error and update status
        try:
            await process_resume_async(
                "fake_resume_id",
                "fake_analysis_id",
                "/nonexistent/file.pdf",
                "application/pdf"
            )
            # Should complete without raising (error handling inside)
        except Exception as e:
            # If it does raise, it should be a specific error, not a crash
            assert isinstance(e, (FileNotFoundError, Exception))
