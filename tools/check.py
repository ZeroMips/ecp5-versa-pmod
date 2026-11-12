#!/usr/bin/env python3
"""Cross-check the board against the schematic netlist (independently of KiCad's parity check),
check the fit of the 1BitSquared 12-bit DVI Pmod, and write out/pinmap.csv.

Usage:  kicad-cli sch export netlist --format kicadsexpr -o out/netlist.net ecp5-versa-pmod.kicad_sch
        python3 tools/check.py
"""
import csv
import os
import re
import sys

import pcbnew

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate as G   # noqa: E402  (tables and geometry; importing does not generate anything)

OUT = os.path.join(G.ROOT, "out")


def sx(text):
    tokens = re.findall(r'"(?:[^"\\]|\\.)*"|\(|\)|[^\s()"]+', text)
    pos = 0

    def parse():
        nonlocal pos
        tok = tokens[pos]
        pos += 1
        if tok == "(":
            lst = []
            while tokens[pos] != ")":
                lst.append(parse())
            pos += 1
            return lst
        return tok[1:-1] if tok.startswith('"') else tok
    return parse()


def netlist_nets(path):
    tree = sx(open(path).read())
    nets = {}
    for sec in tree:
        if isinstance(sec, list) and sec and sec[0] == "nets":
            for net in sec[1:]:
                name = [x for x in net if isinstance(x, list) and x[0] == "name"][0][1]
                nodes = {(x[1][1], x[2][1]) for x in net if isinstance(x, list) and x[0] == "node"}
                nets[name] = nodes
    return nets


def board_nets(path):
    b = pcbnew.LoadBoard(path)
    nets = {}
    for fp in b.GetFootprints():
        for pad in fp.Pads():
            n = pad.GetNetname()
            if n:
                nets.setdefault(n, set()).add((fp.GetReference(), pad.GetNumber()))
    return nets


def check_nets():
    sch = netlist_nets(os.path.join(OUT, "netlist.net"))
    pcb = board_nets(os.path.join(G.ROOT, G.NAME + ".kicad_pcb"))
    bad = 0
    for name, nodes in sorted(sch.items()):
        if name.startswith("unconnected-"):
            if pcb.get(name, set()) != nodes:
                print("NC mismatch", name, pcb.get(name), nodes)
                bad += 1
            continue
        if pcb.get(name) != nodes:
            print("MISMATCH", name, "schematic:", sorted(nodes), "board:", sorted(pcb.get(name, ())))
            bad += 1
    for name in pcb:
        if name not in sch:
            print("board-only net", name, sorted(pcb[name]))
            bad += 1
    print("nets: %d in schematic, %d on board, %d mismatches" % (len(sch), len(pcb), bad))
    return bad


def pair_note(ball):
    pt = G.PT.get(ball, "")
    site = pt.split("/")[0]
    note = ""
    if "PCLK" in pt:
        note = pt.split("/")[1]
    return site, note


def write_pinmap():
    rows = []
    for l in G.LINES:
        site, note = pair_note(l["ball"])
        partner = [m for m in G.LINES if m["port"] == l["port"] and (m["pmod"] - 1) % 6 == (l["pmod"] - 1) % 6 and m is not l][0]
        psite, _ = pair_note(partner["ball"])
        pair = "pair with pin %d (%s)" % (partner["pmod"], site[:-1]) if site[:-1] == psite[:-1] else "no pair"
        rows.append(dict(port=l["port"], pmod_pin=l["pmod"], net=l["net_p"], resistor=l["r"], x4_pin=l["x4"],
                         x4_io=l["io"], ball=l["ball"], ecp5_pad=G.PT[l["ball"]], pair=pair, clock=note,
                         dvi_pmod=G.DVI.get(l["port"], {}).get(l["pmod"], "")))
    for port in "ABC":
        for pmod, nm in ((5, "GND"), (11, "GND"), (6, "3V3"), (12, "3V3")):
            x4 = {"GND": "2,19,22,...", "3V3": "20 (via F1)"}[nm]
            rows.append(dict(port=port, pmod_pin=pmod, net=nm, resistor="", x4_pin=x4, x4_io=nm, ball="", ecp5_pad="",
                             pair="", clock="", dvi_pmod=nm))
    rows.sort(key=lambda r: (r["port"], r["pmod_pin"]))
    path = os.path.join(OUT, "pinmap.csv")
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    return path, rows


def check_dvi_fit():
    """Module v1.1a (dvi-12bit.kicad_pcb): J2 at y=35.12, J1 at y=58.01 (same x), pins 1..6 at 2.54 mm
    pitch along the edge, pins 7..12 in the row 2.54 mm nearer the module edge.  Mated on ports A+B with
    the module's J2 pin 1 on port A pin 1, every module pin must land on the adapter pad of the same
    Pmod number."""
    J2, J1 = 35.12, 58.01
    worst = 0.0
    for port, yconn in (("A", J2), ("B", J1)):
        for pmod in range(1, 13):
            k = (pmod - 1) % 6
            x = G.PORT_X["A"] + (yconn - J2) + 2.54 * k
            y = G.Y_FAR if pmod <= 6 else G.Y_NEAR
            px, py = G.port_pad(port, pmod)
            worst = max(worst, abs(px - x), abs(py - y))
    assert worst < 0.1, worst
    return worst


def main():
    bad = check_nets()
    path, rows = write_pinmap()
    print("pin map:", path, len(rows), "rows")
    print("DVI Pmod fit on A+B: worst pin offset %.3f mm" % check_dvi_fit())
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
