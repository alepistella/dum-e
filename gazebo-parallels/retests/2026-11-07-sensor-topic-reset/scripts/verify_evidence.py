#!/usr/bin/env python3
"""Check the published evidence; does not start Gazebo or contact a VM."""
from pathlib import Path
import json,tarfile
root=Path(__file__).resolve().parents[1]
s=json.loads((root/'evidence/summary.json').read_text())
assert s['valid_cases']==6 and s['accepted_resets']==18
assert (root/'evidence/profile-fingerprint.before.txt').read_bytes()==(root/'evidence/profile-fingerprint.after.txt').read_bytes()
with tarfile.open(root/'evidence/raw-ecm-and-logs.tar.gz') as t:
 for row in s['cases']:
  name=row['case'];j=json.loads(t.extractfile(name+'.json').read())
  assert j['status']=='completed'
  before={e['entity']:e['sensor_topic'] for e in j['snapshots'][0]['sensors']}
  assert len(before)==(2 if 'official' in name else 3) and all(before.values())
  resets=[x for x in j['snapshots'] if x['tag'].startswith('after_reset_')]
  assert len(resets)==3 and all(x['transport_ok'] and x['accepted'] for x in j['resets'])
  preserved=all({e['entity']:e['sensor_topic'] for e in x['sensors']}==before for x in resets)
  assert preserved==row['expected_corrective_patch']==row['metadata_preserved_all_resets']
  code=int(t.extractfile(name+'.check-exit').read())
  assert code==(0 if preserved else 1)
  paths={line.split()[-1] for line in t.extractfile(name+'-loaded-libraries.txt').read().decode().splitlines() if 'gz-sim8-rendering.so' in line or 'gz-sim8-sensors-system.so' in line}
  overlays=[p for p in paths if '/tmp/independent-pr4082-review' in p]
  assert len(overlays)==(2 if preserved else 0)
  start=j['snapshots'][1]['messages'];end=j['snapshots'][-1]['messages']
  assert start and all(end.get(k,0)>v for k,v in start.items())
  print(name+': '+('metadata preserved' if preserved else 'defect reproduced'))
print('Six valid cases, 18 accepted resets; evidence checks passed.')
