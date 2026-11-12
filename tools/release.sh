#!/bin/sh
# ecp5-versa-pmod: verify the design and produce the fabrication outputs (KiCad 10 kicad-cli).
#   ERC, DRC with schematic parity, independent netlist cross-check and pin map, schematic PDF, BOM,
#   Gerbers + drill (JLCPCB style), placement file, 1:1 fit-check PDF, STEP, renders.
set -eu
cd "$(dirname "$0")/.."
N=ecp5-versa-pmod
mkdir -p out/gerber preview

echo "== ERC";  kicad-cli sch erc --severity-all --exit-code-violations --format report -o out/erc.rpt $N.kicad_sch
echo "== DRC";  kicad-cli pcb drc --schematic-parity --refill-zones --save-board --severity-all --exit-code-violations \
                 --format report -o out/drc.rpt $N.kicad_pcb
echo "== netlist cross-check and pin map"
kicad-cli sch export netlist --format kicadsexpr -o out/netlist.net $N.kicad_sch
python3 tools/check.py

echo "== schematic PDF and BOM"
kicad-cli sch export pdf -o out/$N-schematic.pdf $N.kicad_sch
kicad-cli sch export bom --fields 'Reference,Value,Footprint,LCSC,MPN,Description,${QUANTITY}' \
    --labels 'Refs,Value,Footprint,LCSC,MPN,Description,Qty' --group-by 'Value,LCSC,Footprint' --exclude-dnp \
    -o out/bom.csv $N.kicad_sch

echo "== Gerbers, drill, placement"
rm -f out/gerber/*
kicad-cli pcb export gerbers -l F.Cu,B.Cu,F.Mask,B.Mask,F.Silkscreen,B.Silkscreen,F.Paste,Edge.Cuts \
    --subtract-soldermask -o out/gerber/ $N.kicad_pcb
kicad-cli pcb export drill --format excellon -u mm --generate-map --map-format gerberx2 -o out/gerber/ $N.kicad_pcb
kicad-cli pcb export pos --format csv --units mm --side both --exclude-dnp -o out/$N-pos.csv $N.kicad_pcb
python3 - <<'EOF'
import os, zipfile
with zipfile.ZipFile("out/ecp5-versa-pmod-gerber.zip", "w", zipfile.ZIP_DEFLATED) as z:
    for f in sorted(os.listdir("out/gerber")):
        z.write(os.path.join("out/gerber", f), f)
EOF

echo "== 1:1 fit check (print the PDF at 100 %), STEP, renders"
kicad-cli pcb export pdf -l Edge.Cuts,F.Cu,F.Silkscreen --mode-single --drill-shape-opt 2 --black-and-white \
    -o out/$N-fitcheck-top-1to1.pdf $N.kicad_pcb
kicad-cli pcb export step --subst-models -f -o out/$N.step $N.kicad_pcb >/dev/null
kicad-cli pcb render --side top    --quality high --background opaque -w 2000 -h 1300 -o preview/top.png    $N.kicad_pcb >/dev/null
kicad-cli pcb render --side bottom --quality high --background opaque -w 2000 -h 1300 -o preview/bottom.png $N.kicad_pcb >/dev/null
kicad-cli pcb render --quality high --background opaque -w 2000 -h 1300 --perspective --rotate '-55,0,25' --zoom 1.1 \
    -o preview/iso.png $N.kicad_pcb >/dev/null
echo "== done"
