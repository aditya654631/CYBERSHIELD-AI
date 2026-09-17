/**
 * CyberShield AI — Deterministic Layered Graph Layout Engine
 * 
 * Implements a hierarchical layered layout (Sugiyama-style) tailored for
 * financial transaction networks:
 *   [Victim / Source] -> [Intermediary Layers] -> [Terminal Accounts] -> [ATM Cash-Out Terminals]
 * 
 * Features:
 * 1. Deterministic coordinate generation without random jitter.
 * 2. Robust cycle detection: breaks feedback cycles without infinite recursion.
 * 3. Preserves multi-hop branches and merges with vertical clearance.
 * 4. Barycentric ordering to minimize edge crossings.
 * 5. Handles disconnected components in distinct vertical tracks.
 * 6. Generous node and label spacing to prevent label collisions.
 */

export interface LayoutNodeInput {
  id: string;
  is_source?: boolean;
  node_type?: string;
  hop_level?: number;
  [key: string]: any;
}

export interface LayoutEdgeInput {
  id: string;
  source: string;
  target: string;
  [key: string]: any;
}

export interface LayeredLayoutOptions {
  layerGapX?: number;   // Horizontal distance between successive hop layers
  nodeGapY?: number;    // Vertical distance between nodes in the same layer
  startX?: number;      // Left margin
  startY?: number;      // Top margin
  componentGapY?: number; // Vertical gap between disconnected graph components
}

export interface LayoutResult {
  positions: Record<string, { x: number; y: number }>;
  layers: Record<string, number>;
  bounds: {
    minX: number;
    maxX: number;
    minY: number;
    maxY: number;
    width: number;
    height: number;
  };
}

/**
 * Computes deterministic layered positions for Cytoscape nodes.
 */
export function computeLayeredPositions(
  nodes: LayoutNodeInput[],
  edges: LayoutEdgeInput[],
  options: LayeredLayoutOptions = {}
): LayoutResult {
  const layerGapX = options.layerGapX ?? 270;
  const nodeGapY = options.nodeGapY ?? 115;
  const startX = options.startX ?? 80;
  const startY = options.startY ?? 90;
  const componentGapY = options.componentGapY ?? 130;

  if (!nodes || nodes.length === 0) {
    return {
      positions: {},
      layers: {},
      bounds: { minX: 0, maxX: 0, minY: 0, maxY: 0, width: 0, height: 0 },
    };
  }

  // 1. Index nodes and valid edges
  const nodeIds = new Set<string>(nodes.map((n) => String(n.id)));
  const nodeMap = new Map<string, LayoutNodeInput>(nodes.map((n) => [String(n.id), n]));

  // Adjacency lists for directed graph and undirected connectivity
  const forwardAdj = new Map<string, string[]>();
  const reverseAdj = new Map<string, string[]>();
  const undirectedAdj = new Map<string, string[]>();
  const inDegree = new Map<string, number>();

  nodeIds.forEach((id) => {
    forwardAdj.set(id, []);
    reverseAdj.set(id, []);
    undirectedAdj.set(id, []);
    inDegree.set(id, 0);
  });

  edges.forEach((e) => {
    const src = String(e.source);
    const tgt = String(e.target);
    if (nodeIds.has(src) && nodeIds.has(tgt) && src !== tgt) {
      forwardAdj.get(src)!.push(tgt);
      reverseAdj.get(tgt)!.push(src);
      undirectedAdj.get(src)!.push(tgt);
      undirectedAdj.get(tgt)!.push(src);
      inDegree.set(tgt, (inDegree.get(tgt) || 0) + 1);
    }
  });

  // 2. Partition into Weakly Connected Components
  const visitedComponents = new Set<string>();
  const components: string[][] = [];

  // Prioritize source/victim nodes as first components
  const sortedNodeIds = Array.from(nodeIds).sort((a, b) => {
    const nodeA = nodeMap.get(a);
    const nodeB = nodeMap.get(b);
    const isSourceA = nodeA?.is_source || nodeA?.node_type === 'victim' ? 1 : 0;
    const isSourceB = nodeB?.is_source || nodeB?.node_type === 'victim' ? 1 : 0;
    if (isSourceA !== isSourceB) return isSourceB - isSourceA;
    return a.localeCompare(b, undefined, { numeric: true });
  });

  for (const id of sortedNodeIds) {
    if (!visitedComponents.has(id)) {
      const comp: string[] = [];
      const queue = [id];
      visitedComponents.add(id);

      while (queue.length > 0) {
        const curr = queue.shift()!;
        comp.push(curr);
        for (const neighbor of undirectedAdj.get(curr) || []) {
          if (!visitedComponents.has(neighbor)) {
            visitedComponents.add(neighbor);
            queue.push(neighbor);
          }
        }
      }
      components.push(comp);
    }
  }

  // 3. Process each component and assign layers
  const positions: Record<string, { x: number; y: number }> = {};
  const layers: Record<string, number> = {};
  let currentComponentOffsetY = startY;

  for (const compNodes of components) {
    const compSet = new Set(compNodes);

    // Identify roots for this component
    let roots = compNodes.filter((id) => {
      const n = nodeMap.get(id);
      return (n?.is_source || n?.node_type === 'victim') || inDegree.get(id) === 0;
    });

    if (roots.length === 0) {
      // If cycle with no in-degree 0, pick node with smallest ID deterministically
      roots = [compNodes.sort((a, b) => a.localeCompare(b, undefined, { numeric: true }))[0]];
    }

    // Detect cycles and assign layers using BFS with cycle detection
    const compLayers = new Map<string, number>();
    roots.forEach((r) => compLayers.set(r, 0));

    // Queue contains { id, layer }
    const queue: { id: string; layer: number }[] = roots.map((r) => ({ id: r, layer: 0 }));
    const visitedInQueue = new Set<string>();
    const recursionPath = new Set<string>();

    while (queue.length > 0) {
      const { id, layer } = queue.shift()!;
      if (visitedInQueue.has(id)) {
        // Only update layer if we found a longer path (longest-path layer assignment for DAGs)
        // Guard against cycles: do not increase layer if node is part of a cycle
        continue;
      }
      visitedInQueue.add(id);

      const neighbors = forwardAdj.get(id) || [];
      for (const nbr of neighbors) {
        if (!compSet.has(nbr)) continue;

        const currentL = compLayers.get(nbr) ?? -1;
        const nextL = Math.max(currentL, layer + 1);

        // If nbr is not yet assigned or found a longer forward path
        if (currentL < nextL) {
          compLayers.set(nbr, nextL);
        }

        // Avoid infinite re-queuing in cycles
        if (!visitedInQueue.has(nbr)) {
          queue.push({ id: nbr, layer: nextL });
        }
      }
    }

    // Handle any unreached nodes in component
    compNodes.forEach((id) => {
      if (!compLayers.has(id)) {
        const n = nodeMap.get(id);
        if (typeof n?.hop_level === 'number' && n.hop_level >= 0) {
          compLayers.set(id, n.hop_level);
        } else {
          compLayers.set(id, 1);
        }
      }
    });

    // Special treatment for ATM and predicted cluster nodes: push them to the end of their branch
    compNodes.forEach((id) => {
      const n = nodeMap.get(id);
      if (n?.node_type === 'atm' || n?.node_type === 'cluster') {
        const preds = reverseAdj.get(id) || [];
        if (preds.length > 0) {
          const maxPredLayer = Math.max(...preds.map((p) => compLayers.get(p) ?? 0));
          compLayers.set(id, maxPredLayer + 1);
        }
      }
    });

    // Group component nodes by layer
    const layerBuckets = new Map<number, string[]>();
    compNodes.forEach((id) => {
      const l = compLayers.get(id)!;
      layers[id] = l;
      if (!layerBuckets.has(l)) {
        layerBuckets.set(l, []);
      }
      layerBuckets.get(l)!.push(id);
    });

    const sortedLayerIndices = Array.from(layerBuckets.keys()).sort((a, b) => a - b);

    // Barycentric Ordering within layers to minimize edge crossings
    sortedLayerIndices.forEach((layerIdx) => {
      const bucket = layerBuckets.get(layerIdx)!;
      if (bucket.length <= 1) return;

      if (layerIdx === 0) {
        // Sort root nodes deterministically
        bucket.sort((a, b) => a.localeCompare(b, undefined, { numeric: true }));
      } else {
        // Sort by average position of predecessors
        bucket.sort((a, b) => {
          const predsA = reverseAdj.get(a) || [];
          const predsB = reverseAdj.get(b) || [];

          const avgA =
            predsA.length > 0
              ? predsA.reduce((sum, p) => sum + (positions[p]?.y ?? 0), 0) / predsA.length
              : 0;
          const avgB =
            predsB.length > 0
              ? predsB.reduce((sum, p) => sum + (positions[p]?.y ?? 0), 0) / predsB.length
              : 0;

          if (Math.abs(avgA - avgB) > 0.001) {
            return avgA - avgB;
          }
          return a.localeCompare(b, undefined, { numeric: true });
        });
      }
    });

    // Calculate vertical centering for this component
    let maxNodesInAnyLayer = 1;
    sortedLayerIndices.forEach((l) => {
      maxNodesInAnyLayer = Math.max(maxNodesInAnyLayer, layerBuckets.get(l)!.length);
    });

    const compTotalHeight = (maxNodesInAnyLayer - 1) * nodeGapY;

    // Assign final coordinates for component
    sortedLayerIndices.forEach((layerIdx) => {
      const bucket = layerBuckets.get(layerIdx)!;
      const layerHeight = (bucket.length - 1) * nodeGapY;
      const layerOffsetY = currentComponentOffsetY + (compTotalHeight - layerHeight) / 2;

      bucket.forEach((nodeId, idxInLayer) => {
        positions[nodeId] = {
          x: startX + layerIdx * layerGapX,
          y: layerOffsetY + idxInLayer * nodeGapY,
        };
      });
    });

    // Advance Y offset for the next disconnected component
    currentComponentOffsetY += Math.max(compTotalHeight, nodeGapY) + componentGapY;
  }

  // Calculate overall layout bounding box
  let minX = Infinity;
  let maxX = -Infinity;
  let minY = Infinity;
  let maxY = -Infinity;

  Object.values(positions).forEach((pos) => {
    minX = Math.min(minX, pos.x);
    maxX = Math.max(maxX, pos.x);
    minY = Math.min(minY, pos.y);
    maxY = Math.max(maxY, pos.y);
  });

  return {
    positions,
    layers,
    bounds: {
      minX: Number.isFinite(minX) ? minX : 0,
      maxX: Number.isFinite(maxX) ? maxX : 0,
      minY: Number.isFinite(minY) ? minY : 0,
      maxY: Number.isFinite(maxY) ? maxY : 0,
      width: Number.isFinite(maxX - minX) ? maxX - minX : 0,
      height: Number.isFinite(maxY - minY) ? maxY - minY : 0,
    },
  };
}
