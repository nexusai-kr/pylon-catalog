"""카탈로그 검증 — 스키마, 이름 중복, 신뢰하는 소유자(조직), 다운로드 URL 과 저장소의 일치,
(선택) 실제 파일의 sha256·manifest. 서버(mcpb)와 플러그인(zip) 모두."""

from __future__ import annotations

import hashlib
import io
import json
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
TRUSTED_OWNERS = {"nexusai-kr"}  # 다운로드를 허용하는 GitHub 소유자. 다른 조직을 올리려면 여기에 추가하는 PR 을 별도로 검토한다.
MAX_BYTES = 200 * 1024 * 1024  # Grid 의 번들 상한과 같다
KINDS = {"servers": ("mcpb", "서버"), "plugins": ("zip", "플러그인")}
PLUGIN_MANIFESTS = (".claude-plugin/plugin.json", "plugin.json")


def load(path: Path | None = None) -> dict:
    return json.loads((path or ROOT / "catalog.json").read_text(encoding="utf-8"))


def validate(catalog: dict, schema: dict | None = None) -> list[str]:
    """오류 문장 목록 (비어 있으면 통과)."""
    schema = schema or json.loads((ROOT / "catalog.schema.json").read_text(encoding="utf-8"))
    errors = [
        f"{'/'.join(map(str, e.absolute_path)) or '(root)'}: {e.message}"
        for e in Draft202012Validator(schema).iter_errors(catalog)
    ]
    for key, (ext, _) in KINDS.items():
        seen: set[str] = set()
        for i, s in enumerate(catalog.get(key, [])):
            if not isinstance(s, dict):
                continue
            name = s.get("name", f"#{i}")
            if name in seen:
                errors.append(f"{key}/{name}: 이름이 중복되었습니다")
            seen.add(name)
            repo, dl = s.get("repository", ""), s.get("download", "")
            owner = repo.removeprefix("https://github.com/").split("/")[0] if repo.startswith("https://github.com/") else ""
            if owner and owner not in TRUSTED_OWNERS:
                errors.append(f"{key}/{name}: 신뢰 목록에 없는 소유자입니다 ({owner})")
            if repo and dl and not dl.startswith(repo + "/releases/download/"):
                errors.append(f"{key}/{name}: download 가 repository 의 Release 가 아닙니다")
            if dl and s.get("version") and f"-{s['version']}.{ext}" not in dl:
                errors.append(f"{key}/{name}: download 파일명에 버전({s['version']})이 없습니다")
    return errors


def fetch(url: str, limit: int = MAX_BYTES) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "pylon-catalog"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = resp.read(limit + 1)
    if len(data) > limit:
        raise ValueError(f"{url}: 파일이 상한({limit:,} 바이트)을 넘습니다")
    return data


def _unsafe(names: list[str]) -> bool:
    return any(n.startswith("/") or "\\" in n or ".." in PurePosixPath(n).parts for n in names)


def verify_bundle(server: dict, data: bytes) -> list[str]:
    """내려받은 mcpb 가 카탈로그 항목과 같은지."""
    name, errors = server["name"], []
    if hashlib.sha256(data).hexdigest() != server["sha256"]:
        errors.append(f"servers/{name}: sha256 이 다릅니다")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            manifest = json.loads(zf.read("manifest.json"))
            names = [i.filename for i in zf.infolist()]
    except (zipfile.BadZipFile, KeyError, ValueError) as exc:
        return [*errors, f"servers/{name}: mcpb 를 읽을 수 없습니다 ({exc.__class__.__name__})"]
    if manifest.get("name") != name:
        errors.append(f"servers/{name}: manifest 의 name({manifest.get('name')})이 다릅니다")
    if manifest.get("version") != server["version"]:
        errors.append(f"servers/{name}: manifest 의 version({manifest.get('version')})이 다릅니다")
    if _unsafe(names):
        errors.append(f"servers/{name}: 허용하지 않는 경로가 들어 있습니다")
    return errors


def inspect_plugin(data: bytes) -> dict:
    """플러그인 zip 을 읽어 {name, version, skills, agents, contains}. 읽을 수 없으면 ValueError."""
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise ValueError("zip 형식이 아닙니다") from exc
    with zf:
        names = [i.filename for i in zf.infolist() if not i.is_dir()]
        if _unsafe(names):
            raise ValueError("허용하지 않는 경로가 들어 있습니다")
        tops = {n.split("/")[0] for n in names}
        strip = f"{next(iter(tops))}/" if len(tops) == 1 and all("/" in n for n in names) else ""
        rel = {n[len(strip):]: n for n in names}
        manifest: dict = {}
        for m in PLUGIN_MANIFESTS:
            if m in rel:
                try:
                    manifest = json.loads(zf.read(rel[m]))
                except ValueError as exc:
                    raise ValueError(f"{m} 을 읽을 수 없습니다") from exc
                break
    skills = sorted({p.split("/")[1] for p in rel if p.startswith("skills/") and p.endswith("/SKILL.md") and p.count("/") == 2})
    agents = sorted({p[7:-3] for p in rel if p.startswith("agents/") and p.endswith(".md") and p.count("/") == 1})
    contains = {
        "hooks": any(p in ("hooks/hooks.json", "hooks.json") for p in rel),
        "tools": any(p.startswith("tools/") and p.endswith(".py") and p.count("/") == 1 and not p[6:].startswith("_") for p in rel),
        "bin": any(p.startswith("bin/") and p.count("/") == 1 for p in rel),
        "mcpb": any(p.endswith((".mcpb", ".dxt")) for p in rel),
    }
    return {"name": manifest.get("name"), "version": manifest.get("version"), "skills": skills, "agents": agents, "contains": contains}


def verify_plugin(plugin: dict, data: bytes) -> list[str]:
    """내려받은 플러그인 zip 이 카탈로그 항목과 같은지 (sha256·이름·버전·구성물·hooks/tools 표시)."""
    name, errors = plugin["name"], []
    if hashlib.sha256(data).hexdigest() != plugin["sha256"]:
        errors.append(f"plugins/{name}: sha256 이 다릅니다")
    try:
        info = inspect_plugin(data)
    except ValueError as exc:
        return [*errors, f"plugins/{name}: {exc}"]
    if info["name"] != name:
        errors.append(f"plugins/{name}: plugin.json 의 name({info['name']})이 다릅니다")
    if str(info["version"]) != plugin["version"]:
        errors.append(f"plugins/{name}: plugin.json 의 version({info['version']})이 다릅니다")
    if not info["skills"] and not info["agents"]:
        errors.append(f"plugins/{name}: 스킬·에이전트가 하나도 없습니다")
    comps = plugin.get("components", {})
    if "skills" in comps and sorted(comps["skills"]) != info["skills"]:
        errors.append(f"plugins/{name}: components.skills 가 묶음과 다릅니다")
    if "agents" in comps and sorted(comps["agents"]) != info["agents"]:
        errors.append(f"plugins/{name}: components.agents 가 묶음과 다릅니다")
    for key, actual in info["contains"].items():
        # 훅·tools 는 승인 판단에 쓰이므로 표시를 빠뜨리면 안 된다 (있는데 false 이거나 생략하면 오류)
        declared = plugin.get("contains", {}).get(key)
        if key in ("hooks", "tools") and actual and declared is not True:
            errors.append(f"plugins/{name}: 묶음에 {key} 가 있는데 contains.{key} 가 true 가 아닙니다")
        elif declared is not None and declared != actual:
            errors.append(f"plugins/{name}: contains.{key}({declared})가 묶음({actual})과 다릅니다")
    return errors
