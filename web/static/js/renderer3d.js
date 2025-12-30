
class Renderer3D {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(0x111111);

        // Isometric Camera Setup
        // Aspect ratio will be set in onWindowResize
        const aspect = this.container.clientWidth / this.container.clientHeight;
        const d = 20;
        this.camera = new THREE.OrthographicCamera(-d * aspect, d * aspect, d, -d, 1, 1000);

        // Classic Isometric Angle: approx 35.264 degrees down (atan(1/sqrt(2))) and 45 degrees rotation
        this.camera.position.set(20, 20, 20);
        this.camera.lookAt(this.scene.position); // Look at 0,0,0

        this.renderer = new THREE.WebGLRenderer({ antialias: true });
        this.renderer.setSize(this.container.clientWidth, this.container.clientHeight);
        // Enable shadows
        this.renderer.shadowMap.enabled = true;
        this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;

        this.container.appendChild(this.renderer.domElement);

        // Lighting
        const ambientLight = new THREE.AmbientLight(0x404040, 0.6); // Soft white light
        this.scene.add(ambientLight);

        const dirLight = new THREE.DirectionalLight(0xffffff, 0.8);
        dirLight.position.set(10, 20, 10);
        dirLight.castShadow = true;
        dirLight.shadow.mapSize.width = 2048;
        dirLight.shadow.mapSize.height = 2048;
        const dLight = 50;
        dirLight.shadow.camera.left = -dLight;
        dirLight.shadow.camera.right = dLight;
        dirLight.shadow.camera.top = dLight;
        dirLight.shadow.camera.bottom = -dLight;
        this.scene.add(dirLight);

        // Objects map
        this.rooms = new Map(); // Key: "x,y", Value: THREE.Mesh
        this.characters = new Map(); // Key: name, Value: THREE.Group
        this.items = new Map(); // Key: id (or constructed key), Value: THREE.Mesh

        // Materials
        this.materials = {
            floor: new THREE.MeshStandardMaterial({ color: 0x1a1a2e, roughness: 0.7, metalness: 0.2 }),
            wall: new THREE.MeshStandardMaterial({ color: 0x444455, roughness: 0.9 }),
            player: new THREE.MeshStandardMaterial({ color: 0x00ff88, emissive: 0x00ff88, emissiveIntensity: 0.2 }), // Tealish green
            crew: new THREE.MeshStandardMaterial({ color: 0x0088ff }),   // Deep blue
            enemy: new THREE.MeshStandardMaterial({ color: 0xff3333, emissive: 0xff0000, emissiveIntensity: 0.3 }),  // Angry red
            item: new THREE.MeshStandardMaterial({ color: 0xffff00, emissive: 0xffff00, emissiveIntensity: 0.4 })    // Glowing yellow
        };

        // Resize handler
        window.addEventListener('resize', this.onWindowResize.bind(this), false);

        // Scaling factor to match grid coordinates to 3D units
        this.gridScale = 2.0;

        // Asset Configuration (Commented out missing .glb assets to silence 404s)
        this.assets = {
            models: {
                // macready: 'static/assets/models/characters/MacReady.glb',
                // crew: 'static/assets/models/characters/Crew_Generic.glb',
                // thing: 'static/assets/models/characters/Thing_Revealed.glb',
                // wall: 'static/assets/models/environment/Wall_Straight.glb',
                // floor: 'static/assets/models/environment/Floor_Tile.glb'
            }
        };

        // Model Cache
        this.loadedModels = {}; // { key: { scene: THREE.Group, animations: [] } }
        this.mixers = []; // Array of active mixers
        this.clock = new THREE.Clock();
        this.loader = new THREE.GLTFLoader();

        // Start loading assets
        this.loadAssets();

        // --- Interactive Terminals (Tier 11.2) ---
        this.terminals = new Map(); // Key: roomName, Value: THREE.Mesh
        this.terminalGlowStates = {}; // Track which terminals are glowing
        this.raycaster = new THREE.Raycaster();
        this.mouse = new THREE.Vector2();

        // Click handler for terminal interaction
        this.renderer.domElement.addEventListener('click', this.onCanvasClick.bind(this), false);

        // Animation loop
        this.animate();
    }

    loadAssets() {
        const models = this.assets.models;
        for (const [key, url] of Object.entries(models)) {
            this.loader.load(
                url,
                (gltf) => {
                    console.log(`Loaded ${key}`);
                    const model = gltf.scene;
                    // Enable shadows
                    model.traverse((node) => {
                        if (node.isMesh) {
                            node.castShadow = true;
                            node.receiveShadow = true;
                        }
                    });

                    this.loadedModels[key] = {
                        scene: model,
                        animations: gltf.animations || []
                    };

                    // Check for pending characters that were waiting for this model
                    if (this.characters) {
                        this.characters.forEach((group, name) => {
                            if (group.userData.isFallback && group.userData.pendingModel === key) {
                                console.log(`Upgrading ${name} to loaded model ${key}`);
                                this.upgradeToModel(group, key);
                            }
                        });
                    }
                },
                undefined,
                (error) => {
                    console.warn(`Failed to load ${key}:`, error);
                    this.loadedModels[key] = { error: true };
                }
            );
        }
    }

    onWindowResize() {
        if (!this.container) return;
        const aspect = this.container.clientWidth / this.container.clientHeight;
        const d = 20;

        this.camera.left = -d * aspect;
        this.camera.right = d * aspect;
        this.camera.top = d;
        this.camera.bottom = -d;

        this.camera.updateProjectionMatrix();
        this.renderer.setSize(this.container.clientWidth, this.container.clientHeight);
    }

    animate() {
        requestAnimationFrame(this.animate.bind(this));

        const delta = this.clock.getDelta();

        // Update all mixers
        this.mixers.forEach(mixer => mixer.update(delta));

        // Fallback animation for box characters (bopping)
        const time = Date.now() * 0.005;
        this.characters.forEach((charGroup) => {
            if (charGroup.userData.isFallback) {
                // Simple float effect for boxes
                charGroup.position.y = 1 + Math.sin(time + charGroup.userData.randomOffset) * 0.1;
            }
        });

        // Item rotation
        this.items.forEach((mesh) => {
            mesh.rotation.y += 0.02;
        });

        this.renderer.render(this.scene, this.camera);
    }

    update(gameState) {
        if (!gameState) return;

        // Store visibility data for other methods
        this.visibleRooms = gameState.visible_rooms || [];
        this.roomLighting = gameState.room_lighting || {};
        this.flashlightActive = gameState.flashlight_active || false;
        this.playerRoom = gameState.location;

        this.updateMap(gameState);
        this.updateRoomVisibility(gameState);

        // Create terminals once on first update
        if (!this.terminalsCreated) {
            this.createTerminals();
            this.terminalsCreated = true;
        }

        this.updateCharacters(gameState);
        this.updateAtmosphere(gameState);
        // this.updateItems(gameState); 

        // Center camera on player
        this.centerCameraOnPlayer(gameState);
    }

    updateMap(gameState) {
        if (gameState.ascii_map) {
            this.parseAsciiMap(gameState.ascii_map);
            this.renderRoomLabels();
        }
    }

    parseAsciiMap(asciiMap) {
        if (!asciiMap) return;

        // Only rebuild if the map string has actually changed to save performance
        if (this.lastAsciiMap === asciiMap) return;
        this.lastAsciiMap = asciiMap;

        if (this.mapGroup) {
            this.scene.remove(this.mapGroup);
        }

        this.mapGroup = new THREE.Group();
        this.scene.add(this.mapGroup);

        // Add floor plane (ground below everything)
        if (!this.floorPlane) {
            const geometry = new THREE.PlaneGeometry(100, 100);
            const material = new THREE.MeshStandardMaterial({ color: 0x0a0a0a, side: THREE.DoubleSide });
            this.floorPlane = new THREE.Mesh(geometry, material);
            this.floorPlane.rotation.x = -Math.PI / 2;
            this.floorPlane.position.y = -0.05;
            this.floorPlane.receiveShadow = true;
            this.scene.add(this.floorPlane);
        }

        const lines = asciiMap.split('\n');
        const wallGeo = new THREE.BoxGeometry(this.gridScale, this.gridScale * 1.5, this.gridScale);
        const floorGeo = new THREE.PlaneGeometry(this.gridScale, this.gridScale);
        const doorGeo = new THREE.BoxGeometry(this.gridScale * 0.8, this.gridScale * 1.2, this.gridScale * 0.2);

        lines.forEach((line, r) => {
            for (let c = 0; c < line.length; c++) {
                const char = line[c];
                const x = c * this.gridScale;
                const z = r * this.gridScale;

                // Ground Tile (Floor)
                if (char === '.' || char === '+' || char === '@' || (char >= 'A' && char <= 'Z')) {
                    let floorMesh = new THREE.Mesh(floorGeo, this.materials.floor);
                    floorMesh.rotation.x = -Math.PI / 2;
                    floorMesh.position.set(x, 0, z);
                    floorMesh.receiveShadow = true;
                    this.mapGroup.add(floorMesh);
                }

                if (char === '#') {
                    // WALL
                    let mesh = new THREE.Mesh(wallGeo, this.materials.wall);
                    mesh.position.set(x, this.gridScale * 0.75, z);
                    mesh.castShadow = true;
                    mesh.receiveShadow = true;
                    this.mapGroup.add(mesh);
                }
                else if (char === '+') {
                    // DOOR
                    let mesh = new THREE.Mesh(doorGeo, new THREE.MeshStandardMaterial({ color: 0x442200, roughness: 0.9 }));
                    mesh.position.set(x, this.gridScale * 0.6, z);

                    // Simple door rotation logic
                    const left = c > 0 ? line[c - 1] : ' ';
                    const right = c < line.length - 1 ? line[c + 1] : ' ';
                    if (left === '#' && right === '#') {
                        // Door is between horizontal walls
                    } else {
                        mesh.rotation.y = Math.PI / 2;
                    }

                    mesh.castShadow = true;
                    mesh.receiveShadow = true;
                    this.mapGroup.add(mesh);
                }
            }
        });
    }

    renderRoomLabels() {
        if (this.labelsGroup) {
            this.scene.remove(this.labelsGroup);
        }
        this.labelsGroup = new THREE.Group();
        this.scene.add(this.labelsGroup);

        const rooms = {
            "Rec Room": [7.5, 7.5],
            "Infirmary": [2, 2],
            "Generator": [17, 17],
            "Kennel": [2, 17],
            "Radio Room": [12.5, 2],
            "Storage": [17, 2],
            "Lab": [12.5, 12.5],
            "Sleeping Quarters": [2, 8],
            "Mess Hall": [7, 2],
            "Hangar": [7.5, 17]
        };

        for (const [name, pos] of Object.entries(rooms)) {
            const sprite = this.createTextLabel(name);
            sprite.position.set(pos[0] * this.gridScale, 4, pos[1] * this.gridScale);
            this.labelsGroup.add(sprite);
        }
    }

    createTextLabel(text) {
        const canvas = document.createElement('canvas');
        const context = canvas.getContext('2d');
        canvas.width = 256;
        canvas.height = 64;

        context.fillStyle = 'rgba(0,0,0,0)';
        context.fillRect(0, 0, canvas.width, canvas.height);

        context.font = 'Bold 24px Courier New';
        context.textAlign = 'center';
        context.textBaseline = 'middle';

        // Glow effect
        context.shadowColor = 'rgba(0, 255, 136, 0.8)';
        context.shadowBlur = 4;
        context.fillStyle = '#00ff88';
        context.fillText(text.toUpperCase(), canvas.width / 2, canvas.height / 2);

        const texture = new THREE.CanvasTexture(canvas);
        const spriteMaterial = new THREE.SpriteMaterial({ map: texture, transparent: true });
        const sprite = new THREE.Sprite(spriteMaterial);
        sprite.scale.set(8, 2, 1);
        return sprite;
    }

    // --- 3D Fog of War (Tier 11.1) ---
    updateRoomVisibility(gameState) {
        // Room bounding boxes (matching station_map.py)
        const roomBounds = {
            "Rec Room": { x1: 5, y1: 5, x2: 10, y2: 10 },
            "Infirmary": { x1: 0, y1: 0, x2: 4, y2: 4 },
            "Generator": { x1: 15, y1: 15, x2: 19, y2: 19 },
            "Kennel": { x1: 0, y1: 15, x2: 4, y2: 19 },
            "Radio Room": { x1: 11, y1: 0, x2: 14, y2: 4 },
            "Storage": { x1: 15, y1: 0, x2: 19, y2: 4 },
            "Lab": { x1: 11, y1: 11, x2: 14, y2: 14 },
            "Sleeping Quarters": { x1: 0, y1: 6, x2: 4, y2: 10 },
            "Mess Hall": { x1: 5, y1: 0, x2: 9, y2: 4 },
            "Hangar": { x1: 5, y1: 15, x2: 10, y2: 19 }
        };

        // Initialize fog overlay group if not exists
        if (!this.fogGroup) {
            this.fogGroup = new THREE.Group();
            this.scene.add(this.fogGroup);
        }

        // Clear existing fog overlays
        while (this.fogGroup.children.length > 0) {
            this.fogGroup.remove(this.fogGroup.children[0]);
        }

        const visibleRooms = this.visibleRooms || [];
        const playerRoom = this.playerRoom;
        const roomLighting = this.roomLighting || {};

        for (const [roomName, bounds] of Object.entries(roomBounds)) {
            const lighting = roomLighting[roomName] || {};
            const visibility = lighting.visibility || 'hidden';
            const isDark = lighting.is_dark || false;

            // Determine fog opacity based on visibility
            let fogOpacity = 0;
            let fogColor = 0x000000;

            if (visibility === 'full') {
                // Current room - no fog unless dark
                fogOpacity = isDark ? 0.3 : 0;
            } else if (visibility === 'partial') {
                // Adjacent room through open door - dim
                fogOpacity = isDark ? 0.6 : 0.3;
            } else {
                // Hidden room - heavy fog
                fogOpacity = isDark ? 0.85 : 0.7;
            }

            // Only create fog overlay if needed
            if (fogOpacity > 0) {
                const width = (bounds.x2 - bounds.x1 + 1) * this.gridScale;
                const height = (bounds.y2 - bounds.y1 + 1) * this.gridScale;
                const centerX = ((bounds.x1 + bounds.x2) / 2) * this.gridScale;
                const centerZ = ((bounds.y1 + bounds.y2) / 2) * this.gridScale;

                const fogGeo = new THREE.PlaneGeometry(width, height);
                const fogMat = new THREE.MeshBasicMaterial({
                    color: fogColor,
                    transparent: true,
                    opacity: fogOpacity,
                    side: THREE.DoubleSide,
                    depthWrite: false
                });
                const fogMesh = new THREE.Mesh(fogGeo, fogMat);
                fogMesh.rotation.x = -Math.PI / 2;
                fogMesh.position.set(centerX, 0.5, centerZ); // Slightly above floor
                fogMesh.userData.roomName = roomName;
                this.fogGroup.add(fogMesh);
            }
        }
    }

    // --- Interactive Terminals (Tier 11.2) ---
    createTerminals() {
        // Terminal positions (near room corner, not obstructing center)
        const terminalPositions = {
            "Rec Room": { x: 6, y: 6 },
            "Infirmary": { x: 1, y: 1 },
            "Generator": { x: 16, y: 16 },
            "Kennel": { x: 1, y: 16 },
            "Radio Room": { x: 12, y: 1 },
            "Storage": { x: 16, y: 1 },
            "Lab": { x: 12, y: 12 },
            "Sleeping Quarters": { x: 1, y: 7 },
            "Mess Hall": { x: 6, y: 1 },
            "Hangar": { x: 6, y: 16 }
        };

        // Create terminal group
        if (!this.terminalGroup) {
            this.terminalGroup = new THREE.Group();
            this.scene.add(this.terminalGroup);
        }

        // Clear existing terminals
        while (this.terminalGroup.children.length > 0) {
            this.terminalGroup.remove(this.terminalGroup.children[0]);
        }
        this.terminals.clear();

        for (const [roomName, pos] of Object.entries(terminalPositions)) {
            // Terminal body (box)
            const bodyGeo = new THREE.BoxGeometry(0.6, 1.2, 0.4);
            const bodyMat = new THREE.MeshStandardMaterial({
                color: 0x222233,
                roughness: 0.8,
                metalness: 0.3
            });
            const body = new THREE.Mesh(bodyGeo, bodyMat);
            body.position.y = 0.6;

            // Terminal screen (emissive plane)
            const screenGeo = new THREE.PlaneGeometry(0.5, 0.4);
            const screenMat = new THREE.MeshBasicMaterial({
                color: 0x00ff88,
                emissive: 0x00ff88,
                transparent: true,
                opacity: 0.9
            });
            const screen = new THREE.Mesh(screenGeo, screenMat);
            screen.position.set(0, 0.9, 0.21);

            // Group terminal components
            const terminal = new THREE.Group();
            terminal.add(body);
            terminal.add(screen);
            terminal.position.set(pos.x * this.gridScale, 0, pos.y * this.gridScale);
            terminal.userData.roomName = roomName;
            terminal.userData.isTerminal = true;
            terminal.userData.screen = screen;

            this.terminalGroup.add(terminal);
            this.terminals.set(roomName, terminal);
        }
    }

    onCanvasClick(event) {
        // Calculate mouse position in normalized device coordinates
        const rect = this.renderer.domElement.getBoundingClientRect();
        this.mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
        this.mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

        // Update raycaster
        this.raycaster.setFromCamera(this.mouse, this.camera);

        // Check terminal intersections
        if (this.terminalGroup) {
            const terminalMeshes = [];
            this.terminalGroup.traverse((child) => {
                if (child.isMesh) terminalMeshes.push(child);
            });

            const intersects = this.raycaster.intersectObjects(terminalMeshes, false);
            if (intersects.length > 0) {
                // Find the parent terminal group
                let terminal = intersects[0].object;
                while (terminal && !terminal.userData.isTerminal) {
                    terminal = terminal.parent;
                }

                if (terminal && terminal.userData.roomName) {
                    this.openTerminalModal(terminal.userData.roomName);
                }
            }
        }
    }

    openTerminalModal(roomName) {
        // Dispatch custom event for game.js to handle modal opening
        const event = new CustomEvent('terminalClicked', {
            detail: { roomName: roomName }
        });
        window.dispatchEvent(event);
        console.log(`Terminal clicked: ${roomName}`);
    }

    updateTerminalGlow(roomName, glowing) {
        const terminal = this.terminals.get(roomName);
        if (terminal && terminal.userData.screen) {
            const screen = terminal.userData.screen;
            if (glowing) {
                // Pulsing glow effect
                screen.material.color.setHex(0xff8800); // Orange
                screen.material.opacity = 0.7 + Math.sin(Date.now() * 0.01) * 0.3;
            } else {
                // Normal state
                screen.material.color.setHex(0x00ff88); // Green
                screen.material.opacity = 0.9;
            }
        }
    }

    // ... updateMap and parseAsciiMap methods ...

    updateCharacters(gameState) {
        // Track which characters we updated to handle removals
        const updatedNames = new Set();

        gameState.crew.forEach(member => {
            updatedNames.add(member.name);
            const x = member.coords[0] * this.gridScale;
            const z = member.coords[1] * this.gridScale;

            let group = this.characters.get(member.name);

            if (group) {
                // Calculate movement for animation
                const dist = Math.sqrt(Math.pow(x - group.position.x, 2) + Math.pow(z - group.position.z, 2));
                const isMoving = dist > 0.1;

                // Update position
                group.position.set(x, group.position.y, z);

                // --- 3D Visibility: Hide NPCs in non-visible rooms (Tier 11.1) ---
                const memberRoom = member.location;
                const visibleRooms = this.visibleRooms || [];
                const roomLighting = this.roomLighting || {};
                const flashlight = this.flashlightActive || false;
                const isPlayer = member.name === 'MacReady';

                if (!isPlayer) {
                    const roomInfo = roomLighting[memberRoom] || {};
                    const roomVisibility = roomInfo.visibility || 'hidden';
                    const isRoomDark = roomInfo.is_dark || false;

                    // Determine NPC visibility
                    let npcOpacity = 1.0;
                    if (roomVisibility === 'hidden' && !flashlight) {
                        // NPC in non-visible room - completely hidden
                        npcOpacity = 0;
                    } else if (isRoomDark && !flashlight) {
                        // NPC in dark room but visible - silhouette (very dim)
                        npcOpacity = 0.2;
                    } else if (roomVisibility === 'partial') {
                        // NPC in adjacent room - slightly dimmed
                        npcOpacity = 0.7;
                    }

                    // Apply visibility to all meshes in group
                    group.traverse((node) => {
                        if (node.isMesh) {
                            node.material.transparent = true;
                            node.material.opacity = npcOpacity;
                        }
                    });
                    group.visible = npcOpacity > 0;
                }

                // Rotate to face movement direction (approximate if we tracked history)
                if (isMoving) {
                    // group.lookAt(targetX, group.position.y, targetZ); 
                }

                // Handle Animation State
                if (group.userData.mixer && group.userData.animations) {
                    const actionName = isMoving ? 'Walk' : 'Idle';
                    this.playAnimation(group, actionName);
                }

                // STEALTH: Posture Indicator (Player only)
                if (member.name === 'MacReady' && gameState.player_stealth_posture) {
                    this.updatePostureIcon(group, gameState.player_stealth_posture);
                }

                // STEALTH: Detection Alert (Player only)
                if (member.name === 'MacReady' && gameState.detection_status) {
                    this.updateDetectionAlert(group, gameState.detection_status);
                }


                // Panic Shake: High stress causes vibration
                if (member.stress && member.stress > 5) {
                    const shakeIntensity = (member.stress - 5) * 0.02;
                    group.position.x += (Math.random() - 0.5) * shakeIntensity;
                    group.position.z += (Math.random() - 0.5) * shakeIntensity;
                }

                // Out-of-place marker: purple ring pulse
                if (member.out_of_place && !group.userData.outOfPlaceMarker) {
                    const oopGeo = new THREE.RingGeometry(0.7, 0.95, 32);
                    const oopMat = new THREE.MeshBasicMaterial({
                        color: 0xbb55ff,
                        side: THREE.DoubleSide,
                        transparent: true,
                        opacity: 0.7
                    });
                    const oopRing = new THREE.Mesh(oopGeo, oopMat);
                    oopRing.rotation.x = -Math.PI / 2;
                    oopRing.position.y = 0.08;
                    group.add(oopRing);
                    group.userData.outOfPlaceMarker = oopRing;

                    const oopInterval = setInterval(() => {
                        if (oopRing.parent) {
                            const scale = 0.9 + Math.sin(Date.now() * 0.006) * 0.1;
                            oopRing.scale.set(scale, scale, 1);
                        } else {
                            clearInterval(oopInterval);
                        }
                    }, 60);
                } else if (!member.out_of_place && group.userData.outOfPlaceMarker) {
                    group.remove(group.userData.outOfPlaceMarker);
                    delete group.userData.outOfPlaceMarker;
                }

                // Trust Indicator: Add colored ring for low trust
                if (member.trust < 30 && !group.userData.trustIndicator) {
                    const ringGeo = new THREE.RingGeometry(0.8, 1.0, 32);
                    const ringMat = new THREE.MeshBasicMaterial({
                        color: 0xff0000,
                        side: THREE.DoubleSide,
                        transparent: true,
                        opacity: 0.6
                    });
                    const ring = new THREE.Mesh(ringGeo, ringMat);
                    ring.rotation.x = -Math.PI / 2;
                    ring.position.y = 0.1;
                    group.add(ring);
                    group.userData.trustIndicator = ring;
                } else if (member.trust >= 30 && group.userData.trustIndicator) {
                    // Remove indicator if trust recovers
                    group.remove(group.userData.trustIndicator);
                    delete group.userData.trustIndicator;
                }

                // Stealth Posture Indicator (Player Only or Debug)
                if (member.stealth_posture && member.name === 'MacReady') {
                    // Remove existing posture ring if it exists but state changed
                    if (group.userData.postureRing && group.userData.lastPosture !== member.stealth_posture) {
                        group.remove(group.userData.postureRing);
                        delete group.userData.postureRing;
                    }

                    if (!group.userData.postureRing && member.stealth_posture !== 'STANDING') {
                        let color = 0x00ff00; // Default green (unused)
                        let opacity = 0.5;

                        // Transparency effect (Visual Stealth)
                        // Traverse models to set opacity
                        group.traverse((node) => {
                            if (node.isMesh) {
                                node.material.transparent = true;
                                if (member.stealth_posture === 'CROUCHING') {
                                    node.material.opacity = 0.8;
                                    color = 0xffff00; // Yellow
                                } else if (member.stealth_posture === 'CRAWLING') {
                                    node.material.opacity = 0.6;
                                    color = 0xff8800; // Orange
                                } else if (member.stealth_posture === 'HIDING') {
                                    node.material.opacity = 0.4;
                                    color = 0x0088ff; // Blue
                                } else {
                                    node.material.opacity = 1.0;
                                }
                            }
                        });


                        // Physical Scaling for Posture
                        let targetScaleY = 1.0;
                        if (member.stealth_posture === 'CROUCHING') targetScaleY = 0.7;
                        else if (member.stealth_posture === 'CRAWLING') targetScaleY = 0.4;
                        else if (member.stealth_posture === 'HIDING') targetScaleY = 0.7;

                        group.scale.y = targetScaleY;


                        const ringGeo = new THREE.RingGeometry(0.5, 0.7, 32);
                        const ringMat = new THREE.MeshBasicMaterial({
                            color: color,
                            side: THREE.DoubleSide,
                            transparent: true,
                            opacity: 0.6
                        });
                        const ring = new THREE.Mesh(ringGeo, ringMat);
                        ring.rotation.x = -Math.PI / 2;
                        ring.position.y = 0.05;
                        group.add(ring);
                        group.userData.postureRing = ring;
                        group.userData.lastPosture = member.stealth_posture;

                        // Pulse animation for HIDING
                        if (member.stealth_posture === 'HIDING') {
                            const pulseInterval = setInterval(() => {
                                if (ring.parent) {
                                    const scale = 1 + Math.sin(Date.now() * 0.005) * 0.1;
                                    ring.scale.set(scale, scale, 1);
                                } else {
                                    clearInterval(pulseInterval);
                                }
                            }, 50);
                        }

                    } else if (member.stealth_posture === 'STANDING') {
                        // Restore opacity and scale
                        group.scale.y = 1.0;
                        group.traverse((node) => {
                            if (node.isMesh) {
                                node.material.opacity = 1.0;
                                node.material.transparent = false;
                            }
                        });
                    }
                }

                // Stealth Detection: Alert icon when NPC detects player
                if (member.detected_player && !group.userData.alertIcon) {
                    const alertGeo = new THREE.ConeGeometry(0.3, 0.8, 4);
                    const alertMat = new THREE.MeshBasicMaterial({ color: 0xff0000 });
                    const alert = new THREE.Mesh(alertGeo, alertMat);
                    alert.position.y = 2.5;
                    alert.rotation.x = Math.PI; // Point down
                    group.add(alert);
                    group.userData.alertIcon = alert;

                    // Pulse animation
                    const pulseInterval = setInterval(() => {
                        if (alert.parent) {
                            alert.scale.y = 1 + Math.sin(Date.now() * 0.01) * 0.2;
                        } else {
                            clearInterval(pulseInterval);
                        }
                    }, 50);
                } else if (!member.detected_player && group.userData.alertIcon) {
                    group.remove(group.userData.alertIcon);
                    delete group.userData.alertIcon;
                }

                // AI Destination: Arrow pointing to target room
                if (member.target_room && !group.userData.destinationArrow) {
                    const arrowGeo = new THREE.ConeGeometry(0.2, 0.6, 3);
                    const arrowMat = new THREE.MeshBasicMaterial({
                        color: 0x00ffff,
                        transparent: true,
                        opacity: 0.7
                    });
                    const arrow = new THREE.Mesh(arrowGeo, arrowMat);
                    arrow.position.y = 2.0;
                    arrow.rotation.x = Math.PI / 2; // Point forward
                    group.add(arrow);
                    group.userData.destinationArrow = arrow;
                } else if (!member.target_room && group.userData.destinationArrow) {
                    group.remove(group.userData.destinationArrow);
                    delete group.userData.destinationArrow;
                }

                // Lynch Mob: Red glow for mob members
                if (member.in_lynch_mob && !group.userData.mobGlow) {
                    const glowGeo = new THREE.SphereGeometry(1.2, 16, 16);
                    const glowMat = new THREE.MeshBasicMaterial({
                        color: 0xff0000,
                        transparent: true,
                        opacity: 0.3,
                        side: THREE.BackSide
                    });
                    const glow = new THREE.Mesh(glowGeo, glowMat);
                    glow.position.y = 1.0;
                    group.add(glow);
                    group.userData.mobGlow = glow;

                    // Pulsing glow
                    const glowInterval = setInterval(() => {
                        if (glow.parent) {
                            glow.material.opacity = 0.2 + Math.sin(Date.now() * 0.005) * 0.15;
                        } else {
                            clearInterval(glowInterval);
                        }
                    }, 50);
                } else if (!member.in_lynch_mob && group.userData.mobGlow) {
                    group.remove(group.userData.mobGlow);
                    delete group.userData.mobGlow;
                }

                // Location Hint: Orange pulse for NPCs out of place
                if (member.location_hint_active && !group.userData.hintGlow) {
                    const hintGeo = new THREE.RingGeometry(0.9, 1.1, 32);
                    const hintMat = new THREE.MeshBasicMaterial({
                        color: 0xff8800,
                        side: THREE.DoubleSide,
                        transparent: true,
                        opacity: 0.8
                    });
                    const hint = new THREE.Mesh(hintGeo, hintMat);
                    hint.rotation.x = -Math.PI / 2;
                    hint.position.y = 0.05;
                    group.add(hint);
                    group.userData.hintGlow = hint;

                    // Pulse effect
                    const hintInterval = setInterval(() => {
                        if (hint.parent) {
                            const scale = 1 + Math.sin(Date.now() * 0.008) * 0.1;
                            hint.scale.set(scale, scale, 1);
                        } else {
                            clearInterval(hintInterval);
                        }
                    }, 50);
                } else if (!member.location_hint_active && group.userData.hintGlow) {
                    group.remove(group.userData.hintGlow);
                    delete group.userData.hintGlow;
                }

                // Upgrade from fallback if model available
                if (group.userData.isFallback) {
                    const key = member.name === 'MacReady' ? 'macready' : 'crew';
                    if (this.loadedModels[key] && this.loadedModels[key].scene) {
                        this.upgradeToModel(group, key);
                    }
                }

            } else {
                // Create new character
                group = new THREE.Group();
                const key = member.name === 'MacReady' ? 'macready' : 'crew';

                if (this.loadedModels[key] && this.loadedModels[key].scene) {
                    this.setupModel(group, key);
                } else {
                    this.setupFallback(group, member);
                }

                group.position.set(x, 0, z); // Models usually pivot at feet (y=0)
                group.userData.randomOffset = Math.random() * 100;

                this.scene.add(group);
                this.characters.set(member.name, group);
            }
        });

        // Remove missing characters
        for (const [name, group] of this.characters) {
            if (!updatedNames.has(name)) {
                // Cleanup mixer
                if (group.userData.mixer) {
                    this.mixers = this.mixers.filter(m => m !== group.userData.mixer);
                }
                this.scene.remove(group);
                this.characters.delete(name);
            }
        }
    }

    setupModel(group, key) {
        const data = this.loadedModels[key];
        if (!data || !data.scene) {
            // If not loaded yet or failed, we stay in fallback or wait
            group.userData.pendingModel = key;
            return;
        }

        const model = data.scene.clone();
        group.add(model);
        group.userData.isFallback = false;

        // Setup Animation
        if (data.animations && data.animations.length > 0) {
            const mixer = new THREE.AnimationMixer(model);
            group.userData.mixer = mixer;
            group.userData.animations = data.animations; // original clips
            this.mixers.push(mixer);

            this.playAnimation(group, 'Idle');
        }
    }

    setupFallback(group, member) {
        const color = member.name === 'MacReady' ? this.materials.player.color : this.materials.crew.color;
        const geometry = new THREE.BoxGeometry(0.8, 1.8, 0.8);
        const material = new THREE.MeshStandardMaterial({ color: color });
        const mesh = new THREE.Mesh(geometry, material);
        mesh.position.y = 0.9; // Box center is 0.9 up for a 1.8 unit tall box
        mesh.castShadow = true;
        group.add(mesh);
        group.userData.isFallback = true;
    }

    upgradeToModel(group, key) {
        // Remove old children
        while (group.children.length > 0) {
            group.remove(group.children[0]);
        }
        this.setupModel(group, key);
        // Reset position Y to 0 as models are feet-based usually
        group.position.y = 0;
    }

    playAnimation(group, actionName) {
        const mixer = group.userData.mixer;
        const clips = group.userData.animations;

        // Fuzzy match clips (case-insensitive, partial)
        const clip = clips.find(c => c.name.toLowerCase().includes(actionName.toLowerCase())) || clips[0];

        if (clip) {
            const action = mixer.clipAction(clip);
            if (!action.isRunning()) {
                mixer.stopAllAction();
                action.fadeIn(0.2).play();
            }
        }
    }

    updateAtmosphere(gameState) {
        // Power Loss & Fog of War Logic
        // Determine Lighting Intensity based on Power AND Room State
        let ambientIntensity = 0.6;
        let directIntensity = 0.8;
        let lightColor = 0xffffff;

        if (gameState.power_on === false) {
            ambientIntensity = 0.2;
            directIntensity = 0.3;
            lightColor = 0x8888ff; // Cold blue tint
        }

        // "Fog of War" / Room Darkness Check
        // If the player is in a dark room, dim everything significantly
        const playerRoom = gameState.location; // Location name
        const darkRooms = gameState.dark_rooms || [];

        if (darkRooms.includes(playerRoom)) {
            ambientIntensity *= 0.3; // Very dark
            directIntensity *= 0.2; // Almost no direct light
            lightColor = 0x444455; // Dark gloomy
        }

        this.scene.children.forEach(child => {
            if (child.isLight && child.type === 'AmbientLight') {
                child.intensity = ambientIntensity;
                child.color.setHex(lightColor);
            }
            if (child.isLight && child.type === 'DirectionalLight') {
                child.intensity = directIntensity;
                child.color.setHex(lightColor);
            }
        });

        // Weather: Dynamic fog based on visibility
        if (gameState.weather_detail) {
            const visibility = gameState.weather_detail.visibility;

            if (visibility < 0.7) {
                // Enable fog for poor visibility
                const fogDensity = (1.0 - visibility) * 0.05; // Scale fog density
                this.scene.fog = new THREE.FogExp2(0xcccccc, fogDensity);
            } else {
                // Clear fog
                this.scene.fog = null;
            }
        }
    }

    updatePostureIcon(group, posture) {
        // Remove existing icon if posture changed
        if (group.userData.currentPosture !== posture) {
            if (group.userData.postureIcon) {
                group.remove(group.userData.postureIcon);
                delete group.userData.postureIcon;
            }
            group.userData.currentPosture = posture;
        }

        if (!group.userData.postureIcon && posture !== 'STANDING') {
            let color = 0xffffff;
            let scale = 1.0;

            if (posture === 'CROUCHING') {
                color = 0xffdd00; // Yellow
                scale = 0.8;
            } else if (posture === 'CRAWLING') {
                color = 0xff8800; // Orange
                scale = 0.6;
            } else if (posture === 'HIDING') {
                color = 0x00ff00; // Green
                scale = 0.5;
            }

            const geometry = new THREE.SphereGeometry(0.2 * scale, 8, 8);
            const material = new THREE.MeshBasicMaterial({
                color: color,
                transparent: true,
                opacity: 0.8
            });
            const icon = new THREE.Mesh(geometry, material);

            // Position above head
            icon.position.y = 2.5;

            group.add(icon);
            group.userData.postureIcon = icon;

            // Pulse animation
            const pulseInterval = setInterval(() => {
                if (icon.parent) {
                    icon.scale.setScalar(1 + Math.sin(Date.now() * 0.005) * 0.2);
                } else {
                    clearInterval(pulseInterval);
                }
            }, 50);
        }
    }

    updateDetectionAlert(group, status) {
        // Only show for a short time or persist?
        // Using userData to track if we already showed this specific event might be tough without a unique ID.
        // For now, let's just show it based on current state.

        if (status === 'detected' && !group.userData.detectionAlert) {
            const geometry = new THREE.ConeGeometry(0.3, 0.8, 4);
            const material = new THREE.MeshBasicMaterial({ color: 0xff0000 }); // Red !
            const alert = new THREE.Mesh(geometry, material);
            alert.position.y = 3.0;
            alert.rotation.x = Math.PI; // Point down
            group.add(alert);
            group.userData.detectionAlert = alert;

            // Pulse
            const pulse = setInterval(() => {
                if (alert.parent) {
                    alert.scale.setScalar(1 + Math.sin(Date.now() * 0.01) * 0.3);
                } else {
                    clearInterval(pulse);
                }
            }, 50);

        } else if (status !== 'detected' && group.userData.detectionAlert) {
            group.remove(group.userData.detectionAlert);
            delete group.userData.detectionAlert;
        }

        // Evaded Logic (Brief flash)
        if (status === 'evaded' && !group.userData.evadedFlash) {
            const geometry = new THREE.RingGeometry(0.5, 0.7, 16);
            const material = new THREE.MeshBasicMaterial({ color: 0x00ff00, side: THREE.DoubleSide });
            const flash = new THREE.Mesh(geometry, material);
            flash.position.y = 0.1;
            flash.rotation.x = -Math.PI / 2;
            group.add(flash);
            group.userData.evadedFlash = flash;

            // Remove after 1 second
            setTimeout(() => {
                if (flash.parent) group.remove(flash);
                delete group.userData.evadedFlash;
            }, 1000);
        }
    }

    centerCameraOnPlayer(gameState) {
        // Find player coords
        const player = gameState.crew.find(c => c.name === 'MacReady');
        if (player) {
            const x = player.coords[0] * this.gridScale;
            const z = player.coords[1] * this.gridScale;

            const offset = 20; // Distance of camera

            // Smooth lerp for camera
            // this.camera.position.x += ( (x + offset) - this.camera.position.x ) * 0.1;
            // this.camera.position.z += ( (z + offset) - this.camera.position.z ) * 0.1;

            // Hard snap is cleaner for now to avoid jitter
            this.camera.position.x = x + offset;
            this.camera.position.z = z + offset;

            this.camera.lookAt(x, 0, z);

            // Update detection cones relative to player position
            this.updateDetectionCones(gameState, player);
        }
    }

    updateDetectionCones(gameState, player) {
        // Identify NPCs in the same room as the player
        const playerRoom = gameState.location;
        const visibleNPCs = gameState.crew.filter(c => c.location === playerRoom && c.name !== 'MacReady');

        visibleNPCs.forEach(npc => {
            const group = this.characters.get(npc.name);
            if (!group) return;

            // If NPC has detected player, show intense cone
            // If just in room, show faint cone
            const isDetected = npc.detected_player;

            if (!group.userData.detectionCone) {
                // Create cone - smaller and more subtle
                const coneGeo = new THREE.ConeGeometry(2, 6, 16, 1, true);
                const coneMat = new THREE.MeshBasicMaterial({
                    color: 0xff0000,
                    transparent: true,
                    opacity: 0.15,
                    side: THREE.BackSide // Shows only inside, looks more like a beam
                });
                const cone = new THREE.Mesh(coneGeo, coneMat);

                // Orient cone to point forward
                cone.rotation.x = -Math.PI / 2;
                cone.position.y = 1.0;
                cone.position.z = 3.0; // Offset forward

                group.add(cone);
                group.userData.detectionCone = cone;
            }

            const cone = group.userData.detectionCone;

            // Point cone at player
            const playerGroup = this.characters.get('MacReady');
            if (playerGroup) {
                cone.lookAt(playerGroup.position.x, 0.5, playerGroup.position.z);
            }

            // Adjust intensity
            if (isDetected) {
                cone.material.opacity = 0.3 + Math.sin(Date.now() * 0.01) * 0.1; // Pulse
                cone.scale.set(1, 1, 1.5); // Extend range
            } else {
                cone.material.opacity = 0.1;
                cone.scale.set(1, 1, 1);
            }

        });

        // Remove cones from NPCs no longer in room or valid
        this.characters.forEach((group, name) => {
            if (name === 'MacReady') return;
            // Check if still should have cone
            const npc = gameState.crew.find(c => c.name === name);
            if (!npc || npc.location !== playerRoom) {
                if (group.userData.detectionCone) {
                    group.remove(group.userData.detectionCone);
                    delete group.userData.detectionCone;
                }
            }
        });
    }

    handleStealthEvent(data) {
        // Handle visual feedback for stealth events
        const outcome = data.outcome;
        const playerGroup = this.characters.get('MacReady');

        if (outcome === 'detected') {
            // Red Flash on Camera or Screen overlay
            const flash = document.createElement('div');
            flash.style.position = 'absolute';
            flash.style.top = '0';
            flash.style.left = '0';
            flash.style.width = '100%';
            flash.style.height = '100%';
            flash.style.backgroundColor = 'rgba(255, 0, 0, 0.3)';
            flash.style.pointerEvents = 'none';
            flash.style.zIndex = '9999';
            document.body.appendChild(flash);

            setTimeout(() => {
                flash.remove();
            }, 500);

            // Shake camera
            if (this.camera) {
                const originalPos = this.camera.position.clone();
                let shakeDuration = 500;
                let startTime = Date.now();

                const shake = () => {
                    const elapsed = Date.now() - startTime;
                    if (elapsed < shakeDuration) {
                        this.camera.position.x = originalPos.x + (Math.random() - 0.5) * 1;
                        this.camera.position.z = originalPos.z + (Math.random() - 0.5) * 1;
                        requestAnimationFrame(shake);
                    } else {
                        this.camera.position.copy(originalPos);
                    }
                };
                shake();
            }

        } else if (outcome === 'evaded') {
            // Green Glow on Player
            if (playerGroup) {
                const glowGeo = new THREE.SphereGeometry(1.5, 32, 32);
                const glowMat = new THREE.MeshBasicMaterial({
                    color: 0x00ff00,
                    transparent: true,
                    opacity: 0.3,
                    side: THREE.BackSide
                });
                const glow = new THREE.Mesh(glowGeo, glowMat);
                playerGroup.add(glow);

                setTimeout(() => {
                    playerGroup.remove(glow);
                }, 1000);
            }
        }
    }
}
