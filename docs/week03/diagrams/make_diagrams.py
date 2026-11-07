#!/usr/bin/env python3
"""Sinh sơ đồ cho proposal/spec tuần 3 (W3-I02).

Nguồn sự thật của sơ đồ nằm trong script này: sửa script rồi chạy lại để sinh
SVG. Không cần công cụ ngoài matplotlib.

    python3 docs/week03/diagrams/make_diagrams.py

Đầu ra (cùng thư mục):
    architecture-pipeline.svg  - pipeline async READ submit -> dispatch -> IRQ -> wait/release
    scan-boundary.svg          - ví dụ SCAN logic: head=40, dir tang, boundary 1999
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

OUT = Path(__file__).resolve().parent

VI_FONT = [
    "DejaVu Sans",
    "Segoe UI",
    "Arial",
    "Liberation Sans",
    "sans-serif",
]
plt.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.sans-serif": VI_FONT,
        "svg.fonttype": "path",
        "axes.unicode_minus": False,
    }
)


def box(ax, x, y, w, h, text, face="#eef4fb", edge="#3b5b7a", size=8.4, bold=False):
    p = FancyBboxPatch(
        (x - w / 2, y - h / 2),
        w,
        h,
        boxstyle="round,pad=0.02,rounding_size=0.06",
        linewidth=1.1,
        facecolor=face,
        edgecolor=edge,
        zorder=2,
    )
    ax.add_patch(p)
    ax.text(
        x,
        y,
        text,
        ha="center",
        va="center",
        fontsize=size,
        fontweight="bold" if bold else "normal",
        color="#13202b",
        zorder=3,
        linespacing=1.15,
    )
    return (x, y, w, h)


def arrow(ax, p0, p1, color="#3b5b7a", style="-|>", lw=1.2, ls="-", rad=0.0):
    a = FancyArrowPatch(
        p0,
        p1,
        arrowstyle=style,
        mutation_scale=11,
        linewidth=lw,
        color=color,
        linestyle=ls,
        connectionstyle=f"arc3,rad={rad}",
        zorder=1,
        shrinkA=0,
        shrinkB=0,
    )
    ax.add_patch(a)


def pipeline_svg():
    fig, ax = plt.subplots(figsize=(11.2, 4.35))
    ax.set_xlim(0, 11.2)
    ax.set_ylim(0, 4.35)
    ax.axis("off")

    w, h = 1.52, 0.78
    xs = [0.95, 2.65, 4.35, 6.05, 7.75, 9.45]
    y1 = 3.30
    y2 = 1.72

    row1 = [
        ("caller\n(process)", "#e8f1fb"),
        ("aio_read_submit\n(validate, alloc slot)", "#e8f1fb"),
        ("request pool\n16 slot BSS\n+ staging buffer", "#eef7ee"),
        ("pending queue\nQUEUED\nenqueue_seq", "#eef7ee"),
        ("policy\nFCFS (mặc định)\nSCAN logic", "#fdf6e3"),
        ("dispatcher\nio_dispatch_locked", "#eef7ee"),
    ]
    for x, (t, c) in zip(xs, row1):
        box(ax, x, y1, w, h, t, face=c)

    for i in range(len(xs) - 1):
        arrow(ax, (xs[i] + w / 2 + 0.02, y1), (xs[i + 1] - w / 2 - 0.02, y1))

    # dispatcher -> driver (xuống hàng 2, đi từ phải sang trái)
    arrow(ax, (xs[-1], y1 - h / 2 - 0.02), (xs[-1], y2 + h / 2 + 0.02), rad=0.0)

    row2 = [
        ("aio_wait / aio_poll\naio_data / aio_release", "#e8f1fb"),
        ("completion\nDONE / ERROR\ntrước wakeup", "#eef7ee"),
        ("IRQ\nvirtio_disk_intr\nreap + reclaim", "#fff4e5"),
        ("QEMU\nvirtio-blk", "#f3e8f7"),
        ("virtqueue\nNUM = 8 desc\n2 chain / 3 desc", "#f3e8f7"),
        ("try_submit_read\n3 desc / 1 block", "#fff4e5"),
    ]
    for x, (t, c) in zip(xs, row2):
        box(ax, x, y2, w, h, t, face=c, size=8.0)

    # hàng 2 đi từ phải sang trái: try_submit -> ... -> aio_wait
    for i in range(len(xs) - 1, 0, -1):
        arrow(ax, (xs[i] - w / 2 - 0.02, y2), (xs[i - 1] + w / 2 + 0.02, y2))

    # nhãn khóa / quy ước
    ax.text(
        5.6,
        0.52,
        "Một miền khóa io_lock = disk.vdisk_lock  ·  IRQ: không printk/kalloc/sleep  ·  "
        "buffer DMA thuộc pool, không caller-owned",
        ha="center",
        va="center",
        fontsize=8.0,
        color="#5a5a5a",
    )
    ax.text(
        xs[5],
        y1 + h / 2 + 0.20,
        "process context",
        ha="center",
        va="center",
        fontsize=7.4,
        color="#8a6d3b",
        style="italic",
    )
    ax.text(
        xs[2],
        y2 - h / 2 - 0.22,
        "IRQ context: chỉ terminal + wakeup rồi dispatch lại",
        ha="center",
        va="center",
        fontsize=7.4,
        color="#8a6d3b",
        style="italic",
    )
    fig.savefig(OUT / "architecture-pipeline.svg", bbox_inches="tight", pad_inches=0.06, facecolor="white")
    plt.close(fig)


def scan_svg():
    fig, ax = plt.subplots(figsize=(9.2, 4.6))
    ax.set_xlim(-0.5, 5.7)
    ax.set_ylim(-140, 2180)
    ax.set_xlabel("thứ tự dispatch (không phải thời gian thực)", fontsize=8.2, color="#333333")
    ax.set_ylabel("blockno", fontsize=8.2, color="#333333")
    ax.set_xticks([0, 1, 2, 3, 4, 5])
    ax.set_xticklabels(["head\n40", "1", "2", "3", "4", "5"], fontsize=7.8, color="#333333")
    ax.set_yticks([0, 500, 1000, 1500, 1999])
    ax.tick_params(labelsize=7.6, colors="#333333")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color("#8a8a8a")
    ax.grid(axis="y", color="#e2e2e2", lw=0.7, zorder=0)

    # head ban đầu + đường tham chiếu
    ax.axhline(40, color="#2e7d32", lw=1.0, ls=":", zorder=1)

    # các bước dispatch theo chiều tăng
    pts_up = [(0, 40), (1, 50), (2, 70), (3, 90)]
    xs = [p[0] for p in pts_up]
    ys = [p[1] for p in pts_up]
    ax.plot(xs, ys, color="#1565c0", lw=1.6, marker="o", ms=4.5, zorder=3)
    labels_up = {0: "head 40", 1: "50 (seq5)", 2: "70 (seq1)", 3: "90 (seq3)"}
    for x, y in pts_up:
        ax.annotate(
            labels_up[x],
            (x, y),
            textcoords="offset points",
            xytext=(8, 10 if x else 6),
            fontsize=7.6,
            color="#1565c0",
        )

    # sự kiện biên logic + đảo chiều
    ax.annotate(
        "",
        xy=(3.55, 1999),
        xytext=(3, 90),
        arrowprops=dict(arrowstyle="-|>", color="#c62828", lw=1.3, ls="--"),
    )
    ax.annotate(
        "",
        xy=(4, 20),
        xytext=(3.55, 1999),
        arrowprops=dict(arrowstyle="-|>", color="#c62828", lw=1.3, ls="--"),
    )
    ax.axhline(1999, color="#c62828", lw=1.0, ls="-.")
    ax.text(0.0, 2035, "BOUNDARY logic = FSSIZE-1 = 1999 (không phát READ giả)", fontsize=7.6, color="#c62828")

    # các bước dispatch theo chiều giảm
    pts_down = [(4, 20), (5, 10)]
    ax.plot(
        [p[0] for p in pts_down],
        [p[1] for p in pts_down],
        color="#6a1b9a",
        lw=1.6,
        marker="o",
        ms=4.5,
        zorder=3,
    )
    ax.annotate("20 (seq2)", (4, 20), textcoords="offset points", xytext=(8, 12), fontsize=7.6, color="#6a1b9a")
    ax.annotate("10 (seq4)", (5, 10), textcoords="offset points", xytext=(8, 12), fontsize=7.6, color="#6a1b9a")
    ax.annotate(
        "đảo chiều: direction = +  →  -",
        xy=(3.75, 1050),
        xytext=(4.55, 1250),
        fontsize=7.8,
        color="#6a1b9a",
        arrowprops=dict(arrowstyle="-|>", color="#6a1b9a", lw=0.9),
    )

    ax.set_title(
        "Ví dụ SCAN logic: head=40, tăng; queue seq 1..5 = block 70,20,90,10,50",
        fontsize=8.6,
        color="#222222",
    )
    fig.tight_layout()
    fig.savefig(OUT / "scan-boundary.svg", bbox_inches="tight", pad_inches=0.06, facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    pipeline_svg()
    scan_svg()
    print("wrote:", OUT / "architecture-pipeline.svg")
    print("wrote:", OUT / "scan-boundary.svg")
