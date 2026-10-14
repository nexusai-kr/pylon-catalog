#!/usr/bin/env python3
"""저장소의 Release 를 읽어 catalog.json 항목을 만들거나 갱신한다. gh CLI 가 필요하다.

    scripts/update_catalog.py nexusai-kr/pylon-mcp-google-gmail v0.1.0     # 서버 (.mcpb)
    scripts/update_catalog.py nexusai-kr/pylon-plugin-news v1.0.0          # 플러그인 (.zip)

Release 의 `<name>-<버전>.mcpb` 또는 `.zip` 과 `.sha256` 을 읽는다. 서버는 그 태그의 manifest.json,
플러그인은 내려받은 zip 의 plugin.json 과 구성물을 읽는다. 결과는 PR 로 올려 검토한 뒤 합친다.
"""

from __future__ import annotations

import json
import subprocess
import sys

from catalog_lib import ROOT, fetch, inspect_plugin, load, validate


def gh(*args: str) -> str:
    return subprocess.run(["gh", *args], check=True, capture_output=True, text=True).stdout


def release_asset(repo: str, tag: str) -> tuple[str, dict, str]:
    """(종류 'servers'|'plugins', 파일 asset, sha256)."""
    rel = json.loads(gh("api", f"repos/{repo}/releases/tags/{tag}"))
    assets = {a["name"]: a for a in rel["assets"]}
    found = [(k, a) for n, a in assets.items() for k, ext in (("servers", ".mcpb"), ("plugins", ".zip")) if n.endswith(ext)]
    if len(found) != 1 or f"{found[0][1]['name']}.sha256" not in assets:
        raise SystemExit(f"{repo} {tag}: Release 에 .mcpb 또는 .zip 하나와 그 .sha256 이 있어야 합니다")
    kind, mcpb = found[0]
    sha = gh("api", "-H", "Accept: application/octet-stream", f"repos/{repo}/releases/assets/{assets[mcpb['name'] + '.sha256']['id']}").split()[0]
    return kind, mcpb, sha


def build_plugin_entry(repo: str, tag: str, mcpb: dict, sha: str) -> dict:
    data = fetch(mcpb["browser_download_url"])
    info = inspect_plugin(data)
    entry = {
        "name": info["name"], "display_name": info["name"], "description": "", "version": str(info["version"]),
        "repository": f"https://github.com/{repo}", "license": "",
        "download": mcpb["browser_download_url"], "sha256": sha, "size_bytes": mcpb["size"],
        "components": {"skills": info["skills"], "agents": info["agents"]}, "contains": info["contains"],
    }
    raw = json.loads(gh("api", "-H", "Accept: application/vnd.github.raw", f"repos/{repo}/contents/.claude-plugin/plugin.json?ref={tag}"))
    entry["display_name"] = raw.get("display_name", entry["name"])
    entry["description"] = raw.get("description", "")
    entry["license"] = raw.get("license", "")
    return entry


def build_entry(repo: str, tag: str) -> dict:
    kind, mcpb, sha = release_asset(repo, tag)
    if kind == "plugins":
        return build_plugin_entry(repo, tag, mcpb, sha)
    raw = gh("api", "-H", "Accept: application/vnd.github.raw", f"repos/{repo}/contents/manifest.json?ref={tag}")
    m = json.loads(raw)
    meta = m.get("_meta", {}).get("io.pylon.grid", {})
    entry = {
        "name": m["name"], "display_name": m.get("display_name", m["name"]), "description": m.get("description", ""),
        "version": m["version"], "repository": f"https://github.com/{repo}", "license": m.get("license", ""),
        "download": mcpb["browser_download_url"], "sha256": sha, "size_bytes": mcpb["size"],
        "platforms": meta.get("platforms", ["any"]),
        "tools": [t["name"] for t in m.get("tools", [])],
    }
    if meta.get("requires_connection"):
        entry["requires"] = {"connection": meta["requires_connection"], "scopes": meta.get("delegation", {}).get("scopes", [])}
    return entry


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    entry = build_entry(sys.argv[1], sys.argv[2])
    key = "plugins" if entry["download"].endswith(".zip") else "servers"
    catalog = load()
    items = [s for s in catalog[key] if s["name"] != entry["name"]] + [entry]
    catalog[key] = sorted(items, key=lambda s: s["name"])
    errors = validate(catalog)
    if errors:
        raise SystemExit("\n".join(errors))
    (ROOT / "catalog.json").write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{entry['name']} {entry['version']} 반영")


if __name__ == "__main__":
    main()
