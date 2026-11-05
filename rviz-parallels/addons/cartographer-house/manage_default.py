#!/usr/bin/env python3
"""Manage the tested TurtleBot3 default Lua overlay, with dpkg-divert rollback."""
import argparse
import datetime
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

TARGET = Path('/opt/ros/jazzy/share/turtlebot3_cartographer/config/turtlebot3_lds_2d.lua')
ORIGINAL = Path(str(TARGET) + '.distrib')
STATE = Path('/usr/local/share/dum-e/cartographer-house')
MANIFEST = STATE / 'manifest.json'
PACKAGE = 'ros-jazzy-turtlebot3-cartographer'
VERSION = '2.3.6-1noble.20260921.052917'
SOURCE_SHA = '5e9619c353726157b30dd0e3fdbc6dc1fd134494f19ab2560979af309030de4b'
WRAPPER = ('-- TurtleBot3 profile overlay; packaged settings remain in .distrib.\n'
           'include "turtlebot3_lds_2d.lua.distrib"\n'
           'POSE_GRAPH.constraint_builder.fast_correlative_scan_matcher.linear_search_window = 1.0\n'
           'return options\n').encode()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command(*args):
    return subprocess.check_output(args, text=True).strip()


def atomic_write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        handle.write(content)
        name = handle.name
    os.chmod(name, 0o644)
    os.replace(name, path)


def status():
    manifest = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}
    return {
        'manifest': manifest,
        'diversion': command('dpkg-divert', '--list', str(TARGET)),
        'overlay_matches': TARGET.exists() and TARGET.read_bytes() == WRAPPER,
        'packaged_source_sha256': digest(ORIGINAL) if ORIGINAL.exists() else None,
        'packaged_source_changed_since_validation': ORIGINAL.exists() and digest(ORIGINAL) != SOURCE_SHA,
    }


def install():
    current = status()
    if current['manifest'].get('active'):
        if not current['overlay_matches'] or command('dpkg-divert', '--truename', str(TARGET)) != str(ORIGINAL):
            raise RuntimeError('Existing installation differs from the manifest; inspect it first.')
        print(json.dumps(current, indent=2))
        return
    version = command('dpkg-query', '-W', '-f=${Version}', PACKAGE)
    if version != VERSION or TARGET.is_symlink() or digest(TARGET) != SOURCE_SHA:
        raise RuntimeError('Untested package version or source hash; revalidate before installation.')
    if current['diversion'] or ORIGINAL.exists():
        raise RuntimeError('An existing diversion or .distrib file must be reviewed first.')
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    backup = Path('/var/backups/dum-e-cartographer-house') / stamp
    backup.mkdir(parents=True, mode=0o755)
    shutil.copy2(TARGET, backup / TARGET.name)
    command('dpkg-divert', '--local', '--add', '--rename', '--divert', str(ORIGINAL), str(TARGET))
    try:
        atomic_write(TARGET, WRAPPER)
        manifest = {'active': True, 'installed_at_utc': stamp, 'package': PACKAGE,
                    'validated_version': version, 'source_sha256': SOURCE_SHA,
                    'wrapper_sha256': hashlib.sha256(WRAPPER).hexdigest(),
                    'backup': str(backup), 'scope': 'TurtleBot3 default 2D profile only',
                    'linear_search_window_m': 1.0}
        atomic_write(MANIFEST, (json.dumps(manifest, indent=2) + '\n').encode())
        helper = STATE / 'manage_default.py'
        if Path(__file__).resolve() != helper.resolve():
            atomic_write(helper, Path(__file__).read_bytes())
    except Exception:
        if TARGET.exists() and TARGET.read_bytes() == WRAPPER:
            TARGET.unlink()
        command('dpkg-divert', '--local', '--remove', '--rename', '--divert', str(ORIGINAL), str(TARGET))
        raise
    print(json.dumps(status(), indent=2))


def rollback():
    current = status()
    if not current['manifest'].get('active'):
        raise RuntimeError('No active installation recorded.')
    if (not current['overlay_matches'] or not ORIGINAL.is_file()
            or command('dpkg-divert', '--truename', str(TARGET)) != str(ORIGINAL)):
        raise RuntimeError('Files or diversion changed; refusing an unsafe rollback.')
    TARGET.unlink()
    try:
        command('dpkg-divert', '--local', '--remove', '--rename', '--divert', str(ORIGINAL), str(TARGET))
    except Exception:
        if not TARGET.exists():
            atomic_write(TARGET, WRAPPER)
        raise
    manifest = current['manifest']
    manifest['active'] = False
    manifest['rolled_back_at_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    manifest['restored_sha256'] = digest(TARGET)
    atomic_write(MANIFEST, (json.dumps(manifest, indent=2) + '\n').encode())
    print(json.dumps({'active': False, 'restored_sha256': digest(TARGET)}, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['status', 'install', 'rollback'])
    args = parser.parse_args()
    if args.action != 'status' and os.geteuid() != 0:
        parser.error('Use sudo for install or rollback.')
    if args.action == 'status':
        print(json.dumps(status(), indent=2))
    else:
        {'install': install, 'rollback': rollback}[args.action]()


if __name__ == '__main__':
    main()
