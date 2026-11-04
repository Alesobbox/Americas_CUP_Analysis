"""Create educational diagrams and annotate captured dashboard screenshots.

Diagrams use synthetic geometry and arithmetic, with sources identified in the
figure appendix. Original screenshots remain untouched; numbered annotations
occupy margins or empty space and a new caption banner.
"""
from pathlib import Path
import math
from PIL import Image, ImageDraw, ImageFont

PACK = Path(__file__).resolve().parents[1]
ASSETS = PACK / 'assets'
WIDTH, HEIGHT = 1600, 1000
NAVY = '#132d46'
BLUE = '#1769c9'
TEAL = '#087c83'
ORANGE = '#b26012'
RED = '#b83a47'
INK = '#21394f'
MUTED = '#51697c'
PALE = '#edf4fa'
WHITE = '#ffffff'
FONT_DIR = Path('C:/Windows/Fonts')


def font(size, bold=False):
    return ImageFont.truetype(str(FONT_DIR / ('arialbd.ttf' if bold else 'arial.ttf')), size)


def wrap(draw, text, size, max_width, bold=False):
    selected = font(size, bold)
    lines = []
    for paragraph in text.split('\n'):
        words = paragraph.split()
        line = ''
        for word in words:
            candidate = f'{line} {word}'.strip()
            if draw.textlength(candidate, font=selected) <= max_width or not line:
                line = candidate
            else:
                lines.append(line)
                line = word
        lines.append(line)
    return lines


def text(draw, xy, content, size=28, fill=INK, max_width=None, bold=False, spacing=9):
    x, y = xy
    lines = wrap(draw, content, size, max_width, bold) if max_width else content.split('\n')
    for line in lines:
        draw.text((x, y), line, fill=fill, font=font(size, bold))
        y += size + spacing
    return y


def arrow(draw, start, end, fill=BLUE, width=6, head=17):
    draw.line([start, end], fill=fill, width=width)
    angle = math.atan2(end[1] - start[1], end[0] - start[0])
    points = [end]
    for offset in (-0.46, 0.46):
        points.append((end[0] - head * math.cos(angle + offset),
                       end[1] - head * math.sin(angle + offset)))
    draw.polygon(points, fill=fill)


def box(draw, bounds, title, body='', accent=BLUE, size=28):
    draw.rounded_rectangle(bounds, radius=20, fill=PALE, outline=accent, width=3)
    x0, y0, x1, _ = bounds
    y = text(draw, (x0 + 22, y0 + 18), title, 31, accent, x1 - x0 - 44, True)
    if body:
        text(draw, (x0 + 22, y + 7), body, size, INK, x1 - x0 - 44)


def canvas(title, subtitle):
    image = Image.new('RGB', (WIDTH, HEIGHT), WHITE)
    draw = ImageDraw.Draw(image)
    text(draw, (60, 35), title, 48, NAVY, bold=True)
    text(draw, (60, 103), subtitle, 27, MUTED, max_width=1480)
    return image, draw


def save(image, name):
    image.save(ASSETS / name, optimize=True)


def dataflow():
    image, draw = canvas('One source archive two computational paths',
                         'Current responsibilities. The forecast path starts from causal raw-data features.')
    box(draw, (360, 168, 1240, 290), 'Source records and metadata',
        'Boat / mark telemetry, session course, competitor timing', TEAL)
    arrow(draw, (550, 290), (410, 345), TEAL)
    arrow(draw, (1050, 290), (1190, 345), TEAL)
    box(draw, (75, 350, 745, 485), 'Replay ingestion',
        'Identity, local metres, unrounded 100 ms synchronization')
    box(draw, (855, 350, 1525, 485), 'Causal forecast feature dataset',
        'Information cutoffs, scheduled field, prior-only training', TEAL)
    arrow(draw, (410, 485), (410, 530))
    arrow(draw, (1190, 485), (1190, 530), TEAL)
    box(draw, (75, 535, 745, 685), 'Reconstruction and historical analysis',
        'Crossings / progress; source-checked leg metrics and peer indexes')
    box(draw, (855, 535, 1525, 685), 'Forecast models and simulations',
        'State uncertainty, completion, rankings, correlated race / Cup paths', TEAL)
    arrow(draw, (410, 685), (410, 730))
    arrow(draw, (1190, 685), (1190, 730), TEAL)
    box(draw, (75, 735, 745, 855), 'Replay and historical exports',
        'Replay / Analysis / Compare / Reports')
    box(draw, (855, 735, 1525, 855), 'Immutable forecast publications',
        'Live win / pre-race expectation / Cup bounds', TEAL)
    text(draw, (75, 899), 'Python owns historical and forecast arithmetic. Browser owns playback, selection and instantaneous geometry.',
         28, NAVY, max_width=1450, bold=True)
    save(image, 'fig01_dataflow.png')


def dashed_poly(draw, points, fill, width=4, dash=16):
    for a, b in zip(points, points[1:] + points[:1]):
        length = math.dist(a, b)
        count = max(1, int(length / dash))
        for i in range(0, count, 2):
            left = i / count
            right = min(1, (i + 1) / count)
            draw.line([(a[0] + left * (b[0] - a[0]), a[1] + left * (b[1] - a[1])),
                       (a[0] + right * (b[0] - a[0]), a[1] + right * (b[1] - a[1]))],
                      fill=fill, width=width)


def course():
    image, draw = canvas('Read the course before reading the numbers',
                         'Synthetic north-up schematic. Real sessions supply their own gates, axes and boundaries.')
    draw.rounded_rectangle((70, 175, 1020, 935), radius=25, fill='#f0f7fa')
    dashed_poly(draw, [(160, 220), (920, 220), (960, 870), (120, 870)], MUTED)
    draw.polygon([(250, 300), (830, 300), (860, 800), (220, 800)], outline=BLUE, width=5)
    text(draw, (330, 230), 'Safety boundary', 25, MUTED)
    text(draw, (245, 810), 'Race boundary', 25, BLUE)
    for y in (360, 735):
        draw.line([(400, y), (680, y)], fill=ORANGE, width=6)
        for x in (400, 680):
            draw.ellipse((x-13, y-13, x+13, y+13), fill='#f0a12b', outline=ORANGE, width=3)
    text(draw, (380, 313), 'Top gate', 27, ORANGE, bold=True)
    text(draw, (335, 765), 'Start / bottom gate', 27, ORANGE, bold=True)
    arrow(draw, (775, 700), (775, 400), BLUE, 7, 22)
    text(draw, (820, 490), 'Upwind', 25, BLUE)
    arrow(draw, (310, 400), (310, 690), TEAL, 7, 22)
    text(draw, (110, 520), 'Downwind', 25, TEAL)
    up = [(530, 720), (625, 620), (445, 500), (560, 375)]
    draw.line(up, fill=BLUE, width=7)
    arrow(draw, up[-2], up[-1], BLUE, 7, 19)
    draw.ellipse((612, 607, 638, 633), fill=WHITE, outline=BLUE, width=4)
    text(draw, (645, 610), 'Tack', 24, BLUE)
    down = [(500, 375), (375, 470), (600, 590), (480, 720)]
    draw.line(down, fill=TEAL, width=7)
    arrow(draw, down[-2], down[-1], TEAL, 7, 19)
    draw.ellipse((362, 457, 388, 483), fill=WHITE, outline=TEAL, width=4)
    text(draw, (355, 425), 'Gybe', 24, TEAL)
    arrow(draw, (1100, 260), (1100, 360), ORANGE, 8, 24)
    text(draw, (1050, 188), 'Wind FROM north', 31, ORANGE, max_width=470, bold=True)
    text(draw, (1060, 395), 'Wind comes from the named bearing. A boat tacks with its bow through the wind and gybes with its stern through it.',
         28, INK, max_width=450)
    text(draw, (1060, 625), 'Heading: where the bow points.\nCOG: direction of ground motion.\nSOG: speed over ground.',
         28, INK, max_width=450)
    text(draw, (1060, 815), 'Gate crossings and boundary exposure are reconstructed geometry, not official rulings.',
         27, RED, max_width=450, bold=True)
    save(image, 'fig02_course.png')


def geometry():
    image, draw = canvas('Three reasons a smooth replay needs interpretation',
                         'Synthetic values. Each panel exposes a different transformation or assumption.')
    panels = [(50, 185, 525, 925), (562, 185, 1037, 925), (1075, 185, 1550, 925)]
    for bounds in panels:
        draw.rounded_rectangle(bounds, radius=20, fill=PALE)
    text(draw, (75, 212), '1 Shortest angular arc', 29, BLUE, bold=True)
    center, radius = (286, 440), 145
    draw.ellipse((center[0]-radius, center[1]-radius, center[0]+radius, center[1]+radius), outline='#a9bdce', width=4)
    for angle, label, tx in [(350, '350°', 125), (10, '10°', 355)]:
        a = math.radians(angle)
        endpoint = (center[0]+radius*math.sin(a), center[1]-radius*math.cos(a))
        arrow(draw, center, endpoint, BLUE, 6, 18)
        text(draw, (tx, 275), label, 29, BLUE, bold=True)
    text(draw, (228, 386), '0°', 36, TEAL, bold=True)
    text(draw, (80, 640), 'Shortest change = +20°\nHalfway = 0°\nArithmetic mean = 180°',
         29, INK, max_width=415)
    text(draw, (80, 798), 'Wrapping avoids an invented rotation through south.', 27, MUTED, max_width=410)
    text(draw, (585, 212), '2 A crossing fraction', 29, BLUE, bold=True)
    draw.line([(620, 510), (980, 510)], fill=ORANGE, width=5)
    text(draw, (615, 540), 'Gate (0,0) to (100,0)', 27, ORANGE)
    arrow(draw, (728, 650), (728, 300), BLUE, 6, 18)
    draw.ellipse((719, 501, 737, 519), fill=RED)
    text(draw, (750, 641), '(30,-2)', 25, BLUE)
    text(draw, (750, 298), '(30,+3)', 25, BLUE)
    text(draw, (590, 720), 'u = 2 / (2 + 3) = 0.4\n100 ms interval → +40 ms\nGate fraction = 30 / 100',
         27, INK, max_width=420)
    text(draw, (590, 850), 'Code also permits a 20%\nendpoint extension.', 25, RED, max_width=420)
    text(draw, (1100, 212), '3 A gap still has endpoints', 28, BLUE, max_width=415, bold=True)
    a, b = (1130, 470), (1490, 470)
    dashed_poly(draw, [a, b], BLUE, width=4, dash=18)
    for x in (1130, 1490):
        draw.ellipse((x-12, 458, x+12, 482), fill=TEAL)
    text(draw, (1115, 515), '0 s', 27, TEAL)
    text(draw, (1455, 515), '10 s', 27, TEAL)
    for i in range(1, 10):
        x = 1130 + 36*i
        draw.ellipse((x-4, 466, x+4, 474), fill=BLUE)
    text(draw, (1110, 615), 'A 100 ms visual grid can bridge an unobserved 10 s interval.',
         29, INK, max_width=410)
    text(draw, (1110, 765), 'Historical source coverage rejects gaps longer than 2 s.',
         28, RED, max_width=410, bold=True)
    save(image, 'fig03_geometry.png')


def performance():
    image, draw = canvas('A peer index averages ratios on matching legs',
                         'Synthetic arithmetic. Selected boat is excluded; each eligible peer and matched leg has one vote.')
    box(draw, (65, 195, 755, 695), 'Published equal-leg calculation', accent=BLUE)
    text(draw, (100, 290), 'Leg     Selected     Peer mean     Index', 28, NAVY, bold=True)
    text(draw, (100, 375), '1          20 kt           10 kt            200', 31)
    text(draw, (100, 455), '3          30 kt           30 kt            100', 31)
    draw.line([(100, 525), (715, 525)], fill='#bdcddd', width=3)
    text(draw, (100, 565), '(200 + 100) / 2 = 150', 39, BLUE, bold=True)
    box(draw, (845, 195, 1535, 695), 'A different aggregate calculation', accent=ORANGE)
    text(draw, (885, 295), 'Selected raw mean = 25 kt', 31)
    text(draw, (885, 375), 'Peer raw mean = 20 kt', 31)
    text(draw, (885, 475), '100 × 25 / 20 = 125', 39, ORANGE, bold=True)
    text(draw, (885, 565), '125 does not reconstruct the\npublished dimension index.', 29, RED, max_width=610)
    text(draw, (90, 760), 'Why they differ', 31, NAVY, bold=True)
    text(draw, (90, 817), 'Mean(selected / peer) generally differs from mean(selected) / mean(peer).\nAn index of 110 supports a 10% average relative difference under this weighting and scope.',
         31, INK, max_width=1420)
    text(draw, (90, 932), 'It does not establish intrinsic ability, a causal tactical effect or a win probability.', 27, RED, bold=True)
    save(image, 'fig04_peer_index.png')


def uncertainty():
    image, draw = canvas('Unresolved paths and persistent uncertainty',
                         'Two synthetic calculations. Numerical simulation error is separate from both mechanisms.')
    box(draw, (60, 190, 800, 865), 'Bounds from 100 tournament trials', accent=BLUE)
    counts = [(40, BLUE, 'A 40'), (25, TEAL, 'B 25'), (15, ORANGE, 'C 15'), (20, '#cbd4dd', '? 20')]
    x = 100
    for count, color, label in counts:
        span = count * 6.6
        draw.rectangle((x, 305, x+span, 380), fill=color)
        text(draw, (x+8, 405), label, 25, INK)
        x += span
    text(draw, (100, 500), 'A: [0.40, 0.60]\nB: [0.25, 0.45]\nC: [0.15, 0.35]', 34, BLUE, bold=True)
    text(draw, (100, 675), 'Upper limits give all unresolved paths to each team separately.\nLower sum = 0.80; upper sum = 1.40.', 29, INK, max_width=650)
    text(draw, (100, 803), 'Do not normalize these endpoints.', 27, RED, bold=True)
    box(draw, (850, 190, 1540, 865), 'A shared latent strength across races', accent=TEAL)
    text(draw, (890, 292), 'Choose once per series:', 30, INK)
    box(draw, (900, 365, 1185, 475), 'p = 0.8', '50% chance', TEAL, size=24)
    box(draw, (1210, 365, 1495, 475), 'p = 0.2', '50% chance', TEAL, size=24)
    text(draw, (890, 535), 'Marginal race win = 0.5', 31, TEAL, bold=True)
    text(draw, (890, 600), 'P(two wins)\n= 0.5 × 0.8² + 0.5 × 0.2²\n= 0.34', 31, INK, max_width=610)
    text(draw, (890, 760), 'Independent 0.5 draws would give\n0.25 and a different series model.', 28, RED, max_width=610)
    text(draw, (80, 913), 'More trials refine the specified calculation. They cannot resolve a missing rule or identify transfer loading.',
         28, NAVY, max_width=1440, bold=True)
    save(image, 'fig05_uncertainty.png')


ANNOTATIONS = {
    'replay': [
        ((16, 303), '1 Grid mode renders without remote map tiles.'),
        ((1035, 484), '2 Selected FRA follows the shared race and playhead.'),
        ((1395, 407), '3 Lead margin is an estimate; displayed VMG keeps its course-axis sign.')],
    'analysis': [
        ((480, 492), '1 The selected race identifies the analysis artifact.'),
        ((1330, 673), '2 Source limitations distinguish calculated results from verified official results.'),
        ((1330, 929), '3 Classification and metrics are retrospective exported evidence.')],
    'compare': [
        ((90, 475), '1 A and B remain explicit selections at the shared playhead.'),
        ((1340, 831), '2 Separation, progress difference and leg offset answer different questions.'),
        ((1340, 920), '3 Closure is positive when approaching; a held GBR B trace needs source review.')],
    'reports': [
        ((1415, 374), '1 Results and timings are calculated and have not been independently verified.'),
        ((1415, 523), '2 Canonical metrics carry units, quality and covered seconds.'),
        ((312, 771), '3 USA retains its nested start-state conflict beside the calculated result.')],
    'forecast': [
        ((1420, 325), '1 Three tabs select three targets and their separate evidence contracts.'),
        ((1420, 599), '2 Live probabilities follow publication availability at the shared playhead.'),
        ((1420, 880), '3 Estimated state and source age are support information, not calibration proof.')],
}


def annotate():
    for stem, callouts in ANNOTATIONS.items():
        original = Image.open(ASSETS / f'{stem}.png').convert('RGB')
        width, height = original.size
        top = 66
        banner = 245
        image = Image.new('RGB', (width, height + top + banner), WHITE)
        image.paste(original, (0, top))
        draw = ImageDraw.Draw(image)
        text(draw, (28, 17), f'{stem.capitalize()} workspace  |  captured current interface', 29, NAVY, bold=True)
        draw.rectangle((0, height+top, width, height+top+banner), fill=PALE)
        for number, ((x, y), caption) in enumerate(callouts, 1):
            cy = y + top
            radius = 15
            draw.ellipse((x-radius, cy-radius, x+radius, cy+radius), fill=BLUE, outline=WHITE, width=3)
            bbox = draw.textbbox((0, 0), str(number), font=font(19, True))
            draw.text((x-(bbox[2]-bbox[0])/2, cy-12), str(number), font=font(19, True), fill=WHITE)
            text(draw, (32, height+top+25+(number-1)*66), caption, 25, INK, max_width=width-65)
        image.save(ASSETS / f'{stem}_annotated.png', optimize=True)


def main():
    ASSETS.mkdir(parents=True, exist_ok=True)
    for create in (dataflow, course, geometry, performance, uncertainty):
        create()
    annotate()
    for file in sorted(ASSETS.glob('fig*.png')):
        with Image.open(file) as image:
            print(f'{file.name}: {image.width}x{image.height}')
    print('Annotated five screenshots with retained original content and caption banners.')


if __name__ == '__main__':
    main()
