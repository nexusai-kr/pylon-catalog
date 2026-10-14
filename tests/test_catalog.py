import hashlib
import io
import json
import zipfile

import catalog_lib as lib

SHA = "a" * 64
GOOD = {
    "name": "google-gmail", "display_name": "Gmail", "description": "메일", "version": "0.1.0",
    "repository": "https://github.com/nexusai-kr/pylon-mcp-google-gmail", "license": "Apache-2.0",
    "download": "https://github.com/nexusai-kr/pylon-mcp-google-gmail/releases/download/v0.1.0/google-gmail-0.1.0.mcpb",
    "sha256": SHA, "platforms": ["linux-x86_64"],
    "requires": {"connection": "google", "scopes": ["https://www.googleapis.com/auth/gmail.readonly"]},
    "tools": ["search_messages"],
}


def cat(*servers, plugins=()):
    return {"schema_version": 2, "name": "c", "display_name": "C", "servers": list(servers), "plugins": list(plugins)}


def mcpb(name="google-gmail", version="0.1.0"):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("manifest.json", json.dumps({"name": name, "version": version}))
    return buf.getvalue()


def test_committed_catalog_is_valid():
    assert lib.validate(lib.load()) == []


def test_good_entry_passes():
    assert lib.validate(cat(GOOD)) == []


def test_schema_violations_are_reported():
    bad = {**GOOD, "sha256": "xyz", "name": "Bad Name", "platforms": []}
    errors = " ".join(lib.validate(cat(bad)))
    assert "sha256" in errors and "name" in errors and "platforms" in errors


def test_duplicate_names_are_rejected():
    assert any("중복" in e for e in lib.validate(cat(GOOD, GOOD)))


def test_untrusted_owner_is_rejected():
    other = {**GOOD, "repository": "https://github.com/evil/x",
             "download": "https://github.com/evil/x/releases/download/v0.1.0/google-gmail-0.1.0.mcpb"}
    assert any("신뢰 목록" in e for e in lib.validate(cat(other)))


def test_download_must_belong_to_the_listed_repository_and_version():
    other_repo = {**GOOD, "download": "https://github.com/nexusai-kr/other/releases/download/v0.1.0/google-gmail-0.1.0.mcpb"}
    assert any("Release 가 아닙니다" in e for e in lib.validate(cat(other_repo)))
    wrong_version = {**GOOD, "version": "0.2.0"}
    assert any("버전" in e for e in lib.validate(cat(wrong_version)))


def test_download_must_be_a_github_release_mcpb():
    http = {**GOOD, "download": "http://example.com/google-gmail-0.1.0.mcpb"}
    assert lib.validate(cat(http))


def test_verify_bundle_checks_hash_name_and_version():
    data = mcpb()
    ok = {**GOOD, "sha256": hashlib.sha256(data).hexdigest()}
    assert lib.verify_bundle(ok, data) == []
    assert any("sha256" in e for e in lib.verify_bundle(GOOD, data))
    assert any("name" in e for e in lib.verify_bundle({**ok}, mcpb(name="other")))
    assert any("version" in e for e in lib.verify_bundle({**ok}, mcpb(version="9.9.9")))
    assert any("읽을 수 없습니다" in e for e in lib.verify_bundle(GOOD, b"not a zip"))


def test_verify_bundle_rejects_path_traversal_but_allows_dots_in_names():
    def build(extra):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("manifest.json", json.dumps({"name": "google-gmail", "version": "0.1.0"}))
            zf.writestr(extra, "x")
        return buf.getvalue()

    def entry(data):
        return {**GOOD, "sha256": hashlib.sha256(data).hexdigest()}

    bad, fine = build("../evil"), build("lib/a..b/c.py")
    assert any("경로" in e for e in lib.verify_bundle(entry(bad), bad))
    assert lib.verify_bundle(entry(fine), fine) == []


# ── 플러그인 ──────────────────────────────────────────────
def plugin_zip(name="news", version="1.0.0", extra=None, top="news/"):
    files = {
        f"{top}.claude-plugin/plugin.json": json.dumps({"name": name, "version": version}),
        f"{top}skills/a/SKILL.md": "---\nname: a\n---\nA",
        f"{top}agents/rev.md": "---\nname: rev\n---\n",
        **{f"{top}{k}": v for k, v in (extra or {}).items()},
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for p, b in files.items():
            zf.writestr(p, b)
    return buf.getvalue()


def plugin_entry(data, **over):
    return {
        "name": "news", "display_name": "뉴스", "description": "뉴스 쇼츠", "version": "1.0.0",
        "repository": "https://github.com/nexusai-kr/pylon-plugin-news", "license": "Apache-2.0",
        "download": "https://github.com/nexusai-kr/pylon-plugin-news/releases/download/v1.0.0/news-1.0.0.zip",
        "sha256": hashlib.sha256(data).hexdigest(),
        "components": {"skills": ["a"], "agents": ["rev"]}, "contains": {"hooks": False, "tools": False},
        "requires": {"mcp": ["news-shorts"]},
        **over,
    }


def test_plugin_entry_passes_schema_and_verification():
    data = plugin_zip()
    entry = plugin_entry(data)
    assert lib.validate(cat(plugins=[entry])) == []
    assert lib.verify_plugin(entry, data) == []


def test_plugin_download_must_be_a_zip_release_with_version():
    data = plugin_zip()
    bad = plugin_entry(data, download="https://github.com/nexusai-kr/pylon-plugin-news/releases/download/v1.0.0/news-1.0.0.mcpb")
    assert lib.validate(cat(plugins=[bad]))
    assert any("버전" in e for e in lib.validate(cat(plugins=[plugin_entry(data, version="2.0.0")])))
    assert any("중복" in e for e in lib.validate(cat(plugins=[plugin_entry(data), plugin_entry(data)])))
    other = plugin_entry(data, repository="https://github.com/evil/x", download="https://github.com/evil/x/releases/download/v1.0.0/news-1.0.0.zip")
    assert any("신뢰 목록" in e for e in lib.validate(cat(plugins=[other])))


def test_plugin_verification_catches_mismatches():
    data = plugin_zip()
    entry = plugin_entry(data)
    assert any("sha256" in e for e in lib.verify_plugin({**entry, "sha256": SHA}, data))
    assert any("name" in e for e in lib.verify_plugin(entry, plugin_zip(name="other")))
    assert any("version" in e for e in lib.verify_plugin(entry, plugin_zip(version="9.9.9")))
    assert any("components.skills" in e for e in lib.verify_plugin({**entry, "components": {"skills": ["x"]}}, data))
    assert any("스킬·에이전트" in e for e in lib.verify_plugin(entry, _empty_plugin()))


def _empty_plugin():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(".claude-plugin/plugin.json", json.dumps({"name": "news", "version": "1.0.0"}))
    return buf.getvalue()


def test_hooks_and_tools_must_be_declared():
    data = plugin_zip(extra={"hooks/hooks.json": "{}", "tools/render.py": "x=1"})
    entry = plugin_entry(data, **{"sha256": hashlib.sha256(data).hexdigest()})
    errors = " ".join(lib.verify_plugin(entry, data))
    assert "contains.hooks" in errors and "contains.tools" in errors
    declared = {**entry, "contains": {"hooks": True, "tools": True}}
    assert lib.verify_plugin(declared, data) == []
    omitted = {k: v for k, v in entry.items() if k != "contains"}
    assert any("contains.hooks" in e for e in lib.verify_plugin(omitted, data))


def test_plugin_path_traversal_rejected():
    data = plugin_zip(extra={"../evil": "x"}, top="")
    entry = plugin_entry(data)
    assert any("경로" in e for e in lib.verify_plugin(entry, data))
