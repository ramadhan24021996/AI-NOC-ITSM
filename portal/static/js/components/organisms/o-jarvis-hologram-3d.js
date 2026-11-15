/**
 * Atomic Design — Organism Layer: 3D Holographic Head Face WebGL Engine
 * Path: /static/js/components/organisms/o-jarvis-hologram-3d.js
 * Provides: window.JarvisWebGL & window.UI.Organisms.JarvisHologram3D
 */
window.mouthOpening = window.mouthOpening || 0;
window.isListening = window.isListening || false;

(function (global) {
  let scene, camera, renderer, faceGeometry, faceMesh, faceParticles, orbitRing1, orbitRing2, audioLines;
  let dataDust, neuralCore, brainParticles, mouseX = 0, mouseY = 0, targetX = 0, targetY = 0;
  const originalPositions = [];
  const windowHalfX = window.innerWidth / 2;
  const windowHalfY = window.innerHeight / 2;

  const JarvisHologram3D = {
    setMouthOpening(val) {
      global.mouthOpening = Number(val) || 0;
    },

    getMouthOpening() {
      return Number(global.mouthOpening) || 0;
    },

    init() {
      if (this._initialized) return;
      this._initialized = true;
      this.initThreeJS();

      document.addEventListener('mousemove', (event) => {
        mouseX = (event.clientX - windowHalfX) * 0.4;
        mouseY = (event.clientY - windowHalfY) * 0.4;
      });
    },

    initThreeJS() {
      const container = document.getElementById('jrv-webgl-container');
      if (!container || typeof THREE === 'undefined') {
        setTimeout(() => this.initThreeJS(), 100);
        return;
      }

      const width = container.clientWidth || 800;
      const height = container.clientHeight || 500;

      scene = new THREE.Scene();
      scene.fog = new THREE.FogExp2(0x020611, 0.0006);

      camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 2000);
      camera.position.z = 700;

      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
      renderer.setSize(width, height);
      renderer.setPixelRatio(window.devicePixelRatio);
      container.innerHTML = '';
      container.appendChild(renderer.domElement);

      const pCanvas = document.createElement('canvas');
      pCanvas.width = 32;
      pCanvas.height = 32;
      const pCtx = pCanvas.getContext('2d');
      const grad = pCtx.createRadialGradient(16, 16, 0, 16, 16, 16);
      grad.addColorStop(0, 'rgba(255,255,255,1)');
      grad.addColorStop(0.2, 'rgba(255,255,255,1)');
      grad.addColorStop(1, 'rgba(0,0,0,0)');
      pCtx.fillStyle = grad;
      pCtx.fillRect(0, 0, 32, 32);
      const texture = new THREE.CanvasTexture(pCanvas);

      // EFFECT 1: Realistic 3D Face Wireframe (OBJLoader)
      if (typeof THREE.OBJLoader === 'function') {
        const objLoader = new THREE.OBJLoader();
        objLoader.load('/static/models/WaltHead.obj', (object) => {
          let loadedMesh;
          object.traverse((child) => {
            if (child.isMesh && !loadedMesh) loadedMesh = child;
          });

          if (loadedMesh) {
            faceGeometry = loadedMesh.geometry;
            faceGeometry.center();
            faceGeometry.scale(6.0, 6.0, 6.0);

            originalPositions.length = 0;
            const posAttr = faceGeometry.attributes.position;
            for (let i = 0; i < posAttr.count; i++) {
              originalPositions.push({ y: posAttr.getY(i) });
            }

            const material = new THREE.PointsMaterial({
              size: 2.0,
              color: 0x00FFFF,
              map: texture,
              blending: THREE.AdditiveBlending,
              depthWrite: false,
              transparent: true,
              opacity: 0.8
            });
            faceParticles = new THREE.Points(faceGeometry, material);
            scene.add(faceParticles);

            const wireMat = new THREE.MeshBasicMaterial({
              color: 0x00FFFF,
              wireframe: true,
              transparent: true,
              opacity: 0.01,
              blending: THREE.AdditiveBlending,
              depthWrite: false
            });
            faceMesh = new THREE.Mesh(faceGeometry, wireMat);
            scene.add(faceMesh);
            faceMesh.add(neuralCore);
          }
        });
      }

      // EFFECT 2: Pulsing Neural Core (Inside Head)
      neuralCore = new THREE.Group();
      neuralCore.position.set(0, 135, -45);

      const brainGeo = new THREE.BufferGeometry();
      const brainCount = 3000;
      const brainPos = new Float32Array(brainCount * 3);
      const brainOrigPos = new Float32Array(brainCount * 3);
      const brainPhases = new Float32Array(brainCount);

      for (let i = 0; i < brainCount; i++) {
        let r = Math.pow(Math.random(), 0.5) * 85;
        let theta = Math.random() * 2 * Math.PI;
        let phi = Math.acos(2 * Math.random() - 1);

        let x = r * Math.sin(phi) * Math.cos(theta) * 0.85;
        let y = r * Math.sin(phi) * Math.sin(theta) * 0.75;
        let z = r * Math.cos(phi) * 1.15;

        if (x > 0) x += 2; else x -= 2;

        brainPos[i * 3] = x;
        brainPos[i * 3 + 1] = y;
        brainPos[i * 3 + 2] = z;

        brainOrigPos[i * 3] = x;
        brainOrigPos[i * 3 + 1] = y;
        brainOrigPos[i * 3 + 2] = z;

        brainPhases[i] = Math.random() * Math.PI * 2;
      }
      brainGeo.setAttribute('position', new THREE.BufferAttribute(brainPos, 3));
      brainGeo.setAttribute('originalPosition', new THREE.BufferAttribute(brainOrigPos, 3));
      brainGeo.setAttribute('phase', new THREE.BufferAttribute(brainPhases, 1));

      const bDustMat = new THREE.PointsMaterial({
        color: 0xff2244,
        size: 4.0,
        map: texture,
        transparent: true,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
        opacity: 1.0
      });
      brainParticles = new THREE.Points(brainGeo, bDustMat);
      neuralCore.add(brainParticles);

      // EFFECT 3: Volumetric Data Dust
      const dustGeo = new THREE.BufferGeometry();
      const dustPointsCount = 5000;
      const dustPos = new Float32Array(dustPointsCount * 3);
      for (let i = 0; i < dustPointsCount; i++) {
        dustPos[i * 3] = (Math.random() - 0.5) * 2000;
        dustPos[i * 3 + 1] = (Math.random() - 0.5) * 2000;
        dustPos[i * 3 + 2] = (Math.random() - 0.5) * 2000;
      }
      dustGeo.setAttribute('position', new THREE.BufferAttribute(dustPos, 3));
      const dustMat = new THREE.PointsMaterial({
        color: 0x38bdf8, size: 2.5, transparent: true, opacity: 0.5, blending: THREE.AdditiveBlending
      });
      dataDust = new THREE.Points(dustGeo, dustMat);
      scene.add(dataDust);

      // EFFECT 4: Cyberpunk Grid Floor
      const gridHelper = new THREE.GridHelper(2400, 60, 0x00FFFF, 0x003366);
      gridHelper.position.y = -350;
      gridHelper.material.transparent = true;
      gridHelper.material.opacity = 0.25;
      scene.add(gridHelper);

      // EFFECT 5: Holographic Orbital Rings
      const ringMat1 = new THREE.MeshBasicMaterial({ color: 0x00FFFF, wireframe: true, transparent: true, opacity: 0.25 });
      const ringMat2 = new THREE.MeshBasicMaterial({ color: 0x34d399, wireframe: true, transparent: true, opacity: 0.15 });

      orbitRing1 = new THREE.Mesh(new THREE.TorusGeometry(380, 1.5, 8, 120), ringMat1);
      orbitRing2 = new THREE.Mesh(new THREE.TorusGeometry(340, 1, 4, 120), ringMat2);

      orbitRing1.rotation.x = Math.PI / 3;
      orbitRing2.rotation.y = Math.PI / 4;

      scene.add(orbitRing1);
      scene.add(orbitRing2);

      // 3D Audio Spectrum Waveform Line
      const audioGeo = new THREE.BufferGeometry();
      const numLines = 60;
      const linePositions = new Float32Array(numLines * 2 * 3);
      audioGeo.setAttribute('position', new THREE.BufferAttribute(linePositions, 3));

      const lineMat = new THREE.LineBasicMaterial({ color: 0x34d399, transparent: true, opacity: 0.8, blending: THREE.AdditiveBlending });
      audioLines = new THREE.LineSegments(audioGeo, lineMat);
      audioLines.position.y = -100;
      audioLines.position.z = 200;
      scene.add(audioLines);

      window.addEventListener('resize', () => {
        const w = container.clientWidth;
        const h = container.clientHeight;
        if (w > 0 && h > 0) {
          camera.aspect = w / h;
          camera.updateProjectionMatrix();
          renderer.setSize(w, h);
        }
      });

      this.animate();
    },

    animate() {
      requestAnimationFrame(() => this.animate());

      const time = Date.now() * 0.0005;
      const currentMouth = Number(global.mouthOpening) || 0;

      targetX = mouseX;
      targetY = mouseY;
      camera.position.x += (targetX - camera.position.x) * 0.02;
      camera.position.y += (-targetY - camera.position.y) * 0.02;
      camera.lookAt(scene.position);

      if (faceParticles && faceMesh) {
        faceParticles.rotation.y = Math.sin(time * 0.5) * 0.25;
        faceParticles.rotation.x = Math.sin(time * 0.3) * 0.1;
        faceMesh.rotation.y = faceParticles.rotation.y;
        faceMesh.rotation.x = faceParticles.rotation.x;
      }

      if (dataDust) dataDust.rotation.y = time * 0.1;

      if (orbitRing1 && orbitRing2) {
        orbitRing1.rotation.x = time;
        orbitRing1.rotation.y = time * 0.5;
        orbitRing2.rotation.x = -time * 0.8;
        orbitRing2.rotation.y = time * 1.2;
      }

      if (neuralCore && brainParticles) {
        const pulse = Math.sin(time * 5) * 0.05 + (currentMouth * 0.08);
        neuralCore.scale.set(1.0 + pulse, 1.0 + pulse, 1.0 + pulse);
        brainParticles.material.opacity = 0.8 + (currentMouth * 0.2);

        brainParticles.rotation.y = time * 0.2;
        brainParticles.rotation.z = Math.sin(time * 0.5) * 0.1;

        const posAttr = brainParticles.geometry.attributes.position;
        const origAttr = brainParticles.geometry.attributes.originalPosition;
        const phaseAttr = brainParticles.geometry.attributes.phase;

        for (let i = 0; i < posAttr.count; i++) {
          let ox = origAttr.getX(i);
          let oy = origAttr.getY(i);
          let oz = origAttr.getZ(i);
          let phase = phaseAttr.getX(i);

          let flow = Math.sin(time * 4.0 + phase) * Math.cos(time * 2.0 + ox * 0.05);
          let drift = (time * 15.0 + phase * 10.0) % 20.0;
          if (drift > 10.0) drift = 20.0 - drift;

          posAttr.setXYZ(
            i,
            ox + (ox * flow * 0.03),
            oy + (oy * flow * 0.03) + (drift * 0.2),
            oz + (oz * flow * 0.03)
          );
        }
        posAttr.needsUpdate = true;
      }

      if (currentMouth > 0 || Math.random() < 0.1) {
        if (audioLines && audioLines.geometry) {
          const positions = audioLines.geometry.attributes.position.array;
          const startX = -300;
          const stepX = 600 / 60;

          for (let i = 0; i < 60; i++) {
            const x = startX + (i * stepX);
            const distFromCenter = Math.abs(x);
            const intensity = Math.max(0, 1 - (distFromCenter / 300));
            const h = Math.random() * (currentMouth * 5) * intensity;

            positions[i * 6] = x;     positions[i * 6 + 1] = -h; positions[i * 6 + 2] = 0;
            positions[i * 6 + 3] = x; positions[i * 6 + 4] = h;  positions[i * 6 + 5] = 0;
          }
          audioLines.geometry.attributes.position.needsUpdate = true;
        }

        if (faceGeometry && faceGeometry.attributes) {
          const facePos = faceGeometry.attributes.position.array;
          for (let i = 0; i < originalPositions.length; i++) {
            const origY = originalPositions[i].y;
            const px = facePos[i * 3];
            const mouthY = -130.0;
            let distY = origY - mouthY;
            let ySpread = distY > 0 ? 1500.0 : 4000.0;
            let mouthEffect = Math.exp(-((px * px) / 1000 + (distY * distY) / ySpread));
            let direction = distY > 0 ? 0.3 : -1.0;
            facePos[i * 3 + 1] = origY + (currentMouth * mouthEffect * 0.8 * direction);
          }
          faceGeometry.attributes.position.needsUpdate = true;
        }
      }

      renderer.render(scene, camera);
    }
  };

  global.JarvisWebGL = JarvisHologram3D;
  global.UI = global.UI || {};
  global.UI.Organisms = global.UI.Organisms || {};
  global.UI.Organisms.JarvisHologram3D = JarvisHologram3D;
})(window);
