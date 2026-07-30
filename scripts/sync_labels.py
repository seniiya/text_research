"""XLSX 에 입력된 라벨을 같은 이름의 CSV 에 옮긴다.

코더는 엑셀에서 작업한다. CSV 는 make_coding_sheet.py 가 시트를 만든 시점에
멈춰 있어서, 코딩이 진행될수록 XLSX 와 벌어진다. 실제로 coder1/P01 은
CSV 44건 / XLSX 183건까지 벌어져 있었다.

시트를 다시 만들지 않는다. (turn, sent_no) 로 찾아 esconv·note 만 채운다.
문장이 다르면 그 행은 건너뛴다. 잘못된 위치에 라벨이 붙는 것보다 비는 편이 낫다.

사용: python scripts/sync_labels.py P01 [--coder=coder2]
      python scripts/sync_labels.py --all
"""

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CODING = ROOT / "data" / "coding"

LABEL_FIELDS = ["esconv", "note"]


def read_xlsx(path):
    from openpyxl import load_workbook

    ws = load_workbook(path)["coding"]
    head = [c.value for c in ws[1]]
    col = {k: head.index(k) for k in ("turn", "sent_no", "role", "text")}
    # note 열은 나중에 생겼다. 그 전에 만든 시트에는 없다.
    col.update({f: head.index(f) for f in LABEL_FIELDS if f in head})

    out = {}
    for r in ws.iter_rows(min_row=2, values_only=True):
        if r[col["role"]] != "Response":
            continue
        key = (str(r[col["turn"]]), str(r[col["sent_no"]]))
        out[key] = {
            "text": r[col["text"]] or "",
            **{f: (str(r[col[f]]).strip() if r[col[f]] else "")
               for f in LABEL_FIELDS if f in col},
        }
    return out


def sync(pid, coder):
    xp, cp = CODING / coder / f"{pid}.xlsx", CODING / coder / f"{pid}.csv"
    if not xp.exists() or not cp.exists():
        return None

    src = read_xlsx(xp)
    with open(cp, encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        fields, rows = reader.fieldnames, list(reader)

    moved = changed = 0
    for r in rows:
        if r["role"] != "Response":
            continue
        v = src.get((str(r["turn"]), str(r["sent_no"])))
        if not v:
            continue
        if v["text"] != r["text"]:
            moved += 1          # 문장이 다르다. 붙이지 않는다.
            continue
        for f in LABEL_FIELDS:
            if f in v and v[f] != (r.get(f) or ""):
                r[f] = v[f]
                changed += 1

    if changed:
        with open(cp, "w", encoding="utf-8-sig", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)

    labeled = sum(1 for r in rows if r["role"] == "Response" and (r.get("esconv") or "").strip())
    return changed, moved, labeled


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a.split("=")[0]: a.split("=", 1)[-1]
             for a in sys.argv[1:] if a.startswith("--")}

    if "--all" in flags:
        targets = [(p.stem, p.parent.name)
                   for p in sorted(CODING.glob("*/*.xlsx"))]
    else:
        targets = [(args[0] if args else "P01", flags.get("--coder", "coder1"))]

    total = 0
    for pid, coder in targets:
        res = sync(pid, coder)
        if res is None:
            continue
        changed, moved, labeled = res
        if changed or moved:
            print(f"[{coder}] {pid}: {changed}칸 갱신, 라벨 {labeled}건"
                  + (f" / {moved}행은 문장이 달라 건너뜀" if moved else ""))
            total += changed
    print(f"총 {total}칸 갱신." if total else "갱신할 것 없음. CSV 가 XLSX 와 일치한다.")


if __name__ == "__main__":
    main()
