#!/usr/bin/env python3
"""Isolated gz-sim SensorTopic reset probe. No changes to installed packages."""
import argparse,os,sys,json,time,signal,subprocess,pathlib,threading,hashlib
from gz.transport13 import Node
from gz.msgs10.empty_pb2 import Empty
from gz.msgs10.serialized_map_pb2 import SerializedStepMap
from gz.msgs10.stringmsg_v_pb2 import StringMsg_V
from gz.msgs10.world_control_pb2 import WorldControl
from gz.msgs10.boolean_pb2 import Boolean
from gz.msgs10.laserscan_pb2 import LaserScan
from gz.msgs10.image_pb2 import Image
from gz.msgs10.imu_pb2 import IMU
NAME=17448053894352336366
TOPIC=13120067500290942462
p=argparse.ArgumentParser();p.add_argument('--expected-count',type=int,default=3);p.add_argument('--world',required=True);p.add_argument('--label',required=True);p.add_argument('--engine',required=True);p.add_argument('--software',action='store_true');p.add_argument('--private-mesa',action='store_true');p.add_argument('--mode',default='all',choices=['all','time_only','model_only']);p.add_argument('--gz',nargs='+',default=['gz']);p.add_argument('--expect-preserved',action='store_true');p.add_argument('--resets',type=int,default=3);p.add_argument('--out',required=True)
a=p.parse_args();out=pathlib.Path(a.out);out.mkdir(parents=True,exist_ok=True)
os.environ['GZ_PARTITION']='independent_sensortopic_'+str(os.getpid())+'_'+a.label
os.environ['DISPLAY']=os.environ.get('DISPLAY') or ':0';os.environ['XAUTHORITY']=os.environ.get('XAUTHORITY') or '/run/user/1000/gdm/Xauthority'
for k in ['LD_PRELOAD','GZ_VIRGL_RENDER_ENGINE','LIBGL_DRIVERS_PATH','MESA_GL_VERSION_OVERRIDE','MESA_GLSL_VERSION_OVERRIDE','LIBGL_ALWAYS_SOFTWARE','GALLIUM_DRIVER']:
 os.environ.pop(k,None)
if a.software:os.environ['LIBGL_ALWAYS_SOFTWARE']='1'
if a.private_mesa:
 mesa='/usr/local/lib/gazebo-virgl-defaults/runtime-v2/mesa'
 os.environ['LD_LIBRARY_PATH']=mesa+':'+os.environ.get('LD_LIBRARY_PATH','')
 os.environ['LIBGL_DRIVERS_PATH']=mesa+'/dri'
cmd=a.gz+['sim','-s','-r','-v','4',a.world,'--render-engine',a.engine,'--render-engine-api-backend','opengl']
result={'label':a.label,'partition':os.environ['GZ_PARTITION'],'utc_start':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'command':cmd,'engine_sha256':hashlib.sha256(pathlib.Path(a.engine).resolve().read_bytes()).hexdigest() if pathlib.Path(a.engine).is_file() else None,'software':a.software,'private_mesa':a.private_mesa,'mode':a.mode,'snapshots':[]}
log=(out/(a.label+'-server.log')).open('w');proc=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
node=Node();counts={};samples={};stream=None;phase={"name":"before"};saved_images=set()

try:
 deadline=time.monotonic()+20;world=None
 while time.monotonic()<deadline:
  if proc.poll() is not None:raise RuntimeError('server exited '+str(proc.returncode))
  ok,w=node.request('/gazebo/worlds',Empty(),Empty,StringMsg_V,1000)
  if ok and w.data:world=w.data[0];break
  time.sleep(.3)
 if not world:raise RuntimeError('world discovery failed')
 result['world']=world
 def snapshot(tag):
  ok=False
  for attempt in range(4):
   ok,state=node.request('/world/'+world+'/state',Empty(),Empty,SerializedStepMap,2000)
   if ok:break
   time.sleep(.5)
  if not ok:raise RuntimeError('state request failed after retries')
  (out/(a.label+'-'+tag+'.pb')).write_bytes(state.SerializeToString())
  rows=[]
  for eid,e in state.state.entities.items():
   comps={c.type:c.component for c in e.components.values()}
   name=comps.get(NAME,b'').decode(errors='replace')
   if name in ['gpu_lidar','ms200','spycam','imu','review_lidar','review_camera','review_imu']:
    rows.append({'entity':eid,'name':name,'sensor_topic':comps.get(TOPIC,b'').decode() if TOPIC in comps else None,'component_ids':sorted(comps)})
  streamfile=out/(a.label+'-stream.json')
  if streamfile.exists():
   metrics=json.loads(streamfile.read_text());counts.update(metrics['counts']);samples.update(metrics['samples'])
  snap={'tag':tag,'sensors':rows,'wall_monotonic':time.monotonic(),'messages':dict(counts),'latest_samples':dict(samples)}
  result['snapshots'].append(snap);print(json.dumps({k:v for k,v in snap.items() if k!='latest_samples'}),flush=True)
  return rows
 # Wait for metadata, not only service availability.
 rows=[]
 while time.monotonic()<deadline:
  ok,st=node.request('/world/'+world+'/state',Empty(),Empty,SerializedStepMap,1000)
  if ok and sum(any(c.type==TOPIC for c in e.components.values()) for e in st.state.entities.values())>=a.expected_count:break
  time.sleep(.25)
 time.sleep(3)
 rows=snapshot('before')
 if len(rows)!=a.expected_count or any(row['sensor_topic'] is None for row in rows):raise RuntimeError('initial sensors incomplete')
 stream=subprocess.Popen([sys.executable,str(pathlib.Path(__file__).with_name('sensor_stream.py')),str(out/(a.label+'-stream.json')),json.dumps(rows)],start_new_session=True)
 time.sleep(1)
 snapshot('pre_reset_stream')
 for n in range(1,a.resets+1):
  req=WorldControl();setattr(req.reset,a.mode,True)
  ok,rep=node.request('/world/'+world+'/control',req,WorldControl,Boolean,5000)
  result.setdefault('resets',[]).append({'n':n,'transport_ok':ok,'accepted':bool(rep.data)})
  if not(ok and rep.data):raise RuntimeError('reset rejected')
  phase['name']='after_reset_'+str(n)
  time.sleep(1.5);snapshot('after_reset_'+str(n))
 time.sleep(1.5);snapshot('settled')
 maps=[]
 for f in pathlib.Path('/proc').iterdir():
  if not f.name.isdigit():continue
  try:
   env=(f/'environ').read_bytes()
   if ('GZ_PARTITION='+os.environ['GZ_PARTITION']).encode() in env:
    for line in (f/'maps').read_text().splitlines():
     if any(x in line for x in ['gz-sim','gz-rendering','dri.so','libGLX_mesa','libgazebo_virgl','libgallium']):maps.append(f.name+' '+line)
  except (PermissionError,FileNotFoundError,ProcessLookupError):pass
 (out/(a.label+'-loaded-libraries.txt')).write_text('\n'.join(sorted(set(maps))))
 result['status']='completed'
except Exception as exc:
 result['status']='error';result['error']=repr(exc);print(repr(exc),file=sys.stderr)
finally:
 if stream is not None and stream.poll() is None:
  os.killpg(stream.pid,signal.SIGTERM);stream.wait(timeout=5)
 os.killpg(proc.pid,signal.SIGINT) if proc.poll() is None else None
 try:proc.wait(timeout=6)
 except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait()
 log.close();result['exit_code']=proc.returncode
 (out/(a.label+'.json')).write_text(json.dumps(result,indent=2))
 print(json.dumps({'label':a.label,'status':result['status'],'out':str(out)}),flush=True)

if result['status']!='completed':sys.exit(2)
if a.expect_preserved:
 before={e['entity']:e['sensor_topic'] for e in result['snapshots'][0]['sensors']}
 failed=any({e['entity']:e['sensor_topic'] for e in s['sensors']}!=before for s in result['snapshots'] if s['tag'].startswith('after_reset'))
 sys.exit(1 if failed else 0)
