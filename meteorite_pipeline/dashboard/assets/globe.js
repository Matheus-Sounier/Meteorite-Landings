(function () {
    const DETAIL_LIMIT = 30;
    const INDIVIDUAL_POINT_ALTITUDE = 1.85;

    function escapeHtml(value) {
        return String(value ?? "").replace(/[&<>"']/g, function (character) {
            return {
                "&": "&amp;",
                "<": "&lt;",
                ">": "&gt;",
                '"': "&quot;",
                "'": "&#39;",
            }[character];
        });
    }

    function pointLabel(point) {
        return [
            '<div class="globe-tooltip">',
            `<strong>${escapeHtml(point.name)}</strong>`,
            `<span>${escapeHtml(point.fall)} · ${escapeHtml(point.recclass)}</span>`,
            `<span>ID ${escapeHtml(point.id)} · ${escapeHtml(point.mass_g ?? "Unknown")} g</span>`,
            `<span>${Number(point.reclat).toFixed(4)}, ${Number(point.reclong).toFixed(4)}</span>`,
            "</div>",
        ].join("");
    }

    function hexCounts(hex) {
        const counts = { Fell: 0, Found: 0 };
        hex.points.forEach((point) => {
            if (point.fall === "Fell" || point.fall === "Found") counts[point.fall] += 1;
        });
        return counts;
    }

    function hexColor(hex) {
        const { Fell, Found } = hexCounts(hex);
        const total = Math.max(1, Fell + Found);
        const ratio = Found / total;
        const fellColor = [19, 124, 114];
        const foundColor = [209, 109, 85];
        return `#${fellColor.map((value, index) =>
            Math.round(value + (foundColor[index] - value) * ratio).toString(16).padStart(2, "0")
        ).join("")}`;
    }

    function normalizedLongitude(longitude) {
        return ((longitude + 540) % 360) - 180;
    }

    function nearbyPoints(source, allPoints) {
        const latitudeTolerance = 0.08;
        const longitudeTolerance = latitudeTolerance / Math.max(
            0.2,
            Math.cos(source.reclat * Math.PI / 180),
        );
        return allPoints.filter((point) => {
            const longitudeDistance = Math.abs(normalizedLongitude(point.reclong - source.reclong));
            return Math.abs(point.reclat - source.reclat) <= latitudeTolerance &&
                longitudeDistance <= longitudeTolerance;
        });
    }

    window.renderMeteoriteGlobe = function (records) {
        const container = document.getElementById("meteorite-globe");
        const emptyState = document.getElementById("globe-empty-state");
        if (!container || !emptyState) return;

        let points = Array.isArray(records) ? records : [];
        if (!points.length) {
            container.style.display = "none";
            emptyState.textContent = "No valid coordinates in this view";
            emptyState.style.display = "grid";
            return;
        }

        if (typeof window.Globe !== "function") {
            container.style.display = "none";
            emptyState.textContent = "The 3D globe could not load. Check the network connection and WebGL support.";
            emptyState.style.display = "grid";
            return;
        }

        emptyState.style.display = "none";
        container.style.display = "block";

        let globe = container.globeInstance;
        if (!globe) {
            container.replaceChildren();
            globe = new window.Globe(container, {
                rendererConfig: { antialias: false, powerPreference: "low-power" },
                waitForGlobeReady: true,
                animateIn: true,
            })
                .width(container.clientWidth)
                .height(container.clientHeight)
                .backgroundColor("#050a10")
                .globeImageUrl("https://unpkg.com/three-globe/example/img/earth-blue-marble.jpg")
                .showAtmosphere(true)
                .atmosphereColor("#8bb7ae")
                .atmosphereAltitude(0.1)
                .pointsData([])
                .pointLat((point) => point._displayLat ?? point.reclat)
                .pointLng((point) => point._displayLng ?? point.reclong)
                .pointColor((point) => point.fall === "Fell" ? "#137c72" : "#d16d55")
                .pointRadius(0.28)
                .pointAltitude(0.006)
                .pointResolution(5)
                .pointLabel(pointLabel)
                .pointsMerge(false)
                .pointsTransitionDuration(0)
                .pathsData([])
                .pathPoints((path) => path.points)
                .pathPointLat((coordinate) => coordinate[0])
                .pathPointLng((coordinate) => coordinate[1])
                .pathColor(() => "#607875")
                .pathStroke(0.025)
                .pathTransitionDuration(120)
                .hexBinPointsData([])
                .hexBinPointLat("reclat")
                .hexBinPointLng("reclong")
                .hexBinPointWeight(() => 1)
                .hexBinResolution(1)
                .hexBinMerge(false)
                .hexMargin(0.12)
                .hexAltitude(({ sumWeight }) => Math.min(0.1, 0.008 + Math.log2(sumWeight + 1) * 0.012))
                .hexTopColor(hexColor)
                .hexSideColor(hexColor)
                .hexTransitionDuration(150)
                .hexLabel((hex) => {
                    const counts = hexCounts(hex);
                    return [
                        '<div class="globe-tooltip">',
                        `<strong>${hex.points.length} records in this cell</strong>`,
                        `<span>Found: ${counts.Found}</span>`,
                        `<span>Fell: ${counts.Fell}</span>`,
                        "<span>Click to inspect records</span>",
                        "</div>",
                    ].join("");
                });

            let detailRecords = null;
            const detailControls = document.getElementById("globe-detail-controls");
            const detailSummary = document.getElementById("globe-detail-summary");
            const closeButton = document.getElementById("globe-detail-close");

            function clearDetail() {
                detailRecords = null;
                globe.pathsData([]);
                detailControls.style.display = "none";
            }

            function updateLayer(altitude) {
                if (detailRecords) {
                    if (altitude > 2.35) clearDetail();
                    else return;
                }

                const closeView = altitude <= INDIVIDUAL_POINT_ALTITUDE;
                globe
                    .hexBinPointsData(closeView ? [] : points)
                    .pointsData(closeView ? points : []);
            }

            function currentAltitude() {
                return globe.camera().position.length() / globe.getGlobeRadius() - 1;
            }

            function showSpiderfy(records, center, description) {
                if (!records.length || detailRecords) return;
                const visibleRecords = records.slice(0, DETAIL_LIMIT);
                const origin = center || {
                    lat: records.reduce((sum, point) => sum + point.reclat, 0) / records.length,
                    lng: records.reduce((sum, point) => sum + point.reclong, 0) / records.length,
                };
                const centerLat = Number(origin.lat);
                const centerLng = Number(origin.lng);
                const longitudeScale = Math.max(0.2, Math.cos(centerLat * Math.PI / 180));
                const spread = visibleRecords.map((point, index) => {
                    const ring = Math.floor(index / 12);
                    const slot = index % 12;
                    const countOnRing = Math.min(12, visibleRecords.length - ring * 12);
                    const angle = (2 * Math.PI * slot) / Math.max(1, countOnRing);
                    const radius = 0.3 + ring * 0.3;
                    const displayLat = Math.max(-88, Math.min(88, centerLat + Math.sin(angle) * radius));
                    const displayLng = normalizedLongitude(
                        centerLng + (Math.cos(angle) * radius) / longitudeScale,
                    );
                    return { ...point, _displayLat: displayLat, _displayLng: displayLng };
                });
                const connectors = visibleRecords.map((point, index) => ({
                    points: [
                        [point.reclat, point.reclong],
                        [spread[index]._displayLat, spread[index]._displayLng],
                    ],
                }));

                detailRecords = records;
                globe
                    .hexBinPointsData([])
                    .pointsData(spread)
                    .pathsData(connectors);
                const hiddenCount = records.length - visibleRecords.length;
                detailSummary.textContent = hiddenCount
                    ? `${description}: showing ${visibleRecords.length} of ${records.length}; zoom in for more.`
                    : `${description}: ${records.length} records. Original coordinates are shown in each tooltip.`;
                detailControls.style.display = "flex";
            }

            function handleCanvasClick(event) {
                if (detailRecords || event.target.tagName !== "CANVAS" || isDragClick()) return;
                const bounds = event.target.getBoundingClientRect();
                const clickX = event.clientX - bounds.left;
                const clickY = event.clientY - bounds.top;
                const altitude = currentAltitude();

                if (altitude <= INDIVIDUAL_POINT_ALTITUDE) {
                    let nearestPoint = null;
                    let nearestDistance = 18;
                    points.forEach((point) => {
                        const screen = globe.getScreenCoords(point.reclat, point.reclong);
                        if (screen?.x == null || screen?.y == null) return;
                        const distance = Math.hypot(screen.x - clickX, screen.y - clickY);
                        if (distance < nearestDistance) {
                            nearestDistance = distance;
                            nearestPoint = point;
                        }
                    });
                    if (nearestPoint) {
                        const matches = nearbyPoints(nearestPoint, points);
                        if (matches.length > 1) {
                            showSpiderfy(
                                matches,
                                { lat: nearestPoint.reclat, lng: nearestPoint.reclong },
                                "Nearby records",
                            );
                        }
                    }
                    return;
                }

                const sceneLayers = globe.scene().children.find((child) => child.type === "Group")?.children || [];
                const hexLayer = sceneLayers.find((layer) =>
                    layer.children?.some((mesh) => mesh.geometry?.type === "ConicPolygonGeometry"),
                );
                if (!hexLayer) return;

                let nearestHex = null;
                let nearestDistance = 24;
                hexLayer.children.forEach((mesh) => {
                    const center = mesh.__hexCenter;
                    const recordsInHex = mesh.__data?.points;
                    if (!center || !recordsInHex?.length) return;
                    const screen = globe.getScreenCoords(center[0], center[1]);
                    if (screen?.x == null || screen?.y == null) return;
                    const distance = Math.hypot(screen.x - clickX, screen.y - clickY);
                    if (distance < nearestDistance) {
                        nearestDistance = distance;
                        nearestHex = { records: recordsInHex, center: { lat: center[0], lng: center[1] } };
                    }
                });
                if (nearestHex) {
                    showSpiderfy(nearestHex.records, nearestHex.center, "Selected geographic cell");
                }
            }

            const canvas = container.querySelector("canvas");
            let pointerGesture = null;
            let ignoreClicksUntil = 0;

            function isDragClick() {
                return performance.now() < ignoreClicksUntil;
            }

            canvas.addEventListener("pointerdown", (event) => {
                if (!event.isPrimary || event.button !== 0) return;
                pointerGesture = { id: event.pointerId, x: event.clientX, y: event.clientY, dragged: false };
            }, true);
            window.addEventListener("pointermove", (event) => {
                if (!pointerGesture || event.pointerId !== pointerGesture.id) return;
                if (Math.hypot(event.clientX - pointerGesture.x, event.clientY - pointerGesture.y) > 8) {
                    pointerGesture.dragged = true;
                    ignoreClicksUntil = performance.now() + 350;
                }
            }, true);
            window.addEventListener("pointerup", (event) => {
                if (pointerGesture?.id === event.pointerId) pointerGesture = null;
            }, true);
            window.addEventListener("pointercancel", (event) => {
                if (pointerGesture?.id === event.pointerId) pointerGesture = null;
            }, true);

            globe.onHexClick((hex) => {
                if (isDragClick()) return;
                showSpiderfy(hex.points, hex.center, "Selected geographic cell");
            });
            globe.onPointClick((point) => {
                if (isDragClick()) return;
                const matches = nearbyPoints(point, points);
                if (matches.length > 1) {
                    showSpiderfy(matches, { lat: point.reclat, lng: point.reclong }, "Nearby records");
                }
            });
            container.globeCanvasClickHandler = handleCanvasClick;
            canvas.addEventListener("click", handleCanvasClick, true);
            globe.onZoom(({ altitude }) => updateLayer(altitude));
            closeButton.addEventListener("click", function () {
                clearDetail();
                updateLayer(currentAltitude());
            });
            container.refreshGlobePoints = function (nextPoints) {
                points = nextPoints;
                clearDetail();
                updateLayer(currentAltitude());
            };
            updateLayer(currentAltitude());

            const controls = globe.controls();
            controls.autoRotate = false;
            controls.enableDamping = true;
            controls.dampingFactor = 0.08;
            controls.rotateSpeed = 0.45;
            controls.minDistance = 115;
            controls.maxDistance = 360;
            globe.pointOfView({ lat: 15, lng: 8, altitude: 2.15 }, 0);

            container.globeInstance = globe;
        } else {
            container.refreshGlobePoints(points);
        }
    };
})();