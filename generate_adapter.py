#!/usr/bin/env python3
"""Generate the Versa X4 -> 1BitSquared 12-bit DVI Pmod adapter (KiCad 7 board file).

Run with the system python that has the `pcbnew` bindings:  python3 generate_adapter.py [outdir]

Geometry (all mm, KiCad y axis points down):
  * 2x20 female socket J3 on the BOTTOM side, plugs onto the Versa expansion header X4.
  * Two right-angle 2x6 female Pmod sockets J2 (top) and J1 (bottom) on the top side, 22.89 mm apart,
    opening towards +x, so that the Pmod module lies coplanar to the right of the board.
    J2/J1 carry the module's connectors of the same names (slot "a" = J2, slot "b" = J1).
  * 16 series resistors, one per signal, all signals on F.Cu at 1.27 mm pitch (river route),
    power on B.Cu, ground pours on both layers.
The script is the source of truth; the board file is generated.
"""
import csv
import os
import sys

import pcbnew
from pcbnew import FromMM as mm, VECTOR2I

LIB = "/usr/share/kicad/footprints/"
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
os.makedirs(OUT, exist_ok=True)

# ---- design constants ------------------------------------------------------------------------------------------
HX, HY = 5.0, 4.0            # X4 socket pin 1 (odd column x, first row y)
PITCH = 2.54
LINE0 = HY + PITCH           # y of the first signal line
LPITCH = 1.27                # signal line pitch (half the header pitch)
SX = 50.0                    # far pad column of the Pmod sockets
ST1 = LINE0                  # top of Pmod socket J2 (pad row of Pmod pin 1)
SOCKET_SPACING = 22.89       # J1/J2 spacing of the module
ST2 = ST1 + SOCKET_SPACING
DOGLEG_SHIFT = SOCKET_SPACING - 8 * LPITCH    # 12.73: lines 8..15 move down to socket J1
BOARD_W = SX + 12.8          # socket body front (12.57 + silkscreen) is flush with the board edge
BOARD_H = 56.0
R_VALUE = "100"
TRACK = 0.25
PWR_TRACK = 0.5

# IO number (X4 IO0..IO15) -> FPGA ball, from the Versa schematic (X4 pin = IO + 3)
BALLS = "A12 A13 B13 C13 D13 E13 A14 C14 D14 E14 D11 C10 A9 B10 D12 E12".split()
# Pmod signals of the module (v1.1a): pin -> signal
SIGNALS = {
    "J2": {1: "R3", 2: "R1", 3: "G3", 4: "G1", 7: "R2", 8: "R0", 9: "G2", 10: "G0"},
    "J1": {1: "B3", 2: "CLK", 3: "B0", 4: "HS", 7: "B2", 8: "B1", 9: "DE", 10: "VS"},
}
SIGPINS = [1, 2, 3, 4, 7, 8, 9, 10]

board = pcbnew.BOARD()
nets = {}


def net(name):
    if name not in nets:
        n = pcbnew.NETINFO_ITEM(board, name)
        board.Add(n)
        nets[name] = n
    return nets[name]


def V(x, y):
    return VECTOR2I(mm(x), mm(y))


def load(lib, name):
    return pcbnew.FootprintLoad(LIB + lib + ".pretty", name)


def place(fp, ref, x, y, rot=0.0, flip=False, hide_text=False):
    fp.SetReference(ref)
    fp.SetPosition(V(x, y))
    if rot:
        fp.SetOrientationDegrees(rot)
    board.Add(fp)
    if flip:
        fp.Flip(V(x, y), True)
    if hide_text:
        fp.Reference().SetVisible(False)
        fp.Value().SetVisible(False)
    return fp


def padpos(pad):
    p = pad.GetPosition()
    return (pcbnew.ToMM(p.x), pcbnew.ToMM(p.y))


def track(netname, layer, pts, width=TRACK):
    for a, b in zip(pts[:-1], pts[1:]):
        if a == b:
            continue
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(V(*a))
        t.SetEnd(V(*b))
        t.SetWidth(mm(width))
        t.SetLayer(layer)
        t.SetNet(net(netname))
        board.Add(t)


def via(netname, x, y):
    v = pcbnew.PCB_VIA(board)
    v.SetViaType(pcbnew.VIATYPE_THROUGH)
    v.SetPosition(V(x, y))
    v.SetWidth(mm(0.7))
    v.SetDrill(mm(0.35))
    v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    v.SetNet(net(netname))
    board.Add(v)


def text(s, x, y, layer=pcbnew.F_SilkS, size=1.0, thick=0.15):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(s)
    t.SetPosition(V(x, y))
    t.SetLayer(layer)
    t.SetTextSize(VECTOR2I(mm(size), mm(size)))
    t.SetTextThickness(mm(thick))
    board.Add(t)


# ---- connectors -------------------------------------------------------------------------------------------------
hdr = place(load("Connector_PinSocket_2.54mm", "PinSocket_2x20_P2.54mm_Vertical"), "J3", HX, HY, flip=True, hide_text=True)
hpad = {n: hdr.FindPadByNumber(str(n)) for n in range(1, 41)}
hpos = {n: padpos(p) for n, p in hpad.items()}
# After the flip pin 1 is at (HX, HY), pin 2 at (HX+2.54, HY): odd pins left, even pins right (towards the sockets).
assert abs(hpos[1][0] - HX) < 1e-3 and abs(hpos[2][0] - (HX + PITCH)) < 1e-3, (hpos[1], hpos[2])

sockets = {}
for ref, st in (("J2", ST1), ("J1", ST2)):
    fp = place(load("Connector_PinSocket_2.54mm", "PinSocket_2x06_P2.54mm_Horizontal"), ref, SX, st + 5 * PITCH, rot=180)
    fp.Reference().SetVisible(False)
    fp.Value().SetVisible(False)
    # Renumber the pads to the Pmod pin numbers (pin 1 at the top, pins 1-6 in the column far from the body)
    for p in list(fp.Pads()):
        x, y = padpos(p)
        k = round((y - st) / PITCH)
        pin = k + 1 + (0 if abs(x - SX) < 0.01 else 6)
        p.SetNumber(str(pin))
        p.SetShape(pcbnew.PAD_SHAPE_RECT if pin == 1 else pcbnew.PAD_SHAPE_CIRCLE)
    sockets[ref] = (fp, st)


def socket_pad(ref, pmod_pin):
    """Pad of socket `ref` that holds Pmod pin 1..12 (pads were renumbered to the Pmod numbering above)."""
    return sockets[ref][0].FindPadByNumber(str(pmod_pin))


# ---- signal lines -----------------------------------------------------------------------------------------------
pinmap = []   # rows for the documentation
n_line = 0
for s, ref in enumerate(("J2", "J1")):
    for pin in SIGPINS:
        nl = 2 * (pin - 1) if pin <= 4 else 2 * (pin - 7) + 1       # line index inside the socket
        n = 8 * s + nl
        io = n + 1 if n % 2 == 0 else n - 1                          # even line: pin 4+2i = IO 2i+1
        xpin = 3 + io
        sig = SIGNALS[ref][pin]
        y = LINE0 + LPITCH * n
        px, py = hpos[xpin]
        pts = [(px, py)]
        if px < HX + PITCH - 0.01:                                  # odd pin: stub down to the line
            pts.append((px, y))
        xr = 18.0 if n % 2 == 0 else 26.0
        r = place(load("Resistor_SMD", "R_0603_1608Metric"), "R%d" % (n + 1), xr, y, hide_text=True)
        r.SetValue(R_VALUE)
        r1, r2 = r.FindPadByNumber("1"), r.FindPadByNumber("2")
        r1.SetNet(net("IO%d" % io))
        r2.SetNet(net("DVI_" + ref + "_" + sig))
        hpad[xpin].SetNet(net("IO%d" % io))
        track("IO%d" % io, pcbnew.F_Cu, pts + [padpos(r1)])
        # after the resistor: straight to the socket, or dogleg down for socket J1
        x2 = padpos(r2)[0]
        sp = socket_pad(ref, pin)
        spx, spy = padpos(sp)
        sp.SetNet(net("DVI_" + ref + "_" + sig))
        out = [padpos(r2)]
        yy = y
        if s == 1:
            xd = 34.0 + 0.8 * (15 - n)
            yy = y + DOGLEG_SHIFT
            out += [(xd, y), (xd, yy)]
        out.append((spx, yy))
        if pin >= 7:                                      # near column pad: end with a jog to the pad row
            out.append((spx, spy))
        track("DVI_" + ref + "_" + sig, pcbnew.F_Cu, out)
        pinmap.append(dict(socket=ref, pmod_pin=pin, signal=sig, x4_pin=xpin, io="IO%d" % io, ball=BALLS[io],
                           line=n, resistor="R%d" % (n + 1)))

# ---- power ------------------------------------------------------------------------------------------------------
V33, GND = "3V3", "GND"
hpad[20].SetNet(net(V33))
for p in (19, 22):
    hpad[p].SetNet(net(GND))
for ref in ("J2", "J1"):
    for pin, nm in ((5, GND), (11, GND), (6, V33), (12, V33)):
        socket_pad(ref, pin).SetNet(net(nm))

TRUNK_X = 44.0
y20 = hpos[20][1]
y_j2_pwr = ST1 + 5 * PITCH
y_j1_pwr = ST2 + 5 * PITCH
BUS_Y = 47.0
track(V33, pcbnew.B_Cu, [hpos[20], (TRUNK_X, y20)], PWR_TRACK)
track(V33, pcbnew.B_Cu, [(TRUNK_X, y_j2_pwr), (TRUNK_X, BUS_Y)], PWR_TRACK)
track(V33, pcbnew.B_Cu, [(TRUNK_X, y_j2_pwr), (SX + PITCH, y_j2_pwr)], PWR_TRACK)
track(V33, pcbnew.B_Cu, [(TRUNK_X, y_j1_pwr), (SX + PITCH, y_j1_pwr)], PWR_TRACK)
track(V33, pcbnew.B_Cu, [(40.0, BUS_Y), (57.0, BUS_Y)], PWR_TRACK)


def two_pad(fpref, lib, name, x, y, rot, top_net, bot_net, via_top=True):
    fp = place(load(lib, name), fpref, x, y, rot=rot, hide_text=True)
    pads = sorted(fp.Pads(), key=lambda p: padpos(p)[1])
    pads[0].SetNet(net(top_net))
    pads[1].SetNet(net(bot_net))
    return fp, pads


# decoupling: 10 uF bulk and one 100 nF per socket, power LED with 1k
parts = [("C1", "Capacitor_SMD", "C_0805_2012Metric", 40.0, "10uF"),
         ("C2", "Capacitor_SMD", "C_0603_1608Metric", 46.0, "100nF"),
         ("C3", "Capacitor_SMD", "C_0603_1608Metric", 52.0, "100nF")]
for ref, lib, name, x, val in parts:
    fp, pads = two_pad(ref, lib, name, x, 50.0, 90, V33, GND)
    fp.SetValue(val)
    (tx, ty), (bx, by) = padpos(pads[0]), padpos(pads[1])
    via(V33, x, BUS_Y)
    track(V33, pcbnew.F_Cu, [(x, BUS_Y), (tx, ty)])
    via(GND, x, by + 2.2)
    track(GND, pcbnew.F_Cu, [(bx, by), (x, by + 2.2)])

fpR, padsR = two_pad("R17", "Resistor_SMD", "R_0603_1608Metric", 57.0, 49.0, 90, V33, "LED_A")
fpR.SetValue("1k")
fpL = place(load("LED_SMD", "LED_0603_1608Metric"), "D1", 57.0, 52.2, rot=90, hide_text=True)
fpL.SetValue("3V3 LED")
pa, pk = fpL.FindPadByNumber("2"), fpL.FindPadByNumber("1")
if padpos(pa)[1] > padpos(pk)[1]:
    fpL.SetOrientationDegrees(270)
pa, pk = fpL.FindPadByNumber("2"), fpL.FindPadByNumber("1")
assert padpos(pa)[1] < padpos(pk)[1]
pa.SetNet(net("LED_A"))
pk.SetNet(net(GND))
via(V33, 57.0, BUS_Y)
track(V33, pcbnew.F_Cu, [(57.0, BUS_Y), padpos(padsR[0])])
track("LED_A", pcbnew.F_Cu, [padpos(padsR[1]), padpos(pa)])
via(GND, 57.0, padpos(pk)[1] + 1.6)
track(GND, pcbnew.F_Cu, [padpos(pk), (57.0, padpos(pk)[1] + 1.6)])

# ---- LCSC / JLCPCB part numbers (looked up 2026-11-12; see README for the status of each) ---------------------------
PARTS = {   # reference -> (value text, LCSC number, manufacturer part number)
    "J3": ("2x20 female 8.5mm", "C2977589", "2.54-2*20 (ZHOURI)"),
    "J1": ("2x6 female RA", "C2897426", "PM254-2-06-W-8.5 (HCTL)"),
    "J2": ("2x6 female RA", "C2897426", "PM254-2-06-W-8.5 (HCTL)"),
    "R17": ("1k", "C21190", "0603WAF1001T5E (UNI-ROYAL)"),
    "C1": ("10uF", "C15850", "CL21A106KAYNNNE (Samsung)"),
    "C2": ("100nF", "C14663", "CC0603KRX7R9BB104 (YAGEO)"),
    "C3": ("100nF", "C14663", "CC0603KRX7R9BB104 (YAGEO)"),
    "D1": ("LED red", "C2286", "KT-0603R (Hubei KENTO)"),
}
for i in range(1, 17):
    PARTS["R%d" % i] = (R_VALUE, "C22775", "0603WAF1000T5E (UNI-ROYAL)")
bom = {}
for f in board.GetFootprints():
    ref = f.GetReference()
    val, lcsc, mpn = PARTS[ref]
    f.SetValue("%s %s" % (val, lcsc))
    f.SetProperties({"LCSC": lcsc, "MPN": mpn})
    bom.setdefault((val, lcsc, mpn, str(f.GetFPID().GetLibItemName())), []).append(ref)
with open(os.path.join(OUT, "bom.csv"), "w", newline="") as fbom:
    w = csv.writer(fbom)
    w.writerow(["Designators", "Qty", "Value", "Footprint", "LCSC", "MPN"])
    for (val, lcsc, mpn, fpn), refs in sorted(bom.items(), key=lambda kv: kv[1][0]):
        w.writerow([",".join(sorted(refs, key=lambda r: (r[0], int(r[1:])))), len(refs), val, fpn, lcsc, mpn])

# ---- outline, pours -----------------------------------------------------------------------------------------------
e = pcbnew.PCB_SHAPE(board)
e.SetShape(pcbnew.SHAPE_T_RECT)
e.SetStart(V(0, 0))
e.SetEnd(V(BOARD_W, BOARD_H))
e.SetLayer(pcbnew.Edge_Cuts)
e.SetWidth(mm(0.1))
board.Add(e)

for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
    z = pcbnew.ZONE(board)
    z.SetLayer(layer)
    z.SetNet(net(GND))
    ol = z.Outline()
    ol.NewOutline()
    for x, y in ((0.3, 0.3), (BOARD_W - 0.3, 0.3), (BOARD_W - 0.3, BOARD_H - 0.3), (0.3, BOARD_H - 0.3)):
        ol.Append(mm(x), mm(y))
    z.SetMinThickness(mm(0.25))
    z.SetLocalClearance(mm(0.3))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
    z.SetThermalReliefGap(mm(0.3))
    z.SetThermalReliefSpokeWidth(mm(0.4))
    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    board.Add(z)
for x, y in ((20, 2.2), (30, 2.2), (40, 2.2), (28, 53.5), (36, 53.5), (22, 53.5)):
    via(GND, x, y)

# ---- silkscreen ---------------------------------------------------------------------------------------------------
text("Versa X4 > Pmod DVI adapter rev A", 33.0, 4.2, size=1.0)
text("X4 pin 1", HX + 1.3, 1.4, size=0.9)
text("J3 = Versa X4, plugs UNDER the board", 30.0, 54.4, size=0.8)
text("J2 (slot a)", SX + 7.0, 3.4, size=1.0)
text("J1 (slot b)", SX + 7.0, 22.3, size=1.0)
text("1", SX - 1.9, ST1, size=0.9)
text("1", SX - 1.9, ST2, size=0.9)

# ---- save and documentation ---------------------------------------------------------------------------------------
path = os.path.join(OUT, "versa-pmod-dvi-adapter.kicad_pcb")
pcbnew.SaveBoard(path, board)
with open(os.path.join(OUT, "pinmap.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(pinmap[0].keys()))
    w.writeheader()
    w.writerows(sorted(pinmap, key=lambda r: (r["socket"] != "J2", r["pmod_pin"])))
# Zone fill on a board that was loaded from disk (filling the in-memory board crashes KiCad 7.0.11)
board = pcbnew.LoadBoard(path)
filler = pcbnew.ZONE_FILLER(board)
filler.Fill(board.Zones())
pcbnew.SaveBoard(path, board)
print("wrote", path, "%d signal lines, %d nets" % (len(pinmap), len(nets)))
