# Versa X4 to Pmod DVI adapter (rev A, DRAFT, not ordered)

Plugs onto the Versa expansion header **X4** and carries the two 2x6 Pmod connectors of the 1BitSquared
iCEBreaker 12-bit DVI Pmod (hardware v1.1a). The module lies coplanar beside the adapter, as on any Pmod host.
`generate_adapter.py` is the source of truth (KiCad 7 `pcbnew` bindings); `out/` holds the generated board, Gerbers, drill file, placement file and DRC report; `preview/` has renderings.

| Item | Value |
|---|---|
| Board | 62.8 x 56.0 mm, 2 layers, 1.6 mm |
| J3 | 2x20 female socket, 2.54 mm, on the **bottom**, onto X4 (body height decides the stand-off: check against the Versa) |
| J2, J1 | 2x6 female right-angle Pmod sockets, top side, opening to +x, 22.89 mm apart (the module's J2 above J1) |
| R1 to R16 | 100 ohm 0603, one per signal, in series |
| Power | 3V3 from X4 pin 20 only, GND from X4 pins 19 and 22 only; C1 10 uF 0805, C2 and C3 100 nF 0603, D1 and R17 (1 kohm) as a 3V3 LED |
| Routing | all 16 signals on F.Cu at 1.27 mm pitch (one layer, no crossings), 3V3 on B.Cu, GND pours on both layers |

## Pin map (generated from the board, checked chain by chain)

| Socket | Pmod pin | Signal | R | X4 pin | X4 IO | FPGA ball |
|---|---|---|---|---|---|---|
| J2 | 1 | R3 | R1 | 4 | IO1 | A13 |
| J2 | 2 | R1 | R3 | 6 | IO3 | C13 |
| J2 | 3 | G3 | R5 | 8 | IO5 | E13 |
| J2 | 4 | G1 | R7 | 10 | IO7 | C14 |
| J2 | 7 | R2 | R2 | 3 | IO0 | A12 |
| J2 | 8 | R0 | R4 | 5 | IO2 | B13 |
| J2 | 9 | G2 | R6 | 7 | IO4 | D13 |
| J2 | 10 | G0 | R8 | 9 | IO6 | A14 |
| J1 | 1 | B3 | R9 | 12 | IO9 | E14 |
| J1 | 2 | CLK | R11 | 14 | IO11 | C10 |
| J1 | 3 | B0 | R13 | 16 | IO13 | B10 |
| J1 | 4 | HS | R15 | 18 | IO15 | E12 |
| J1 | 7 | B2 | R10 | 11 | IO8 | D14 |
| J1 | 8 | B1 | R12 | 13 | IO10 | D11 |
| J1 | 9 | DE | R14 | 15 | IO12 | A9 |
| J1 | 10 | VS | R16 | 17 | IO14 | D12 |

Pins 5 and 11 are GND and 6 and 12 are 3V3 on both sockets. The module's J2 is LiteX slot "a", J1 slot "b".
IO11 to IO13 are in bank 0, the rest in bank 1; both banks run at 3.3 V on the Versa.

## Why it is built this way
- **Series resistors and power on three pins only.** The 2x20 socket fits in two positions, rotated by 180 degrees. In the wrong one X4 pin 20 meets the adapter's pin 21 (not connected), the adapter's 3V3 net meets IO16 (an input), and both GND pins meet GND pins. Nothing can be shorted; the card just does not work, and only the pin table changes. The 100 ohm resistors also limit the current if gateware drives a pin by mistake.
- **Pin assignment.** The lines leave X4 in header order and enter the sockets in the same order, so no line crosses another. Any permutation is allowed in the gateware, so the order of this table is fixed by the routing, not by the module.
- **Pmod orientation.** Taken from the module's own PCB file: in its footprint pad 1 (net R3) is the top pin of J2 when the connector edge faces left, pins 1 to 6 are the column away from the plastic (the upper row of the right-angle header), pins 7 to 12 the column next to it. The adapter's sockets are renumbered to the same positions.

## Parts (LCSC / JLCPCB numbers, looked up 2026-11-12; also in `out/bom.csv` and in each part's value and `LCSC` field)

| Ref | Part | LCSC | Status found |
|---|---|---|---|
| R1 to R16 | 100 ohm 1% 0603, UNI-ROYAL 0603WAF1000T5E | [C22775](https://jlcpcb.com/partdetail/C22775) | Basic (JLCPCB page) |
| R17 | 1 kohm 1% 0603, UNI-ROYAL 0603WAF1001T5E | [C21190](https://jlcpcb.com/partdetail/C21190) | Basic (JLCPCB page) |
| C2, C3 | 100 nF 50 V X7R 0603, YAGEO CC0603KRX7R9BB104 | [C14663](https://jlcpcb.com/partdetail/C14663) | Basic (JLCPCB page) |
| C1 | 10 uF 25 V X5R 0805, Samsung CL21A106KAYNNNE | [C15850](https://jlcpcb.com/partdetail/C15850) | page not readable by our fetch (rate limit); part identity from a search result, Basic status from a forum post: check |
| D1 | red LED 0603, Hubei KENTO KT-0603R | [C2286](https://jlcpcb.com/partdetail/C2286) | Basic (JLCPCB page); red, about 1.3 mA through R17: dim but visible |
| J1, J2 | 2x6 female 2.54 mm, right angle, 8.5 mm, HCTL PM254-2-06-W-8.5 | [C2897426](https://www.lcsc.com/product-detail/C2897426.html) | listed "right angle"; class and stock not seen; pin positions vs the footprint **not verified** (the datasheet drawing was not readable) |
| J3 | 2x20 female 2.54 mm, 8.5 mm insulator, 3.2 mm tail, "ZHOURI" 2.54-2*20 | [C2977589](https://www.lcsc.com/product-detail/C2977589.html) | "holes direction: top", so presumably straight, not stated; extended part per a search result; manufacturer name inconsistent on the page: check |

Stock and prices were not visible in what we could read: check them in the JLCPCB parts library before ordering. The connectors are through-hole: plan to solder them by hand (JLCPCB assembles through-hole parts only as a special service). If the 8.5 mm J3 is too tall or short for the Versa, take another 2x20 socket and keep the footprint.

## Check before ordering (the open points)
1. **X4 pin 1.** The board assumes pin 1 at the top left when the adapter is seen from above, with the Pmod sockets to the right. Read the silkscreen of the Versa at X4 and confirm which end is pin 1 and which row (odd or even) is nearer the board edge. If it is wrong, the adapter still cannot be damaged (see above), but the module would stand where the Versa has no room; then the generator needs a mirrored variant.
2. **Room.** The module is 41.0 x 40.8 mm and hangs off to the right of the adapter, at the height of the socket. Check that nothing of the Versa (connectors, heat sink, the other header) is in that space.
3. **1:1 print.** Print `preview/fitcheck_top_1to1.svg` at 100 percent, lay the module's connector next to it, and check the 22.89 mm spacing and that the sockets' rows match the module's header rows. With a multimeter on the module: J2 pin 1 (R3) must be the pin nearest to the module's top edge in the picture of its PCB.
4. **Parts.** Compare the drawing of the chosen right-angle socket (C2897426 or another) with KiCad's `PinSocket_2x06_P2.54mm_Horizontal`: pad positions, which column is the upper row, and where the plastic ends. The 2x20 socket height decides the stand-off to the Versa.
5. **Gerber review.** `out/gerber/` was only inspected as renderings; load it in a viewer before ordering.

## Reproduce
```sh
python3 generate_adapter.py      # system python with the pcbnew bindings (KiCad 7.0.11 tested)
```
Zone filling in KiCad 7.0.11 crashes on an in-memory board, so the script saves, reloads and fills.
DRC: `pcbnew.WriteDRCReport` on the saved board gives 0 errors and 0 unconnected pads; the 24 remaining warnings say that the footprints are not linked to a library table.
No schematic was drawn: the nets come from the script, which is the netlist.
