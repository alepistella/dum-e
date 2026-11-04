#!/usr/bin/env python3
"""Install, inspect or restore the RViz-only private Mesa profile."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess

ROOT = Path('/usr/local/lib/rviz-virgl-defaults')
MANIFEST = ROOT / 'manifest.json'
HELPER = Path('/usr/local/sbin/rviz-virgl-defaults-rollback')
MESA = Path('/usr/local/lib/gazebo-virgl-defaults/runtime-v2/mesa')
TARGETS = [Path('/opt/ros/jazzy/bin/rviz2'),
           Path('/opt/ros/jazzy/lib/rviz2/rviz2')]
EXPECTED_SHA = '8c1b6d120d0bb89d546350d8ed031b2c3df7d15b4f4f8373f7a67310a0e74261'
EXPECTED_VERSION = '14.1.24-1noble.20260916.104902'
EXPECTED_MESA = {
    'libGLX_mesa.so.0': '9828f9a41457439055768f84b3598f2fc458bb7765da1dbf84569aaa2a441e9f',
    'dri/virtio_gpu_dri.so': 'b854f45f32e53468b2bb1631771de22a701c07c644d80dcd8209ed478838270d',
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(*args):
    return subprocess.run(args, check=True, text=True, stdout=subprocess.PIPE).stdout.strip()


def diversion(path):
    return run('dpkg-divert', '--list', str(path))


def check_fresh():
    if platform.machine() not in ('aarch64', 'arm64'):
        raise RuntimeError('Only Ubuntu ARM64 is validated.')
    release = Path('/etc/os-release').read_text()
    if 'ID=ubuntu\n' not in release or 'VERSION_ID="24.04"' not in release:
        raise RuntimeError('Only Ubuntu 24.04 is validated.')
    version = run('dpkg-query', '-W', '-f=${Version}', 'ros-jazzy-rviz2')
    if version != EXPECTED_VERSION:
        raise RuntimeError(f'Untested RViz package: {version}; do not bypass the gate.')
    if ROOT.exists() or HELPER.exists():
        raise RuntimeError('An RViz profile already exists; inspect it before reinstalling.')
    for name in ('libGLX_mesa.so.0', 'dri/virtio_gpu_dri.so'):
        if not (MESA / name).is_file():
            raise RuntimeError(f'Install the Gazebo private runtime first: missing {name}')
        if digest(MESA / name) != EXPECTED_MESA[name]:
            raise RuntimeError(f'Untested private Mesa file: {name}; do not bypass the gate.')
    for path in TARGETS:
        if path.is_symlink() or not path.is_file() or digest(path) != EXPECTED_SHA:
            raise RuntimeError(f'Untested RViz entry point: {path}')
        if diversion(path) or Path(str(path) + '.distrib').exists():
            raise RuntimeError(f'Existing diversion or saved binary: {path}')
    return version


def restore():
    data = json.loads(MANIFEST.read_text())
    for entry in data['entries']:
        path = Path(entry['path'])
        saved = Path(entry['diverted_to'])
        if run('dpkg-divert', '--truename', str(path)) != str(saved):
            raise RuntimeError(f'Diversion changed: {path}')
        if not saved.is_file() or digest(path) != data['wrapper_sha256']:
            raise RuntimeError(f'Missing original or edited wrapper: {path}')
    if os.geteuid() != 0:
        raise RuntimeError('Rollback needs sudo.')
    for entry in reversed(data['entries']):
        path = Path(entry['path'])
        # Keep the wrapper while dpkg restores the CURRENT packaged binary.
        retained = ROOT / (path.parent.name + '-removed-wrapper')
        shutil.copy2(path, retained)
        path.unlink()
        try:
            run('dpkg-divert', '--local', '--remove', '--rename',
                '--divert', entry['diverted_to'], str(path))
        except Exception:
            shutil.copy2(retained, path)
            raise
    data['rolled_back_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    (ROOT / 'manifest.rolled-back.json').write_text(json.dumps(data, indent=2) + '\n')
    MANIFEST.unlink()
    archive = ROOT.with_name(ROOT.name + '.rolled-back-' +
                             datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    if HELPER.exists():
        HELPER.replace(ROOT / 'rollback-command.sh')
    ROOT.rename(archive)
    print(f'Original RViz entry points restored. Restart RViz. Archive: {archive}')


def install():
    version = check_fresh()
    if os.geteuid() != 0:
        raise RuntimeError('Installation needs sudo.')
    kit = Path(__file__).resolve().parent
    wrapper = kit / 'rviz2-wrapper.sh'
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup = Path('/var/backups/rviz-virgl-defaults') / stamp
    backup.mkdir(parents=True, exist_ok=False)
    entries = []
    for index, path in enumerate(TARGETS):
        shutil.copy2(path, backup / f'rviz2-{index}')
        entries.append({'path': str(path), 'diverted_to': str(path) + '.distrib',
                        'original_sha256': digest(path)})
    data = {'installed_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'rviz_package': version, 'mesa_directory': str(MESA),
            'backup_directory': str(backup), 'entries': entries,
            'wrapper_sha256': digest(wrapper),
            'runtime_sha256': {name: digest(MESA / name) for name in
                               ('libGLX_mesa.so.0', 'dri/virtio_gpu_dri.so')}}
    completed = []
    try:
        ROOT.mkdir(parents=True, exist_ok=False)
        for name in ('manage.py', 'rviz2-wrapper.sh'):
            shutil.copy2(kit / name, ROOT / name)
            (ROOT / name).chmod(0o755)
        for entry in entries:
            run('dpkg-divert', '--local', '--add', '--rename', '--divert',
                entry['diverted_to'], entry['path'])
            completed.append(entry)
            path = Path(entry['path'])
            temporary = path.with_name(path.name + '.rviz-virgl-new')
            shutil.copy2(wrapper, temporary)
            temporary.chmod(0o755)
            temporary.replace(path)
        MANIFEST.write_text(json.dumps(data, indent=2) + '\n')
        shutil.copy2(MANIFEST, backup / 'manifest.json')
        HELPER.write_text('#!/bin/sh\nexec python3 /usr/local/lib/rviz-virgl-defaults/manage.py --rollback\n')
        HELPER.chmod(0o755)
    except Exception:
        for entry in reversed(completed):
            Path(entry['path']).unlink(missing_ok=True)
            run('dpkg-divert', '--local', '--remove', '--rename', '--divert',
                entry['diverted_to'], entry['path'])
        if ROOT.exists():
            shutil.rmtree(ROOT)
        HELPER.unlink(missing_ok=True)
        raise
    print(f'RViz profile installed. Backup: {backup}')
    print('Use rviz2, ros2 run rviz2 rviz2, or normal ros2 launch commands.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--check', action='store_true', help='read-only preflight (default)')
    modes.add_argument('--install', action='store_true')
    modes.add_argument('--rollback', action='store_true')
    modes.add_argument('--status', action='store_true')
    args = parser.parse_args()
    try:
        if args.rollback:
            restore()
        elif args.install:
            install()
        elif args.status:
            print(MANIFEST.read_text() if MANIFEST.exists() else 'RViz profile is not active.')
        else:
            check_fresh()
            print('Preflight passed. No changes made. Two RViz entry points will use private Mesa.')
    except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        raise SystemExit(f'STOP: {exc}') from exc


if __name__ == '__main__':
    main()
