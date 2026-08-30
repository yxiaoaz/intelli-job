"""Settings.effective_chat_providers 单元测试。

覆盖：
- YAML 存在 → 返回全部供应商，${VAR} 正确展开
- ${VAR} 引用的环境变量缺失 → 该条目被跳过
- YAML 不存在 → 回退 LLM_COMPLETION_API_* 单供应商
- YAML 存在但 providers 为空 → 同样回退
- 缺 name/api_url/model_name 字段的条目 → 被过滤
"""

import pytest
from pydantic_settings import SettingsConfigDict

from app.config import Settings

# Settings 必填字段的最小取值（_env_file=None 隔离本地 .env）
REQUIRED_KWARGS = {
    "LLM_COMPLETION_API_KEY": "fallback-key",
    "LLM_EMBEDDING_API_KEY": "embedding-key",
    "ZILLIZ_URI": "https://zilliz.test",
    "ZILLIZ_TOKEN": "zilliz-token",
    "_env_file": None,
}


def _make_settings(**overrides) -> Settings:
    kwargs = {**REQUIRED_KWARGS, **overrides}
    kwargs.pop("_env_file", None)
    return Settings(**kwargs, _env_file=None)


# ── YAML 存在：${VAR} 展开 ────────────────────────────────────────────────

class TestYamlProviders:

    def test_yaml_providers_expanded(self, monkeypatch):
        """completion_providers 非空 → 展开占位符后返回全部供应商。"""
        monkeypatch.setenv("LLM_DEEPSEEK_API_KEY", "sk-deepseek-123")
        monkeypatch.setenv("LLM_QWEN_API_KEY", "sk-qwen-456")
        settings = _make_settings(
            completion_providers=[
                {
                    "name": "deepseek",
                    "api_url": "https://api.deepseek.com",
                    "api_key": "${LLM_DEEPSEEK_API_KEY}",
                    "model_name": "deepseek-chat",
                },
                {
                    "name": "qwen",
                    "api_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                    "api_key": "${LLM_QWEN_API_KEY}",
                    "model_name": "qwen-plus",
                },
            ]
        )

        providers = settings.effective_chat_providers
        assert [p["name"] for p in providers] == ["deepseek", "qwen"]
        assert providers[0]["api_key"] == "sk-deepseek-123"
        assert providers[1]["api_key"] == "sk-qwen-456"

    def test_expansion_falls_back_to_settings_fields(self):
        """${VAR} 不在 os.environ 时，回退到 .env 加载的 Settings 字段。"""
        settings = _make_settings(
            LLM_GLM_API_KEY="sk-glm-from-env-file",
            completion_providers=[
                {
                    "name": "glm",
                    "api_url": "https://open.bigmodel.cn/api/paas/v4",
                    "api_key": "${LLM_GLM_API_KEY}",
                    "model_name": "glm-4.7-flash",
                }
            ],
        )

        providers = settings.effective_chat_providers
        assert len(providers) == 1
        assert providers[0]["api_key"] == "sk-glm-from-env-file"

    def test_missing_env_var_entry_skipped(self, monkeypatch):
        """${VAR} 展开后为空的条目被跳过，其余条目保留。"""
        monkeypatch.delenv("LLM_GLM_API_KEY", raising=False)
        settings = _make_settings(
            LLM_GLM_API_KEY="",
            completion_providers=[
                {
                    "name": "glm",
                    "api_url": "https://open.bigmodel.cn/api/paas/v4",
                    "api_key": "${LLM_GLM_API_KEY}",
                    "model_name": "glm-4.7-flash",
                },
                {
                    "name": "deepseek",
                    "api_url": "https://api.deepseek.com",
                    "api_key": "literal-key",
                    "model_name": "deepseek-chat",
                },
            ],
        )

        providers = settings.effective_chat_providers
        assert [p["name"] for p in providers] == ["deepseek"]

    def test_entries_missing_required_fields_filtered(self):
        """缺 name/api_url/model_name 字段的条目被过滤。"""
        settings = _make_settings(
            completion_providers=[
                {"api_url": "https://x", "api_key": "k", "model_name": "m"},   # 缺 name
                {"name": "bad", "api_key": "k", "model_name": "m"},            # 缺 api_url
                {"name": "bad", "api_url": "https://x", "api_key": "k"},       # 缺 model_name
                {"name": "good", "api_url": "https://x", "api_key": "k",
                 "model_name": "m"},
            ]
        )

        providers = settings.effective_chat_providers
        assert [p["name"] for p in providers] == ["good"]

    def test_all_entries_filtered_falls_back(self, monkeypatch):
        """YAML 存在但全部条目被过滤 → 回退旧环境变量单供应商。"""
        monkeypatch.delenv("LLM_GLM_API_KEY", raising=False)
        settings = _make_settings(
            LLM_GLM_API_KEY="",
            completion_providers=[
                {
                    "name": "glm",
                    "api_url": "https://open.bigmodel.cn/api/paas/v4",
                    "api_key": "${LLM_GLM_API_KEY}",
                    "model_name": "glm-4.7-flash",
                }
            ],
        )

        providers = settings.effective_chat_providers
        assert len(providers) == 1
        assert providers[0]["name"] == "deepseek"
        assert providers[0]["api_key"] == "fallback-key"


# ── YAML 缺失 / 为空：回退单供应商 ────────────────────────────────────────

class TestFallbackProviders:

    def test_no_yaml_falls_back(self):
        """YAML 不存在（completion_providers 为默认空）→ 回退单供应商。"""
        settings = _make_settings()

        providers = settings.effective_chat_providers
        assert len(providers) == 1
        assert providers[0]["name"] == "deepseek"
        assert providers[0]["model_name"] == "deepseek-chat"
        assert providers[0]["api_key"] == "fallback-key"

    def test_empty_yaml_providers_falls_back(self):
        """YAML 存在但 providers 为空 → 同样回退。"""
        settings = _make_settings(completion_providers=[])

        providers = settings.effective_chat_providers
        assert len(providers) == 1
        assert providers[0]["api_key"] == "fallback-key"

    def test_fallback_uses_env_values(self):
        """回退单供应商取 LLM_COMPLETION_API_* 的实际值。"""
        settings = _make_settings(
            LLM_COMPLETION_API_URL="https://custom.api",
            LLM_COMPLETION_API_MODEL_NAME="custom-model",
        )

        providers = settings.effective_chat_providers
        assert providers[0]["api_url"] == "https://custom.api"
        assert providers[0]["model_name"] == "custom-model"


# ── 真实 YAML 文件加载（YamlConfigSettingsSource 接线验证）────────────────

class TestYamlFileLoading:

    def test_yaml_file_loaded_into_settings(self, tmp_path):
        """yaml_file 指向真实文件时，completion_providers / timeout 被正确加载。"""
        yaml_file = tmp_path / "llm_providers.yaml"
        yaml_file.write_text(
            "completion_timeout_seconds: 90\n"
            "completion_providers:\n"
            "  - name: deepseek\n"
            "    api_url: https://api.deepseek.com\n"
            "    api_key: literal-test-key\n"
            "    model_name: deepseek-chat\n",
            encoding="utf-8",
        )

        class _YamlSettings(Settings):
            model_config = SettingsConfigDict(
                env_file=None,
                yaml_file=str(yaml_file),
                yaml_file_encoding="utf-8",
                case_sensitive=False,
                extra="ignore",
            )

        settings = _YamlSettings(**REQUIRED_KWARGS)
        assert settings.completion_timeout_seconds == 90
        assert settings.completion_providers[0]["name"] == "deepseek"

        providers = settings.effective_chat_providers
        assert len(providers) == 1
        assert providers[0]["api_key"] == "literal-test-key"

    def test_missing_yaml_file_ignored(self, tmp_path):
        """yaml_file 指向不存在的文件 → 自动忽略，字段保持默认。"""
        class _YamlSettings(Settings):
            model_config = SettingsConfigDict(
                env_file=None,
                yaml_file=str(tmp_path / "not_exists.yaml"),
                yaml_file_encoding="utf-8",
                case_sensitive=False,
                extra="ignore",
            )

        settings = _YamlSettings(**REQUIRED_KWARGS)
        assert settings.completion_providers == []
        assert settings.completion_timeout_seconds == 60

    def test_invalid_yaml_content_falls_back(self, tmp_path):
        """YAML 解析失败（如损坏内容/被误建为目录）→ 不阻塞启动，回退默认值。"""
        # 目录被 Docker volume 挂载误建为文件路径的场景
        not_a_file = tmp_path / "llm_providers.yaml"
        not_a_file.mkdir()

        class _YamlSettings(Settings):
            model_config = SettingsConfigDict(
                env_file=None,
                yaml_file=str(not_a_file),
                yaml_file_encoding="utf-8",
                case_sensitive=False,
                extra="ignore",
            )

        settings = _YamlSettings(**REQUIRED_KWARGS)
        assert settings.completion_providers == []
        assert settings.completion_timeout_seconds == 60

        providers = settings.effective_chat_providers
        assert len(providers) == 1
        assert providers[0]["api_key"] == "fallback-key"

    def test_malformed_yaml_syntax_falls_back(self, tmp_path):
        """YAML 语法错误 → 记 warning 并回退，不抛异常。"""
        bad_yaml = tmp_path / "llm_providers.yaml"
        bad_yaml.write_text(
            "completion_providers: [unclosed\n  bad_indent: : :",
            encoding="utf-8",
        )

        class _YamlSettings(Settings):
            model_config = SettingsConfigDict(
                env_file=None,
                yaml_file=str(bad_yaml),
                yaml_file_encoding="utf-8",
                case_sensitive=False,
                extra="ignore",
            )

        settings = _YamlSettings(**REQUIRED_KWARGS)
        assert settings.completion_providers == []
        assert settings.effective_chat_providers[0]["name"] == "deepseek"
