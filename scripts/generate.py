#!/usr/bin/env python3
"""Render the neofetch-style profile card (dark + light SVG) from live GitHub stats.

Standard library only. Needs a token in GH_TOKEN (or GITHUB_TOKEN):
  - the workflow's GITHUB_TOKEN  -> public repos and public contributions only;
  - a PAT stored as PROFILE_TOKEN -> private repos/commits are counted too
    (only as totals: private repo names never appear on the card).

Usage:  GH_TOKEN=... python scripts/generate.py
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import urllib.request
from html import escape
from pathlib import Path

# ---------------------------------------------------------------- edit me ---
LOGIN = os.environ.get("LOGIN") or os.environ.get("GITHUB_REPOSITORY_OWNER") or "wasti4"
HOST = "github"
STATUS = "open for commissions · will build anything"  # shown highlighted; "" hides it
STATIC_ROWS = [
    ("OS", "Windows 11 · WSL"),
    ("Shell", "PowerShell · bash"),
]
LANGS = ["Python", "TypeScript", "JavaScript", "C#", "C", "C++",
         "SQL", "PowerShell", "Bash", "HTML/CSS"]
FOCUS = "web apps · automation · embedded"
# Pixel monogram: '#' = block. Drawn as rects, so it looks identical in every font.
LOGO = [
    "#.....#...##.",
    "#.....#..#.#.",
    "#.....#.#..#.",
    "#..#..#.#..#.",
    "#.#.#.#.#####",
    "##...##....#.",
    "#.....#....#.",
]
OUT_DIR = Path(__file__).resolve().parent.parent / "assets"
# ----------------------------------------------------------------------------

THEMES = {
    "dark": dict(bg="#0d1117", bar="#161b22", border="#30363d", text="#e6edf3",
                 muted="#7d8590", dot="#484f58", green="#3fb950", blue="#58a6ff",
                 logo=("#3fb950", "#39c5cf"), track="#21262d"),
    "light": dict(bg="#ffffff", bar="#f6f8fa", border="#d0d7de", text="#1f2328",
                  muted="#59636e", dot="#d0d7de", green="#1a7f37", blue="#0969da",
                  logo=("#1a7f37", "#1b7c83"), track="#eaeef2"),
}

REPOS_Q = """
query($login: String!, $after: String) {
  user(login: $login) {
    createdAt
    repositories(first: 100, after: $after, ownerAffiliations: OWNER, isFork: false) {
      totalCount
      pageInfo { hasNextPage endCursor }
      nodes {
        isPrivate
        stargazerCount
        languages(first: 20, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
  }
}"""

CONTRIB_Q = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      totalCommitContributions
      totalPullRequestContributions
      totalIssueContributions
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}"""


def gql(query: str, variables: dict, token: str) -> dict:
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {token}",
                 "Content-Type": "application/json",
                 "User-Agent": "profile-card"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.load(resp)
    if payload.get("errors"):
        sys.exit(f"GitHub API error: {payload['errors']}")
    return payload["data"]


def fetch(token: str) -> dict:
    repos, after, created = [], None, None
    while True:
        user = gql(REPOS_Q, {"login": LOGIN, "after": after}, token)["user"]
        created = user["createdAt"]
        conn = user["repositories"]
        repos += conn["nodes"]
        if not conn["pageInfo"]["hasNextPage"]:
            break
        after = conn["pageInfo"]["endCursor"]

    cc = gql(CONTRIB_Q, {"login": LOGIN}, token)["user"]["contributionsCollection"]
    days = [d for w in cc["contributionCalendar"]["weeks"] for d in w["contributionDays"]]

    langs: dict[str, list] = {}
    for r in repos:
        for e in r["languages"]["edges"]:
            name, color = e["node"]["name"], e["node"]["color"] or "#8b949e"
            langs.setdefault(name, [0, color])[0] += e["size"]

    return dict(
        created=dt.datetime.fromisoformat(created.replace("Z", "+00:00")),
        repos=len(repos),
        public=sum(not r["isPrivate"] for r in repos),
        stars=sum(r["stargazerCount"] for r in repos),
        commits=cc["totalCommitContributions"],
        prs=cc["totalPullRequestContributions"],
        issues=cc["totalIssueContributions"],
        contribs=cc["contributionCalendar"]["totalContributions"],
        days=[d["contributionCount"] for d in sorted(days, key=lambda d: d["date"])],
        langs=langs,
    )


# ------------------------------------------------------------------ helpers --
def plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def uptime(created: dt.datetime) -> str:
    now = dt.datetime.now(dt.timezone.utc)
    months = (now.year - created.year) * 12 + now.month - created.month - (now.day < created.day)
    y, m = divmod(max(months, 0), 12)
    parts = [plural(y, "year")] if y else []
    if m or not y:
        parts.append(plural(m, "month"))
    return ", ".join(parts)


def streaks(days: list[int]) -> tuple[int, int]:
    best = run = 0
    for c in days:
        run = run + 1 if c else 0
        best = max(best, run)
    tail = days[:-1] if days and not days[-1] else days  # today may still be empty
    cur = 0
    for c in reversed(tail):
        if not c:
            break
        cur += 1
    return cur, best


def wrap(items: list[str], width: int = 34) -> list[str]:
    lines, cur = [], ""
    for it in items:
        nxt = f"{cur} · {it}" if cur else it
        if len(nxt) > width and cur:
            lines.append(cur)
            cur = it
        else:
            cur = nxt
    return lines + [cur] if cur else lines


def top_langs(langs: dict, n: int = 5) -> list[tuple[str, float, str]]:
    total = sum(v[0] for v in langs.values()) or 1
    ranked = sorted(langs.items(), key=lambda kv: -kv[1][0])
    out = [(k, v[0] / total, v[1]) for k, v in ranked[:n]]
    rest = sum(v[0] for _, v in ranked[n:]) / total
    if rest > 0.005:
        out.append(("Other", rest, "#8b949e"))
    return out


# ------------------------------------------------------------------- render --
W, FS, LH = 800, 14, 22          # card width, font size, info line height
PX, GAP = 11, 1.5                # logo pixel size and gap
INFO_X, VAL_X = 250, 340
LEGEND_CH = 7.4                  # generous 12px monospace advance estimate (legend layout)
FONT = "ui-monospace, SFMono-Regular, 'JetBrains Mono', Consolas, 'Liberation Mono', Menlo, monospace"


def styled(value: str, t: dict) -> str:
    """Escape a value and dim the ' · ' separators."""
    parts = value.split(" · ")
    sep = f'<tspan fill="{t["muted"]}"> · </tspan>'
    return sep.join(escape(p) for p in parts)


def render(s: dict, theme: str) -> str:
    t = THEMES[theme]
    cur, best = streaks(s["days"])
    rows: list[tuple[str, str]] = [("Status", STATUS)] if STATUS else []
    rows += [*STATIC_ROWS, ("Uptime", uptime(s["created"]))]
    for i, line in enumerate(wrap(LANGS)):
        rows.append(("Langs" if i == 0 else "", line))
    rows += [
        ("Focus", FOCUS),
        ("Repos", f"{s['repos']} · {s['public']} public"),
        ("Stars", str(s["stars"])),
        ("Commits", f"{s['commits']} in the last year"),
        ("PRs", f"{s['prs']} · issues {s['issues']}"),
        ("Contribs", f"{s['contribs']} in the last year"),
        ("Streak", f"{plural(cur, 'day')} · best {best}"),
    ]

    title_h = 38
    prompt_y = title_h + 36
    info_y = prompt_y + 36
    header = [f'<tspan fill="{t["green"]}">{LOGIN}</tspan>'
              f'<tspan fill="{t["muted"]}">@</tspan>'
              f'<tspan fill="{t["green"]}">{HOST}</tspan>',
              f'<tspan fill="{t["muted"]}">{"─" * len(LOGIN + "@" + HOST)}</tspan>']
    last_y = info_y + (len(header) + len(rows) - 1) * LH
    bar_y = last_y + 20
    legend_y = bar_y + 8 + 22

    # legend items, wrapped to the card width
    langs = top_langs(s["langs"], 4)
    legend, lx, ly = [], float(INFO_X), legend_y
    for name, frac, color in langs:
        label = f"{name} {frac*100:.0f}%"
        w = 13 + len(label) * LEGEND_CH
        if lx + w > W - 28 and lx > INFO_X:
            lx, ly = float(INFO_X), ly + 20
        legend.append((lx, ly, label, color))
        lx += w + 16
    end_y = ly + 40
    H = end_y + 26

    out: list[str] = []
    a = out.append
    a(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
      f'role="img" aria-label="{escape(LOGIN)}@{HOST}: neofetch-style profile card">')
    a(f"""<style>
  .a {{ animation-fill-mode: both; }}
  .ln {{ animation: fade .35s ease-out both; }}
  .ch {{ animation: show .01s linear both; }}
  .cur {{ animation: blink 1.1s steps(1) infinite both; }}
  @keyframes fade {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}
  @keyframes show {{ from {{ fill-opacity: 0; }} to {{ fill-opacity: 1; }} }}
  @keyframes blink {{ 0% {{ fill-opacity: 1; }} 50% {{ fill-opacity: 0; }} }}
  @media (prefers-reduced-motion: reduce) {{ .ln, .ch, .cur {{ animation: none !important; }} }}
</style>""")
    a(f'<defs><clipPath id="bar"><rect x="{INFO_X}" y="{bar_y}" width="300" height="8" rx="4"/></clipPath></defs>')

    # window
    a(f'<rect x=".5" y=".5" width="{W-1}" height="{H-1}" rx="10" fill="{t["bg"]}" stroke="{t["border"]}"/>')
    a(f'<path d="M.5 {title_h}V10.5a10 10 0 0 1 10-10h{W-21}a10 10 0 0 1 10 10V{title_h}Z" fill="{t["bar"]}"/>')
    a(f'<line x1="0" y1="{title_h}.5" x2="{W}" y2="{title_h}.5" stroke="{t["border"]}"/>')
    for i in range(3):
        a(f'<circle cx="{20 + i*18}" cy="{title_h/2}" r="5.5" fill="{t["dot"]}"/>')
    a(f'<text x="{W/2}" y="{title_h/2 + 4.5}" text-anchor="middle" font-family="{FONT}" '
      f'font-size="12.5" fill="{t["muted"]}">{escape(LOGIN)}@{HOST}: ~</text>')

    a(f'<g font-family="{FONT}" font-size="{FS}" fill="{t["text"]}" xml:space="preserve">')

    # prompt + typed command
    def prompt(y: int, cmd: str, start: float, cursor: bool = False, delay: float = 0) -> None:
        cls = ' class="ln"' if delay else ""
        sty = f' style="animation-delay:{delay:.2f}s"' if delay else ""
        a(f'<text x="28" y="{y}"{cls}{sty}>'
          f'<tspan fill="{t["green"]}">{LOGIN}@{HOST}</tspan><tspan fill="{t["muted"]}">:</tspan>'
          f'<tspan fill="{t["blue"]}">~</tspan><tspan fill="{t["muted"]}">$ </tspan>')
        for i, ch in enumerate(cmd):
            a(f'<tspan class="ch" style="animation-delay:{start + i*0.07:.2f}s">{escape(ch)}</tspan>')
        if cursor:
            a(f'<tspan class="cur" fill="{t["green"]}" style="animation-delay:{start:.2f}s">█</tspan>')
        a("</text>")

    prompt(prompt_y, "neofetch", 0.35)
    out_t = 0.35 + len("neofetch") * 0.07 + 0.3

    # pixel logo with a drop shadow, vertically centred against the info block;
    # pixels appear column by column
    step = PX + GAP
    logo_w = len(LOGO[0]) * step
    lx0 = 28 + (INFO_X - 28 - logo_w) / 2 - 8
    ly0 = (info_y - FS) + ((ly - info_y + FS) - len(LOGO) * step) / 2
    a(f'<linearGradient id="lg" gradientUnits="userSpaceOnUse" x1="{lx0:.1f}" y1="{ly0:.1f}" '
      f'x2="{lx0 + logo_w:.1f}" y2="{ly0 + len(LOGO) * step:.1f}">'
      f'<stop offset="0" stop-color="{t["logo"][0]}"/><stop offset="1" stop-color="{t["logo"][1]}"/>'
      f'</linearGradient>')
    a(f'<g fill="url(#lg)">')
    for layer in ("shadow", "pixel"):
        off = 3 if layer == "shadow" else 0
        fill = f' fill="{t["border"]}"' if layer == "shadow" else ""
        for r, row in enumerate(LOGO):
            for c, ch in enumerate(row):
                if ch != "#":
                    continue
                a(f'<rect class="ln" style="animation-delay:{out_t + c*0.035:.2f}s"{fill} '
                  f'x="{lx0 + c*step + off:.1f}" y="{ly0 + r*step + off:.1f}" '
                  f'width="{PX}" height="{PX}" rx="1.5"/>')
    a("</g>")

    # info rows
    y = info_y
    d = out_t
    for h in header:
        a(f'<text x="{INFO_X}" y="{y}" class="ln" style="animation-delay:{d:.2f}s">{h}</text>')
        y += LH
        d += 0.05
    for key, val in rows:
        a(f'<g class="ln" style="animation-delay:{d:.2f}s">')
        if key:
            a(f'<text x="{INFO_X}" y="{y}" fill="{t["green"]}" font-weight="600">{escape(key)}</text>')
        hl = f' fill="{t["green"]}" font-weight="600"' if key == "Status" else ""
        a(f'<text x="{VAL_X}" y="{y}"{hl}>{styled(val, t)}</text></g>')
        y += LH
        d += 0.05

    # language bar (GitHub code by bytes) + legend
    a(f'<g class="ln" style="animation-delay:{d:.2f}s">')
    a(f'<rect x="{INFO_X}" y="{bar_y}" width="300" height="8" rx="4" fill="{t["track"]}"/>')
    a('<g clip-path="url(#bar)">')
    x = float(INFO_X)
    for name, frac, color in langs:
        w = 300 * frac
        a(f'<rect x="{x:.1f}" y="{bar_y}" width="{max(w - 2, 1):.1f}" height="8" fill="{color}"/>')
        x += w
    a("</g>")
    for x, y, label, color in legend:
        a(f'<circle cx="{x + 4:.1f}" cy="{y - 4}" r="4" fill="{color}"/>'
          f'<text x="{x + 13:.1f}" y="{y}" font-size="12" fill="{t["muted"]}">{escape(label)}</text>')
    a("</g>")
    d += 0.15

    prompt(end_y, "", d, cursor=True, delay=d)
    a("</g></svg>")
    # No separators: whitespace between <tspan>s would render as visible spaces.
    return "".join(out) + "\n"


def main() -> None:
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        sys.exit("Set GH_TOKEN (or GITHUB_TOKEN) to a GitHub token.")
    stats = fetch(token)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for theme in THEMES:
        path = OUT_DIR / f"terminal-{theme}.svg"
        path.write_text(render(stats, theme), encoding="utf-8", newline="\n")
        print(f"wrote {path.relative_to(OUT_DIR.parent)}")


if __name__ == "__main__":
    main()
