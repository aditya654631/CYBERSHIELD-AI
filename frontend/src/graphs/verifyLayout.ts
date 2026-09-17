/**
 * Verification script for Phase 6 Readable Transaction Network Layout
 * Runs through all 10 fixtures and verifies layout determinism, bounds, and correctness.
 */

import { computeLayeredPositions } from './layeredLayout';
import { formatSafeDisplayLabel, computeBoundedEdgeWidth } from './graphUtils';
import { ALL_VERIFICATION_FIXTURES } from './layoutFixtures';

let totalAssertions = 0;
let passedAssertions = 0;

function assert(condition: boolean, message: string) {
  totalAssertions++;
  if (!condition) {
    console.error(`❌ FAILED: ${message}`);
    throw new Error(`Assertion failed: ${message}`);
  }
  passedAssertions++;
}

console.log('================================================================');
console.log('PHASE 6: READABLE TRANSACTION NETWORK LAYOUT VERIFICATION');
console.log('================================================================\n');

for (const [name, fixture] of Object.entries(ALL_VERIFICATION_FIXTURES)) {
  console.log(`[Testing Fixture] ${name}`);
  const startTime = performance.now();

  const rawNodes = fixture.nodes.map(n => ({
    id: n.data.id,
    hop_level: n.data.hop_level,
    is_source: n.data.is_source,
    is_sink: n.data.is_sink,
  }));

  const rawEdges = fixture.edges.map(e => ({
    id: e.data.id,
    source: e.data.source,
    target: e.data.target,
    amount: e.data.amount,
  }));

  const layout = computeLayeredPositions(rawNodes, rawEdges, {
    layerGapX: 270,
    nodeGapY: 115,
    startX: 90,
    startY: 100,
  });

  const elapsed = performance.now() - startTime;

  // 1. Node count conservation: exactly one position per input node
  const positionKeys = Object.keys(layout.positions);
  assert(
    positionKeys.length === fixture.nodes.length,
    `Fixture "${name}": Expected ${fixture.nodes.length} node positions, got ${positionKeys.length}`
  );

  // 2. Coordinate validity (finite, non-NaN)
  const posSet = new Set<string>();
  for (const [id, pos] of Object.entries(layout.positions)) {
    assert(Number.isFinite(pos.x), `Fixture "${name}" node ${id}: x position must be finite (got ${pos.x})`);
    assert(Number.isFinite(pos.y), `Fixture "${name}" node ${id}: y position must be finite (got ${pos.y})`);
    
    // 3. Collision check: No two nodes should share exact same coordinates
    const key = `${Math.round(pos.x)},${Math.round(pos.y)}`;
    assert(!posSet.has(key), `Fixture "${name}": Collision detected at coordinate (${key}) for node ${id}`);
    posSet.add(key);
  }

  // 4. Directionality check: In non-cyclic DAG components, sources should precede targets horizontally
  if (name !== 'A Cycle' && fixture.edges.length > 0) {
    for (const e of fixture.edges) {
      const srcPos = layout.positions[e.data.source];
      const dstPos = layout.positions[e.data.target];
      if (srcPos && dstPos) {
        assert(
          dstPos.x >= srcPos.x,
          `Fixture "${name}": Target node ${e.data.target} (x=${dstPos.x}) must be to the right of or aligned with source node ${e.data.source} (x=${srcPos.x})`
        );
      }
    }
  }

  // 5. Determinism check: Running layout a second time on identical inputs yields identical positions
  const secondRun = computeLayeredPositions(rawNodes, rawEdges, {
    layerGapX: 270,
    nodeGapY: 115,
    startX: 90,
    startY: 100,
  });
  for (const id of positionKeys) {
    assert(
      layout.positions[id].x === secondRun.positions[id].x &&
      layout.positions[id].y === secondRun.positions[id].y,
      `Fixture "${name}": Non-deterministic coordinates detected for node ${id}`
    );
  }

  console.log(`  ✓ Passed (${positionKeys.length} nodes, ${rawEdges.length} edges, ${elapsed.toFixed(2)}ms)`);
}

console.log('\n[Testing Visual Hierarchy & Label Helpers]');

// Test formatSafeDisplayLabel
assert(
  formatSafeDisplayLabel('', 'account', false, 'ACC••••1234') === 'Account\nACC••••1234',
  'formatSafeDisplayLabel should fallback to role and masked ID on empty label'
);
assert(
  formatSafeDisplayLabel('Primary Beneficiary', 'mule', false, 'ACC••••9999') === 'Primary Beneficiary\nACC••••9999',
  'formatSafeDisplayLabel should format multi-line label with masked ID'
);
assert(
  formatSafeDisplayLabel('Complainant', 'victim', true, 'ACC••••0001') === 'Complainant\nACC••••0001',
  'formatSafeDisplayLabel should display victim label cleanly'
);

// Test computeBoundedEdgeWidth
assert(computeBoundedEdgeWidth(0) === 2.0, 'Zero amount should have minimum bound 2.0px');
assert(computeBoundedEdgeWidth(-500) === 2.0, 'Negative amount should have minimum bound 2.0px');
assert(computeBoundedEdgeWidth(100000000) === 5.5, 'Huge amount should have maximum bound 5.5px');
const midWidth = computeBoundedEdgeWidth(50000);
assert(midWidth >= 2.0 && midWidth <= 5.5, 'Intermediate amount width should be strictly bounded between 2.0 and 5.5');

console.log(`  ✓ Visual hierarchy helpers passed`);

console.log('\n================================================================');
console.log(`ALL ASSERTIONS PASSED (${passedAssertions} / ${totalAssertions})`);
console.log('================================================================\n');
