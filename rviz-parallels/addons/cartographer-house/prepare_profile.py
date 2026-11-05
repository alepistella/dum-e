#!/usr/bin/env python3
"""Copy the packaged TurtleBot3 Lua config and add one house-specific override."""
import argparse
import hashlib
import json
import re
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path)
    parser.add_argument('--output-dir', type=Path, default=Path.home() /
                        '.local/share/dum-e/cartographer-house')
    args = parser.parse_args()
    if args.source is None:
        args.source = Path('/opt/ros/jazzy/share/turtlebot3_cartographer/config/turtlebot3_lds_2d.lua')
        if args.source.read_text().startswith('-- TurtleBot3 profile overlay;'):
            args.source = Path(str(args.source) + '.distrib')
    source = args.source.read_text()
    returns = list(re.finditer(r'(?m)^return options\s*$', source))
    if len(returns) != 1 or source[returns[0].end():].strip():
        parser.error('Expected one final "return options"; review this source manually.')
    if re.search(r'(?m)^\s*POSE_GRAPH\.optimize_every_n_nodes\s*=\s*0\b', source):
        parser.error('Source disables global optimization; this profile must retain it.')
    if re.search(r'(?m)^\s*POSE_GRAPH\..*linear_search_window\s*=', source):
        parser.error('Source already overrides a search window; review it manually.')
    override = ('-- House-specific loop-closure search; global optimization stays enabled.\n'
                'POSE_GRAPH.constraint_builder.fast_correlative_scan_matcher.'
                'linear_search_window = 1.0\n\n')
    content = source[:returns[0].start()] + override + source[returns[0].start():]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    target = args.output_dir / 'turtlebot3_house_2d.lua'
    if target.exists() and target.read_text() != content:
        parser.error(f'Refusing to overwrite a different profile: {target}')
    target.write_text(content)
    manifest = {
        'source': str(args.source),
        'source_sha256': hashlib.sha256(args.source.read_bytes()).hexdigest(),
        'profile_sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
        'parameter': 'POSE_GRAPH.constraint_builder.fast_correlative_scan_matcher.linear_search_window',
        'value_m': 1.0,
        'scope': 'Experimental TurtleBot3 house profile; validate on independent routes.',
    }
    (args.output_dir / 'profile.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(target)


if __name__ == '__main__':
    main()
