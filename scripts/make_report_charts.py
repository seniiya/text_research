"""보고서 차트 c1~c6 을 data/output/report/ 에 그린다.

수치는 하나도 하드코딩하지 않는다. analyze_speechact.py 가 만든
report_stats.json 과 surface_va_probe.build() 만 읽는다. 라벨이 바뀌면
analyze_speechact.py 를 다시 돌린 뒤 이 파일을 돌리면 차트가 따라간다.

색: dataviz 문서에 검증치가 명시된 파랑 순차/서열 램프만 쓴다. 범주형 팔레트는
쓰지 않는다 (검증기를 이 환경에서 돌릴 수 없어 문서화된 값 밖으로 나가지 않는다).

사용: python scripts/analyze_speechact.py && python scripts/make_report_charts.py
"""

import json
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt          # noqa: E402
import numpy as np                       # noqa: E402
from matplotlib import font_manager as fm  # noqa: E402

from speechact_data import BUILD, REPORT_DIR, ROOT  # noqa: E402
from surface_va_probe import build as build_va         # noqa: E402

fm.fontManager.addfont("C:/Windows/Fonts/malgun.ttf")
plt.rcParams.update({
    "font.family": "Malgun Gothic", "axes.unicode_minus": False,
    "figure.facecolor": "#fcfcfb", "axes.facecolor": "#fcfcfb",
    "text.color": "#0b0b0b", "axes.labelcolor": "#52514e",
    "xtick.color": "#898781", "ytick.color": "#52514e",
    "axes.edgecolor": "#c3c2b7", "font.size": 10,
})
B250, B400, B450, B550 = "#86b6ef", "#3987e5", "#2a78d6", "#1c5cab"
MUTED, RULE = "#898781", "#e1e0d9"


def strip(ax, grid_x=True):
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color("#c3c2b7")
    if grid_x:
        ax.xaxis.grid(True, color=RULE, lw=.8)
        ax.set_axisbelow(True)
    ax.tick_params(length=0)


def save(fig, name):
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    p = REPORT_DIR / name
    fig.tight_layout()
    fig.savefig(p, dpi=200)
    plt.close(fig)
    print(f"  {p.relative_to(ROOT)}")


# ── c1. 참가자별 정서 비율 vs 설문 자기보고 ───────────────────────────
def c1(st):
    rows = sorted(st["c1"], key=lambda r: -r["surf"])
    fig, ax = plt.subplots(figsize=(8.4, 4.6))
    ax.barh(range(len(rows)), [r["surf"] for r in rows], height=.62,
            color=B450, zorder=3)
    for i, r in enumerate(rows):
        v = int(r["v"]) if r["v"] else 5
        neg = v <= 3
        ax.text(r["surf"] + 1.6, i, f'{r["surf"]:.0f}%', va="center", fontsize=9,
                color="#52514e")
        ax.text(-2, i, r["pid"], va="center", ha="right", fontsize=9.5,
                color="#0b0b0b", fontweight="bold" if neg else "normal")
        ax.text(101, i, f"V{v}", va="center", ha="left", fontsize=9,
                color=B550 if neg else MUTED, fontweight="bold" if neg else "normal")
        ax.text(110, i, str(r["word"])[:9], va="center", ha="left", fontsize=8.5,
                color=B550 if neg else MUTED)
    ax.set_yticks([]); ax.set_xlim(0, 148); ax.set_ylim(-.7, len(rows) - .3)
    ax.invert_yaxis(); strip(ax)
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.set_xticklabels(["0", "25", "50", "75", "100%"])
    ax.set_xlabel("대화에서 정서가 읽힌 문장 비율 (EXP + IMP)", fontsize=9.5, labelpad=8)
    ax.text(101, -1.15, "설문 자기보고", fontsize=8.5, color=MUTED, ha="left")
    save(fig, "c1.png")


# ── c2. 화행별 정서 표면성 (100% 누적) ────────────────────────────────
def c2(st):
    cross = sorted(st["cross"], key=lambda c: -(c[1] + c[2]) / sum(c[1:]))
    fig, ax = plt.subplots(figsize=(8.4, 3.5))
    labs = [c[0] for c in cross]
    tot = [sum(c[1:]) for c in cross]
    e, i_, n = ([c[k] / t * 100 for c, t in zip(cross, tot)] for k in (1, 2, 3))
    ax.barh(labs, e, height=.6, color=B550, label="EXP  감정어 명시", zorder=3)
    ax.barh(labs, i_, left=e, height=.6, color=B400, label="IMP  맥락상 읽힘", zorder=3)
    ax.barh(labs, n, left=[a + b for a, b in zip(e, i_)], height=.6,
            color=B250, label="NONE  정서 무관", zorder=3)
    for k, t in enumerate(tot):
        ax.text(102, k, f"n={t}", va="center", fontsize=8.5, color=MUTED)
    ax.invert_yaxis(); ax.set_xlim(0, 116); strip(ax, grid_x=False)
    ax.set_xticks([0, 50, 100]); ax.set_xticklabels(["0", "50", "100%"])
    ax.legend(loc="lower center", bbox_to_anchor=(.45, 1.02), ncol=3,
              frameon=False, fontsize=9)
    save(fig, "c2.png")


# ── c3. 원 체계(v1) → 보완 체계(v2) ──────────────────────────────────
def c3(st):
    pair = st.get("v1v2") or []
    if not pair:
        return
    fig, ax = plt.subplots(figsize=(8.4, 3.2))
    idx = range(len(pair))
    ax.barh([i + .19 for i in idx], [p[1] for p in pair], height=.34,
            color=B250, label="v1  3i4K 6클래스", zorder=3)
    ax.barh([i - .19 for i in idx], [p[2] for p in pair], height=.34,
            color=B450, label="v2  대화행위 보완", zorder=3)
    for i, (c, a, b) in enumerate(pair):
        if a:
            ax.text(a + .3, i + .19, str(a), va="center", fontsize=8.5, color="#52514e")
        if b:
            ax.text(b + .3, i - .19, str(b), va="center", fontsize=8.5, color="#52514e")
    ax.set_yticks(list(idx)); ax.set_yticklabels([p[0] for p in pair], fontsize=9.5)
    ax.invert_yaxis(); ax.set_xlim(0, max(max(p[1], p[2]) for p in pair) * 1.15)
    strip(ax)
    n = sum(p[1] for p in pair)
    ax.set_xlabel(f"문장 수 (P04 · 동일한 {n}문장)", fontsize=9.5, labelpad=6)
    ax.legend(loc="lower right", frameon=False, fontsize=9)
    save(fig, "c3.png")


# ── c4. 축 A 분포 ────────────────────────────────────────────────────
def c4(st):
    dist = st["dist_a"]
    tot = st["n_act"]
    fig, ax = plt.subplots(figsize=(8.4, 3.2))
    ax.barh([d[0] for d in dist], [d[1] for d in dist], height=.6, color=B450, zorder=3)
    for i, (c, v) in enumerate(dist):
        if v:
            ax.text(v + 1.5, i, f"{v}  {v / tot * 100:.1f}%", va="center",
                    fontsize=8.5, color="#52514e")
        else:
            ax.text(1.5, i, "관찰되지 않음", va="center", fontsize=8.5,
                    color=MUTED, style="italic")
    ax.invert_yaxis(); ax.set_xlim(0, max(d[1] for d in dist) * 1.2); strip(ax)
    ax.set_xlabel(f"문장 수 ({st['n_participants']}명 · {tot}문장)",
                  fontsize=9.5, labelpad=6)
    save(fig, "c4.png")


# ── c5. 3i4K 원 코퍼스 대조 ──────────────────────────────────────────
def c5(st):
    rows = sorted(st["c5"], key=lambda r: -r[2])   # 본 연구 비율 큰 순
    fig, ax = plt.subplots(figsize=(8.4, 3.4))
    idx = range(len(rows))
    ax.barh([i + .19 for i in idx], [r[1] for r in rows], height=.34,
            color=B250, label=f"3i4K 원 코퍼스  n=17,735", zorder=3)
    ax.barh([i - .19 for i in idx], [r[2] for r in rows], height=.34,
            color=B450, label=f"본 연구  n={st['n_3i4k']}", zorder=3)
    for i, (c, orig, mine) in enumerate(rows):
        ax.text(orig + .5, i + .19, f"{orig:.1f}%", va="center", fontsize=8.5,
                color="#52514e")
        ax.text(mine + .5, i - .19, f"{mine:.1f}%", va="center", fontsize=8.5,
                color="#52514e" if mine else MUTED)
        if abs(mine - orig) >= 10:
            ax.text(52, i, f"{mine - orig:+.1f}p", va="center", fontsize=9.5,
                    color=B550, fontweight="bold")
    ax.set_yticks(list(idx)); ax.set_yticklabels([r[0] for r in rows], fontsize=9.5)
    ax.invert_yaxis(); ax.set_xlim(0, 60); strip(ax)
    ax.set_xticks([0, 10, 20, 30, 40, 50])
    ax.set_xticklabels(["0", "10", "20", "30", "40", "50%"])
    ax.set_xlabel("해당 코드가 차지하는 비율 (IU 제외 · 3i4K 6코드 기준)",
                  fontsize=9.5, labelpad=6)
    ax.legend(loc="lower right", frameon=False, fontsize=9)
    save(fig, "c5.png")


# ── c6. 표면 정서 vs 자기보고 산점도 ─────────────────────────────────
def c6():
    recs = [r for r in build_va() if r["topic_V"] is not None]
    x = np.array([r["surf"] for r in recs])
    y = np.array([r["topic_V"] for r in recs])
    n = np.array([r["n"] for r in recs])
    r_, _ = __import__("scipy.stats", fromlist=["pearsonr"]).pearsonr(x, y)

    fig, ax = plt.subplots(figsize=(8.6, 5.0))
    ax.axhspan(0.4, 4.4, color=B250, alpha=.16, zorder=0)
    ax.text(99, 4.28, "자기보고 부정", ha="right", va="top", fontsize=8.5, color=B550)
    ax.yaxis.grid(True, color=RULE, lw=.8, zorder=1); ax.set_axisbelow(True)
    b, a = np.polyfit(x, y, 1)
    xs = np.array([0, 90])
    ax.plot(xs, a + b * xs, color=MUTED, lw=1.2, ls="--", zorder=2)
    ax.scatter(x, y, s=18 + n * 3.2, color=B450, alpha=.85, zorder=4,
               edgecolor="#fcfcfb", linewidth=1.1)
    # 겹치는 라벨만 손으로 내린다. 나머지는 점 위.
    BELOW = {"P02", "P22", "P03", "P10", "P11", "P18", "P14", "P17"}
    for r in recs:
        dy = -.38 if r["pid"] in BELOW else .30
        neg = r["topic_V"] <= 4
        ax.text(r["surf"], r["topic_V"] + dy, r["pid"], ha="center", fontsize=8.5,
                color="#0b0b0b" if neg else "#52514e", zorder=5,
                fontweight="bold" if neg else "normal")
    lo = min(recs, key=lambda r: r["surf"] if r["topic_V"] <= 2 else 1e9)
    hi = max(recs, key=lambda r: r["surf"] if r["topic_V"] <= 2 else -1)
    ax.annotate("", xy=(lo["surf"] + .2, 1.62), xytext=(hi["surf"] - .2, 1.62),
                arrowprops=dict(arrowstyle="<->", color=B550, lw=1.3))
    ax.text((lo["surf"] + hi["surf"]) / 2, 1.42,
            f"같은 자기보고 V2 - 표면 정서는 {lo['surf']:.0f}% ↔ {hi['surf']:.0f}%",
            ha="center", va="top", fontsize=9, color=B550, fontweight="bold")
    ax.set_xlim(-4, 100); ax.set_ylim(0.4, 9.2)
    ax.set_yticks([1, 3, 5, 7, 9])
    ax.set_yticklabels(["1\n매우 부정", "3", "5\n중립", "7", "9\n매우 긍정"], fontsize=9)
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.set_xticklabels(["0", "25", "50", "75", "100%"])
    strip(ax, grid_x=False)
    ax.set_xlabel("대화에서 정서가 읽힌 문장 비율  (EXP + IMP)", fontsize=9.5, labelpad=8)
    ax.set_ylabel("설문 자기보고 Valence  (주제별 최솟값)", fontsize=9.5, labelpad=8)
    ax.text(-4, 9.75, "자기보고 정서와 발화에 드러난 정서는 거의 겹치지 않는다",
            fontsize=12.5, fontweight="bold", color="#0b0b0b")
    ax.text(-4, 9.42,
            f"{len(recs)}명 · {sum(n)}문장   ·   r = {r_:.2f}   ·   R² = {r_ ** 2:.2f}"
            f"   ·   원 크기 = 문장 수", fontsize=9, color=MUTED)
    save(fig, "c6.png")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    p = BUILD / "chart_input.json"
    if not p.exists():
        sys.exit("chart_input.json 이 없다. 먼저 analyze_speechact.py 를 돌린다.")
    st = json.load(open(p, encoding="utf-8"))
    print("차트 생성")
    c1(st); c2(st); c3(st); c4(st); c5(st); c6()


if __name__ == "__main__":
    main()
