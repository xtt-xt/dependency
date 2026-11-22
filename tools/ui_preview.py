# -*- coding: utf-8 -*-
"""ui_preview.py -- pixel-accurate previews for MC JSON UI textures / nine-slice / layout.

为什么需要它
------------
JSON UI 改完只能进游戏看，而且「贴图替换必须完全重启游戏」才重新加载。改九宫、改贴图之前
先用本脚本按引擎规则重演一遍，就能提前看出：边框到底几 px、九宫切片有没有把内区吃掉、
进度裁剪到哪、控件百分比落在哪，省掉一轮「改 → 重启 → 进游戏 → 还是不对」。

子命令
------
pixels   打印贴图每个像素（判断九宫该切几）
nine     按 9 宫把贴图拉伸到目标尺寸（重演引擎渲染）
bar      模拟 common.slider：原版 1px 边框 + 内缩 2px 的底图/进度 + 手柄
profile  量真实截图某一列/行的颜色分段（反推边框几 px、内区多高）
sheet    多张图拼一张对照图（NEAREST 放大 + 标签）
mktex    生成「1px 顶高光 + 平色 + 1px 底暗边」的三色带贴图（配 nineslice [1,1,1,1]）
card     模拟一个内容项卡片：九宫底图 + 指定颜色的标题/正文（查配色可读性，默认琥珀色）

Python 需要 Pillow。本机没有系统 Python3 时用 DSH 内置运行时
（路径可用 load_workspace_dependencies 查）：

    PY="C:\\Users\\acer\\.dsh\\dsh-runtimes\\dsh-primary-runtime\\dependencies\\python\\python.exe"
    $PY tools/ui_preview.py pixels resource_pack_nka0OOhF/textures/ui/slider/slider_backdrop.png
    $PY tools/ui_preview.py nine  <png> --w 224 --h 8 --slice 1 --zoom 6 --out %TEMP%\\preview.png
    $PY tools/ui_preview.py bar   <bg.png> --progress <pr.png> --slice 1 --fill 0.55 --out %TEMP%\\bar.png
    $PY tools/ui_preview.py profile shot.png --x 900 --y0 258 --y1 300
    $PY tools/ui_preview.py sheet   --out %TEMP%\\sheet.png --zoom 6 "before=old.png" "after=new.png"
    $PY tools/ui_preview.py mktex   --top A9AAAE --fill 9A9B9F --bottom 8A8B8F --out out.png

约定
----
* 放大一律 Image.NEAREST，1px 边框才看得清；双线性会把问题糊掉。
* 九宫切片顺序 [左,上,右,下]；重演 MC 的 nineslice_size 时四值通常相同。
* 目标尺寸比「2 × 切片」还小时自动跳过该区域，不会崩。
* 控制台输出用英文（Windows 中文控制台会把 UTF-8 中文打成乱码）；图里的标签支持中文
  （自动找系统 CJK 字体，找不到就退回默认字体、中文会变方块）。
"""
from __future__ import print_function

import argparse
import os
import sys

from PIL import Image, ImageDraw, ImageFont

BAR_BG = (72, 73, 75, 255)   # 设置界面内容区底色，对照图用它当背景
LABEL_FG = (212, 212, 212)

_FONT_CANDIDATES = [
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\msyhbd.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
    r"C:\Windows\Fonts\segoeui.ttf",
]


def _font(size=14):
    for p in _FONT_CANDIDATES:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()


# ---------------------------------------------------------------- 基础渲染
def nineslice(src, w, h, s):
    """把 src 按 9 宫拉伸到 w×h。s = (左, 上, 右, 下) 切片像素。"""
    sl, st, sr, sb = s
    sw, sh = src.size
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    cols = [(0, sl), (sl, sw - sr), (sw - sr, sw)]
    rows = [(0, st), (st, sh - sb), (sh - sb, sh)]
    dxs = [0, sl, w - sr]
    dys = [0, st, h - sb]
    dws = [sl, w - sl - sr, sr]
    dhs = [st, h - st - sb, sb]
    for i in range(3):
        for j in range(3):
            if dws[i] <= 0 or dhs[j] <= 0:
                continue
            box = (cols[i][0], rows[j][0], cols[i][1], rows[j][1])
            if box[2] <= box[0] or box[3] <= box[1]:
                continue
            out.paste(src.crop(box).resize((dws[i], dhs[j]), Image.NEAREST), (dxs[i], dys[j]))
    return out


def frame_fill(bg, w, h, slice_px, border=1, bg_color=(0, 0, 0, 255)):
    """模拟 common.slider：外层 border 像素纯色框 + 内缩 2*border 的九宫底图。"""
    canvas = Image.new("RGBA", (w, h), bg_color)
    iw, ih = w - 2 * border, h - 2 * border
    if iw > 0 and ih > 0:
        canvas.paste(nineslice(bg, iw, ih, slice_px), (border, border))
    return canvas


def handle(size=16, face=(0xD0, 0xD1, 0xD4), edge=(0x12, 0x12, 0x12), top=(0xE6, 0xE7, 0xE9)):
    """MC 滑条手柄：1px 深色边 + 浅色面 + 顶部高光。"""
    im = Image.new("RGBA", (size, size), edge + (255,))
    im.paste(Image.new("RGBA", (size - 2, size - 2), face + (255,)), (1, 1))
    im.paste(Image.new("RGBA", (size - 2, max(1, size // 4)), top + (255,)), (1, 1))
    return im


def vband_texture(w, h, top, fill, bottom):
    """生成「1px 顶高光 + 平色填充 + 1px 底暗边」的竖直渐变贴图（配 nineslice [1,1,1,1]）。"""
    im = Image.new("RGBA", (w, h), fill + (255,))
    px = im.load()
    for x in range(w):
        px[x, 0] = top + (255,)
        px[x, h - 1] = bottom + (255,)
    return im


def hexrgb(s):
    s = s.strip().lstrip("#")
    if len(s) != 6:
        raise ValueError("color must be RRGGBB: %r" % s)
    return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))


def runs(coords):
    """把一串采样点压成 [(颜色, 连续长度), ...]。"""
    out = []
    for c in coords:
        if out and out[-1][0] == c:
            out[-1][1] += 1
        else:
            out.append([c, 1])
    return [(c, n) for c, n in out]


# ---------------------------------------------------------------- 子命令
def cmd_pixels(args):
    for path in args.png:
        im = Image.open(path).convert("RGBA")
        px = im.load()
        print("== %s  %dx%d" % (os.path.basename(path), im.size[0], im.size[1]))
        for y in range(im.size[1]):
            print("  y%-3d " % y + " ".join("%02X%02X%02X/%d" % px[x, y] for x in range(im.size[0])))
        print("  row0 colors: %s" % sorted(set(px[x, 0][:3] for x in range(im.size[0]))))
        print("  col0 colors: %s" % sorted(set(px[0, y][:3] for y in range(im.size[1]))))


def cmd_nine(args):
    src = Image.open(args.png).convert("RGBA")
    s = args.slice if args.slice > 0 else 1
    im = nineslice(src, args.w, args.h, (s, s, s, s))
    out = args.out or os.path.join(os.environ.get("TEMP", "."), "nine.png")
    room = args.pad * 2
    canvas = Image.new("RGBA", (im.size[0] + room, im.size[1] + room), BAR_BG)
    canvas.alpha_composite(im, (args.pad, args.pad))
    canvas.resize((canvas.size[0] * args.zoom, canvas.size[1] * args.zoom), Image.NEAREST).save(out)
    print("%s -> %s (src %dx%d, slice %d, dest %dx%d, zoom %d)" % (
        os.path.basename(args.png), out, src.size[0], src.size[1], s, args.w, args.h, args.zoom))


def cmd_bar(args):
    bg = Image.open(args.bg).convert("RGBA")
    pr = Image.open(args.progress).convert("RGBA")
    s = (args.slice,) * 4
    canvas = frame_fill(bg, args.w, args.h, s, args.border)
    iw, ih = args.w - 2 * args.border, args.h - 2 * args.border
    fw = max(0, int(iw * args.fill))
    if fw:
        canvas.paste(nineslice(pr, fw, ih, s), (args.border, args.border))
    pad = max(4, args.zoom * 2)
    hh = args.handle if args.handle else 0
    out_im = Image.new("RGBA", (args.w + pad * 2, max(args.h, hh) + pad * 2), BAR_BG)
    oy = (out_im.size[1] - args.h) // 2
    out_im.alpha_composite(canvas, (pad, oy))
    if hh:
        h = handle(hh)
        hx = min(max(0, int(args.w * args.fill) - h.size[0] // 2), args.w - h.size[0]) + pad
        out_im.alpha_composite(h, (hx, (out_im.size[1] - h.size[1]) // 2))
    out = args.out or os.path.join(os.environ.get("TEMP", "."), "bar.png")
    out_im.resize((out_im.size[0] * args.zoom, out_im.size[1] * args.zoom), Image.NEAREST).save(out)
    print(out)


def cmd_profile(args):
    im = Image.open(args.png).convert("RGB")
    px = im.load()
    if args.x is not None:
        if args.y1 <= args.y0:
            sys.exit("need --y1 > --y0")
        coords = [px[args.x, y] for y in range(args.y0, args.y1)]
        print("column x=%d  y %d..%d" % (args.x, args.y0, args.y1 - 1))
    else:
        if args.x1 <= args.x0:
            sys.exit("need --x1 > --x0")
        coords = [px[x, args.y] for x in range(args.x0, args.x1)]
        print("row y=%d  x %d..%d" % (args.y, args.x0, args.x1 - 1))
    total = 0
    for c, n in runs(coords):
        print("  %3dpx  #%02X%02X%02X  %s" % (n, c[0], c[1], c[2], str(c)))
        total += n
    print("  total %d" % total)


def cmd_sheet(args):
    views = []
    for spec in args.items:
        label, _, path = spec.rpartition("=")
        if not path or not os.path.exists(path):
            label, path = os.path.basename(spec), spec
        im = Image.open(path).convert("RGBA")
        im = im.resize((im.size[0] * args.zoom, im.size[1] * args.zoom), Image.NEAREST)
        views.append((label, im))
    if not views:
        sys.exit("no items")
    w = max(v.size[0] for _, v in views)
    fsize = max(14, min(64, w // 40))
    font = _font(fsize)
    line = fsize + 10
    h = sum(v.size[1] + line for _, v in views) + line // 2
    sheet = Image.new("RGB", (w + 20, h), BAR_BG[:3])
    d = ImageDraw.Draw(sheet)
    y = line // 2
    for label, v in views:
        d.text((10, y), label, fill=LABEL_FG, font=font)
        y += line
        sheet.paste(v, (10, y), v)
        y += v.size[1]
    out = args.out or os.path.join(os.environ.get("TEMP", "."), "sheet.png")
    sheet.save(out)
    print(out)


def cmd_mktex(args):
    im = vband_texture(args.w, args.h, hexrgb(args.top), hexrgb(args.fill), hexrgb(args.bottom))
    im.save(args.out, optimize=True)
    print("%s  %dx%d  top=#%s fill=#%s bottom=#%s  (%d bytes; pair with nineslice_size [1,1,1,1])" % (
        args.out, args.w, args.h, args.top.lstrip("#").upper(), args.fill.lstrip("#").upper(),
        args.bottom.lstrip("#").upper(), os.path.getsize(args.out)))


def cmd_card(args):
    """模拟一个内容项卡片：九宫拉伸底色贴图 + 按指定颜色画标题/正文（查配色可读性）。"""
    bg_src = Image.open(args.tex).convert("RGBA")
    sl = args.slice if args.slice > 0 else 1
    sl = min(sl, bg_src.size[0] // 2, bg_src.size[1] // 2)
    title_font = _font(args.font_size + 4)
    body_font = _font(args.font_size)
    lines = (args.text or "").replace("|", "\n").split("\n")
    line_h = int(args.font_size * 1.4)
    head = (args.font_size + 10) if args.title else 0
    h = args.pad * 2 + head + line_h * len(lines)
    card = nineslice(bg_src, args.w, h, (sl, sl, sl, sl))
    d = ImageDraw.Draw(card)
    y = args.pad
    if args.title:
        d.text((args.pad, y), args.title, font=title_font, fill=hexrgb(args.title_color) + (255,))
        y += head
    for ln in lines:
        d.text((args.pad, y), ln, font=body_font, fill=hexrgb(args.body_color) + (255,))
        y += line_h
    if args.zoom > 1:
        card = card.resize((card.size[0] * args.zoom, card.size[1] * args.zoom), Image.NEAREST)
    canvas = Image.new("RGB", (card.size[0] + 16, card.size[1] + 16), BAR_BG[:3])
    canvas.paste(card, (8, 8), card)
    out = args.out or os.path.join(os.environ.get("TEMP", "."), "card.png")
    canvas.save(out)
    print("%s  card %dx%d (zoom x%d)  title=#%s body=#%s" % (
        out, args.w, h, args.zoom, args.title_color.lstrip("#").upper(),
        args.body_color.lstrip("#").upper()))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Pixel-accurate previews for MC JSON UI textures/nine-slice/layout.")
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("pixels", help="dump every pixel as RGBA")
    p.add_argument("png", nargs="+")
    p.set_defaults(func=cmd_pixels)

    p = sub.add_parser("nine", help="stretch one texture by 9-slice and save a zoomed png")
    p.add_argument("png")
    p.add_argument("--w", type=int, default=224)
    p.add_argument("--h", type=int, default=10)
    p.add_argument("--slice", type=int, default=1, help="slice px applied to all four edges (0 -> 1)")
    p.add_argument("--pad", type=int, default=2, help="padding around the rendered rect")
    p.add_argument("--zoom", type=int, default=6)
    p.add_argument("--out")
    p.set_defaults(func=cmd_nine)

    p = sub.add_parser("bar", help="simulate common.slider: 1px frame + inset bg/progress + handle")
    p.add_argument("bg")
    p.add_argument("--progress", required=True)
    p.add_argument("--w", type=int, default=224)
    p.add_argument("--h", type=int, default=10)
    p.add_argument("--slice", type=int, default=1)
    p.add_argument("--border", type=int, default=1, help="width of the vanilla slider_border, usually 1")
    p.add_argument("--fill", type=float, default=0.0, help="progress ratio 0..1")
    p.add_argument("--handle", type=int, default=16, help="handle size, 0 = no handle")
    p.add_argument("--zoom", type=int, default=6)
    p.add_argument("--out")
    p.set_defaults(func=cmd_bar)

    p = sub.add_parser("profile", help="measure color runs of one column/row of a screenshot")
    p.add_argument("png")
    p.add_argument("--x", type=int)
    p.add_argument("--y0", type=int, default=0)
    p.add_argument("--y1", type=int, default=0)
    p.add_argument("--y", type=int)
    p.add_argument("--x0", type=int, default=0)
    p.add_argument("--x1", type=int, default=0)
    p.set_defaults(func=cmd_profile)

    p = sub.add_parser("sheet", help="stack labelled images into one contact sheet (NEAREST zoom)")
    p.add_argument("items", nargs="+", help="label=path, or a bare path")
    p.add_argument("--zoom", type=int, default=6)
    p.add_argument("--out")
    p.set_defaults(func=cmd_sheet)

    p = sub.add_parser("mktex", help="generate a 3-band vertical texture (top highlight / fill / bottom shade)")
    p.add_argument("--top", default="A9AAAE")
    p.add_argument("--fill", default="9A9B9F")
    p.add_argument("--bottom", default="8A8B8F")
    p.add_argument("--w", type=int, default=5)
    p.add_argument("--h", type=int, default=5)
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_mktex)

    p = sub.add_parser("card", help="mock one content card: 9-slice background + coloured title/body text")
    p.add_argument("--tex", default="resource_pack_nka0OOhF/textures/ui/content.png",
                   help="card background texture (default: setting.text_content's textures/ui/content)")
    p.add_argument("--title", default="")
    p.add_argument("--text", default="", help="body text, use | as line break")
    p.add_argument("--title-color", default="FFB83D", help="RRGGBB (default: the amber of setting.notice_content)")
    p.add_argument("--body-color", default="F7E0AD")
    p.add_argument("--w", type=int, default=560)
    p.add_argument("--pad", type=int, default=14)
    p.add_argument("--slice", type=int, default=1)
    p.add_argument("--font-size", type=int, default=12)
    p.add_argument("--zoom", type=int, default=2)
    p.add_argument("--out")
    p.set_defaults(func=cmd_card)

    args = ap.parse_args(argv)
    if not getattr(args, "func", None):
        ap.print_help()
        return 1
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
