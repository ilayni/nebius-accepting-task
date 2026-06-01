"""Tests for content extraction logic."""

import pytest

from app.content_extractor import (
    build_tree_text,
    classify_file,
    select_files,
    should_ignore,
    truncate,
    build_prompt_content,
    ExtractedContent,
)


class TestShouldIgnore:
    def test_node_modules(self):
        assert should_ignore("node_modules/express/index.js") is True

    def test_pycache(self):
        assert should_ignore("src/__pycache__/foo.cpython-311.pyc") is True

    def test_git_dir(self):
        assert should_ignore(".git/config") is True

    def test_normal_python_file(self):
        assert should_ignore("src/main.py") is False

    def test_readme(self):
        assert should_ignore("README.md") is False

    def test_lock_file(self):
        assert should_ignore("package-lock.json") is True

    def test_image(self):
        assert should_ignore("assets/logo.png") is True

    def test_minified_js(self):
        assert should_ignore("dist/bundle.min.js") is True

    def test_binary(self):
        assert should_ignore("bin/app.exe") is True

    def test_deep_venv(self):
        assert should_ignore("venv/lib/python3.11/site.py") is True

    def test_svg(self):
        assert should_ignore("docs/diagram.svg") is True

    def test_vendor_dir(self):
        assert should_ignore("vendor/github.com/pkg/errors/errors.go") is True


class TestClassifyFile:
    def test_package_json_is_tier1(self):
        assert classify_file("package.json") == 1

    def test_pyproject_toml_is_tier1(self):
        assert classify_file("pyproject.toml") == 1

    def test_dockerfile_is_tier1(self):
        assert classify_file("Dockerfile") == 1

    def test_ci_config_is_tier1(self):
        assert classify_file(".github/workflows/ci.yml") == 1

    def test_main_py_root_is_tier2(self):
        assert classify_file("main.py") == 2

    def test_main_py_in_src_is_tier2(self):
        assert classify_file("src/main.py") == 2

    def test_main_py_deep_is_not_tier2(self):
        assert classify_file("src/pkg/sub/main.py") == 0

    def test_openapi_is_tier2(self):
        assert classify_file("openapi.yaml") == 2

    def test_proto_is_tier2(self):
        assert classify_file("api/service.proto") == 2

    def test_random_source_is_tier0(self):
        assert classify_file("src/utils/helpers.py") == 0

    def test_requirements_txt_is_tier1(self):
        assert classify_file("requirements.txt") == 1


class TestBuildTreeText:
    def test_basic_tree(self):
        tree = [
            {"path": "src", "type": "tree"},
            {"path": "src/main.py", "type": "blob"},
            {"path": "README.md", "type": "blob"},
        ]
        result = build_tree_text(tree)
        assert "src/" in result
        assert "main.py" in result
        assert "README.md" in result

    def test_ignores_node_modules(self):
        tree = [
            {"path": "node_modules", "type": "tree"},
            {"path": "node_modules/express/index.js", "type": "blob"},
            {"path": "src/main.py", "type": "blob"},
        ]
        result = build_tree_text(tree)
        assert "node_modules" not in result
        assert "main.py" in result

    def test_max_depth(self):
        tree = [
            {"path": "a/b/c/d/e/deep.py", "type": "blob"},
            {"path": "top.py", "type": "blob"},
        ]
        result = build_tree_text(tree)
        assert "deep.py" not in result
        assert "top.py" in result

    def test_truncation(self):
        tree = [{"path": f"file{i}.py", "type": "blob"} for i in range(200)]
        result = build_tree_text(tree, max_lines=10)
        assert "truncated" in result


class TestTruncate:
    def test_no_truncation_needed(self):
        assert truncate("short", 100) == "short"

    def test_truncation(self):
        result = truncate("a" * 200, 50)
        assert len(result) < 200
        assert "truncated" in result


class TestSelectFiles:
    def test_selects_tier1_and_tier2(self):
        tree = [
            {"path": "package.json", "type": "blob", "size": 500},
            {"path": "main.py", "type": "blob", "size": 1000},
            {"path": "src/utils.py", "type": "blob", "size": 2000},
            {"path": "node_modules/foo.js", "type": "blob", "size": 100},
        ]
        t1, t2 = select_files(tree)
        assert "package.json" in t1
        assert "main.py" in t2
        assert "src/utils.py" not in t1 and "src/utils.py" not in t2
        assert "node_modules/foo.js" not in t1 and "node_modules/foo.js" not in t2

    def test_skips_large_files(self):
        tree = [
            {"path": "package.json", "type": "blob", "size": 500_000},
        ]
        t1, t2 = select_files(tree)
        assert "package.json" not in t1

    def test_skips_directories(self):
        tree = [
            {"path": "src", "type": "tree"},
        ]
        t1, t2 = select_files(tree)
        assert len(t1) == 0 and len(t2) == 0


class TestBuildPromptContent:
    def test_includes_all_sections(self):
        content = ExtractedContent(
            readme="# My Project\nA cool project.",
            tree_text="src/\n  main.py",
            languages={"Python": 10000, "JavaScript": 5000},
            tier1_files={"package.json": '{"name": "test"}'},
            tier2_files={"main.py": 'print("hello")'},
        )
        result = build_prompt_content(content)
        assert "LANGUAGES" in result
        assert "DIRECTORY STRUCTURE" in result
        assert "README" in result
        assert "package.json" in result
        assert "main.py" in result

    def test_empty_content(self):
        content = ExtractedContent()
        result = build_prompt_content(content)
        assert result == ""
