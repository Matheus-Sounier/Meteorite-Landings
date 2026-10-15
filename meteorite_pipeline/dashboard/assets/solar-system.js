(function () {
    function bootScene() {
        const container = document.getElementById("solar-system-scene");
        if (!container) return false;

        import("https://cdn.jsdelivr.net/npm/three@0.170.0/build/three.module.js")
            .then((THREE) => initializeScene(THREE))
            .catch(() => {
                container.dataset.state = "unavailable";
            });

        function initializeScene(THREE) {

    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(42, 1, 0.1, 120);
    const cameraStartDistance = 36;
    const cameraEndDistance = 1.45;
    const cameraTilt = 0.52;
    let zoomProgress = 0;
    camera.position.z = cameraStartDistance;

    const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true, powerPreference: "low-power" });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
    renderer.setClearColor(0x05090f, 0);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    container.appendChild(renderer.domElement);

    const system = new THREE.Group();
    system.position.set(2.4, 0.15, 0);
    scene.add(system);
    scene.add(new THREE.AmbientLight(0x9ab3c5, 1.35));
    const sunLight = new THREE.PointLight(0xffd69a, 68, 55, 1.55);
    system.add(sunLight);

    const sun = new THREE.Mesh(
        new THREE.SphereGeometry(1.15, 40, 28),
        new THREE.MeshBasicMaterial({ color: 0xffc879 }),
    );
    system.add(sun);
    system.add(new THREE.Mesh(
        new THREE.SphereGeometry(2.1, 32, 24),
        new THREE.MeshBasicMaterial({ color: 0xffae55, transparent: true, opacity: 0.16, depthWrite: false }),
    ));

    function createPlanetTexture(planetIndex, baseColor) {
        const textureCanvas = document.createElement("canvas");
        textureCanvas.width = 512;
        textureCanvas.height = 256;
        const textureContext = textureCanvas.getContext("2d");
        textureContext.fillStyle = `#${baseColor.toString(16).padStart(6, "0")}`;
        textureContext.fillRect(0, 0, textureCanvas.width, textureCanvas.height);

        let randomSeed = (planetIndex + 1) * 9187;
        function randomValue() {
            randomSeed = (randomSeed * 16807) % 2147483647;
            return (randomSeed - 1) / 2147483646;
        }

        if (planetIndex === 1 || planetIndex >= 4) {
            const bandCount = planetIndex === 4 ? 34 : planetIndex === 5 ? 24 : 42;
            for (let bandIndex = 0; bandIndex < bandCount; bandIndex += 1) {
                const bandY = (bandIndex / bandCount) * textureCanvas.height;
                const bandHeight = textureCanvas.height / bandCount;
                const shade = bandIndex % 2 === 0 ? 0.19 : 0.09;
                const bandColor = planetIndex === 1 ? "255, 236, 204" : "255, 244, 224";
                textureContext.fillStyle = `rgba(${bandColor}, ${shade + randomValue() * 0.1})`;
                textureContext.beginPath();
                textureContext.moveTo(0, bandY);
                textureContext.quadraticCurveTo(
                    textureCanvas.width * 0.5,
                    bandY + (randomValue() - 0.5) * bandHeight * 1.8,
                    textureCanvas.width,
                    bandY + (randomValue() - 0.5) * bandHeight,
                );
                textureContext.lineTo(textureCanvas.width, bandY + bandHeight);
                textureContext.quadraticCurveTo(
                    textureCanvas.width * 0.5,
                    bandY + bandHeight + (randomValue() - 0.5) * bandHeight,
                    0,
                    bandY + bandHeight,
                );
                textureContext.closePath();
                textureContext.fill();
            }

            if (planetIndex === 4) {
                const storm = textureContext.createRadialGradient(352, 154, 3, 352, 154, 43);
                storm.addColorStop(0, "rgba(156, 71, 43, 0.82)");
                storm.addColorStop(0.54, "rgba(185, 100, 61, 0.55)");
                storm.addColorStop(1, "rgba(185, 100, 61, 0)");
                textureContext.fillStyle = storm;
                textureContext.beginPath();
                textureContext.ellipse(352, 154, 48, 22, -0.08, 0, Math.PI * 2);
                textureContext.fill();
                textureContext.strokeStyle = "rgba(255, 226, 192, 0.24)";
                textureContext.lineWidth = 3;
                textureContext.beginPath();
                textureContext.ellipse(352, 154, 53, 25, -0.08, 0, Math.PI * 2);
                textureContext.stroke();
            }

            if (planetIndex === 1) {
                for (let cloudIndex = 0; cloudIndex < 22; cloudIndex += 1) {
                    const cloudX = randomValue() * textureCanvas.width;
                    const cloudY = randomValue() * textureCanvas.height;
                    const cloudWidth = 18 + randomValue() * 52;
                    textureContext.strokeStyle = `rgba(255, 247, 226, ${0.12 + randomValue() * 0.2})`;
                    textureContext.lineWidth = 3 + randomValue() * 7;
                    textureContext.beginPath();
                    textureContext.ellipse(cloudX, cloudY, cloudWidth, 3 + randomValue() * 5, randomValue() * 0.4, 0, Math.PI * 2);
                    textureContext.stroke();
                }
            }

            if (planetIndex === 7) {
                const storm = textureContext.createRadialGradient(164, 116, 2, 164, 116, 34);
                storm.addColorStop(0, "rgba(188, 223, 255, 0.7)");
                storm.addColorStop(0.6, "rgba(107, 157, 219, 0.42)");
                storm.addColorStop(1, "rgba(77, 120, 196, 0)");
                textureContext.fillStyle = storm;
                textureContext.beginPath();
                textureContext.ellipse(164, 116, 38, 17, 0.16, 0, Math.PI * 2);
                textureContext.fill();
            }
        } else if (planetIndex !== 2) {
            for (let craterIndex = 0; craterIndex < 140; craterIndex += 1) {
                const craterX = randomValue() * textureCanvas.width;
                const craterY = randomValue() * textureCanvas.height;
                const craterRadius = 2 + randomValue() * (planetIndex === 3 ? 13 : 11);
                const craterGradient = textureContext.createRadialGradient(
                    craterX - craterRadius * 0.3,
                    craterY - craterRadius * 0.3,
                    craterRadius * 0.08,
                    craterX,
                    craterY,
                    craterRadius,
                );
                craterGradient.addColorStop(0, "rgba(255, 244, 222, 0.42)");
                craterGradient.addColorStop(0.58, "rgba(40, 35, 30, 0.08)");
                craterGradient.addColorStop(1, "rgba(5, 9, 15, 0.52)");
                textureContext.fillStyle = craterGradient;
                textureContext.beginPath();
                textureContext.arc(craterX, craterY, craterRadius, 0, Math.PI * 2);
                textureContext.fill();
            }

            if (planetIndex === 3) {
                textureContext.fillStyle = "rgba(235, 218, 190, 0.5)";
                textureContext.beginPath();
                textureContext.ellipse(256, 11, 116, 13, 0, 0, Math.PI * 2);
                textureContext.ellipse(256, 245, 82, 9, 0, 0, Math.PI * 2);
                textureContext.fill();
            }
        }

        const planetTexture = new THREE.CanvasTexture(textureCanvas);
        planetTexture.colorSpace = THREE.SRGBColorSpace;
        return planetTexture;
    }

    const specifications = [
        [2.6, 0.16, 0xb8b3a8, 0.42, 0.01],
        [4.0, 0.3, 0xe2ae72, 0.29, 0.03],
        [5.8, 0.46, 0x397fb5, 0.22, 0.02],
        [7.8, 0.26, 0xe07156, 0.17, 0.04],
        [10.6, 0.82, 0xc6a57f, 0.1, 0.02],
        [13.4, 0.68, 0xd1bc8b, 0.075, 0.03],
        [16.0, 0.52, 0x7ab9c5, 0.055, 0.05],
        [18.6, 0.5, 0x4d78c4, 0.043, 0.04],
    ];
    const planets = [];
    let earth;
    let earthAtmosphere;

    specifications.forEach(([orbit, size, color, speed, inclination], index) => {
        const points = [];
        for (let point = 0; point <= 128; point += 1) {
            const angle = (point / 128) * Math.PI * 2;
            points.push(new THREE.Vector3(Math.cos(angle) * orbit, Math.sin(angle) * orbit, 0));
        }
        const orbitLine = new THREE.Line(
            new THREE.BufferGeometry().setFromPoints(points),
            new THREE.LineBasicMaterial({ color: 0x9db3c2, transparent: true, opacity: 0.19 }),
        );
        orbitLine.rotation.x = inclination;
        system.add(orbitLine);

        const surfaceTexture = createPlanetTexture(index, color);
        const planetMaterial = new THREE.MeshStandardMaterial({
            color: 0xffffff,
            map: surfaceTexture,
            bumpMap: index === 2 ? null : surfaceTexture,
            bumpScale: size * 0.1,
            roughness: 0.88,
            emissive: color,
            emissiveIntensity: 0.035,
            transparent: index === 2,
        });
        const planet = new THREE.Mesh(new THREE.SphereGeometry(size, 40, 28), planetMaterial);
        const group = new THREE.Group();
        group.rotation.x = inclination;
        group.rotation.z = index * 0.78;
        planet.position.x = orbit;
        group.add(planet);
        system.add(group);
        planets.push({ group, planet, speed, phase: group.rotation.z });
        if (index === 2) earth = planet;

        if (index === 2) {
            earthAtmosphere = new THREE.Mesh(
                new THREE.SphereGeometry(size * 1.075, 40, 28),
                new THREE.MeshBasicMaterial({
                    color: 0x55bfff,
                    side: THREE.BackSide,
                    transparent: true,
                    opacity: 0.3,
                }),
            );
            planet.add(earthAtmosphere);
        }

        if (index === 5) {
            [
                [1.32, 1.48, 0xe8d1a1, 0.46],
                [1.5, 1.59, 0x776c5a, 0.3],
                [1.62, 1.77, 0xd9c394, 0.54],
                [1.8, 1.88, 0x716957, 0.26],
                [1.91, 2.12, 0xe8d5ae, 0.4],
            ].forEach(([inner, outer, ringColor, opacity]) => {
                const ring = new THREE.Mesh(
                    new THREE.RingGeometry(size * inner, size * outer, 64),
                    new THREE.MeshBasicMaterial({
                        color: ringColor,
                        side: THREE.DoubleSide,
                        transparent: true,
                        opacity,
                        depthWrite: false,
                    }),
                );
                ring.rotation.x = Math.PI / 2.35;
                planet.add(ring);
            });
        }
    });

    const asteroidCount = 280;
    const asteroidBelt = new THREE.InstancedMesh(
        new THREE.DodecahedronGeometry(0.055, 0),
        new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 1, metalness: 0.03 }),
        asteroidCount,
    );
    const asteroid = new THREE.Object3D();
    const asteroidTint = new THREE.Color();
    for (let asteroidIndex = 0; asteroidIndex < asteroidCount; asteroidIndex += 1) {
        const angle = Math.random() * Math.PI * 2;
        const radius = 8.65 + Math.random() * 1.35;
        asteroid.position.set(
            Math.cos(angle) * radius,
            Math.sin(angle) * radius,
            (Math.random() - 0.5) * 0.65,
        );
        asteroid.rotation.set(Math.random() * Math.PI, Math.random() * Math.PI, Math.random() * Math.PI);
        asteroid.scale.setScalar(0.35 + Math.random() * 1.25);
        asteroid.updateMatrix();
        asteroidBelt.setMatrixAt(asteroidIndex, asteroid.matrix);
        asteroidTint.setHSL(0.08 + Math.random() * 0.07, 0.12 + Math.random() * 0.16, 0.28 + Math.random() * 0.3);
        asteroidBelt.setColorAt(asteroidIndex, asteroidTint);
    }
    asteroidBelt.instanceMatrix.needsUpdate = true;
    if (asteroidBelt.instanceColor) asteroidBelt.instanceColor.needsUpdate = true;
    asteroidBelt.rotation.x = 0.035;
    system.add(asteroidBelt);

    new THREE.TextureLoader().load(
        "https://unpkg.com/three-globe/example/img/earth-blue-marble.jpg",
        (texture) => {
            texture.colorSpace = THREE.SRGBColorSpace;
            earth.material.map = texture;
            earth.material.color.set(0xffffff);
            earth.material.needsUpdate = true;
        },
    );

    const nebulaCanvas = document.createElement("canvas");
    nebulaCanvas.width = 1024;
    nebulaCanvas.height = 512;
    const nebulaContext = nebulaCanvas.getContext("2d");
    [
        [270, 210, 250, "rgba(21, 112, 151, 0.3)"],
        [670, 170, 210, "rgba(25, 79, 139, 0.26)"],
        [760, 390, 190, "rgba(41, 119, 128, 0.2)"],
        [400, 380, 180, "rgba(80, 108, 151, 0.14)"],
    ].forEach(([x, y, radius, color]) => {
        const haze = nebulaContext.createRadialGradient(x, y, 0, x, y, radius);
        haze.addColorStop(0, color);
        haze.addColorStop(0.52, color.replace(/0\.\d+\)/, "0.08)"));
        haze.addColorStop(1, "rgba(0, 0, 0, 0)");
        nebulaContext.fillStyle = haze;
        nebulaContext.fillRect(x - radius, y - radius, radius * 2, radius * 2);
    });
    const nebulaTexture = new THREE.CanvasTexture(nebulaCanvas);
    nebulaTexture.colorSpace = THREE.SRGBColorSpace;
    const nebula = new THREE.Sprite(new THREE.SpriteMaterial({
        map: nebulaTexture,
        color: 0xb7dced,
        transparent: true,
        opacity: 0.72,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
    }));
    nebula.position.set(0, 0, -20);
    nebula.scale.set(54, 27, 1);
    scene.add(nebula);

    const nebulaDepth = new THREE.Sprite(nebula.material.clone());
    nebulaDepth.material.opacity = 0.34;
    nebulaDepth.position.set(-12, 5, -42);
    nebulaDepth.scale.set(70, 34, 1);
    scene.add(nebulaDepth);

    const starPositions = new Float32Array(5600 * 3);
    const starColors = new Float32Array(5600 * 3);
    const starColor = new THREE.Color();
    for (let index = 0; index < starPositions.length; index += 3) {
        starPositions[index] = (Math.random() - 0.5) * 64;
        starPositions[index + 1] = (Math.random() - 0.5) * 42;
        starPositions[index + 2] = -5 - Math.random() * 35;
        starColor.setHSL(Math.random() < 0.18 ? 0.11 : 0.55 + Math.random() * 0.12, 0.34, 0.72 + Math.random() * 0.28);
        starColors[index] = starColor.r;
        starColors[index + 1] = starColor.g;
        starColors[index + 2] = starColor.b;
    }
    const starGeometry = new THREE.BufferGeometry();
    starGeometry.setAttribute("position", new THREE.BufferAttribute(starPositions, 3));
    starGeometry.setAttribute("color", new THREE.BufferAttribute(starColors, 3));
    const starField = new THREE.Points(
        starGeometry,
        new THREE.PointsMaterial({ vertexColors: true, size: 0.17, transparent: true, opacity: 1 }),
    );
    scene.add(starField);

    const distantStarPositions = new Float32Array(1800 * 3);
    for (let index = 0; index < distantStarPositions.length; index += 3) {
        distantStarPositions[index] = (Math.random() - 0.5) * 92;
        distantStarPositions[index + 1] = (Math.random() - 0.5) * 58;
        distantStarPositions[index + 2] = -48 - Math.random() * 42;
    }
    const distantStarGeometry = new THREE.BufferGeometry();
    distantStarGeometry.setAttribute("position", new THREE.BufferAttribute(distantStarPositions, 3));
    const distantStarField = new THREE.Points(
        distantStarGeometry,
        new THREE.PointsMaterial({ color: 0x9fc8ed, size: 0.13, transparent: true, opacity: 0.58 }),
    );
    scene.add(distantStarField);

    let running = false;
    let frameId = 0;
    let lastFrame = 0;
    let storyContext;
    let storyObserver;
    const clock = new THREE.Clock();
    const activeFlybys = [];
    let nextFlybyAt = 4.5 + Math.random();

    function randomPointOnEdge(edge, halfWidth, halfHeight, depth) {
        const horizontal = (Math.random() * 2 - 1) * halfWidth * 1.15;
        const vertical = (Math.random() * 2 - 1) * halfHeight * 1.15;
        if (edge === 0) return new THREE.Vector3(horizontal, halfHeight * 1.15, -depth);
        if (edge === 1) return new THREE.Vector3(halfWidth * 1.15, vertical, -depth);
        if (edge === 2) return new THREE.Vector3(horizontal, -halfHeight * 1.15, -depth);
        return new THREE.Vector3(-halfWidth * 1.15, vertical, -depth);
    }

    function createFlyby(now) {
        const focus = new THREE.Vector3();
        if (earth) {
            system.updateMatrixWorld(true);
            earth.getWorldPosition(focus);
        }
        camera.updateMatrixWorld(true);

        const cameraDistance = camera.position.distanceTo(focus);
        const pathDepth = cameraDistance + 10;
        const halfHeight = pathDepth * Math.tan(THREE.MathUtils.degToRad(camera.fov / 2));
        const halfWidth = halfHeight * camera.aspect;
        const startEdge = Math.floor(Math.random() * 4);
        const endEdge = (startEdge + 1 + Math.floor(Math.random() * 3)) % 4;
        const start = camera.localToWorld(randomPointOnEdge(startEdge, halfWidth, halfHeight, pathDepth));
        const end = camera.localToWorld(randomPointOnEdge(endEdge, halfWidth, halfHeight, pathDepth));
        const direction = end.clone().sub(start).normalize();
        const roll = Math.random();
        const type = roll < 0.02 ? "ship" : roll < 0.2 ? "meteorite" : roll < 0.46 ? "meteor" : "shooting-star";
        const headSize = halfHeight * (type === "shooting-star" ? 0.01 : type === "ship" ? 0.012 : 0.014);
        const tailLength = halfHeight * (type === "shooting-star" ? 0.2 : type === "meteor" ? 0.16 : 0.12);
        const color = type === "ship" ? 0x7de4ff : type === "meteorite" ? 0xff9a63 : 0xc5edff;
        const group = new THREE.Group();
        group.position.copy(start);
        group.lookAt(end);

        const trailMaterial = new THREE.MeshBasicMaterial({
                color,
                transparent: true,
                opacity: 0.92,
                blending: THREE.AdditiveBlending,
                depthWrite: false,
            });
        const trail = new THREE.Mesh(
            new THREE.ConeGeometry(headSize * 0.42, tailLength, 8, 1, true),
            trailMaterial,
        );
        trail.rotation.x = Math.PI / 2;
        trail.position.z = -tailLength / 2;
        group.add(trail);
        const fadeMaterials = [trailMaterial];

        if (type === "ship") {
            const hullMaterial = new THREE.MeshBasicMaterial({
                color: 0xd8f5ff,
                transparent: true,
                blending: THREE.AdditiveBlending,
                depthWrite: false,
            });
            const hull = new THREE.Mesh(
                new THREE.ConeGeometry(headSize * 1.7, headSize * 5, 6),
                hullMaterial,
            );
            hull.rotation.x = Math.PI / 2;
            group.add(hull);
            fadeMaterials.push(hullMaterial);

            const wingMaterial = new THREE.MeshBasicMaterial({
                color: 0x83dfff,
                transparent: true,
                blending: THREE.AdditiveBlending,
                depthWrite: false,
            });
            const wing = new THREE.Mesh(
                new THREE.BoxGeometry(headSize * 7, headSize * 0.4, headSize * 1.8),
                wingMaterial,
            );
            wing.position.z = -headSize * 1.1;
            group.add(wing);
            fadeMaterials.push(wingMaterial);
        } else {
            const geometry = type === "shooting-star"
                ? new THREE.SphereGeometry(headSize, 8, 6)
                : new THREE.IcosahedronGeometry(headSize, 0);
            const material = new THREE.MeshStandardMaterial({
                color: type === "meteorite" ? 0x70665c : 0xffbd7e,
                emissive: type === "meteorite" ? 0x80391f : 0xff6a2b,
                emissiveIntensity: type === "shooting-star" ? 2.2 : 1.2,
                roughness: 0.82,
                transparent: true,
                depthWrite: false,
            });
            group.add(new THREE.Mesh(geometry, material));
            fadeMaterials.push(material);
        }

        scene.add(group);
        const duration = type === "ship" ? 6 : 3.4 + Math.random() * 1.5;
        activeFlybys.push({ group, start, end, direction, type, createdAt: now, duration, fadeMaterials });
    }

    function disposeFlyby(group) {
        scene.remove(group);
        group.traverse((object) => {
            if (object.geometry) object.geometry.dispose();
            if (!object.material) return;
            const materials = Array.isArray(object.material) ? object.material : [object.material];
            materials.forEach((material) => material.dispose());
        });
    }

    function updateCamera() {
        const progress = Math.max(0, Math.min(1, zoomProgress));
        const earthFade = Math.max(0, Math.min(1, (progress - 0.98) / 0.02));
        const focus = new THREE.Vector3();
        if (progress > 0 && earth) {
            system.updateMatrixWorld(true);
            earth.getWorldPosition(focus);
            focus.multiplyScalar(progress);
        }
        const cameraDistance = cameraStartDistance + (cameraEndDistance - cameraStartDistance) * progress;
        camera.position.set(
            focus.x,
            focus.y + Math.sin(cameraTilt) * cameraDistance,
            focus.z + Math.cos(cameraTilt) * cameraDistance,
        );
        camera.lookAt(focus);
        earth.material.opacity = 1 - earthFade * 0.97;
        earthAtmosphere.material.opacity = 0.3 * (1 - earthFade);
    }

    function resizeScene() {
        const width = Math.max(container.clientWidth, 1);
        const height = Math.max(container.clientHeight, 1);
        camera.aspect = width / height;
        system.position.x = width < 700 ? -3 : 2.4;
        camera.position.z = width < 700 ? cameraStartDistance + 4 : cameraStartDistance;
        camera.updateProjectionMatrix();
        updateCamera();
        renderer.setSize(width, height, false);
        if (!running) renderer.render(scene, camera);
    }

    function renderFrame(now) {
        if (!running) return;
        frameId = window.requestAnimationFrame(renderFrame);
        if (now - lastFrame < 32) return;
        lastFrame = now;
        const elapsed = clock.getElapsedTime();
        planets.forEach(({ group, planet, speed, phase }) => {
            group.rotation.z = phase + elapsed * speed * 0.55;
            planet.rotation.y += 0.0018;
        });
        asteroidBelt.rotation.z = elapsed * 0.009;
        updateCamera();
        if (elapsed >= nextFlybyAt) {
            createFlyby(elapsed);
            nextFlybyAt = elapsed + 4.5 + Math.random();
        }
        for (let flybyIndex = activeFlybys.length - 1; flybyIndex >= 0; flybyIndex -= 1) {
            const flyby = activeFlybys[flybyIndex];
            const progress = Math.min(1, (elapsed - flyby.createdAt) / flyby.duration);
            flyby.group.position.lerpVectors(flyby.start, flyby.end, progress);
            if (flyby.type === "meteor" || flyby.type === "meteorite") {
                flyby.group.children[1].rotation.x += 0.035;
                flyby.group.children[1].rotation.y += 0.045;
            }
            const opacity = Math.sin(Math.PI * progress);
            flyby.fadeMaterials.forEach((material) => {
                material.opacity = opacity;
            });
            if (progress >= 1) {
                disposeFlyby(flyby.group);
                activeFlybys.splice(flybyIndex, 1);
            }
        }
        starField.rotation.z = elapsed * 0.0007;
        starField.rotation.y = elapsed * 0.00035;
        distantStarField.rotation.z = elapsed * 0.00012;
        nebula.material.rotation = Math.sin(elapsed * 0.08) * 0.04;
        nebulaDepth.material.rotation = -nebula.material.rotation * 0.55;
        renderer.render(scene, camera);
    }

    function startScene() {
        if (running || document.hidden || reduceMotion.matches) return;
        running = true;
        clock.start();
        frameId = window.requestAnimationFrame(renderFrame);
    }

    function stopScene() {
        running = false;
        window.cancelAnimationFrame(frameId);
        renderer.render(scene, camera);
    }

    function updateProgress() {
        const progressTrack = document.getElementById("scroll-progress-track");
        const progressFill = document.getElementById("scroll-progress-fill");
        if (!progressTrack || !progressFill) return;
        const maximum = document.documentElement.scrollHeight - window.innerHeight;
        const progress = maximum > 0 ? Math.min(1, Math.max(0, window.scrollY / maximum)) : 0;
        progressFill.style.transform = `scaleX(${progress})`;
        progressTrack.setAttribute("aria-valuenow", String(Math.round(progress * 100)));
    }

    window.addEventListener("scroll", updateProgress, { passive: true });
    window.addEventListener("resize", updateProgress, { passive: true });
    updateProgress();

    new ResizeObserver(resizeScene).observe(container);
    resizeScene();

    function setupScrollStory() {
        if (!window.gsap || !window.ScrollTrigger) return;
        if (!document.querySelector("#timeline-section")) {
            if (!storyObserver) {
                storyObserver = new MutationObserver(() => {
                    if (!document.querySelector("#timeline-section")) return;
                    storyObserver.disconnect();
                    storyObserver = null;
                    setupScrollStory();
                });
                storyObserver.observe(document.documentElement, { childList: true, subtree: true });
            }
            return;
        }
        gsap.registerPlugin(ScrollTrigger);
        if (storyContext) storyContext.revert();

        if (reduceMotion.matches) {
            gsap.set(container, { clearProps: "opacity" });
            const earthSection = document.querySelector("#earth-section");
            zoomProgress = earthSection && earthSection.getBoundingClientRect().top < window.innerHeight ? 1 : 0;
            updateCamera();
            return;
        }

        storyContext = gsap.context(() => {
            gsap.to(system.rotation, {
                y: 0.52,
                x: 0.22,
                ease: "none",
                scrollTrigger: {
                    trigger: "#timeline-section",
                    start: "top bottom",
                    end: "bottom top",
                    scrub: 1.1,
                },
            });
            gsap.to(system.position, {
                y: -0.7,
                ease: "none",
                scrollTrigger: {
                    trigger: "#classification-section",
                    start: "top bottom",
                    end: "bottom top",
                    scrub: 1.2,
                },
            });
            gsap.to({ progress: 0 }, {
                progress: 1,
                ease: "none",
                scrollTrigger: {
                    trigger: ".space-hero",
                    start: "top top",
                    endTrigger: "#earth-section",
                    end: "bottom bottom",
                    scrub: 1.4,
                    onUpdate: (trigger) => {
                        zoomProgress = trigger.progress;
                        updateCamera();
                    },
                },
            });
            gsap.utils.toArray(".story-reveal").forEach((section) => {
                gsap.fromTo(section, { y: 34, opacity: 0.35 }, {
                    y: 0,
                    opacity: 1,
                    duration: 0.9,
                    ease: "power2.out",
                    scrollTrigger: { trigger: section, start: "top 84%", once: true },
                });
            });
        });
        ScrollTrigger.refresh();
    }

    window.initializeMeteoriteStory = setupScrollStory;
    window.pauseMeteoriteStory = stopScene;
    window.resumeMeteoriteStory = startScene;
    document.addEventListener("visibilitychange", () => {
        if (document.hidden) stopScene();
        else startScene();
    });
    reduceMotion.addEventListener("change", () => {
        if (reduceMotion.matches) stopScene();
        else startScene();
        setupScrollStory();
    });
    startScene();
    setupScrollStory();
    updateProgress();
        }

        return true;
    }

    if (!bootScene()) {
        const observer = new MutationObserver(() => {
            if (bootScene()) observer.disconnect();
        });
        observer.observe(document.documentElement, { childList: true, subtree: true });
    }
})();