#!/usr/bin/env python3
"""ecp5-versa-pmod: generate the KiCad project (symbol/footprint libraries, schematic, board).

Run with the python3 that has KiCad 10's `pcbnew` bindings:   python3 tools/generate.py

The KiCad files written here are the design (edit them in KiCad from now on); this script
documents how rev A was derived and can regenerate it.  Geometry: millimetres, KiCad board axes
(x right, y down); the Versa board edge is the adapter's top edge (y = 0).

Everything about pin assignment comes from the two tables X4 and PORTS below; the schematic,
the board, the silkscreen and the pin map are all generated from them, so they cannot disagree.
"""
import json
import math
import os
import re
import uuid

import pcbnew
from pcbnew import FromMM as mm, VECTOR2I

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NAME = "ecp5-versa-pmod"
REV = "A"
DATE = "2026-11-12"
KICAD_FP = "/usr/share/kicad/footprints/"
KICAD_SYM = "/usr/share/kicad/symbols/"

# ---------------------------------------------------------------------------------------------
# Versa X4 (Lattice FPGA-EB-02021, Table 12 / schematic sheet 10) and the ECP5 PT site names
# ---------------------------------------------------------------------------------------------
X4 = {1: ("RESOUT#", "A8"), 2: ("GND", ""), 19: ("GND", ""), 20: ("3V3", ""), 22: ("GND", ""),
      24: ("GND", ""), 26: ("GND", ""), 30: ("GND", ""), 34: ("GND", ""), 38: ("CARDSEL#", "A7"),
      40: ("GND", "")}
for i, ball in enumerate("A12 A13 B13 C13 D13 E13 A14 C14 D14 E14 D11 C10 A9 B10 D12 E12".split()):
    X4[3 + i] = ("IO%d" % i, ball)
_HI = (21, 23, 25, 27, 28, 29, 31, 32, 33, 35, 36, 37, 39)
for i, (pin, ball) in enumerate(zip(_HI, "B15 C15 D15 E15 A16 B16 C16 D16 B17 C17 A17 B18 A18".split())):
    X4[pin] = ("IO%d" % (16 + i), ball)
assert len(X4) == 40
PT = {  # ball -> ECP5 pad name (prjtrellis iodb / Versa schematic); A = true, B = complement
    "A12": "PT49A", "A13": "PT49B", "B13": "PT51A", "C13": "PT51B", "D13": "PT53A", "E13": "PT53B",
    "A14": "PT56A", "C14": "PT56B", "D14": "PT58A", "E14": "PT58B", "D11": "PT42A/PCLKT1_1",
    "C10": "PT31B", "A9": "PT33A/GR_PCLK0_1", "B10": "PT33B/GR_PCLK0_0", "D12": "PT47A/GR_PCLK1_0",
    "E12": "PT47B/GR_PCLK1_1", "B15": "PT69A", "C15": "PT69B", "D15": "PT71A", "E15": "PT71B",
    "A16": "PT74A", "B16": "PT74B", "C16": "PT76A", "D16": "PT76B", "B17": "PT78A", "C17": "PT78B",
    "A17": "PT80A", "B18": "PT80B", "A7": "PT18A", "A8": "PT18B", "A18": "PT83A"}

# Port -> four columns; each column (X4 pin for Pmod pin j, X4 pin for Pmod pin 6+j)
PORTS = {"A": [(3, 4), (5, 6), (7, 8), (9, 10)],
         "B": [(11, 12), (13, 14), (15, 16), (17, 18)],
         "C": [(21, 23), (25, 27), (28, 29), (31, 32)]}
PORT_REF = {"A": "J2", "B": "J3", "C": "J4"}
# 1BitSquared 12-bit DVI Pmod v1.1a: module J2 mates with port A, J1 with port B
DVI = {"A": {1: "R3", 2: "R1", 3: "G3", 4: "G1", 7: "R2", 8: "R0", 9: "G2", 10: "G0"},
       "B": {1: "B3", 2: "CLK", 3: "B0", 4: "HS", 7: "B2", 8: "B1", 9: "DE", 10: "VS"}}


def lines():
    """All 24 signal lines in resistor order: port A pin 1, 7, 2, 8, ... then B, then C."""
    out = []
    n = 0
    for port in "ABC":
        for j, (pa, pb) in enumerate(PORTS[port], start=1):
            for pmod, x4 in ((j, pa), (6 + j, pb)):
                n += 1
                out.append(dict(port=port, pmod=pmod, x4=x4, io=X4[x4][0], ball=X4[x4][1],
                                r="R%d" % n, net_io=X4[x4][0], net_p="P%s%d" % (port, pmod)))
    return out


LINES = lines()

# ---------------------------------------------------------------------------------------------
# parts (LCSC numbers: see README for what was verified)
# ---------------------------------------------------------------------------------------------
R_VAL = "33R"
PARTS = {  # ref -> (value, footprint lib:name, LCSC, MPN, description)
    "J1": ("Versa X4", "Connector_PinSocket_2.54mm:PinSocket_2x20_P2.54mm_Vertical", "C2977589",
           "ZHOURI 2.54-2*20", "2x20 female socket 2.54 mm, 8.5 mm, bottom side, onto Versa X4"),
    "F1": ("0.5A", "Fuse:Fuse_1206_3216Metric", "", "PTC 1206 Ihold 0.5 A",
           "resettable fuse in the 3V3 feed from X4 pin 20"),
    "C1": ("10uF", "Capacitor_SMD:C_0805_2012Metric", "C15850", "Samsung CL21A106KAYNNNE",
           "10 uF 25 V X5R 0805"),
    "R25": ("1k", "Resistor_SMD:R_0603_1608Metric", "C21190", "UNI-ROYAL 0603WAF1001T5E", "1 k 0603, LED"),
    "D1": ("GREEN", "LED_SMD:LED_0603_1608Metric", "C72043", "Everlight 19-217/GHC-YR1S2/3T",
           "green LED 0603, 3V3 indicator"),
}
for p in "ABC":
    PARTS[PORT_REF[p]] = ("PMOD %s" % p, "%s:Pmod_Host_2x06_Horizontal" % NAME, "C2897426",
                          "HCTL PM254-2-06-W-8.5", "Pmod host port %s, 2x6 female right angle 2.54 mm" % p)
for i, ref in enumerate(("C2", "C3", "C4")):
    PARTS[ref] = ("100nF", "Capacitor_SMD:C_0603_1608Metric", "C14663", "YAGEO CC0603KRX7R9BB104",
                  "100 nF 50 V X7R 0603, one per port")
for l in LINES:
    PARTS[l["r"]] = (R_VAL, "Resistor_SMD:R_0603_1608Metric", "C23140", "UNI-ROYAL 0603WAF330JT5E",
                     "33 ohm 0603, series resistor in every Pmod signal")

# ---------------------------------------------------------------------------------------------
# board geometry
# ---------------------------------------------------------------------------------------------
P = 2.54
X1 = 3.0                 # X4 socket column 1 (pins 1/2)
Y_EVEN = 37.1            # X4 even row (faces the Versa edge = top)
Y_ODD = Y_EVEN + P       # X4 odd row (pin 1 bottom left)
Y_FAR = 12.70            # port pads 1..6  (inner row)
Y_NEAR = 10.16           # port pads 7..12 (0.40 in from the edge, Pmod spec fig. 5)
XA = X1 + P              # port A pin 1 column = X4 column 2
PORT_PITCH = 22.86
PORT_X = {"A": XA, "B": XA + PORT_PITCH, "C": XA + 2 * PORT_PITCH}
BOARD_W = 67.0
BOARD_H = 42.5
Y_R1, Y_R2 = 34.0, 30.7  # resistor rows (R1 nearer the socket); 0603 courtyards are 2.96 mm long
Y_D0 = 28.9              # doglegs start here
SLOPE = math.tan(math.radians(60))   # horizontal shift per mm of vertical travel in a dogleg
HALF = 0.635             # river offset: A-side line at x_t - HALF, B-side line at x_t + HALF
Y_JOG = Y_FAR + 2.2      # end of the vertical run below the far row
TRACK = 0.25
PWR = 0.5
VIA_D, VIA_DRILL = 0.6, 0.3


def xcol(c):
    return X1 + P * (c - 1)


def x4_pos(pin):
    c = (pin + 1) // 2
    return (xcol(c), Y_EVEN if pin % 2 == 0 else Y_ODD)


def port_pad(port, pmod):
    k = pmod if pmod <= 6 else pmod - 6
    return (PORT_X[port] + P * (k - 1), Y_FAR if pmod <= 6 else Y_NEAR)


def escape_x(pin):
    """x of the vertical run right above the X4 socket (odd pins leave through the gap on their left)."""
    x, y = x4_pos(pin)
    return x if pin % 2 == 0 else x - 1.27


# ---------------------------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------------------------
def uid(*key):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "ecp5-versa-pmod/" + "/".join(str(k) for k in key)))


def sx_find_block(text, head):
    """Text of the first s-expression block starting with `head` (balanced parentheses)."""
    i = text.find(head)
    if i < 0:
        raise KeyError(head)
    d = 0
    j = i
    while True:
        c = text[j]
        if c == '(':
            d += 1
        elif c == ')':
            d -= 1
            if d == 0:
                return text[i:j + 1]
        elif c == '"':
            j = text.index('"', j + 1)
        j += 1


def f(v):
    return ("%.4f" % v).rstrip("0").rstrip(".") if isinstance(v, float) else str(v)


# ---------------------------------------------------------------------------------------------
# symbol library
# ---------------------------------------------------------------------------------------------
def pin_sx(num, name, x, y, angle, etype="passive", length=2.54):
    return ('(pin %s line (at %s %s %d) (length %s) (name "%s" (effects (font (size 1.27 1.27)))) '
            '(number "%s" (effects (font (size 1.27 1.27)))))' % (etype, f(x), f(y), angle, f(length), name, num))


def prop_sx(name, value, x, y, hide=False):
    return ('(property "%s" "%s" (at %s %s 0) (show_name no) (do_not_autoplace no)%s '
            '(effects (font (size 1.27 1.27))%s))' % (name, value, f(x), f(y), " (hide yes)" if hide else "",
                                                     " (hide yes)" if hide else ""))


X4_LEFT = [20, 2, 19, 22, 24, 26, 30, 34, 40, None, 1, 38, 33, 35, 36, 37, 39]   # left side of the symbol, None = gap
X4_IO_PINS = [l["x4"] for l in LINES]                                              # right side: IO0..IO23 in order
PORT_LEFT = [1, 7, 2, 8, 3, 9, 4, 10]                                              # physical column order
PORT_RIGHT = {6: 0, 12: 1, 5: 6, 11: 7}                                            # pin -> row


def io_row(i):
    """Row of IO line i on the X4 symbol (and of the port pins): a four-row gap between the ports."""
    return i + 4 * (i // 8)


def symbol_versa_x4():
    """X4 drawn for reading: IO0..IO23 on the right in order (grouped per port), 3V3, the GND pins and
    the unused pins on the left.  Pin numbers are the X4 pin numbers."""
    w = 15.24
    top, bot = 38.1, -45.72
    s = ['(symbol "Versa_X4" (pin_names (offset 1.016)) (exclude_from_sim no) (in_bom yes) (on_board yes) '
         '(in_pos_files yes) (duplicate_pin_numbers_are_jumpers no)',
         prop_sx("Reference", "J", 0, top + 1.27),
         prop_sx("Value", "Versa_X4", 0, bot - 1.27),
         prop_sx("Footprint", "Connector_PinSocket_2.54mm:PinSocket_2x20_P2.54mm_Vertical", 0, 0, hide=True),
         prop_sx("Datasheet", "https://www.latticesemi.com/products/developmentboardsandkits/ecp5versadevelopmentkit", 0, 0, hide=True),
         prop_sx("Description", "Lattice ECP5 Versa expansion header X4 (2x20, 2.54 mm), pin names per FPGA-EB-02021 table 12, drawn by function", 0, 0, hide=True),
         prop_sx("ki_keywords", "Versa X4 expansion header", 0, 0, hide=True),
         '(symbol "Versa_X4_0_1" (rectangle (start %s %s) (end %s %s) (stroke (width 0.254) (type default)) (fill (type background))))'
         % (f(-w + 2.54), f(top), f(w - 2.54), f(bot)),
         '(symbol "Versa_X4_1_1"']

    def label(pin):
        name, ball = X4[pin]
        return name if not ball else "%s %s" % (name, ball)

    def etype(pin):
        name = X4[pin][0]
        return {"GND": "passive", "3V3": "power_out"}.get(name, "bidirectional" if name.startswith("IO") else "passive")
    for i, pin in enumerate(X4_IO_PINS):
        s.append(pin_sx(pin, label(pin), w, 35.56 - P * io_row(i), 180, etype(pin)))
    for row, pin in enumerate(X4_LEFT):
        if pin is not None:
            s.append(pin_sx(pin, label(pin), -w, 35.56 - P * row, 0, etype(pin)))
    s.append(")")
    s.append("(embedded_fonts no))")
    return "\n".join(s)


def symbol_pmod_host():
    """Pmod host port: signal pins on the left in physical column order (1, 7, 2, 8, ...), so one X4
    pin pair ends on two adjacent symbol pins; VCC and GND on the right."""
    w = 12.7
    s = ['(symbol "Pmod_Host_2x06" (pin_names (offset 1.016)) (exclude_from_sim no) (in_bom yes) (on_board yes) '
         '(in_pos_files yes) (duplicate_pin_numbers_are_jumpers no)',
         prop_sx("Reference", "J", 0, 12.7),
         prop_sx("Value", "Pmod_Host_2x06", 0, -12.7),
         prop_sx("Footprint", "%s:Pmod_Host_2x06_Horizontal" % NAME, 0, 0, hide=True),
         prop_sx("Datasheet", "Digilent Pmod Interface Specification 1.3.1", 0, 0, hide=True),
         prop_sx("Description", "Pmod host port, 2x6 female right angle, pins numbered as in the Pmod specification (1-6 upper row, 7-12 lower row); drawn in column order", 0, 0, hide=True),
         prop_sx("ki_keywords", "Pmod host port", 0, 0, hide=True),
         '(symbol "Pmod_Host_2x06_0_1" (rectangle (start -10.16 11.43) (end 10.16 -11.43) (stroke (width 0.254) (type default)) (fill (type background))))',
         '(symbol "Pmod_Host_2x06_1_1"']
    for row, pin in enumerate(PORT_LEFT):
        s.append(pin_sx(pin, "P%d" % pin, -w, 8.89 - P * row, 0, "bidirectional"))
    for pin, row in PORT_RIGHT.items():
        s.append(pin_sx(pin, "VCC" if pin in (6, 12) else "GND", w, 8.89 - P * row, 180, "power_in"))
    s.append(")")
    s.append("(embedded_fonts no))")
    return "\n".join(s)


def library_symbols():
    """(own, ext): name -> symbol text, for the project library and the schematic's lib_symbols."""
    own = {"Versa_X4": symbol_versa_x4(), "Pmod_Host_2x06": symbol_pmod_host()}
    ext = {}
    for lib, names in (("Device", ("R", "C", "LED", "Polyfuse")), ("power", ("+3V3", "GND", "PWR_FLAG")),
                       ):
        text = open(KICAD_SYM + lib + ".kicad_sym").read()
        for n in names:
            ext["%s:%s" % (lib, n)] = sx_find_block(text, '(symbol "%s"' % n)
    return own, ext


def write_symbol_lib(own):
    path = os.path.join(ROOT, "lib", NAME + ".kicad_sym")
    with open(path, "w") as fh:
        fh.write('(kicad_symbol_lib (version 20251024) (generator "%s-generate") (generator_version "10.0")\n' % NAME)
        for s in own.values():
            fh.write(s + "\n")
        fh.write(")\n")
    return path


# ---------------------------------------------------------------------------------------------
# footprint library: Pmod host socket = KiCad PinSocket_2x06_P2.54mm_Horizontal, pads renumbered
# ---------------------------------------------------------------------------------------------
def write_footprint_lib():
    src = open(KICAD_FP + "Connector_PinSocket_2.54mm.pretty/PinSocket_2x06_P2.54mm_Horizontal.kicad_mod").read()

    # KiCad numbering: pin n, row 1 (x = 0, far from the opening) for odd n, row 2 (x = -2.54) for even n,
    # position k = (n+1)//2 along +y.  Looking into the opening (from -x) the viewer's right is +y, and the
    # Pmod host has pin 1 at the upper right: Pmod pin = 7-k (row 1) or 13-k (row 2).
    def pmod_of(n):
        k = (n + 1) // 2
        return 7 - k if n % 2 else 13 - k

    out = src.replace('(footprint "PinSocket_2x06_P2.54mm_Horizontal"', '(footprint "Pmod_Host_2x06_Horizontal"')
    out = re.sub(r'\(descr "[^"]*"\)', '(descr "Pmod host port: 2x6 right-angle female socket 2.54 mm, KiCad PinSocket_2x06_P2.54mm_Horizontal geometry with the pads numbered as in the Digilent Pmod Interface Specification (1-6 upper row, 7-12 lower row, pin 1 upper right looking into the port)")', out)
    out = re.sub(r'\(tags "[^"]*"\)', '(tags "Pmod host socket 2x06 right angle")', out)
    out = out.replace('(property "Value" "PinSocket_2x06_P2.54mm_Horizontal"', '(property "Value" "Pmod_Host_2x06_Horizontal"')

    def repl(m):
        new = pmod_of(int(m.group(1)))
        return '(pad "%d" thru_hole %s' % (new, "rect" if new == 1 else "circle")
    out, cnt = re.subn(r'\(pad "(\d+)" thru_hole (\w+)', repl, out)
    assert cnt == 12, cnt

    # drop the library's pin-1 silkscreen marker (silk at the pad side, x > -4); add a marker beyond the
    # body end next to the Pmod pin 1 pad (local (0, 12.7)) instead
    def keep(block):
        if '(layer "F.SilkS")' not in block:
            return True
        xs = [float(v) for v in re.findall(r'\((?:start|end) (-?[\d.]+) ', block)]
        return not xs or min(xs) < -3.9
    parts = re.split(r'(?=\n\t\(fp_line)', out)
    out = "".join(p for p in parts if keep(p))
    marker = ('\n\t(fp_poly (pts (xy -0.5 14.4) (xy 0.5 14.4) (xy 0 15.3)) (stroke (width 0.12) (type solid)) '
              '(fill solid) (layer "F.SilkS"))')
    out = out.replace('\n\t(pad "', marker + '\n\t(pad "', 1)
    path = os.path.join(ROOT, "lib", NAME + ".pretty", "Pmod_Host_2x06_Horizontal.kicad_mod")
    open(path, "w").write(out)
    return path


# ---------------------------------------------------------------------------------------------
# schematic
# ---------------------------------------------------------------------------------------------
class Sch:
    def __init__(self):
        self.items = []
        self.sheet_uuid = uid("sheet")
        self.pins = {}      # lib_id -> {number: (x, y_lib, angle)}
        self.refs = []

    def load_pins(self, lib_id, text):
        d = {}
        for m in re.finditer(r'\(pin \w+ \w+\s*\(at (-?[\d.]+) (-?[\d.]+) (\d+)\)\s*\(length ([\d.]+)\).*?\(number "([^"]+)"', text, re.S):
            d[m.group(5)] = (float(m.group(1)), float(m.group(2)), int(m.group(3)))
        self.pins[lib_id] = d

    def pin_pos(self, lib_id, num, X, Y, rot=0):
        """World position of a pin and its outward direction, for a symbol placed at (X, Y, rot)."""
        px, py, ang = self.pins[lib_id][num]
        x, y = px, -py                      # library y points up
        for _ in range(rot // 90):          # KiCad rotates counter-clockwise on screen
            x, y = y, -x
        return (X + x, Y + y), (ang + rot) % 360

    def symbol(self, lib_id, ref, value, X, Y, footprint="", fields=None, in_bom=True, ref_at=None, val_at=None,
               rot=0, size=1.27, hide_ref=False, hide_val=False):
        self.refs.append(ref)
        rx, ry = ref_at or (X + 2.54, Y - 2.54)
        vx, vy = val_at or (X + 2.54, Y)
        s = ['(symbol (lib_id "%s") (at %s %s %d) (unit 1) (exclude_from_sim no) (in_bom %s) (on_board yes) (dnp no) (uuid "%s")'
             % (lib_id, f(X), f(Y), rot, "yes" if in_bom else "no", uid("sym", ref))]
        s.append('(property "Reference" "%s" (at %s %s 0) (effects (font (size %s %s)) (justify left)%s))'
                 % (ref, f(rx), f(ry), f(size), f(size), " (hide yes)" if hide_ref else ""))
        s.append('(property "Value" "%s" (at %s %s 0) (effects (font (size %s %s)) (justify left)%s))'
                 % (value, f(vx), f(vy), f(size), f(size), " (hide yes)" if hide_val else ""))
        s.append('(property "Footprint" "%s" (at %s %s 0) (effects (font (size 1.27 1.27)) (hide yes)))' % (footprint, f(X), f(Y)))
        s.append('(property "Datasheet" "" (at %s %s 0) (effects (font (size 1.27 1.27)) (hide yes)))' % (f(X), f(Y)))
        for k, v in (fields or {}).items():
            s.append('(property "%s" "%s" (at %s %s 0) (effects (font (size 1.27 1.27)) (hide yes)))' % (k, v, f(X), f(Y)))
        for num in self.pins[lib_id]:
            s.append('(pin "%s" (uuid "%s"))' % (num, uid("pin", ref, num)))
        s.append('(instances (project "%s" (path "/%s" (reference "%s") (unit 1)))))' % (NAME, self.sheet_uuid, ref))
        self.items.append("\n".join(s))

    def wire(self, a, b):
        self.items.append('(wire (pts (xy %s %s) (xy %s %s)) (stroke (width 0) (type default)) (uuid "%s"))'
                          % (f(a[0]), f(a[1]), f(b[0]), f(b[1]), uid("wire", a, b)))

    def label(self, text, at, angle, size=1.27):
        just = {0: "left bottom", 180: "right bottom", 90: "left bottom", 270: "right bottom"}[angle]
        self.items.append('(label "%s" (at %s %s %d) (effects (font (size %s %s)) (justify %s)) (uuid "%s"))'
                          % (text, f(at[0]), f(at[1]), angle, f(size), f(size), just, uid("label", text, at)))

    def junction(self, at):
        self.items.append('(junction (at %s %s) (diameter 0) (color 0 0 0 0) (uuid "%s"))' % (f(at[0]), f(at[1]), uid("junction", at)))

    def power(self, lib, ref, at):
        """Power symbol (+3V3, GND, PWR_FLAG) with its pin at `at`."""
        below = lib.endswith("GND")
        self.symbol(lib, ref, lib.split(":")[1], at[0], at[1], "", None, in_bom=False, hide_ref=True,
                    ref_at=(at[0] + 1.27, at[1] + 3.81), val_at=(at[0] + 1.27, at[1] + (4.45 if below else -3.3)))

    def no_connect(self, at):
        self.items.append('(no_connect (at %s %s) (uuid "%s"))' % (f(at[0]), f(at[1]), uid("nc", at)))

    def text(self, s, at, size=1.27):
        self.items.append('(text "%s" (exclude_from_sim no) (at %s %s 0) (effects (font (size %s %s)) (justify left bottom)) (uuid "%s"))'
                          % (s.replace('"', '\\"'), f(at[0]), f(at[1]), f(size), f(size), uid("text", at)))

    def pin_label(self, lib_id, ref, num, X, Y, name, stub=2.54):
        """Wire stub from the pin end outwards and a label at its end (NC flag when name is None)."""
        (x, y), ang = self.pin_pos(lib_id, num, X, Y)
        dx, dy = {0: (-1, 0), 180: (1, 0), 90: (0, 1), 270: (0, -1)}[ang]   # outward direction
        if name is None:
            self.no_connect((x, y))
            return
        end = (x + dx * stub, y + dy * stub)
        self.wire((x, y), end)
        self.label(name, end, {0: 180, 180: 0, 90: 270, 270: 90}[ang])


def build_schematic(own, ext):
    """One A3 sheet, drawn with wires: X4 on the left, 24 series resistors in the middle (two staggered
    columns), the three ports on the right, the power section below X4."""
    sch = Sch()
    for n, t in own.items():
        sch.load_pins("%s:%s" % (NAME, n), t)
    for n, t in ext.items():
        sch.load_pins(n, t)
    X4ID = "%s:Versa_X4" % NAME
    PMID = "%s:Pmod_Host_2x06" % NAME
    W, J = sch.wire, sch.junction

    def fields(ref):
        val, fp, lcsc, mpn, desc = PARTS[ref]
        d = {"Description": desc}
        if lcsc:
            d["LCSC"] = lcsc
        if mpn:
            d["MPN"] = mpn
        return fp, d

    # --- X4 ----------------------------------------------------------------------------------
    XJ, YJ = 63.5, 73.66                       # IO row 0 (lib y 35.56) lands on y = 38.1
    fp, fl = fields("J1")
    sch.symbol(X4ID, "J1", "Versa X4", XJ, YJ, fp, fl, ref_at=(XJ - 12.7, YJ - 40.64), val_at=(XJ - 12.7, YJ + 38.1))
    Y0 = sch.pin_pos(X4ID, str(X4_IO_PINS[0]), XJ, YJ)[0][1]
    assert abs(Y0 - 38.1) < 1e-6, Y0

    # --- signal lines: X4 pin -> wire -> R -> wire -> port pin, one straight row each -----------
    XR = (109.22, 124.46)                       # resistor columns (staggered)
    XP = 182.88                                 # port symbols

    def port_y(port):
        return Y0 + P * io_row(8 * (ord(port) - 65)) + 8.89   # symbol origin: its row 0 on the group's first IO row
    for port in "ABC":
        ref = PORT_REF[port]
        yp = port_y(port)
        fp, fl = fields(ref)
        sch.symbol(PMID, ref, "PMOD %s" % port, XP, yp, fp, fl, ref_at=(XP - 10.16, yp - 13.97), val_at=(XP - 10.16, yp + 13.97))
    for i, l in enumerate(LINES):
        y = Y0 + P * io_row(i)
        (xa, ya), _ = sch.pin_pos(X4ID, str(l["x4"]), XJ, YJ)
        assert abs(ya - y) < 1e-6
        (xb, yb), _ = sch.pin_pos(PMID, str(l["pmod"]), XP, port_y(l["port"]))
        assert abs(yb - y) < 1e-6, (l, yb, y)
        xr = XR[i % 2]
        fp, fl = fields(l["r"])
        sch.symbol("Device:R", l["r"], R_VAL, xr, y, fp, fl, rot=90, ref_at=(xr - 3.6, y - 1.78), val_at=(xr + 0.4, y - 1.78), size=1.0)
        (r1, _), (r2, _) = sch.pin_pos("Device:R", "1", xr, y, 90), sch.pin_pos("Device:R", "2", xr, y, 90)
        left, right = (r1, r2) if r1[0] < r2[0] else (r2, r1)
        W((xa, y), left)
        W(right, (xb, y))
        sch.label(l["net_io"], (xa + 2.54, y), 0)
        sch.label(l["net_p"], (xb - 8.89, y), 0)
    # port VCC / GND pins: short wires to +3V3 and GND symbols
    for gi, port in enumerate("ABC"):
        yp = port_y(port)
        (x6, y6), _ = sch.pin_pos(PMID, "6", XP, yp)
        (x12, y12), _ = sch.pin_pos(PMID, "12", XP, yp)
        (x5, y5), _ = sch.pin_pos(PMID, "5", XP, yp)
        (x11, y11), _ = sch.pin_pos(PMID, "11", XP, yp)
        xv = x6 + 2.54
        W((x6, y6), (xv, y6)); W((x12, y12), (xv, y12)); W((xv, y12), (xv, y6 - 2.54)); J((xv, y6))
        sch.power("power:+3V3", "#PWR%d1" % (gi + 1), (xv, y6 - 2.54))
        W((x5, y5), (xv, y5)); W((x11, y11), (xv, y11)); W((xv, y5), (xv, y11 + 2.54)); J((xv, y11))
        sch.power("power:GND", "#PWR%d2" % (gi + 1), (xv, y11 + 2.54))

    # --- X4 left side: 3V3 feed, GND bus, unused pins --------------------------------------------
    XF, XG = 33.02, 40.64                       # x of the VCC_X4 feed wire and of the GND bus
    YR1, YR2 = 134.62, 157.48                   # +3V3 rail, GND rail
    (x20, y20), _ = sch.pin_pos(X4ID, "20", XJ, YJ)
    fp, fl = fields("F1")
    sch.symbol("Device:Polyfuse", "F1", "0.5A", XF, YR1 - 3.81, fp, fl, ref_at=(XF + 2.54, YR1 - 5.08), val_at=(XF + 2.54, YR1 - 2.54))
    (f1a, _), (f1b, _) = sch.pin_pos("Device:Polyfuse", "1", XF, YR1 - 3.81), sch.pin_pos("Device:Polyfuse", "2", XF, YR1 - 3.81)
    assert f1a[1] < f1b[1] and abs(f1b[1] - YR1) < 1e-6
    W((x20, y20), (XF, y20)); W((XF, y20), f1a)
    sch.label("VCC_X4", (XF, y20 + 40.64), 90)
    gnd_pins = [pin for pin in X4_LEFT if pin is not None and X4[pin][0] == "GND"]
    ys = []
    for pin in gnd_pins:
        (xg, yg), _ = sch.pin_pos(X4ID, str(pin), XJ, YJ)
        W((xg, yg), (XG, yg)); ys.append(yg)
    W((XG, min(ys)), (XG, YR2))
    for yg in ys[1:]:
        J((XG, yg))
    for pin in X4_LEFT:
        if pin is not None and X4[pin][0] != "GND" and pin != 20 and not any(l["x4"] == pin for l in LINES):
            sch.no_connect(sch.pin_pos(X4ID, str(pin), XJ, YJ)[0])

    # --- power section: +3V3 rail and GND rail with C1..C4, R25/D1 ---------------------------------
    XC = [55.88, 71.12, 86.36, 101.6]
    XR25, XD, XK = 127.0, 116.84, 109.22
    W(f1b, (XR25, YR1))                         # +3V3 rail
    W((XG, YR2), (XK, YR2))                     # GND rail (continues the GND bus)
    for x, ref in zip(XC, ("C1", "C2", "C3", "C4")):
        fp, fl = fields(ref)
        yc = (YR1 + YR2) / 2
        sch.symbol("Device:C", ref, PARTS[ref][0], x, yc, fp, fl, ref_at=(x + 2.54, yc - 1.27), val_at=(x + 2.54, yc + 1.27))
        (c1, _), (c2, _) = sch.pin_pos("Device:C", "1", x, yc), sch.pin_pos("Device:C", "2", x, yc)
        W((x, YR1), c1); W(c2, (x, YR2)); J((x, YR1)); J((x, YR2))
    fp, fl = fields("R25")
    sch.symbol("Device:R", "R25", "1k", XR25, YR1 + 3.81, fp, fl, ref_at=(XR25 + 2.54, YR1 + 2.54), val_at=(XR25 + 2.54, YR1 + 5.08))
    (ra, _), (rb, _) = sch.pin_pos("Device:R", "1", XR25, YR1 + 3.81), sch.pin_pos("Device:R", "2", XR25, YR1 + 3.81)
    assert abs(ra[1] - YR1) < 1e-6
    YL = YR1 + 13.97
    fp, fl = fields("D1")
    sch.symbol("Device:LED", "D1", "GREEN", XD, YL, fp, fl, ref_at=(XD - 2.54, YL - 3.81), val_at=(XD - 3.81, YL + 5.08))
    (dk, _), (da, _) = sch.pin_pos("Device:LED", "1", XD, YL), sch.pin_pos("Device:LED", "2", XD, YL)
    assert dk[0] < da[0]
    W(rb, (XR25, YL)); W((XR25, YL), da)
    sch.label("LED_A", (XR25 - 2.54, YL), 0)
    W(dk, (XK, YL)); W((XK, YL), (XK, YR2))
    sch.power("power:+3V3", "#PWR01", (45.72, YR1)); J((45.72, YR1))
    sch.power("power:GND", "#PWR02", (45.72, YR2)); J((45.72, YR2))
    sch.power("power:PWR_FLAG", "#FLG01", (63.5, YR1)); J((63.5, YR1))
    sch.power("power:PWR_FLAG", "#FLG02", (63.5, YR2)); J((63.5, YR2))

    # --- notes ---------------------------------------------------------------------------------
    sch.text("Versa expansion header X4: 2x20 male on the Versa, 2x20 female socket J1 on the bottom of this board.\\n"
             "Pin names per Lattice FPGA-EB-02021 table 12 with the FPGA ball. IO24..IO28, RESOUT# and CARDSEL# are not used.\\n"
             "3V3 comes from the single 3V3 pin of X4 (pin 20) through F1; the X4 GND pins are tied together on the board.",
             (20.32, 190.5), 1.27)
    sch.text("Pmod host ports J2..J4, pin numbers as in the Pmod Interface Specification 1.3.1 (1-6 upper row, 7-12 lower row).\\n"
             "Symbol pins are in connector column order: pins n and n+6 share a column and are one ECP5 differential pair\\n"
             "(A = pin 1..4, B = pin 7..10), except PB2/PB8 (IO10/IO11). PB2 = IO10 = PCLKT1_1 (primary clock input).\\n"
             "33 ohm series resistors in every signal (source termination, current limit). 12-bit DVI Pmod: its J2 on PMOD A, its J1 on PMOD B.",
             (140.97, 190.5), 1.27)

    # --- file ----------------------------------------------------------------------------------
    lib_symbols = []
    for n, t in own.items():
        lib_symbols.append(t.replace('(symbol "%s"' % n, '(symbol "%s:%s"' % (NAME, n), 1))
    for n, t in ext.items():
        short = n.split(":")[1]
        lib_symbols.append(t.replace('(symbol "%s"' % short, '(symbol "%s"' % n, 1))
    out = ['(kicad_sch (version 20250114) (generator "eeschema") (generator_version "9.0") (uuid "%s") (paper "A3")' % sch.sheet_uuid,
           '(title_block (title "%s: Lattice ECP5 Versa X4 to 3x Pmod") (date "%s") (rev "%s") (company "open hardware")'
           ' (comment 1 "Generic Pmod host adapter for the Versa expansion header X4; fits the 1BitSquared 12-bit DVI Pmod on ports A+B"))'
           % (NAME, DATE, REV),
           "(lib_symbols"] + lib_symbols + [")"] + sch.items + \
          ['(sheet_instances (path "/" (page "1")))', "(embedded_fonts no))"]
    path = os.path.join(ROOT, NAME + ".kicad_sch")
    open(path, "w").write("\n".join(out) + "\n")
    return path, sch


# ---------------------------------------------------------------------------------------------
# board
# ---------------------------------------------------------------------------------------------
class Board:
    def __init__(self):
        self.b = pcbnew.BOARD()
        self.nets = {}
        self.b.SetCopperLayerCount(2)
        bds = self.b.GetDesignSettings()
        bds.m_MinClearance = mm(0.2)
        bds.m_TrackMinWidth = mm(0.2)
        bds.m_ViasMinSize = mm(0.5)
        bds.m_ViasMinAnnularWidth = mm(0.13)
        bds.m_MinThroughDrill = mm(0.3)
        bds.m_HoleClearance = mm(0.25)
        bds.m_HoleToHoleMin = mm(0.5)
        bds.m_CopperEdgeClearance = mm(0.3)
        bds.m_SilkClearance = mm(0.0)
        bds.m_MinSilkTextHeight = mm(0.7)
        bds.m_MinSilkTextThickness = mm(0.1)
        nc = bds.m_NetSettings.GetDefaultNetclass()
        nc.SetClearance(mm(0.2))
        nc.SetTrackWidth(mm(TRACK))
        nc.SetViaDiameter(mm(VIA_D))
        nc.SetViaDrill(mm(VIA_DRILL))
        tb = self.b.GetTitleBlock()
        tb.SetTitle("%s: Lattice ECP5 Versa X4 to 3x Pmod" % NAME)
        tb.SetDate(DATE)
        tb.SetRevision(REV)
        tb.SetCompany("open hardware")

    def net(self, name):
        """Net by schematic name: local labels get the root sheet prefix "/" in the netlist."""
        if not name.startswith("unconnected-") and name not in ("+3V3", "GND"):   # power symbols: global
            name = "/" + name
        if name not in self.nets:
            n = pcbnew.NETINFO_ITEM(self.b, name)
            self.b.Add(n)
            self.nets[name] = n
        return self.nets[name]

    @staticmethod
    def V(x, y):
        return VECTOR2I(mm(x), mm(y))

    @staticmethod
    def pos(pad):
        p = pad.GetPosition()
        return (pcbnew.ToMM(p.x), pcbnew.ToMM(p.y))

    def place(self, ref, x, y, rot=0.0, bottom=False, hide_ref=True, hide_val=True):
        val, fpn, lcsc, mpn, desc = PARTS[ref]
        libname, fname = fpn.split(":")
        if libname == NAME:
            fp = pcbnew.FootprintLoad(os.path.join(ROOT, "lib", NAME + ".pretty"), fname)
        else:
            fp = pcbnew.FootprintLoad(KICAD_FP + libname + ".pretty", fname)
        assert fp, fpn
        fp.SetFPID(pcbnew.LIB_ID(libname, fname))
        fp.SetReference(ref)
        fp.SetValue(val)
        for k, v in (("LCSC", lcsc), ("MPN", mpn), ("Description", desc)):
            if v:
                fp.SetField(k, v)
                fp.GetField(k).SetVisible(False)
        self.b.Add(fp)
        fp.SetPosition(self.V(x, y))
        if bottom:
            fp.SetLayerAndFlip(pcbnew.B_Cu)
        fp.SetOrientationDegrees(rot)
        fp.SetPosition(self.V(x, y))
        fp.Reference().SetVisible(not hide_ref)
        fp.Value().SetVisible(not hide_val)
        return fp

    @staticmethod
    def chamfer(pts, c=0.6):
        """Replace every 90-degree corner of a polyline by a 45-degree chamfer of length c."""
        out = [pts[0]]
        for a, b, d in zip(pts, pts[1:], pts[2:]):
            v1 = (b[0] - a[0], b[1] - a[1])
            v2 = (d[0] - b[0], d[1] - b[1])
            l1, l2 = math.hypot(*v1), math.hypot(*v2)
            if l1 > 2 * c and l2 > 2 * c and abs(v1[0] * v2[0] + v1[1] * v2[1]) < 1e-9:
                out.append((b[0] - v1[0] / l1 * c, b[1] - v1[1] / l1 * c))
                out.append((b[0] + v2[0] / l2 * c, b[1] + v2[1] / l2 * c))
            else:
                out.append(b)
        out.append(pts[-1])
        return out

    def track(self, netname, layer, pts, width=TRACK):
        pts = self.chamfer(pts)
        for a, b in zip(pts[:-1], pts[1:]):
            if abs(a[0] - b[0]) < 1e-6 and abs(a[1] - b[1]) < 1e-6:
                continue
            t = pcbnew.PCB_TRACK(self.b)
            t.SetStart(self.V(*a))
            t.SetEnd(self.V(*b))
            t.SetWidth(mm(width))
            t.SetLayer(layer)
            t.SetNet(self.net(netname))
            self.b.Add(t)

    def via(self, netname, x, y):
        v = pcbnew.PCB_VIA(self.b)
        v.SetViaType(pcbnew.VIATYPE_THROUGH)
        v.SetPosition(self.V(x, y))
        v.SetWidth(mm(VIA_D))
        v.SetDrill(mm(VIA_DRILL))
        v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        v.SetNet(self.net(netname))
        self.b.Add(v)

    def text(self, s, x, y, layer=pcbnew.F_SilkS, size=0.8, thick=0.12, rot=0, h="center", v="center"):
        t = pcbnew.PCB_TEXT(self.b)
        t.SetText(s)
        t.SetPosition(self.V(x, y))
        t.SetLayer(layer)
        t.SetTextSize(VECTOR2I(mm(size), mm(size)))
        t.SetTextThickness(mm(thick))
        t.SetTextAngleDegrees(rot)
        if layer in (pcbnew.B_SilkS, pcbnew.B_Cu, pcbnew.B_Fab):   # mirrored: swap so that "left" means
            h = {"left": "right", "right": "left"}.get(h, h)       # "extends toward +x" in board coordinates
        t.SetHorizJustify({"left": pcbnew.GR_TEXT_H_ALIGN_LEFT, "center": pcbnew.GR_TEXT_H_ALIGN_CENTER,
                           "right": pcbnew.GR_TEXT_H_ALIGN_RIGHT}[h])
        t.SetVertJustify({"top": pcbnew.GR_TEXT_V_ALIGN_TOP, "center": pcbnew.GR_TEXT_V_ALIGN_CENTER,
                          "bottom": pcbnew.GR_TEXT_V_ALIGN_BOTTOM}[v])
        if layer in (pcbnew.B_SilkS, pcbnew.B_Cu, pcbnew.B_Fab):
            t.SetMirrored(True)
        self.b.Add(t)
        return t

    def shape_line(self, a, b, layer, width=0.12):
        s = pcbnew.PCB_SHAPE(self.b)
        s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(self.V(*a))
        s.SetEnd(self.V(*b))
        s.SetLayer(layer)
        s.SetWidth(mm(width))
        self.b.Add(s)

    def poly(self, pts, layer, width=0.12):
        s = pcbnew.PCB_SHAPE(self.b)
        s.SetShape(pcbnew.SHAPE_T_POLY)
        chain = pcbnew.SHAPE_LINE_CHAIN()
        for x, y in pts:
            chain.Append(mm(x), mm(y))
        chain.SetClosed(True)
        ps = pcbnew.SHAPE_POLY_SET()
        ps.AddOutline(chain)
        s.SetPolyShape(ps)
        s.SetLayer(layer)
        s.SetWidth(mm(width))
        s.SetFilled(True)
        self.b.Add(s)

    def logo(self, ref, x, y, bottom=False):
        fp = pcbnew.FootprintLoad(KICAD_FP + "Symbol.pretty", "OSHW-Logo_7.5x8mm_SilkScreen")
        fp.SetReference(ref)
        fp.Reference().SetVisible(False)
        fp.Value().SetVisible(False)
        fp.SetAttributes(pcbnew.FP_BOARD_ONLY | pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES)
        self.b.Add(fp)
        if bottom:
            fp.SetLayerAndFlip(pcbnew.B_Cu)
        fp.SetPosition(self.V(x, y))


def pad_by(fp, num):
    p = fp.FindPadByNumber(str(num))
    assert p, (fp.GetReference(), num)
    return p


def two_pad(B, ref, x, y, upper_pin, upper_net, lower_net):
    """Place a vertical two-pad part so that pad `upper_pin` is the upper one; nets by pin number
    (identical to the schematic).  Returns (footprint, upper pad pos, lower pad pos)."""
    fp = B.place(ref, x, y, rot=90)
    if Board.pos(pad_by(fp, upper_pin))[1] > Board.pos(pad_by(fp, 3 - upper_pin))[1]:
        fp.SetOrientationDegrees(270)
    assert Board.pos(pad_by(fp, upper_pin))[1] < Board.pos(pad_by(fp, 3 - upper_pin))[1]
    pad_by(fp, upper_pin).SetNet(B.net(upper_net))
    pad_by(fp, 3 - upper_pin).SetNet(B.net(lower_net))
    return fp, Board.pos(pad_by(fp, upper_pin)), Board.pos(pad_by(fp, 3 - upper_pin))


def build_board():
    B = Board()
    V, pos = Board.V, Board.pos

    # --- outline -----------------------------------------------------------------------------
    r = 1.5
    W, H = BOARD_W, BOARD_H
    for a, b in (((r, 0), (W - r, 0)), ((W, r), (W, H - r)), ((W - r, H), (r, H)), ((0, H - r), (0, r))):
        B.shape_line(a, b, pcbnew.Edge_Cuts, 0.1)
    for (cx, cy), (sx, sy) in (((r, r), (0, r)), ((W - r, r), (W - r, 0)), ((W - r, H - r), (W, H - r)), ((r, H - r), (r, H))):
        arc = pcbnew.PCB_SHAPE(B.b)
        arc.SetShape(pcbnew.SHAPE_T_ARC)
        arc.SetCenter(V(cx, cy))
        arc.SetStart(V(sx, sy))
        arc.SetArcAngleAndEnd(pcbnew.EDA_ANGLE(90, pcbnew.DEGREES_T), False)
        arc.SetLayer(pcbnew.Edge_Cuts)
        arc.SetWidth(mm(0.1))
        B.b.Add(arc)

    # --- X4 socket on the bottom: pin 1 bottom left, pin 2 above it, numbers increasing to the right
    j1 = None
    for rot in (0, 90, 180, 270):
        fp = B.place("J1", X1, Y_ODD, rot=rot, bottom=True)
        p1, p2, p3 = pos(pad_by(fp, 1)), pos(pad_by(fp, 2)), pos(pad_by(fp, 3))
        if (abs(p1[0] - X1) < 1e-3 and abs(p1[1] - Y_ODD) < 1e-3 and abs(p2[0] - X1) < 1e-3
                and abs(p2[1] - Y_EVEN) < 1e-3 and abs(p3[0] - xcol(2)) < 1e-3 and abs(p3[1] - Y_ODD) < 1e-3):
            j1 = fp
            break
        B.b.Remove(fp)
    assert j1, "X4 socket orientation not found"
    for pin in range(1, 41):
        assert tuple(round(v, 3) for v in pos(pad_by(j1, pin))) == tuple(round(v, 3) for v in x4_pos(pin)), pin
        name = X4[pin][0]
        if name == "GND":
            pad_by(j1, pin).SetNet(B.net("GND"))
            pad_by(j1, pin).SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_NONE)   # no pour fits between the pins
        elif name == "3V3":
            pad_by(j1, pin).SetNet(B.net("VCC_X4"))
        elif any(l["x4"] == pin for l in LINES):
            pad_by(j1, pin).SetNet(B.net(name))
        else:   # not connected: KiCad names these nets after the symbol pin
            label = name if not X4[pin][1] else "%s_%s" % (name, X4[pin][1])
            pad_by(j1, pin).SetNet(B.net("unconnected-(J1-%s-Pad%d)" % (label, pin)))

    # --- Pmod ports: pin 1 at the left end of the inner row, pin 7 toward the edge of it ------
    ports = {}
    for port in "ABC":
        ref = PORT_REF[port]
        xp = PORT_X[port]
        found = None
        for rot in (270, 90, 0, 180):
            fp = B.place(ref, xp + 5 * P, Y_FAR, rot=rot)
            p1, p6, p7 = pos(pad_by(fp, 1)), pos(pad_by(fp, 6)), pos(pad_by(fp, 7))
            if (abs(p1[0] - xp) < 1e-3 and abs(p1[1] - Y_FAR) < 1e-3 and abs(p6[0] - (xp + 5 * P)) < 1e-3
                    and abs(p7[0] - xp) < 1e-3 and abs(p7[1] - Y_NEAR) < 1e-3):
                found = fp
                break
            B.b.Remove(fp)
        assert found, "port %s orientation not found" % port
        ports[port] = found
        for pin in range(1, 13):
            assert tuple(round(v, 3) for v in pos(pad_by(found, pin))) == tuple(round(v, 3) for v in port_pad(port, pin)), (port, pin)
            if pin in (5, 11):
                pad_by(found, pin).SetNet(B.net("GND"))
            elif pin in (6, 12):
                pad_by(found, pin).SetNet(B.net("+3V3"))
            else:
                pad_by(found, pin).SetNet(B.net("P%s%d" % (port, pin)))
    assert abs(pos(pad_by(ports["B"], 1))[0] - pos(pad_by(ports["A"], 1))[0] - PORT_PITCH) < 1e-6
    assert abs(pos(pad_by(ports["C"], 1))[0] - pos(pad_by(ports["B"], 1))[0] - PORT_PITCH) < 1e-6
    assert abs(Y_NEAR - 10.16) < 1e-9   # 0.40 in from the board edge (y = 0)

    # --- signal lines --------------------------------------------------------------------------
    for i, l in enumerate(LINES):
        pin, port, pmod = l["x4"], l["port"], l["pmod"]
        sx, sy = x4_pos(pin)
        xs = escape_x(pin)
        tx, ty = port_pad(port, pmod)
        upper = pmod <= 6
        xr = tx - HALF if upper else tx + HALF
        # resistor on the vertical run above the socket; rows alternate so neighbours 1.27 apart differ
        yr = Y_R1 if i % 2 == 0 else Y_R2
        fp, phi, plo = two_pad(B, l["r"], xs, yr, 2, l["net_p"], l["net_io"])   # pin 1 = X4 side, lower
        if pin % 2:   # odd row: diagonal up-left into the gap between the even-row pads, then up
            B.track(l["net_io"], pcbnew.F_Cu, [(sx, sy), (xs, sy - 1.27), (xs, plo[1]), plo])
        else:
            B.track(l["net_io"], pcbnew.F_Cu, [(sx, sy), (xs, plo[1]), plo])
        shift = xr - xs
        y_end = Y_D0 - abs(shift) / SLOPE
        assert y_end > Y_JOG + 0.3, (l, y_end)
        pts = [phi, (xs, Y_D0), (xr, y_end)]
        if upper:
            pts += [(xr, Y_JOG), (tx, Y_JOG - 0.7), (tx, ty)]
        else:
            g = tx + 1.27                       # gap between the far-row pads
            pts += [(xr, Y_JOG), (g, Y_JOG - 0.7), (g, Y_FAR - 1.27), (tx, ty)]
        B.track(l["net_p"], pcbnew.F_Cu, pts)

    # --- power -------------------------------------------------------------------------------
    XF, XC1, XL, XR = 62.5, 59.5, 57.5, 65.3
    f1, f1_hi, f1_lo = two_pad(B, "F1", XF, 23.5, 2, "+3V3", "VCC_X4")       # pin 1 (VCC_X4) lower
    c1, c1_hi, c1_lo = two_pad(B, "C1", XC1, 24.5, 1, "+3V3", "GND")
    # GND bus on B.Cu for the X4 socket's GND pins (no pour fits between the socket pins)
    YG = Y_EVEN - 1.5
    B.track("GND", pcbnew.B_Cu, [(X1 - 1.5, YG), (xcol(20) + 1.5, YG)], 0.4)
    for pin in range(1, 41):
        if X4[pin][0] != "GND":
            continue
        x, y = x4_pos(pin)
        if pin % 2 == 0:
            B.track("GND", pcbnew.B_Cu, [(x, y), (x, YG)], 0.4)
        else:   # pin 19: diagonal into the gap between the even-row pads 18 and 20, then up
            B.track("GND", pcbnew.B_Cu, [(x, y), (x - 1.27, y - 1.27), (x - 1.27, YG)], 0.3)
    # VCC_X4: X4 pin 20 -> along the bottom edge (below the socket, where no signal return current
    # flows) -> straight up into F1 pin 1.  The only way out of the even row is between two
    # odd-row pads (0.84 mm gap), so the feed leaves on both layers at the widest track the gap
    # allows (0.4 mm, B.Cu between pads 19/21, F.Cu between 17/19) and both copies run in parallel
    # (2 x 0.5 mm) to the via at F1: no point of the feed is narrower than the trunk.
    x20, y20 = x4_pos(20)
    YB = Y_ODD + 1.5
    for layer, xg in ((pcbnew.B_Cu, x20 + 1.27), (pcbnew.F_Cu, x20 - 1.27)):
        B.track("VCC_X4", layer, [(x20, y20), (xg, y20 + 1.27), (xg, YB - 0.4)], 0.4)
        pts = [(xg, YB - 0.4), (xg + 0.4, YB), (XF - 0.5, YB), (XF, YB - 0.5), (XF, 27.0)]
        if layer == pcbnew.F_Cu:
            pts.append(f1_lo)           # straight on into F1 pin 1
        B.track("VCC_X4", layer, pts, PWR)
    B.via("VCC_X4", XF, 27.0)           # joins the B.Cu copy
    # +3V3: F1 pin 2 -> C1, R25 (F.Cu) and via -> B.Cu up the right edge -> trunk along the top edge
    yv = f1_hi[1]
    B.track("+3V3", pcbnew.F_Cu, [f1_hi, (XR, yv)], PWR)
    B.via("+3V3", XR, yv)
    YT = 7.5
    xa = PORT_X["A"] + 5 * P
    B.track("+3V3", pcbnew.B_Cu, [(XR, yv), (XR, YT + 1.0), (XR - 1.0, YT), (xa + 1.0, YT), (xa, YT + 1.0), (xa, Y_NEAR),
                                  (xa, Y_FAR)], PWR)
    for port in "BC":
        xv = PORT_X[port] + 5 * P
        B.track("+3V3", pcbnew.B_Cu, [(xv, YT), (xv, Y_NEAR), (xv, Y_FAR)], PWR)
    B.track("GND", pcbnew.F_Cu, [c1_lo, (XC1, c1_lo[1] + 1.6)], PWR)
    B.via("GND", XC1, c1_lo[1] + 1.6)
    # decoupling at each port: 100 nF below pin 6, GND through a via
    for port, ref in zip("ABC", ("C2", "C3", "C4")):
        xv = PORT_X[port] + 5 * P
        c, c_hi, c_lo = two_pad(B, ref, xv, 18.1, 1, "+3V3", "GND")
        B.track("+3V3", pcbnew.F_Cu, [(xv, Y_FAR), c_hi], 0.4)
        B.track("GND", pcbnew.F_Cu, [c_lo, (xv - 1.5, c_lo[1])], 0.4)   # via beside the pad: the port C
        B.via("GND", xv - 1.5, c_lo[1])                                     # doglegs run right below
    # LED: +3V3 -> R25 -> D1 -> GND
    r25, r_hi, r_lo = two_pad(B, "R25", XL, 31.5, 1, "+3V3", "LED_A")
    B.track("+3V3", pcbnew.F_Cu, [(XF, yv), (XL, yv), r_hi], PWR)       # branch from F1 to R25 (chamfered corner)
    B.track("+3V3", pcbnew.F_Cu, [(XC1, yv), c1_hi], PWR)                 # C1 hangs off it
    d1, d_a, d_k = two_pad(B, "D1", XL, 35.5, 2, "LED_A", "GND")                # pin 2 = anode, upper
    B.track("LED_A", pcbnew.F_Cu, [r_lo, d_a])
    B.via("GND", XL, d_k[1] + 1.5)
    B.track("GND", pcbnew.F_Cu, [d_k, (XL, d_k[1] + 1.5)])
    # stitching vias
    for x, y in ((1.5, 20.0), (1.5, 28.0), (23.3, 4.0), (46.2, 4.0), (14.7, 26.0), (46.5, 32.5), (54.5, 36.5),
                 (60.0, 33.0), (24.5, 18.0), (47.0, 16.5), (63.8, 31.5), (33.0, 4.0), (55.0, 29.5), (15.5, 16.0)):
        B.via("GND", x, y)

    # --- pours -------------------------------------------------------------------------------
    for layer, clr in ((pcbnew.F_Cu, 0.4), (pcbnew.B_Cu, 0.3)):
        z = pcbnew.ZONE(B.b)
        z.SetLayer(layer)
        z.SetNet(B.net("GND"))
        ol = z.Outline()
        ol.NewOutline()
        for x, y in ((0, 0), (W, 0), (W, H), (0, H)):
            ol.Append(mm(x), mm(y))
        z.SetMinThickness(mm(0.3))
        z.SetLocalClearance(mm(clr))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
        z.SetThermalReliefGap(mm(0.3))
        z.SetThermalReliefSpokeWidth(mm(0.4))
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
        z.SetZoneName("GND_" + ("top" if layer == pcbnew.F_Cu else "bottom"))
        B.b.Add(z)

    # --- silkscreen, top ---------------------------------------------------------------------
    FS = pcbnew.F_SilkS
    for port in "ABC":
        xp = PORT_X[port]
        B.text("PMOD %s" % port, xp + 6.35, 19.0, FS, 1.0, 0.15)
        B.text("1", xp - 2.8, Y_FAR, FS, 0.8, 0.12, h="right")
        B.text("7", xp - 2.8, Y_NEAR, FS, 0.8, 0.12, h="right")
        for j, (pa, pb) in enumerate(PORTS[port], start=1):
            B.text(X4[pa][0][2:], xp + P * (j - 1), 14.9, FS, 0.7, 0.1)
            B.text(X4[pb][0][2:], xp + P * (j - 1), 15.9, FS, 0.7, 0.1)
        B.text("GND", xp + 4 * P, 14.9, FS, 0.7, 0.1)
        B.text("3V3", xp + 5 * P, 14.9, FS, 0.7, 0.1)
    B.text("X4 IO numbers: pin 1-4 above, pin 7-10 below", 22.0, 21.2, FS, 0.7, 0.1, h="left")
    B.text("PB2 = IO10 = PCLKT1_1 (clock input)", 22.0, 22.4, FS, 0.7, 0.1, h="left")
    B.text("12-bit DVI Pmod: its J2 on A, its J1 on B", 22.0, 23.6, FS, 0.7, 0.1, h="left")
    B.text("VERSA EDGE", 23.3, 3.0, FS, 0.7, 0.1)
    B.text("VERSA EDGE", 46.2, 3.0, FS, 0.7, 0.1)
    B.text("X4 pin 1", X1 - 0.6, Y_ODD + 1.75, FS, 0.7, 0.1, h="left")
    B.poly([(X1 - 2.0, Y_ODD - 0.5), (X1 - 2.0, Y_ODD + 0.5), (X1 - 1.2, Y_ODD)], FS)
    B.text("X4 bottom", xcol(20) + 1.8, Y_EVEN + 1.27, FS, 0.7, 0.1, h="left")
    B.text("3V3", XL + 1.3, 35.5, FS, 0.7, 0.1, h="left")
    B.text("F1 0.5A", XF - 1.75, 23.5, FS, 0.7, 0.1, rot=90)
    B.text("%s rev %s" % (NAME, REV), 64.9, 29.5, FS, 0.8, 0.12, rot=90)
    B.logo("LOGO1", 17.6, 24.0)

    # --- silkscreen, bottom (mirrored) -------------------------------------------------------
    BS = pcbnew.B_SilkS
    B.text("%s rev %s  %s" % (NAME, REV, DATE), 30.0, 17.0, BS, 1.0, 0.15)
    B.text("Lattice ECP5 Versa X4 -> 3x Pmod host (open source hardware)", 30.0, 18.7, BS, 0.8, 0.12)
    for gi, port in enumerate("ABC"):
        x0 = 4.0 + gi * 19.0
        B.text("PMOD %s  pin: IO ball" % port, x0, 21.0, BS, 0.7, 0.1, h="left")
        for j, (pa, pb) in enumerate(PORTS[port], start=1):
            B.text("%2d: %-4s %-3s %2d: %-4s %-3s" % (j, X4[pa][0], X4[pa][1], 6 + j, X4[pb][0], X4[pb][1]),
                   x0, 22.2 + j * 1.1, BS, 0.7, 0.1, h="left")
        B.text(" 5: GND      11: GND", x0, 22.2 + 5 * 1.1, BS, 0.7, 0.1, h="left")
        B.text(" 6: 3V3      12: 3V3", x0, 22.2 + 6 * 1.1, BS, 0.7, 0.1, h="left")
    B.text("Pmod pin n and n+6 = one ECP5 pair (A/B), except PB2/PB8.  PB2 = PCLKT1_1.", 4.0, 30.3, BS, 0.7, 0.1, h="left")
    B.text("12-bit DVI Pmod: its J2 on PMOD A, its J1 on PMOD B.  3V3: X4 pin 20 -> F1 -> ports.", 4.0, 31.4, BS, 0.7, 0.1, h="left")
    B.text("X4 pin 1", X1 + 1.2, Y_ODD + 2.1, BS, 0.7, 0.1, h="left")
    B.poly([(X1 - 0.4, Y_ODD + 2.45), (X1 + 0.4, Y_ODD + 2.45), (X1, Y_ODD + 1.75)], BS)
    B.logo("LOGO2", 60.5, 22.5, bottom=True)

    # --- save, fill zones on the reloaded board ------------------------------------------------
    path = os.path.join(ROOT, NAME + ".kicad_pcb")
    pcbnew.SaveBoard(path, B.b)
    board = pcbnew.LoadBoard(path)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(path, board)
    return path


# ---------------------------------------------------------------------------------------------
# project files
# ---------------------------------------------------------------------------------------------
def write_project():
    pro = {
        "board": {"design_settings": {
            "defaults": {"silk_text_size_h": 0.8, "silk_text_size_v": 0.8, "silk_text_thickness": 0.12,
                         "silk_line_width": 0.12},
            "rule_severities": {"lib_footprint_issues": "warning", "lib_footprint_mismatch": "warning"},
            "rules": {"min_clearance": 0.2, "min_copper_edge_clearance": 0.3, "min_hole_clearance": 0.25,
                      "min_hole_to_hole": 0.5, "min_silk_clearance": 0.0, "min_text_height": 0.7,
                      "min_text_thickness": 0.1, "min_through_hole_diameter": 0.3, "min_track_width": 0.2,
                      "min_via_annular_width": 0.13, "min_via_diameter": 0.5},
            "track_widths": [0.0, 0.25, 0.4, 0.5], "via_dimensions": [{"diameter": 0.0, "drill": 0.0}, {"diameter": 0.6, "drill": 0.3}]},
            "layer_presets": [], "viewports": []},
        "boards": [], "cvpcb": {"equivalence_files": []},
        "libraries": {"pinned_footprint_libs": [], "pinned_symbol_libs": []},
        "meta": {"filename": NAME + ".kicad_pro", "version": 3},
        "net_settings": {"classes": [{"bus_width": 12, "clearance": 0.2, "diff_pair_gap": 0.25, "diff_pair_via_gap": 0.25,
                                      "diff_pair_width": 0.2, "line_style": 0, "microvia_diameter": 0.3, "microvia_drill": 0.1,
                                      "name": "Default", "pcb_color": "rgba(0, 0, 0, 0.000)", "priority": 2147483647,
                                      "schematic_color": "rgba(0, 0, 0, 0.000)", "track_width": 0.25, "via_diameter": 0.6,
                                      "via_drill": 0.3, "wire_width": 6}],
                         "meta": {"version": 5}, "net_colors": {}, "netclass_assignments": {}, "netclass_patterns": []},
        "pcbnew": {"last_paths": {}, "page_layout_descr_file": ""},
        "schematic": {"legacy_lib_dir": "", "legacy_lib_list": []},
        "sheets": [], "text_variables": {}}
    open(os.path.join(ROOT, NAME + ".kicad_pro"), "w").write(json.dumps(pro, indent=2) + "\n")
    open(os.path.join(ROOT, "fp-lib-table"), "w").write(
        '(fp_lib_table\n  (version 7)\n  (lib (name "%s")(type "KiCad")(uri "${KIPRJMOD}/lib/%s.pretty")(options "")(descr "project footprints"))\n)\n' % (NAME, NAME))
    open(os.path.join(ROOT, "sym-lib-table"), "w").write(
        '(sym_lib_table\n  (version 7)\n  (lib (name "%s")(type "KiCad")(uri "${KIPRJMOD}/lib/%s.kicad_sym")(options "")(descr "project symbols"))\n)\n' % (NAME, NAME))


def main():
    own, ext = library_symbols()
    print("symbol lib   ", write_symbol_lib(own))
    print("footprint lib", write_footprint_lib())
    path, sch = build_schematic(own, ext)
    print("schematic    ", path, len(sch.refs), "symbols")
    write_project()
    print("board        ", build_board())
    print("board %.1f x %.1f mm, %d signal lines" % (BOARD_W, BOARD_H, len(LINES)))


if __name__ == "__main__":
    main()
