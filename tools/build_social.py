#!/usr/bin/env python3
"""Render the social card with the site's Georgia typeface (Pillow required)."""
import argparse
import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

parser = argparse.ArgumentParser()
parser.add_argument('--font', default='/System/Library/Fonts/Supplemental/Georgia.ttf')
args = parser.parse_args()
scale = 3
im = Image.new('RGB', (1200*scale, 630*scale), 'white')
d = ImageDraw.Draw(im)
def ellipse(box, **kw):
    d.ellipse(tuple(int(v*scale) for v in box), **kw)
def text(x,y,value,size,fill='#111111',anchor=None):
    d.text((x*scale,y*scale),value,font=ImageFont.truetype(args.font,size*scale),fill=fill,anchor=anchor)
cx,cy,r=1195,315,403
ellipse((cx-r-15,cy-r-15,cx+r+15,cy+r+15),fill='#111111')
ellipse((cx-r-10,cy-r-10,cx+r+10,cy+r+10),fill='white')
for i in range(37):
    a=-90+i*360/37
    d.pieslice(tuple(int(v*scale) for v in (cx-r,cy-r,cx+r,cy+r)),a,a+360/37,fill='#b5222c' if i%2==0 else '#171717',outline='white',width=2*scale)
ellipse((cx-r+86,cy-r+86,cx+r-86,cy+r-86),fill='white')
ellipse((cx-r+105,cy-r+105,cx+r-105,cy+r-105),outline='#111111',width=2*scale)
for i in range(37):
    a=math.radians(-90+(i+.5)*360/37)
    x,y=cx+(r-43)*math.cos(a),cy+(r-43)*math.sin(a)
    text(x,y,str(i),20,'white','mm')

text(68,155,'MATH',116)
text(62,280,'GAMBLING',116)
text(70,488,'x³ + y³ + z³ = 114',28)
out=Path(__file__).resolve().parents[1]/'web/assets/social.png'
im.resize((1200,630),Image.Resampling.LANCZOS).save(out,optimize=True)
print(out)
