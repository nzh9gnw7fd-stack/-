import * as THREE from 'three';

/**
 * three.js の 3D サンプル。WASD/矢印で移動、Space でジャンプ、光る玉を集める。
 * 3D モデル（.glb）を使う場合:
 *   import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
 *   new GLTFLoader().load('assets/model.glb', (gltf) => scene.add(gltf.scene));
 */
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.shadowMap.enabled = true;
document.body.appendChild(renderer.domElement);

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x9fd3ff);
scene.fog = new THREE.Fog(0x9fd3ff, 30, 80);
const camera = new THREE.PerspectiveCamera(60, 1, 0.1, 200);

scene.add(new THREE.HemisphereLight(0xffffff, 0x557755, 1.2));
const sun = new THREE.DirectionalLight(0xffffff, 2);
sun.position.set(10, 20, 8);
sun.castShadow = true;
sun.shadow.mapSize.set(2048, 2048);
Object.assign(sun.shadow.camera, { left: -30, right: 30, top: 30, bottom: -30 });
scene.add(sun);

const ARENA = 25;
const ground = new THREE.Mesh(new THREE.PlaneGeometry(ARENA * 2, ARENA * 2), new THREE.MeshStandardMaterial({ color: 0x7cb342 }));
ground.rotation.x = -Math.PI / 2;
ground.receiveShadow = true;
scene.add(ground);

// 障害物（ランダムな箱）
const obstacles: THREE.Box3[] = [];
for (let i = 0; i < 25; i++) {
  const h = 1 + Math.random() * 3;
  const box = new THREE.Mesh(new THREE.BoxGeometry(2, h, 2), new THREE.MeshStandardMaterial({ color: new THREE.Color().setHSL(Math.random(), 0.4, 0.55) }));
  box.position.set((Math.random() - 0.5) * ARENA * 1.8, h / 2, (Math.random() - 0.5) * ARENA * 1.8);
  if (box.position.length() < 4) continue;
  box.castShadow = box.receiveShadow = true;
  scene.add(box);
  obstacles.push(new THREE.Box3().setFromObject(box));
}

const player = new THREE.Mesh(new THREE.CapsuleGeometry(0.5, 0.8, 4, 12), new THREE.MeshStandardMaterial({ color: 0x4fc3f7 }));
player.castShadow = true;
player.position.set(0, 0.9, 0);
scene.add(player);

const gems: THREE.Mesh[] = [];
const gemGeo = new THREE.OctahedronGeometry(0.5);
const gemMat = new THREE.MeshStandardMaterial({ color: 0xffd54f, emissive: 0xff8f00, emissiveIntensity: 0.6 });
function spawnGem(): void {
  const g = new THREE.Mesh(gemGeo, gemMat);
  g.position.set((Math.random() - 0.5) * ARENA * 1.8, 1, (Math.random() - 0.5) * ARENA * 1.8);
  g.castShadow = true;
  scene.add(g);
  gems.push(g);
}
for (let i = 0; i < 10; i++) spawnGem();

const keys = new Set<string>();
addEventListener('keydown', (e) => keys.add(e.code));
addEventListener('keyup', (e) => keys.delete(e.code));
const hud = document.getElementById('hud')!;
let score = 0;
let vy = 0;
let camAngle = 0;

function resize(): void {
  renderer.setSize(innerWidth, innerHeight);
  camera.aspect = innerWidth / innerHeight;
  camera.updateProjectionMatrix();
}
addEventListener('resize', resize);
resize();

const clock = new THREE.Clock();
renderer.setAnimationLoop(() => {
  const dt = Math.min(clock.getDelta(), 0.05);
  // Q/E でカメラ回転、移動はカメラの向きが基準
  if (keys.has('KeyQ')) camAngle += dt * 2;
  if (keys.has('KeyE')) camAngle -= dt * 2;
  const f = (keys.has('KeyW') || keys.has('ArrowUp') ? 1 : 0) - (keys.has('KeyS') || keys.has('ArrowDown') ? 1 : 0);
  const s = (keys.has('KeyD') || keys.has('ArrowRight') ? 1 : 0) - (keys.has('KeyA') || keys.has('ArrowLeft') ? 1 : 0);
  const move = new THREE.Vector3(s, 0, -f);
  if (move.lengthSq() > 0) {
    move.normalize().applyAxisAngle(new THREE.Vector3(0, 1, 0), camAngle).multiplyScalar(8 * dt);
    const prev = player.position.clone();
    player.position.add(move);
    player.position.clampScalar(-ARENA + 1, ARENA - 1);
    const pBox = new THREE.Box3().setFromCenterAndSize(player.position, new THREE.Vector3(1, 1.8, 1));
    if (obstacles.some((o) => o.intersectsBox(pBox))) player.position.copy(prev); // 当たったら戻す
    player.rotation.y = Math.atan2(move.x, move.z);
  }
  // ジャンプと重力
  if (keys.has('Space') && player.position.y <= 0.9) vy = 7;
  vy -= 20 * dt;
  player.position.y = Math.max(0.9, player.position.y + vy * dt);

  for (let i = gems.length - 1; i >= 0; i--) {
    const g = gems[i];
    g.rotation.y += dt * 2;
    g.position.y = 1 + Math.sin(clock.elapsedTime * 3 + i) * 0.2;
    if (g.position.distanceTo(player.position) < 1.2) {
      scene.remove(g);
      gems.splice(i, 1);
      score++;
      spawnGem();
    }
  }
  hud.textContent = `SCORE ${score}　移動: WASD/矢印　ジャンプ: Space　カメラ: Q/E`;

  // カメラはプレイヤーの後ろから追いかける
  const offset = new THREE.Vector3(0, 7, 11).applyAxisAngle(new THREE.Vector3(0, 1, 0), camAngle);
  camera.position.lerp(player.position.clone().add(offset), 0.1);
  camera.lookAt(player.position);
  renderer.render(scene, camera);
});
