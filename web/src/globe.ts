import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { latLonToXYZ } from "./geo";
import { ResourceLedger } from "./resources";
import { clusterStyle, SHAPES } from "./rows";
import type { SelectionController } from "./selection";
import type { Row } from "./types";

export interface GlobeHandle {
  readonly ledger: ResourceLedger;
  setSelected(id: string | null, focus: boolean): void;
  /** Viewport position of a marker if it is on the visible hemisphere (used by browser checks). */
  screenPosition(id: string): { x: number; y: number } | null;
  dispose(): void;
}

export type GlobeResult = { ok: true; handle: GlobeHandle } | { ok: false; reason: string };

const MARKER_RADIUS = 1.012;

function markerSize(magnitude: number | null): number {
  // Magnitude is only a size cue; missing magnitude gets the smallest size.
  if (magnitude === null) return 0.011;
  return Math.min(0.03, Math.max(0.011, 0.011 + (magnitude - 4.5) * 0.0075));
}

export function createGlobe(
  container: HTMLElement,
  rows: readonly Row[],
  controller: SelectionController,
  options: { forceNoWebGL: boolean; onContextLost: () => void },
): GlobeResult {
  const ledger = new ResourceLedger();
  let renderer: THREE.WebGLRenderer;
  try {
    if (options.forceNoWebGL) throw new Error("WebGL disabled by ?webgl=off (test switch)");
    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: "low-power" });
    if (!renderer.getContext()) throw new Error("no WebGL context");
  } catch (err) {
    return { ok: false, reason: err instanceof Error ? err.message : String(err) };
  }

  const canvas = renderer.domElement;
  canvas.setAttribute("aria-hidden", "true"); // the table and inspector carry the accessible content
  container.appendChild(canvas);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(40, 1, 0.1, 50);
  camera.position.set(0, 0.4, 3.3);

  const controls = new OrbitControls(camera, canvas);
  controls.enablePan = false;
  controls.minDistance = 1.6;
  controls.maxDistance = 6;
  controls.rotateSpeed = 0.6;

  // Sphere and graticule (no coastlines, no tiles, no network).
  const sphereGeo = ledger.track(new THREE.SphereGeometry(1, 64, 48), "sphere geometry");
  const sphereMat = ledger.track(new THREE.MeshBasicMaterial({ color: 0x17324d }), "sphere material");
  const sphere = new THREE.Mesh(sphereGeo, sphereMat);
  scene.add(sphere);

  const linePositions: number[] = [];
  const segments = 96;
  for (let lat = -60; lat <= 60; lat += 30) {
    for (let i = 0; i < segments; i++) {
      linePositions.push(...latLonToXYZ(lat, (i / segments) * 360 - 180, 1.002));
      linePositions.push(...latLonToXYZ(lat, ((i + 1) / segments) * 360 - 180, 1.002));
    }
  }
  for (let lon = -180; lon < 180; lon += 30) {
    for (let i = 0; i < segments / 2; i++) {
      linePositions.push(...latLonToXYZ(-90 + (i / (segments / 2)) * 180, lon, 1.002));
      linePositions.push(...latLonToXYZ(-90 + ((i + 1) / (segments / 2)) * 180, lon, 1.002));
    }
  }
  const gratGeo = ledger.track(new THREE.BufferGeometry(), "graticule geometry");
  gratGeo.setAttribute("position", new THREE.Float32BufferAttribute(linePositions, 3));
  const gratMat = ledger.track(new THREE.LineBasicMaterial({ color: 0x4f7ba3, transparent: true, opacity: 0.55 }), "graticule material");
  scene.add(new THREE.LineSegments(gratGeo, gratMat));

  // Markers: one InstancedMesh per shape (circle, diamond, square, noise triangle).
  const shapeGeos: Record<string, THREE.BufferGeometry> = {
    circle: ledger.track(new THREE.SphereGeometry(1, 12, 8), "circle marker geometry"),
    diamond: ledger.track(new THREE.OctahedronGeometry(1.25), "diamond marker geometry"),
    square: ledger.track(new THREE.BoxGeometry(1.6, 1.6, 1.6), "square marker geometry"),
    noise: ledger.track(new THREE.TetrahedronGeometry(1.35), "noise marker geometry"),
  };
  const markerMat = ledger.track(new THREE.MeshBasicMaterial({ color: 0xffffff }), "marker material");
  const byShape = new Map<string, Row[]>();
  for (const row of rows) {
    const { shape } = clusterStyle(row.analysis.cluster);
    const list = byShape.get(shape) ?? [];
    list.push(row);
    byShape.set(shape, list);
  }
  const meshes: { mesh: THREE.InstancedMesh; rows: Row[] }[] = [];
  const dummy = new THREE.Object3D();
  const color = new THREE.Color();
  for (const shape of [...SHAPES, "noise"] as const) {
    const list = byShape.get(shape);
    if (!list || list.length === 0) continue;
    const mesh = new THREE.InstancedMesh(shapeGeos[shape]!, markerMat, list.length);
    ledger.track(mesh, `${shape} instanced mesh`);
    list.forEach((row, i) => {
      const [x, y, z] = latLonToXYZ(row.event.latitude_deg, row.event.longitude_deg, MARKER_RADIUS);
      dummy.position.set(x, y, z);
      dummy.scale.setScalar(markerSize(row.event.magnitude));
      dummy.updateMatrix();
      mesh.setMatrixAt(i, dummy.matrix);
      mesh.setColorAt(i, color.set(clusterStyle(row.analysis.cluster).color));
    });
    mesh.instanceMatrix.needsUpdate = true;
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
    mesh.computeBoundingSphere();
    scene.add(mesh);
    meshes.push({ mesh, rows: list });
  }
  const rowById = new Map(rows.map((r) => [r.event.id, r] as const));

  // Selection halo
  const haloGeo = ledger.track(new THREE.RingGeometry(1.5, 2.1, 40), "halo geometry");
  const haloMat = ledger.track(new THREE.MeshBasicMaterial({ color: 0xffffff, side: THREE.DoubleSide, depthTest: false }), "halo material");
  const halo = new THREE.Mesh(haloGeo, haloMat);
  halo.visible = false;
  halo.renderOrder = 10;
  scene.add(halo);

  let disposed = false;
  let raf = 0;
  const render = () => {
    raf = 0;
    if (!disposed) renderer.render(scene, camera);
  };
  const requestRender = () => {
    if (!raf && !disposed) raf = requestAnimationFrame(render);
  };
  controls.addEventListener("change", requestRender);

  const resize = () => {
    const w = Math.max(1, container.clientWidth);
    const h = Math.max(1, container.clientHeight);
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    requestRender();
  };
  const ro = new ResizeObserver(resize);
  ro.observe(container);
  resize();

  // Picking: a click (not a drag) selects the nearest marker in front of the sphere.
  const raycaster = new THREE.Raycaster();
  const ndc = new THREE.Vector2();
  let downAt: { x: number; y: number } | null = null;
  const onDown = (e: PointerEvent) => {
    downAt = { x: e.clientX, y: e.clientY };
  };
  const onUp = (e: PointerEvent) => {
    if (!downAt || Math.hypot(e.clientX - downAt.x, e.clientY - downAt.y) > 5) {
      downAt = null;
      return;
    }
    downAt = null;
    const rect = canvas.getBoundingClientRect();
    ndc.set(((e.clientX - rect.left) / rect.width) * 2 - 1, -((e.clientY - rect.top) / rect.height) * 2 + 1);
    raycaster.setFromCamera(ndc, camera);
    const sphereHit = raycaster.intersectObject(sphere, false)[0];
    let best: { dist: number; row: Row } | null = null;
    for (const { mesh, rows: list } of meshes) {
      const hit = raycaster.intersectObject(mesh, false)[0];
      if (hit && hit.instanceId !== undefined && (!best || hit.distance < best.dist)) {
        const row = list[hit.instanceId];
        if (row) best = { dist: hit.distance, row };
      }
    }
    if (best && (!sphereHit || best.dist < sphereHit.distance)) controller.select(best.row.event.id, "globe");
  };
  canvas.addEventListener("pointerdown", onDown);
  canvas.addEventListener("pointerup", onUp);
  const onLost = (e: Event) => {
    e.preventDefault();
    options.onContextLost();
  };
  canvas.addEventListener("webglcontextlost", onLost);

  const setSelected = (id: string | null, focus: boolean) => {
    const row = id === null ? undefined : rowById.get(id);
    if (!row) {
      halo.visible = false;
      requestRender();
      return;
    }
    const [x, y, z] = latLonToXYZ(row.event.latitude_deg, row.event.longitude_deg, MARKER_RADIUS + 0.004);
    halo.position.set(x, y, z);
    halo.scale.setScalar(Math.max(0.014, markerSize(row.event.magnitude)));
    halo.lookAt(x * 2, y * 2, z * 2);
    halo.visible = true;
    if (focus) {
      const distance = camera.position.length();
      camera.position.set(x, y, z).normalize().multiplyScalar(distance);
      controls.update();
    }
    requestRender();
  };

  const screenPosition = (id: string) => {
    const row = rowById.get(id);
    if (!row || disposed) return null;
    camera.updateMatrixWorld();
    const [x, y, z] = latLonToXYZ(row.event.latitude_deg, row.event.longitude_deg, MARKER_RADIUS);
    const p = new THREE.Vector3(x, y, z);
    if (p.dot(camera.position) <= 1) return null; // far side of the globe
    const rect = canvas.getBoundingClientRect();
    p.project(camera);
    return { x: rect.left + ((p.x + 1) / 2) * rect.width, y: rect.top + ((1 - p.y) / 2) * rect.height };
  };

  const dispose = () => {
    if (disposed) return;
    disposed = true;
    if (raf) cancelAnimationFrame(raf);
    ro.disconnect();
    controls.removeEventListener("change", requestRender);
    controls.dispose();
    canvas.removeEventListener("pointerdown", onDown);
    canvas.removeEventListener("pointerup", onUp);
    canvas.removeEventListener("webglcontextlost", onLost);
    ledger.disposeAll();
    scene.clear();
    renderer.dispose();
    renderer.forceContextLoss();
    canvas.remove();
  };

  return { ok: true, handle: { ledger, setSelected, screenPosition, dispose } };
}
