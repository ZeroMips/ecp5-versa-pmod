# Notes: the facts this adapter rests on (2026-11-12)

## Versa expansion header X4 (Lattice FPGA-EB-02021 2.3, table 12 and schematic sheet 10; board photo figure 1)

| Pin | Signal | Ball | ECP5 pad | Pin | Signal | Ball | ECP5 pad |
|---|---|---|---|---|---|---|---|
| 1 | RESOUT# | A8 | PT18B | 2 | GND | | |
| 3 | IO0 | A12 | PT49A | 4 | IO1 | A13 | PT49B |
| 5 | IO2 | B13 | PT51A | 6 | IO3 | C13 | PT51B |
| 7 | IO4 | D13 | PT53A | 8 | IO5 | E13 | PT53B |
| 9 | IO6 | A14 | PT56A | 10 | IO7 | C14 | PT56B |
| 11 | IO8 | D14 | PT58A | 12 | IO9 | E14 | PT58B |
| 13 | IO10 | D11 | PT42A / PCLKT1_1 | 14 | IO11 | C10 | PT31B |
| 15 | IO12 | A9 | PT33A / GR_PCLK0_1 | 16 | IO13 | B10 | PT33B / GR_PCLK0_0 |
| 17 | IO14 | D12 | PT47A / GR_PCLK1_0 | 18 | IO15 | E12 | PT47B / GR_PCLK1_1 |
| 19 | GND | | | 20 | 3V3 | | |
| 21 | IO16 | B15 | PT69A | 22 | GND | | |
| 23 | IO17 | C15 | PT69B | 24 | GND | | |
| 25 | IO18 | D15 | PT71A | 26 | GND | | |
| 27 | IO19 | E15 | PT71B | 28 | IO20 | A16 | PT74A |
| 29 | IO21 | B16 | PT74B | 30 | GND | | |
| 31 | IO22 | C16 | PT76A | 32 | IO23 | D16 | PT76B |
| 33 | IO24 | B17 | PT78A | 34 | GND | | |
| 35 | IO25 | C17 | PT78B | 36 | IO26 | A17 | PT80A |
| 37 | IO27 | B18 | PT80B | 38 | CARDSEL# | A7 | PT18A |
| 39 | IO28 | A18 | PT83A | 40 | GND | | |

- X3 and X4 are Wurth 61304021121 (2x20 male, 2.54 mm). X3 pin 2 is removed for coding; X4 is not keyed.
- The ECP5 pad names come from the Versa schematic (sheet 10) and agree with prjtrellis `iodb.json` for LFE5UM-45F
  CABGA381; A/B of the same PT number are one differential pair. VCCIO0 and VCCIO1 are on the 3.3 V rail.
- The amaranth-boards `versa_ecp5.py` connector definition for X4 matches ball by ball.
- Placement (photo, figure 1 of the guide): X4 along the top edge (opposite the PCIe fingers), body about 1 mm from the
  edge, right end about 3 mm from the board's right edge (mounting hole TH3 in that corner). X3 parallel, 25 mm further in.
  The pin 1 triangle of both headers is at the lower left corner (row nearer X3). Confirmed on the real board.
- X4 has one 3V3 pin (20); X3 carries 3V3 on 25, 27, 35, 37, 39, 5VIN on 21 and 2V5 on 3 and 23.

Connector table in LiteX/Amaranth style (pin number -> ball), for a platform file:

```
X4: 3 A12, 4 A13, 5 B13, 6 C13, 7 D13, 8 E13, 9 A14, 10 C14, 11 D14, 12 E14, 13 D11, 14 C10, 15 A9, 16 B10, 17 D12,
    18 E12, 21 B15, 23 C15, 25 D15, 27 E15, 28 A16, 29 B16, 31 C16, 32 D16, 33 B17, 35 C17, 36 A17, 37 B18, 39 A18
PMOD A pins 1-4, 7-10:  A12 B13 D13 A14,  A13 C13 E13 C14
PMOD B pins 1-4, 7-10:  D14 D11 A9  D12,  E14 C10 B10 E12
PMOD C pins 1-4, 7-10:  B15 D15 A16 C16,  C15 E15 B16 D16
```

## Pmod Interface Specification 1.3.1 (Digilent, October 2020)

- Host ports side by side: 0.90 in = 22.86 mm centre to centre (figure 5).
- Host port pad pattern (figure 5, host seen from above, port opening to the right): pin 1 (square) at the top of the
  column farther from the board edge, 1..6 down that column, 7..12 in the column nearer the edge; near column 0.40 in =
  10.16 mm from the board edge. Looking into the port, pin 1 is upper right; on the module (figure 2), looking at its
  pins, pin 1 is upper left. "The pin numbering conventions for the 2x6 connectors are non-standard and are mirrored
  between the host connector and the peripheral board connector."
- Module: right-angle male header at the board edge, near pin column 0.15 in = 3.81 mm from the module edge (figure 2).
- Standard host ports "generally have ESD protection diodes and 200-ohm series resistors"; high-speed ports have neither.
- A module "should not be assumed to draw more than approximately 100 mA". 3.3 V LVCMOS/LVTTL logic.
- "The Pmod interface is not intended for high frequency operation"; >100 MHz is said to be feasible with direct
  connection. Pins 5/11 GND, 6/12 VCC; SPI/UART interfaces use the upper row (1-6) on 12-pin hosts.

## 1BitSquared iCEBreaker 12-bit DVI Pmod, hardware v1.1a

Source: Codeberg `icebreaker-fpga/icebreaker-pmod`, `dvi-12bit/v1.1a/dvi-12bit.kicad_pcb` (CC-BY-SA 4.0, 1BitSquared /
Piotr Esden-Tempski). Revisions v1.0a/b, v1.1a/b, v1.2a/b exist in the repository; only v1.1a was read.

- Footprint `PMODHeader_2x06_P2.54mm_Horizontal`, J2 at (36.60, 35.12), J1 at (36.60, 58.01), both rotated 180 degrees:
  connectors **22.89 mm** apart along the board edge, which is at x = 30. Pins 1..6 in the column 6.60 mm from the edge
  (upper row), 7..12 in the column 4.06 mm from the edge; pin 1 at the small-y end. Outline 40.0 x 40.8 mm
  (x 30..70, y 19.8..60.6); HDMI connector J6 at the far end.
- J2 = R3 R1 G3 G1 / R2 R0 G2 G0 (pins 1 2 3 4 / 7 8 9 10), J1 = B3 CLK B0 HS / B2 B1 DE VS. 5/11 GND, 6/12 3V3.
  SiI164 (or TFP410) transmitter, single data rate pixel clock, 12 bits per pixel on the top 4 bits of each colour.
- Mated on ports A+B: module J2 on A, J1 on B; with the Versa edge at the top the module's J2 is the left connector.
  The module then spans adapter x 2.9..43.7 (40.8 mm) and reaches 40 mm beyond the Versa edge.
