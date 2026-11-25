#!/usr/bin/env bash
# Phase 7 (Issue #8) full browser QA chain: the reported Phase 7 run (no seed) and the earlier phases' browser QA as
# regression, each into its own folder under docs/3d-world-expansion/qa/phase7 (earlier evidence folders untouched).
# Ports: Phase 7 8798/5198, 6: 8796/5196, 4/5: 8775/5175, lab: Vite 5199. Port 5173 (the user's dev server) is never used.
cd "$(dirname "$0")/.."
Q=../../docs/3d-world-expansion/qa/phase7
node scripts/phase7-qa.mjs; echo "phase7 exit $?"
node scripts/phase6-qa.mjs --out=$Q/regression-phase6; echo "phase6 exit $?"
node scripts/phase5-qa.mjs --out=$Q/regression-phase5; echo "phase5 exit $?"
node scripts/phase4-qa.mjs --out=$Q/regression-phase4; echo "phase4 exit $?"
SRS3D_VITE_CACHE=.qa-saves/vite-cache-lab node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5199 --strictPort > /dev/null 2>&1 &
VITE=$!; sleep 6
node scripts/browser-qa.mjs --url=http://127.0.0.1:5199/lab.html --output=$Q/regression-lab; echo "lab exit $?"
kill $VITE
