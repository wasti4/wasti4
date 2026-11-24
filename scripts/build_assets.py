#!/usr/bin/env python3
"""Builds the SVGs of the profile README: intro, project cards, services and contact.

The images have transparent backgrounds and use GitHub's own text colours, so they sit on the page
like native content. Each one comes in a dark and a light variant, picked with <picture>.
Everything is self-contained (embedded font and screenshots). Needs Pillow.

Usage:  python scripts/build_assets.py
"""
from __future__ import annotations

import base64
import io
from html import escape
from pathlib import Path

from PIL import Image, ImageFont

ROOT = Path(__file__).resolve().parent.parent
FONT_FILE = ROOT / 'scripts' / 'fonts' / 'Manrope-latin.woff2'
MEDIA = ROOT / 'scripts' / 'media'
OUT = ROOT / 'assets'
FONT = base64.b64encode(FONT_FILE.read_bytes()).decode()
FAMILY = "'Manrope','Segoe UI',system-ui,-apple-system,sans-serif"
WIDTH = 1200

THEMES = {
    'dark': {'fg': '#e6edf3', 'muted': '#9198a1', 'faint': '#6e7681', 'line': '#2d333b', 'dot': '#3fb950', 'wash': '#ffffff'},
    'light': {'fg': '#1f2328', 'muted': '#59636e', 'faint': '#818b98', 'line': '#d8dee4', 'dot': '#1a7f37', 'wash': '#1f2328'},
}

_measure = ImageFont.truetype(str(FONT_FILE), 200)


def text_width(text: str, size: float, weight: int) -> float:
    _measure.set_variation_by_axes([weight])
    return _measure.getlength(text) * size / 200


def jpeg(path: Path, width: int) -> str:
    image = Image.open(path).convert('RGB')
    if image.width > width:
        image = image.resize((width, round(image.height * width / image.width)), Image.Resampling.LANCZOS)
    buffer = io.BytesIO()
    image.save(buffer, 'JPEG', quality=80, optimize=True, progressive=True)
    return 'data:image/jpeg;base64,' + base64.b64encode(buffer.getvalue()).decode()


def document(height: int, title: str, desc: str, t: dict, body: str, style: str = '', defs: str = '') -> str:
    return f'''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 {WIDTH} {height}" width="{WIDTH}" height="{height}" role="img" aria-labelledby="title desc">
<title id="title">{escape(title)}</title>
<desc id="desc">{escape(desc)}</desc>
<defs>
<style>
@font-face{{font-family:'Manrope';src:url(data:font/woff2;base64,{FONT}) format('woff2');font-weight:200 800}}
text{{font-family:{FAMILY}}}
.fg{{fill:{t['fg']}}}.muted{{fill:{t['muted']}}}.faint{{fill:{t['faint']}}}
{style}
@media (prefers-reduced-motion:reduce){{*{{animation:none!important}}}}
</style>
{defs}
</defs>
{body}
</svg>
'''


def section_label(label: str, y: float, t: dict) -> str:
    """A small label followed by a hairline that runs to the right edge."""
    end = text_width(label, 17, 600) + 20
    return (f'<text x="0" y="{y}" class="faint" style="font-weight:600;font-size:17px;letter-spacing:.2px">{escape(label)}</text>'
            f'<line x1="{end:.1f}" y1="{y - 6}" x2="{WIDTH}" y2="{y - 6}" stroke="{t["line"]}" stroke-width="1.5"/>')


# ----------------------------------------------------------------- intro ---
def intro(t: dict) -> str:
    height = 300
    phrases = [
        'Mostly I build software for fun and for myself.',
        "Lately that's Folio, a calm media gallery for Windows.",
        'And Dustmap, a fast disk space analyzer.',
    ]
    slot = 6.0
    period = slot * len(phrases)
    fade = 0.9 / period * 100
    hold = (slot - 0.9) / period * 100
    out = slot / period * 100
    style = '\n'.join([
        '.phrase{opacity:0;animation:phrase %.0fs ease-in-out infinite}' % period,
        '@keyframes phrase{0%%{opacity:0;transform:translateY(5px)}%.2f%%{opacity:1;transform:translateY(0)}'
        '%.2f%%{opacity:1;transform:translateY(0)}%.2f%%,100%%{opacity:0;transform:translateY(-5px)}}' % (fade, hold, out),
        '@media (prefers-reduced-motion:reduce){.p0{opacity:1}}',
    ])
    lines = '\n'.join(
        f'<text class="phrase p{i} faint" x="2" y="262" style="font-weight:500;font-size:22px;animation-delay:{-((period - i * slot) % period):.0f}s">{escape(p)}</text>'
        for i, p in enumerate(phrases))
    body = f'''<circle cx="8" cy="30" r="5" fill="{t['dot']}"/>
<text x="24" y="37" class="muted" style="font-weight:600;font-size:19px">Available for commissions</text>
<text x="-4" y="152" class="fg" style="font-weight:700;font-size:104px;letter-spacing:-4px">wasti4</text>
<text x="2" y="208" class="muted" style="font-weight:500;font-size:28px;letter-spacing:-.3px">Software engineer. Desktop, web, automation and embedded.</text>
{lines}'''
    return document(height, 'wasti4', 'Software engineer for desktop apps, web apps, automation and embedded systems. Available for commissions.',
                    t, body, style)


# --------------------------------------------------------- project cards ---
def project(t: dict, name: str, description: list[str], meta: str, screenshot: Path, label: str | None) -> str:
    top = 64 if label else 8
    shot_w = 700
    with Image.open(screenshot) as image:
        shot_h = round(shot_w * image.height / image.width)
    shot_x = WIDTH - shot_w - 1
    height = top + shot_h + 24
    data = jpeg(screenshot, 1200)
    text_top = top + shot_h / 2 - 70
    desc = ''.join(f'<text x="0" y="{text_top + 62 + i * 32:.0f}" class="muted" style="font-weight:500;font-size:22px">{escape(line)}</text>'
                   for i, line in enumerate(description))
    meta_y = text_top + 62 + len(description) * 32 + 26
    defs = f'<clipPath id="shot"><rect x="{shot_x}" y="{top}" width="{shot_w}" height="{shot_h}" rx="12"/></clipPath>'
    body = f'''{section_label(label, 28, t) if label else ''}
<text x="-2" y="{text_top:.0f}" class="fg" style="font-weight:700;font-size:46px;letter-spacing:-1.6px">{escape(name)}</text>
{desc}
<text x="0" y="{meta_y:.0f}" class="faint" style="font-weight:500;font-size:18px">{escape(meta)}</text>
<text x="0" y="{top + shot_h - 6}" class="fg" style="font-weight:600;font-size:19px">View on GitHub  →</text>
<image x="{shot_x}" y="{top}" width="{shot_w}" height="{shot_h}" href="{data}" xlink:href="{data}" clip-path="url(#shot)" preserveAspectRatio="xMidYMid slice"/>
<rect x="{shot_x + .5}" y="{top + .5}" width="{shot_w - 1}" height="{shot_h - 1}" rx="11.5" fill="none" stroke="{t['wash']}" stroke-opacity=".12"/>'''
    return document(height, name, ' '.join(description), t, body, defs=defs)


# -------------------------------------------------------------- services ---
def services(t: dict) -> str:
    height = 250
    columns = [
        ('Desktop apps', ['Native-feeling Windows', 'apps with care for detail.']),
        ('Web apps', ['Products and dashboards,', 'front to back.']),
        ('Automation', ['Bots, integrations and', 'scripts that do the busywork.']),
        ('Embedded', ['Firmware in C and C++', 'and the tools around it.']),
    ]
    gap = 40
    col_w = (WIDTH - gap * 3) / 4
    markup = []
    for i, (title, lines) in enumerate(columns):
        x = i * (col_w + gap)
        markup.append(f'<text x="{x:.0f}" y="96" class="fg" style="font-weight:650;font-size:23px;letter-spacing:-.3px">{escape(title)}</text>')
        markup += [f'<text x="{x:.0f}" y="{130 + j * 28}" class="muted" style="font-weight:500;font-size:19px">{escape(line)}</text>'
                   for j, line in enumerate(lines)]
    tools = 'Python   ·   TypeScript   ·   C#   ·   C / C++   ·   React   ·   Electron   ·   Node.js   ·   SQL   ·   Linux'
    body = f'''{section_label('What I build', 28, t)}
{''.join(markup)}
<text x="0" y="226" class="faint" xml:space="preserve" style="font-weight:500;font-size:18px">{escape(tools)}</text>'''
    return document(height, 'What I build', 'Desktop apps, web apps, automation and embedded firmware. Tools: ' + tools.replace('   ·   ', ', ') + '.',
                    t, body)


# --------------------------------------------------------------- contact ---
def contact(t: dict) -> str:
    height = 250
    button = 'Request a commission'
    bw = text_width(button, 20, 600) + 84
    body = f'''{section_label('Work with me', 28, t)}
<text x="-2" y="110" class="fg" style="font-weight:700;font-size:40px;letter-spacing:-1.2px">Have something in mind?</text>
<text x="0" y="152" class="muted" style="font-weight:500;font-size:22px">Describe it in an issue. I'll reply with a plan, a timeline and a price.</text>
<rect x="1" y="186" width="{bw:.1f}" height="54" rx="27" fill="{t['wash']}" fill-opacity=".04" stroke="{t['line']}" stroke-width="1.5"/>
<text x="31" y="220" class="fg" style="font-weight:600;font-size:20px">{button}</text>
<path d="M{31 + text_width(button, 20, 600) + 14:.1f} 213 h16 m-6 -6 l6 6 l-6 6" fill="none" stroke="{t['fg']}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'''
    return document(height, 'Request a commission', 'Have something in mind? Request a commission.', t, body)


def main() -> None:
    OUT.mkdir(exist_ok=True)
    for theme, t in THEMES.items():
        files = {
            'intro': intro(t),
            'folio': project(t, 'Folio', ['A calm, private media gallery', 'and player for Windows.'],
                             'Electron  ·  React  ·  FFmpeg', MEDIA / 'folio-library.jpg', 'Selected work'),
            'dustmap': project(t, 'Dustmap', ['See what fills your disk and', "clean up what's gathering dust."],
                               'TypeScript  ·  Electron  ·  C#', MEDIA / 'dustmap-overview.jpg', None),
            'services': services(t),
            'contact': contact(t),
        }
        for name, content in files.items():
            path = OUT / f'{name}-{theme}.svg'
            path.write_text(content, encoding='utf-8')
            print(f'{path.name:20} {len(content.encode()) / 1024:7.1f} KB')


if __name__ == '__main__':
    main()
