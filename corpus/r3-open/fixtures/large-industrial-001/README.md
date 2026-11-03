# large-industrial-001

A synthetic industrial site of one million entities (pipe-run lines, valve circles, elbow arcs and cable-tray polylines on a 2 km by 1 km grid). It is generated, never committed as a DWG: run `python3 tools/authoring/gen_large_industrial.py --count 1000000 --seed 96 --out large-industrial-001.json`. The output is a pure function of seed and count, and `sample_sha256` in the manifest is the hash of the same command run with `--count 1000`.
