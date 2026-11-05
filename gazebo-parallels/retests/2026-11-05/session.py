#!/usr/bin/env python3
"""Isolated launches; invoke after sourcing Jazzy. No system configuration edits."""
import hashlib,json,os,signal,subprocess,sys,shutil
from pathlib import Path
root = Path('/tmp/parallels-2710-retest')
root.mkdir(exist_ok=True)
state = root / 'processes.json'
procs = json.loads(state.read_text()) if state.exists() else {}

def save():
    state.write_text(json.dumps(procs,indent=2)+'\n')

def clean_env():
    env = os.environ.copy()
    for key in list(env):
        if key.startswith(('LIBGL_', 'MESA_', 'GALLIUM_')) or key in ('LD_PRELOAD', 'GZ_VIRGL_RENDER_ENGINE'):
            env.pop(key,None)
    env['LD_LIBRARY_PATH'] = ':'.join(p for p in env.get('LD_LIBRARY_PATH','').split(':') if 'gazebo-virgl-defaults' not in p)
    env.update(DISPLAY=':0', XAUTHORITY='/run/user/1000/gdm/Xauthority',
               QT_QPA_PLATFORM='xcb', DBUS_SESSION_BUS_ADDRESS='unix:path=/run/user/1000/bus',
               ROS_DOMAIN_ID='86', GZ_PARTITION='parallels_2710_retest')
    return env

def start(name,args,env):
    case = root/name;case.mkdir(exist_ok=True)
    log = open(case/'console.log','w')
    p = subprocess.Popen(args,env=env,cwd=case,stdout=log,stderr=subprocess.STDOUT,
                         stdin=subprocess.DEVNULL,start_new_session=True)
    procs[name]={'pid':p.pid,'args':args};save()
    print(json.dumps({'case':name,'pid':p.pid,'args':args}))

mode = sys.argv[1]
if mode == 'snapshot':
    paths = ['/opt/ros/jazzy/opt/gz_tools_vendor/bin/gz',
             '/opt/ros/jazzy/opt/gz_tools_vendor/bin/gz.vendor',
             '/opt/ros/jazzy/lib/ros_gz_sim/gzserver',
             '/opt/ros/jazzy/lib/ros_gz_sim/gzserver.vendor',
             '/opt/ros/jazzy/bin/rviz2','/opt/ros/jazzy/bin/rviz2.distrib',
             '/opt/ros/jazzy/lib/rviz2/rviz2','/opt/ros/jazzy/lib/rviz2/rviz2.distrib',
             '/usr/local/share/gazebo-virgl-defaults/manifest.json',
             '/usr/local/lib/rviz-virgl-defaults/manifest.json',
             '/usr/local/lib/rviz-virgl-defaults/manage.py',
             '/usr/local/lib/gazebo-virgl-defaults/profile.rb',
             '/usr/local/lib/gazebo-virgl-defaults/runtime-v2/profile.rb',
             '/usr/local/lib/gazebo-virgl-defaults/runtime-v2/libgazebo_virgl_defaults.so',
             '/usr/local/lib/gazebo-virgl-defaults/runtime-v2/engine/libgz-rendering-ogre.so',
             '/usr/local/lib/gazebo-virgl-defaults/runtime-v2/mesa/libGLX_mesa.so.0',
             '/usr/local/lib/gazebo-virgl-defaults/runtime-v2/mesa/dri/virtio_gpu_dri.so',
             str(Path.home()/'.gz/sim/8/gui.config'),str(Path.home()/'.gz/sim/8/server.config')]
    data={}
    for name in paths:
        p=Path(name)
        if p.exists():
            data[name]={'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
                        'mode':oct(p.stat().st_mode & 0o777),'symlink':os.readlink(p) if p.is_symlink() else None}
            if p.stat().st_size<100000:
                dest=root/'backup'/name.lstrip('/');dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
    data['dpkg_divert']=subprocess.check_output(['dpkg-divert','--list'],text=True)
    (root/'before.json').write_text(json.dumps(data,indent=2)+'\n')
    print('State recorded; no installed files modified.')
elif mode == 'check-state':
    before=json.loads((root/'before.json').read_text());changed=[]
    for name,record in before.items():
        if name=='dpkg_divert':continue
        p=Path(name)
        if not p.exists() or hashlib.sha256(p.read_bytes()).hexdigest()!=record['sha256'] or oct(p.stat().st_mode & 0o777)!=record['mode']:
            changed.append(name)
    if subprocess.check_output(['dpkg-divert','--list'],text=True)!=before['dpkg_divert']:changed.append('dpkg diversions')
    print(json.dumps({'changed_files':changed,'configuration_matches_before':not changed}))
    sys.exit(bool(changed))
elif mode == 'stop':
    for name in sys.argv[2:]:
        rec=procs.get(name)
        if rec:
            pid=rec['pid']
            try:
                cmd=Path(f'/proc/{pid}/cmdline').read_bytes()
                # PID reuse must not stop an unrelated process.
                if b'gz' in cmd or b'rviz' in cmd or b'map_fixture.py' in cmd:
                    os.killpg(pid,signal.SIGINT)
            except (FileNotFoundError,ProcessLookupError):pass
            procs.pop(name,None)
    save();print('Requested test processes stopped.')
else:
    env=clean_env()
    if mode=='fixture':start(mode,['python3',str(root/'map_fixture.py')],env)
    elif mode.startswith('rviz-'):
        stock=mode=='rviz-stock'
        env['RVIZ_VIRGL_DEFAULTS']='0' if stock else '1'
        exe='/opt/ros/jazzy/lib/rviz2/rviz2.distrib' if stock else '/opt/ros/jazzy/lib/rviz2/rviz2'
        start(mode,[exe,'-l','-t','RViz STOCK Mesa25' if stock else 'RViz RESTORED Mesa24',
                    '-d',str(root/'map.rviz'),'--ros-args','-p','use_sim_time:=false'],env)
    elif mode.startswith('gazebo-'):
        stock=mode=='gazebo-stock'
        env['GZ_VIRGL_DEFAULTS']='0' if stock else '1'
        config=root/('stock-gui.config' if stock else 'profile-gui.config')
        args=['/opt/ros/jazzy/opt/gz_tools_vendor/bin/gz','sim','-r','shapes.sdf','-v','4','--gui-config',str(config)]
        if stock:args+=['--render-engine','ogre2']
        start(mode,args,env)
    else:raise SystemExit('Unknown mode')
