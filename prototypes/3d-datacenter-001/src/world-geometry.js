import * as THREE from 'three';
import landSource from './assets/land.geojson?raw';
import { COUNTRIES, FACILITIES } from './world-store.js';

const V=(x,y,z)=>new THREE.Vector3(x,y,z);
const COLORS={normal:0x68dfce,fault:0xff657d,repairing:0xf8be68,awaiting:0x89baff,request:0xf3c37b};
export function createWorldGeometry() {
  const world=new THREE.Group(),campus=new THREE.Group(),pickables={world:[],campus:[]},markers={},buildings={},routes=[];
  const materials={ dark:new THREE.MeshStandardMaterial({color:0x172535,roughness:.66,metalness:.42}), metal:new THREE.MeshStandardMaterial({color:0x506574,roughness:.45,metalness:.65}), roof:new THREE.MeshStandardMaterial({color:0x344a60,roughness:.56,metalness:.52}), road:new THREE.MeshStandardMaterial({color:0x1b2836,roughness:.95}), ground:new THREE.MeshStandardMaterial({color:0x304453,roughness:.82}), glass:new THREE.MeshStandardMaterial({color:0x237789,roughness:.22,metalness:.8}), green:new THREE.MeshStandardMaterial({color:0x204a45,roughness:.9}), light:new THREE.MeshBasicMaterial({color:0x90cfe4,toneMapped:false}), gold:new THREE.MeshBasicMaterial({color:0xc1a46e}), cyan:new THREE.MeshBasicMaterial({color:0x62dacd,toneMapped:false}) };
  const geo=new THREE.BoxGeometry(1,1,1),batches=new Map();
  function box(root,mat,x,y,z,w,h,d,batched=true){
    if(batched){const key=mat.uuid;if(!batches.has(key))batches.set(key,{root,mat,items:[]});batches.get(key).items.push([x,y,z,w,h,d]);return;}
    const mesh=new THREE.Mesh(geo,mat);mesh.position.set(x,y,z);mesh.scale.set(w,h,d);mesh.castShadow=true;mesh.receiveShadow=true;root.add(mesh);return mesh;
  }
  function line(root,points,color=0x3b6479,opacity=1){const mesh=new THREE.Line(new THREE.BufferGeometry().setFromPoints(points),new THREE.LineBasicMaterial({color,transparent:opacity<1,opacity}));root.add(mesh);return mesh;}
  function label(root,text,sub,x,y,z,width=4,color='#afd7e4'){
    const canvas=document.createElement('canvas');canvas.width=768;canvas.height=192;const c=canvas.getContext('2d');
    c.fillStyle='#0c1928dd';c.fillRect(0,0,768,192);c.fillStyle=color;c.fillRect(0,0,5,192);c.font='500 52px Consolas';c.fillText(text,26,78);c.fillStyle='#9aaec0';c.font='27px Consolas';c.fillText(sub,27,137);
    const tex=new THREE.CanvasTexture(canvas);tex.colorSpace=THREE.SRGBColorSpace;const sprite=new THREE.Sprite(new THREE.SpriteMaterial({map:tex,depthTest:false,toneMapped:false}));sprite.position.set(x,y,z);sprite.scale.set(width,width/4,1);root.add(sprite);return sprite;
  }
  function pipe(root,points,mat,radius=.06){const curve=new THREE.CurvePath();for(let i=1;i<points.length;i++)curve.add(new THREE.LineCurve3(V(...points[i-1]),V(...points[i])));root.add(new THREE.Mesh(new THREE.TubeGeometry(curve,40,radius,6,false),mat));return curve;}

  // Natural Earth public-domain land; geography only. All links below are fictional.
  box(world,new THREE.MeshStandardMaterial({color:0x101e30,roughness:.8,metalness:.35}),0,-.3,0,43,.5,23,false);
  const landMaterial=new THREE.MeshStandardMaterial({color:0x29495a,metalness:.34,roughness:.64});
  const land=JSON.parse(landSource);
  for(const feature of land.features){
    const polygons=feature.geometry.type==='MultiPolygon'?feature.geometry.coordinates:[feature.geometry.coordinates];
    for(const polygon of polygons){
      const shape=new THREE.Shape(polygon[0].map(([lon,lat])=>new THREE.Vector2(lon*.11,lat*.11)));
      for(const hole of polygon.slice(1))shape.holes.push(new THREE.Path(hole.map(([lon,lat])=>new THREE.Vector2(lon*.11,lat*.11))));
      const mesh=new THREE.Mesh(new THREE.ExtrudeGeometry(shape,{depth:.16,bevelEnabled:false}),landMaterial);mesh.rotation.x=-Math.PI/2;mesh.position.y=.04;world.add(mesh);
      const contour=polygon[0].map(([lon,lat])=>V(lon*.11,.21,-lat*.11));line(world,contour,0x527f8a,.7);
    }
  }
  for(let x=-19.8;x<=20;x+=3.3)line(world,[V(x,.015,-10),V(x,.015,10)],0x294251,.5);
  for(let z=-9.9;z<=10;z+=3.3)line(world,[V(-20,.015,z),V(20,.015,z)],0x294251,.5);
  line(world,[V(-21.5,.05,-11.5),V(21.5,.05,-11.5),V(21.5,.05,11.5),V(-21.5,.05,11.5),V(-21.5,.05,-11.5)],0x456d81);
  label(world,'GLOBAL / OPERATIONS','VIRTUAL NETWORK · NATURAL EARTH LAND',-14,.8,10,7);
  label(world,'ASIA PACIFIC','ULSAN / SINGAPORE / JAPAN',12,.8,9.4,6);
  const sphereGeo=new THREE.SphereGeometry(.17,16,12),ringGeo=new THREE.TorusGeometry(.44,.025,6,40);
  for(const [id,c] of Object.entries(COUNTRIES)){
    const point=V(c.lon*.11,.42,-c.lat*.11),mat=new THREE.MeshBasicMaterial({color:id==='KR'?0x81f1da:id==='SG'?0xf3c37b:0x7ba7bd,toneMapped:false});
    const node=new THREE.Mesh(sphereGeo,mat);node.position.copy(point);world.add(node);
    const ring=new THREE.Mesh(ringGeo,mat);ring.rotation.x=Math.PI/2;ring.position.copy(point);world.add(ring);
    const proxy=new THREE.Mesh(new THREE.SphereGeometry(.72,10,8),new THREE.MeshBasicMaterial({visible:false}));proxy.position.copy(point);proxy.userData.pickId=`country:${id}`;world.add(proxy);pickables.world.push(proxy);
    const offset=id==='KR'?[1.25,1.6,-1.1]:id==='JP'?[2.3,1.1,1.15]:id==='SG'?[1.7,1.5,1.25]:[1.5,1.5,-1.5];
    label(world,c.short,id==='KR'?'NAM-GU · HWANGSEONG / YONGYEON':id==='SG'?'SG-2026-001 / REQUEST':'NO ACTIVE REQUEST',point.x+offset[0],offset[1],point.z+offset[2],id==='SG'?5:4,id==='SG'?'#f4ca8d':'#b6dbe5');
    markers[id]={node,ring,point};
  }
  for(const id of ['SG','JP','US']){
    const from=markers[id].point,to=markers.KR.point,mid=from.clone().lerp(to,.5);mid.y=id==='US'?5:2.3;
    const curve=new THREE.QuadraticBezierCurve3(from,mid,to),material=new THREE.MeshBasicMaterial({color:id==='SG'?0x70e8d1:0x3d718d,transparent:true,opacity:id==='SG'?.85:.35,toneMapped:false});
    const mesh=new THREE.Mesh(new THREE.TubeGeometry(curve,80,id==='SG'?.035:.018,5,false),material);world.add(mesh);
    const dot=new THREE.Mesh(new THREE.SphereGeometry(.085,8,6),new THREE.MeshBasicMaterial({color:0xe0fff5,toneMapped:false}));world.add(dot);routes.push({id,curve,material,dot});
  }
  // Virtual customer traffic packets on every fictional link (opening + map). Not real cable routes.
  const traffic=[],packetGeo=new THREE.SphereGeometry(.06,6,5),packetMat=new THREE.MeshBasicMaterial({color:0x9ff5e4,toneMapped:false});
  for(const route of routes)for(let k=0;k<5;k++){const dot=new THREE.Mesh(packetGeo,packetMat);world.add(dot);traffic.push({route,dot,offset:k/5+.07});}

  // An original campus model: long compute building, separate power/UPS yard,
  // cooling plant, operations hub, network building and generous maintenance roads.
  box(campus,materials.dark,0,-.5,0,34,.8,24);
  box(campus,materials.ground,0,-.06,0,33.5,.1,23.5);
  box(campus,materials.road,0,.03,8.5,33,.04,3);
  box(campus,materials.road,-5.3,.035,-1.6,2.7,.045,17);
  box(campus,materials.road,6.1,.035,-1.6,2.5,.045,17);
  for(let x=-15;x<16;x+=2)box(campus,materials.gold,x,.068,8.5,.75,.015,.055);
  for(let z=-10;z<7;z+=2)for(const x of[-5.3,6.1])box(campus,materials.gold,x,.068,z,.045,.015,.75);
  for(let x=-15;x<16;x+=2.5){box(campus,materials.metal,x,.8,-11.3,.035,1.6,.035);box(campus,materials.metal,x,.8,11.3,.035,1.6,.035);}
  for(const z of[-11.3,11.3])for(const y of[.45,.9,1.35])box(campus,materials.metal,0,y,z,32,.023,.025);
  const outlines=[];
  for(const [id,f] of Object.entries(FACILITIES)){
    const w=id==='HALL-01'?8.3:id==='NOC'?6:id==='COOLING'?5.5:4.6,d=id==='HALL-01'?12:id==='NOC'?3.1:3.2,h=id==='HALL-01'?2.8:id==='NOC'?2.1:1.9;
    box(campus,materials.dark,f.x,.15,f.z,w+.4,.25,d+.4);
    const body=box(campus,(id==='NOC'?materials.roof:materials.metal).clone(),f.x,h/2+.22,f.z,w,h,d,false);body.userData.pickId=`facility:${id}`;pickables.campus.push(body);
    box(campus,materials.roof,f.x,h+.26,f.z,w+.1,.12,d+.1);
    for(let z=f.z-d/2+.3;z<f.z+d/2;z+=.65)box(campus,materials.dark,f.x,h+.34,z,w-.3,.035,.025);
    const rimMaterial=new THREE.LineBasicMaterial({color:0x6fe7d2});
    const rim=new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(w+.6,.09,d+.6)),rimMaterial);rim.position.set(f.x,.24,f.z);campus.add(rim);outlines.push({id,rim});
    for(let x=f.x-w/2+.45;x<f.x+w/2-.2;x+=.75){
      box(campus,id==='NOC'?materials.glass:materials.dark,x,1.35,f.z+d/2+.025,.48,.7,.04);
      if(id==='NOC')box(campus,materials.light,x,1.08,f.z+d/2+.055,.38,.035,.015);
    }
    box(campus,materials.dark,f.x,.8,f.z+d/2+.04,.7,1.3,.05);
    const name=label(campus,f.code,id==='HALL-01'?'SG-2026-001 / D-06':id==='NOC'?'OPERATIONS CENTER':f.name==='냉각 플랜트'?'THERMAL PLANT':id,f.x,h+1,f.z+d/2,5,id==='HALL-01'?'#8af0d4':'#b1c9d6');
    buildings[id]={body,baseColor:body.material.color.clone(),point:V(f.x,h/2,f.z),rim,name};
    if(id==='HALL-01')for(let row=0;row<2;row++)for(let k=0;k<6;k++){
      const x=f.x-2+row*4,z=f.z-4.8+k*1.8;
      box(campus,materials.dark,x,h+.59,z,1.5,.55,1.2);
      const fan=new THREE.Mesh(new THREE.CylinderGeometry(.42,.42,.05,16),materials.metal);fan.position.set(x,h+.89,z);campus.add(fan);
    }
  }
  // An outdoor auxiliary cooling deck beside the chiller building. Fans, LEDs, the icon and the
  // coolant flow all follow the shared ops.cooling.mode (educational loop, not a thermal model).
  const coolingLed=new THREE.MeshBasicMaterial({color:COLORS.normal,toneMapped:false}),fanRotors=[];
  for(let k=0;k<6;k++){
    const x=8.1+(k%3)*1.9,z=-9.1+Math.floor(k/3)*2;
    box(campus,materials.roof,x,.8,z,1.55,1.5,1.6);
    const fan=new THREE.Mesh(new THREE.CylinderGeometry(.57,.57,.1,20),materials.dark);fan.position.set(x,1.62,z);campus.add(fan);
    const rotor=new THREE.Group();rotor.position.set(x,1.69,z);campus.add(rotor);fanRotors.push(rotor);
    for(let blade=0;blade<3;blade++){const b=new THREE.Mesh(geo,materials.metal);b.scale.set(1,.025,.14);b.rotation.y=blade*Math.PI/3;rotor.add(b);}
    for(const side of[-.65,.65])box(campus,materials.metal,x+side,.8,z,.025,1.4,1.55);
    const led=new THREE.Mesh(geo,coolingLed);led.position.set(x,1.3,z+.81);led.scale.set(1.1,.06,.02);campus.add(led);
  }
  const supply=[];
  for(const dz of[0,.35])supply.push(pipe(campus,[[9,1.2,-6+dz],[5.8,1.2,-6+dz],[5.8,.22,3+dz],[4.3,.22,3+dz]],dz?materials.roof:materials.glass,.1));
  const flowMat=new THREE.MeshBasicMaterial({color:COLORS.normal,toneMapped:false}),flowDots=[];
  for(let k=0;k<10;k++){const dot=new THREE.Mesh(new THREE.SphereGeometry(.11,8,6),flowMat);campus.add(dot);flowDots.push({dot,offset:k/10});}
  const iconCanvas=document.createElement('canvas');iconCanvas.width=512;iconCanvas.height=256;
  const iconTexture=new THREE.CanvasTexture(iconCanvas);iconTexture.colorSpace=THREE.SRGBColorSpace;
  const coolingIcon=new THREE.Sprite(new THREE.SpriteMaterial({map:iconTexture,depthTest:false,toneMapped:false}));coolingIcon.position.set(10,4.6,-4);coolingIcon.scale.set(4,2,1);campus.add(coolingIcon);
  let coolingMode=null,fanAngle=0,flowPhase=0;
  function drawCoolingIcon(mode){
    const c=iconCanvas.getContext('2d'),col=mode==='on'?'#6fe7d2':mode==='warn'?'#ffad5c':'#7d8a96';
    c.clearRect(0,0,512,256);c.fillStyle='#0c1928ee';c.fillRect(0,0,512,256);c.strokeStyle=col;c.lineWidth=6;c.strokeRect(3,3,506,250);
    c.beginPath();c.arc(118,128,82,0,Math.PI*2);c.fillStyle=mode==='off'?'#1b2631':mode==='warn'?'#3a2412':'#10332f';c.fill();c.stroke();
    c.fillStyle=col;c.font='bold 104px "Segoe UI Symbol","Malgun Gothic",sans-serif';c.textAlign='center';c.textBaseline='middle';c.fillText(mode==='warn'?'⚠':'❄',118,134);
    c.textAlign='left';c.font='bold 64px "Malgun Gothic",sans-serif';c.fillText(mode==='on'?'켜짐':mode==='warn'?'경고':'꺼짐',228,104);
    c.font='30px Consolas,"Malgun Gothic",monospace';c.fillStyle='#a9bfcf';c.fillText('AUX COOLING',230,170);c.fillText(mode==='on'?'ON':mode==='warn'?'WARNING':'OFF',230,208);
    iconTexture.needsUpdate=true;
  }
  // A covered, glazed sky-bridge: the control building and the server building are separate buildings.
  box(campus,materials.roof,-5.1,1.65,4,2.3,.12,1.1);box(campus,materials.glass,-5.1,1.3,4,2.2,.62,1);box(campus,materials.dark,-5.1,.95,4,2.3,.1,1.1);
  for(const x of[-5.9,-4.3])box(campus,materials.metal,x,.45,4,.12,.9,.12);
  const bridgeLight=new THREE.Mesh(geo,new THREE.MeshBasicMaterial({color:0x8af0d4,toneMapped:false}));bridgeLight.position.set(-5.1,1.02,4.56);bridgeLight.scale.set(2.2,.04,.03);campus.add(bridgeLight);
  label(campus,'LINK BRIDGE','관제동 ↔ 서버동 01 연결 통로',-5.1,2.6,4.6,3.4,'#8af0d4');

  // Surrounding industrial district: an ORIGINAL low-poly reconstruction inspired by the public
  // description of the Ulsan Mipo national industrial complex (Nam-gu, Hwangseong-dong / Yongyeon).
  // Not a site boundary, not a copy of any rendering or photo.
  const district=new THREE.Group();campus.add(district);
  const dm={ground:new THREE.MeshStandardMaterial({color:0x131d27,roughness:.95}),sea:new THREE.MeshStandardMaterial({color:0x0d2133,roughness:.35,metalness:.55}),
    shed:new THREE.MeshStandardMaterial({color:0x1f2e3c,roughness:.75,metalness:.35}),tank:new THREE.MeshStandardMaterial({color:0x56656f,roughness:.5,metalness:.5}),
    stack:new THREE.MeshStandardMaterial({color:0x44525d,roughness:.6,metalness:.4}),road:new THREE.MeshStandardMaterial({color:0x151f2a,roughness:1}),
    beacon:new THREE.MeshBasicMaterial({color:0xff5a5a,toneMapped:false})};
  box(district,dm.ground,-5,-1.05,0,140,.3,110);box(district,dm.sea,96,-1.2,0,92,.2,130);box(district,materials.metal,50.2,-.95,0,.6,.5,110);
  for(const z of[-17,18,40])box(district,dm.road,-5,-.88,z,140,.04,2.4);
  for(const x of[-28,24,44])box(district,dm.road,x,-.87,0,2.4,.04,110);
  let seed=7;const rnd=()=>((seed=(seed*16807)%2147483647)/2147483647);
  const sheds=[];
  for(const [x0,x1,z0,z1,n] of[[-68,-30,-50,-20,14],[-66,-32,22,52,12],[-20,20,22,52,10],[-20,18,-52,-22,9]])for(let i=0;i<n;i++){
    const w=3+rnd()*6,d=3+rnd()*8,h=1+rnd()*3.5;sheds.push([x0+rnd()*(x1-x0),z0+rnd()*(z1-z0),w,d,h]);}
  for(const [x,z,w,d,h]of sheds){box(district,dm.shed,x,h/2-.85,z,w,h,d);box(district,materials.roof,x,h-.83,z,w+.1,.08,d+.1);}
  const tanks=[];
  for(let i=0;i<3;i++)for(let j=0;j<3;j++)tanks.push([28+i*5.2,-46+j*5.2,2.1,3]);
  for(let i=0;i<4;i++)for(let j=0;j<2;j++)tanks.push([-62+i*3.8,0+j*4,1.5,2.4]);
  const tankMesh=new THREE.InstancedMesh(new THREE.CylinderGeometry(1,1,1,28),dm.tank,tanks.length),m4=new THREE.Matrix4(),q0=new THREE.Quaternion();
  tanks.forEach(([x,z,r,h],i)=>tankMesh.setMatrixAt(i,m4.compose(V(x,h/2-.85,z),q0,V(r,h,r))));tankMesh.receiveShadow=true;district.add(tankMesh);
  for(let i=0;i<8;i++){const x=30+(i%4)*5,z=-20.5+Math.floor(i/4)*1.2;box(district,materials.metal,x,.3,z,4.9,.08,.6);box(district,materials.metal,x-2.4,-.3,z,.1,1.2,.1);}
  // A gas power-plant motif with two stacks and aviation beacons (energy infrastructure of the district).
  box(district,dm.shed,32,1.2,10,12,4.2,7);box(district,materials.roof,32,3.35,10,12.2,.15,7.2);
  const stackMesh=new THREE.InstancedMesh(new THREE.CylinderGeometry(.55,.75,1,16),dm.stack,2),beacons=[];
  [[35.5,8],[38,8]].forEach(([x,z],i)=>{stackMesh.setMatrixAt(i,m4.compose(V(x,6.2,z),q0,V(1,14,1)));const b=new THREE.Mesh(new THREE.SphereGeometry(.22,8,6),dm.beacon);b.position.set(x,13.4,z);district.add(b);beacons.push(b);});district.add(stackMesh);
  for(let i=0;i<3;i++){const z=-30+i*22;box(district,materials.metal,53,4,z,1,8,1);box(district,materials.metal,53,8.2,z+1.5,1,.6,9);}
  label(district,'MIPO INDUSTRIAL COMPLEX','울산미포국가산단 · 남구 황성동·용연 (가상 재구성)',-34,7,-8,12,'#b1c9d6');
  label(district,'ULSAN BAY','바다 · 실제 해안선·부지 경계 아님',70,3,22,8,'#7fa5bd');
  label(campus,'ULSAN AIDC · 2026+','미래 가상 시설 · 실제 조감도 복제 아님',1,5.6,-14,9,'#8af0d4');
  for(let k=0;k<4;k++){
    const x=-14.6+k*.95;
    box(campus,materials.roof,x,.8,2.8,.7,1.5,1.4);box(campus,materials.dark,x,1,3.52,.35,.24,.025);
    for(let vent=0;vent<5;vent++)box(campus,materials.metal,x,.4+vent*.12,3.52,.45,.025,.025);
  }
  pipe(campus,[[-9,.15,-4],[-5.6,.15,-4],[-5.6,.15,-7],[-4.3,.15,-7]],materials.gold,.05);
  const campusLinkMat=new THREE.MeshBasicMaterial({color:0x65d9d0,toneMapped:false});
  pipe(campus,[[9,.15,4],[6.2,.15,4],[6.2,.15,1],[4.3,.15,1]],campusLinkMat,.05);
  for(let x=-14;x<15;x+=2.1){
    box(campus,materials.dark,x,.1,10.4,.035,.025,1.3);
    if(x<-7){box(campus,materials.roof,x,.32,10.3,1,.42,.48);box(campus,materials.glass,x,.6,10.3,.45,.22,.44);}
  }
  // Small trees and perimeter lights keep scale legible without external assets.
  const treeGeo=new THREE.ConeGeometry(.45,1.4,7);
  for(let x=-15;x<16;x+=3){const tree=new THREE.Mesh(treeGeo,materials.green);tree.position.set(x,.95,6.6);campus.add(tree);box(campus,materials.dark,x,.35,6.6,.1,.7,.1);}
  for(const x of[-15.5,15.5])for(const z of[-9,-2,5,10]){box(campus,materials.metal,x,1.8,z,.05,3.5,.05);box(campus,materials.light,x,3.58,z,.35,.05,.15);}
  label(campus,'ULSAN / AIDC','ORIGINAL CAMPUS · DIAGRAM',1,.5,11.7,8);
  for(const b of batches.values()){
    const instance=new THREE.InstancedMesh(geo,b.mat,b.items.length),matrix=new THREE.Matrix4(),q=new THREE.Quaternion();
    b.items.forEach(([x,y,z,w,h,d],i)=>{matrix.compose(V(x,y,z),q,V(w,h,d));instance.setMatrixAt(i,matrix);});instance.castShadow=true;instance.receiveShadow=true;b.root.add(instance);
  }
  function update(time,state){
    const phase=state.request.phase,bad=phase==='fault',repair=phase==='repairing',awaiting=phase==='awaiting',incoming=['new','reviewed'].includes(phase);
    const color=bad?COLORS.fault:repair?COLORS.repairing:awaiting?COLORS.awaiting:COLORS.normal;
    // The SG marker keeps the legend's gold "incoming request" colour until the request is accepted.
    const sgColor=incoming?COLORS.request:color,pulse=incoming||bad?.3:.12;
    for(const r of routes){r.material.color.setHex(r.id==='SG'?sgColor:0x3d718d);r.dot.visible=r.id==='SG'&&!bad&&!repair;r.dot.position.copy(r.curve.getPoint((time*.1)%1));}
    for(const [id,m]of Object.entries(markers)){m.ring.scale.setScalar(1+(id==='SG'?pulse*(.5+.5*Math.sin(time*3)):0));if(id==='SG')m.node.material.color.setHex(sgColor);}
    for(const {id,rim}of outlines){rim.visible=state.navigation.facility===id;rim.material.color.setHex(id==='HALL-01'?color:COLORS.normal);}
    campusLinkMat.color.setHex(color);
    buildings['HALL-01'].body.material.color.copy(buildings['HALL-01'].baseColor);
    if(bad||repair||awaiting)buildings['HALL-01'].body.material.color.lerp(new THREE.Color(color),.3);
    const mode=state.ops.cooling.mode,dt=Math.max(0,Math.min(.1,time-(update.last??time)));update.last=time;
    if(mode!==coolingMode){coolingMode=mode;drawCoolingIcon(mode);const c=mode==='on'?COLORS.normal:mode==='warn'?0xffad5c:0x3a4652;coolingLed.color.setHex(c);flowMat.color.setHex(mode==='warn'?0xffad5c:COLORS.normal);}
    const fanSpeed=mode==='on'?6:mode==='warn'?14:0,flowSpeed=mode==='on'?.12:mode==='warn'?.03:0;
    fanAngle+=fanSpeed*dt;flowPhase+=flowSpeed*dt;for(const r of fanRotors)r.rotation.y=fanAngle;
    for(const {dot,offset}of flowDots){dot.visible=mode!=='off';dot.position.copy(supply[0].getPointAt((flowPhase+offset)%1));}
    if(mode==='warn')coolingLed.color.setHex(Math.sin(time*6)>0?0xffad5c:0x6a3a1a);
    for(const b of beacons)b.visible=Math.sin(time*3)>-.2;
    for(const t of traffic){t.dot.visible=state.request.phase!=='fault'&&state.request.phase!=='repairing'||t.route.id!=='SG';t.dot.position.copy(t.route.curve.getPoint((time*.09+t.offset)%1));}
    coolingVisual={mode,fanSpeed,flowVisible:mode!=='off',icon:mode==='warn'?'warn':mode==='on'?'on':'off',led:'#'+coolingLed.color.getHexString()};
  }
  let coolingVisual=null;
  function project(kind,id,camera,rect){
    const p=kind==='world'?markers[id]?.point:buildings[id]?.point;if(!p)return null;const v=p.clone().project(camera);return {x:rect.left+(v.x+1)/2*rect.width,y:rect.top+(1-v.y)/2*rect.height,visible:v.z>-1&&v.z<1};
  }
  return {world,campus,pickables,update,project,coolingVisual:()=>coolingVisual&&{...coolingVisual},markerColor:id=>markers[id]?.node.material.color.getHexString(),focusPoint:(kind,id)=>(kind==='world'?markers[id]?.point:buildings[id]?.point)?.clone(),pickLabel:id=>{const [kind,key]=id.split(':');return kind==='country'?COUNTRIES[key]?.name:FACILITIES[key]?.name;}};
}
