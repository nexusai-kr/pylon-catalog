# 기여 안내

- 서버·플러그인을 카탈로그에 올리거나 버전을 올리는 변경은 `catalog.json` 만 고치는 Pull Request 로 합니다 (`scripts/update_catalog.py` 사용).
- 서버·플러그인 코드는 각 저장소에서 관리합니다. 이 저장소에는 목록과 검증 도구만 둡니다.
- PR 전에 `uv run pytest -q && uv run python scripts/validate.py` 를 통과시키세요.
- 다운로드 소유자 목록(`TRUSTED_OWNERS`) 변경은 별도 PR 로 올리고 이유를 적습니다.
