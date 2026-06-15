"""Stop-hook gate: refuse to finish while the AQA dogfood project has open coverage
gaps (a finalized requirement with no linked test). Exit 2 blocks the agent from
stopping and feeds the reason back; exit 0 lets it finish.

Fails OPEN: if AQA is unreachable (server down, no creds), it does not block — the
gate hardens the loop, it must not break it. Auth via scripts/_aqaclient
(AQA_API_KEY or admin login).
"""

import sys

PREFIX = "AQA"


def main() -> int:
    try:
        from scripts._aqaclient import auth, get

        auth()
        proj = next((p for p in get("/api/v1/projects") if p["prefix"] == PREFIX), None)
        if proj is None:
            return 0
        gaps = get(f"/api/v1/projects/{proj['id']}/coverage-gaps")
    except Exception:
        return 0  # AQA unreachable — never block the dev loop

    if gaps:
        docs = ", ".join(g["req_doc_id"] for g in gaps)
        print(
            f"AQA coverage gate: {len(gaps)} requirement(s) have no test coverage: {docs}. "
            "Write the failing test, make it pass, then link_coverage(req_id, [case_id]) "
            "before finishing.",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
