# External framebuffer PoC: 1BitSquared 12-bit DVI Pmod on the Versa (notes, 2026-11-11)

Goal: the host sends frames over PCIe into a framebuffer that lives in the FPGA (block RAM); the FPGA scans it out
to a monitor through the iCEBreaker 12-bit DVI Pmod. Nothing built yet; this records what was verified.

## Sources (all read locally)
- Pmod design, hardware v1.1a: the 1BitSquared `icebreaker-pmod` repository, `dvi-12bit/v1.1a/` (KiCad schematic, PCB, `dvi-12bit-sch.pdf`).
  Credit: 1BitSquared and Piotr Esden-Tempski, CC-BY-SA 4.0 (from the schematic's title block). Our adapter only uses
  its connector dimensions and pin names.
- LiteX-Boards `litex_boards/extensions/pmod.py` `PmodDVI` (same map as the schematic, checked pin by pin) and
  LiteX `VideoDVIPHY` (parallel 12-bit PHY) as used by the iCEBreaker target.
- Versa: EB98 board guide (schematic sheet 10 "Expansion Connector", BOM, block diagram).
- The Codeberg web pages were not used: the site serves "AI scraper" filler pages to automated clients; the clone was made by the user.

## The Pmod (v1.1a)
SiI164 DVI transmitter, HDMI-type connector J6, two right-angle 2x6 male Pmod headers J1/J2 (pins 1-4 and 7-10 are signals,
5/11 GND, 6/12 3V3). 12 bits per pixel: the top 4 bits of R, G, B on the transmitter's data inputs, the others tied to GND.
Single-data-rate pixel clock. 3.3 V logic. Optional 5 V for the HDMI connector through J4 (pads, not wired to the Pmod).

| Pmod pin | J2 (LiteX slot "a") | J1 (slot "b") |
|---|---|---|
| 1 | R3 | B3 |
| 2 | R1 | CLK |
| 3 | G3 | B0 |
| 4 | G1 | HS (hsync) |
| 7 | R2 | B2 |
| 8 | R0 | B1 |
| 9 | G2 | DE |
| 10 | G0 | VS (vsync) |

Mechanics (KiCad PCB): J1 at y=58.01 and J2 at y=35.12 mm, same x: the two connectors are 22.89 mm (0.90 in) apart, pin 1 to pin 6 along
the y axis, 2.54 mm pitch; board outline 41.0 x 40.8 mm.

## Versa side
- X3 and X4: Wurth 61304021121, 2x20 male headers, 0.1 in, populated (BOM). X3 pin 2 is removed for coding.
- Banks: X4 IO0-IO28 are balls in Bank 1 (26) and Bank 0 (3: IO11 C10, IO12 A9, IO13 B10); X3 IO29-IO45 mostly Bank 0.
  Schematic sheet 10: VCCIO0 and VCCIO1 are both on the 3_3V rail, so all of them are 3.3 V LVCMOS.
- X4 pins: 3-18 = IO0-IO15 (no ground pin in between), pin 20 = 3V3, GND on pins 2, 19, 22, 24, ...
- X3 pin 21 is 5VIN (the only 5 V on the headers), X3 pin 29 OSC, X3 31 CLKIN, X3 33 CLKOUT.

## Proposed pin assignment (adapter and gateware)
Superseded by the routed adapter in `hw/versa-pmod-dvi-adapter/` (rev A, draft): its README has the pin table, generated from the board.
J2 (slot "a") takes X4 IO0-IO7, J1 (slot "b") IO8-IO15, in an order fixed by the routing (the lines leave X4 in header order); Pmod 3V3 comes
from X4 pin 20 and GND from pins 19 and 22 only. The platform needs the connector definitions `pmoda`/`pmodb` with those balls
(LiteX's Versa platform defines X3 only).

## Framebuffer in block RAM
ECP5-45F: 108 EBR (DP16KD). A 12-bit pixel packs into 3 x 4-bit-wide slices (4096 words per EBR).
| Image | Bits | EBR (packed) | Scanout |
|---|---:|---:|---|
| 160x120 | 230 kbit | 14 | x4 to 640x480 |
| 256x192 | 590 kbit | 36 | x2.5, so 512x384 centered |
| 320x240 | 922 kbit | 57 | x2 to 640x480 |
The DMA design with the analyzer already uses 56 EBR: 320x240 needs the analyzer off (or a smaller image). Pixel clock 25 MHz = sys 75 MHz / 3.

## Host path
Host writes pixels into BAR0 (memory-mapped RAM region on the SoC bus, needs a larger BAR0), a kernel DRM driver exposes it to Wayland
(the compositor renders on its GPU and the driver copies damaged rectangles; GPU peer-to-peer into a BAR is not needed).
