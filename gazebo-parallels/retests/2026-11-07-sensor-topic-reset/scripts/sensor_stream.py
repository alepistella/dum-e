#!/usr/bin/env python3
import sys,json,time,os,signal,threading,math
from pathlib import Path
from gz.transport13 import Node
from gz.msgs10.laserscan_pb2 import LaserScan
from gz.msgs10.image_pb2 import Image
from gz.msgs10.imu_pb2 import IMU
out=Path(sys.argv[1]);rows=json.loads(sys.argv[2]);node=Node();lock=threading.Lock();data={'counts':{},'samples':{}}
def cb(topic):
 def receive(msg):
  with lock:
   data['counts'][topic]=data['counts'].get(topic,0)+1
   if isinstance(msg,LaserScan):
    rr=list(msg.ranges);v=rr[len(rr)//2] if rr else None
    data['samples'][topic]={'count':msg.count,'ranges_count':len(rr),'central_m':v if v is None or math.isfinite(v) else str(v)}
   elif isinstance(msg,Image):data['samples'][topic]={'width':msg.width,'height':msg.height,'bytes':len(msg.data)}
   else:data['samples'][topic]={'angular_velocity':[msg.angular_velocity.x,msg.angular_velocity.y,msg.angular_velocity.z]}
 return receive
for row in rows:
 topic='/'+row['sensor_topic'].lstrip('/')
 cls=LaserScan if row['name'] in ('gpu_lidar','review_lidar') else Image if row['name']=='review_camera' else IMU
 node.subscribe(cls,topic,cb(topic))
while True:
 with lock:text=json.dumps(data)
 tmp=out.with_suffix('.tmp');tmp.write_text(text);os.replace(tmp,out)
 time.sleep(.15)
