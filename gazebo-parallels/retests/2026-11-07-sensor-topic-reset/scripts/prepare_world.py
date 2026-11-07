#!/usr/bin/env python3
"""Change only the Sensors plugin filename in a fresh SDF copy."""
from pathlib import Path
import argparse,html,hashlib
p=argparse.ArgumentParser()
p.add_argument('--source',required=True);p.add_argument('--plugin',required=True);p.add_argument('--output',required=True)
a=p.parse_args();source=Path(a.source);plugin=Path(a.plugin).resolve(strict=True);out=Path(a.output)
if out.exists():raise SystemExit('Refusing to overwrite '+str(out))
s=source.read_text();needle='filename="gz-sim-sensors-system"'
if s.count(needle)!=1:raise SystemExit('Expected exactly one Sensors plugin')
out.write_text(s.replace(needle,'filename="'+html.escape(str(plugin),quote=True)+'"'))
print('source_sha256',hashlib.sha256(source.read_bytes()).hexdigest())
print('output_sha256',hashlib.sha256(out.read_bytes()).hexdigest())
