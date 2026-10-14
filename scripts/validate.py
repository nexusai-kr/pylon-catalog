#!/usr/bin/env python3
"""catalog.json 검증. `--verify-downloads` 면 각 mcpb·플러그인 zip 을 내려받아 sha256·내용까지 확인한다 (PR·주기 점검에서)."""

from __future__ import annotations

import argparse
import sys

from catalog_lib import fetch, load, validate, verify_bundle, verify_plugin


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify-downloads", action="store_true")
    args = ap.parse_args()
    catalog = load()
    errors = validate(catalog)
    if args.verify_downloads and not errors:
        for key, verify in (("servers", verify_bundle), ("plugins", verify_plugin)):
            for s in catalog[key]:
                try:
                    errors += verify(s, fetch(s["download"]))
                except Exception as exc:  # 네트워크·404 등
                    errors.append(f"{key}/{s['name']}: 내려받지 못했습니다 ({exc})")
    for e in errors:
        print("ERROR", e)
    print(f"서버 {len(catalog['servers'])}개, 플러그인 {len(catalog['plugins'])}개, 오류 {len(errors)}건")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
