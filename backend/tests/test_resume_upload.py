"""
Tests for ResumeUploadService
"""
import pytest
import uuid
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
from fastapi import UploadFile, HTTPException

from app.services.resume_upload_service import ResumeUploadService


class TestResumeUploadService:
    """简历上传服务测试"""
    
    @pytest.fixture
    def upload_service(self, tmp_path):
        """创建上传服务实例，使用临时目录"""
        return ResumeUploadService(storage_root=str(tmp_path))
    
    @pytest.fixture
    def mock_pdf_file(self):
        """模拟 PDF 文件"""
        file = Mock(spec=UploadFile)
        file.filename = "test_resume.pdf"
        file.content_type = "application/pdf"
        file.size = 1024 * 100  # 100KB
        file.read = AsyncMock(return_value=b"fake pdf content")
        return file
    
    @pytest.fixture
    def mock_docx_file(self):
        """模拟 DOCX 文件"""
        file = Mock(spec=UploadFile)
        file.filename = "test_resume.docx"
        file.content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        file.size = 1024 * 200  # 200KB
        file.read = AsyncMock(return_value=b"fake docx content")
        return file
    
    def test_validate_file_success_pdf(self, upload_service, mock_pdf_file):
        """测试 PDF 文件验证通过"""
        # 不应该抛出异常
        upload_service.validate_file(mock_pdf_file)
    
    def test_validate_file_success_docx(self, upload_service, mock_docx_file):
        """测试 DOCX 文件验证通过"""
        # 不应该抛出异常
        upload_service.validate_file(mock_docx_file)
    
    def test_validate_file_unsupported_type(self, upload_service):
        """测试不支持的文件类型"""
        file = Mock(spec=UploadFile)
        file.filename = "test.jpg"
        file.content_type = "image/jpeg"
        file.size = 1024
        
        with pytest.raises(HTTPException) as exc_info:
            upload_service.validate_file(file)
        
        assert exc_info.value.status_code == 415
        assert "不支持的文件类型" in exc_info.value.detail
    
    def test_validate_file_too_large(self, upload_service):
        """测试文件过大"""
        file = Mock(spec=UploadFile)
        file.filename = "large_resume.pdf"
        file.content_type = "application/pdf"
        file.size = 11 * 1024 * 1024  # 11MB
        
        with pytest.raises(HTTPException) as exc_info:
            upload_service.validate_file(file)
        
        assert exc_info.value.status_code == 413
        assert "文件大小不能超过" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_save_file_success(self, upload_service, mock_pdf_file):
        """测试文件保存成功"""
        user_id = uuid.uuid4()
        
        file_info = await upload_service.save_file(mock_pdf_file, user_id)
        
        assert "filename" in file_info
        assert "file_path" in file_info
        assert "file_size" in file_info
        assert file_info["content_type"] == "application/pdf"
        assert file_info["original_filename"] == "test_resume.pdf"
        
        # 验证文件已实际保存
        file_path = Path(file_info["file_path"])
        assert file_path.exists()
        assert file_path.parent.name == str(user_id)
    
    @pytest.mark.asyncio
    async def test_save_file_creates_user_directory(self, upload_service, mock_pdf_file):
        """测试创建用户专属目录"""
        user_id = uuid.uuid4()
        
        await upload_service.save_file(mock_pdf_file, user_id)
        
        user_dir = upload_service.storage_root / str(user_id)
        assert user_dir.exists()
        assert user_dir.is_dir()
    
    @pytest.mark.asyncio
    async def test_save_file_unique_names(self, upload_service, mock_pdf_file):
        """测试生成唯一文件名"""
        user_id = uuid.uuid4()
        
        # 保存两次相同文件
        info1 = await upload_service.save_file(mock_pdf_file, user_id)
        info2 = await upload_service.save_file(mock_pdf_file, user_id)
        
        # 文件名应该不同
        assert info1["filename"] != info2["filename"]
    
    def test_delete_file_success(self, upload_service, mock_pdf_file, tmp_path):
        """测试删除文件成功"""
        # 先创建一个测试文件
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")
        
        result = upload_service.delete_file(str(test_file))
        
        assert result is True
        assert not test_file.exists()
    
    def test_delete_file_not_exists(self, upload_service):
        """测试删除不存在的文件"""
        result = upload_service.delete_file("/nonexistent/file.txt")
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_save_file_content_size_check(self, upload_service):
        """测试文件内容大小检查"""
        file = Mock(spec=UploadFile)
        file.filename = "test.pdf"
        file.content_type = "application/pdf"
        file.size = 1024  # 报告的大小很小
        # 但实际读取的内容很大
        file.read = AsyncMock(return_value=b"x" * (11 * 1024 * 1024))  # 11MB
        
        user_id = uuid.uuid4()
        
        with pytest.raises(HTTPException) as exc_info:
            await upload_service.save_file(file, user_id)
        
        assert exc_info.value.status_code == 413
