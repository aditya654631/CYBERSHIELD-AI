'use strict';

const { WINDOWS_MS } = require('./constants');

/**
 * Partitions signals into temporal lookback windows relative to refTimeMs.
 * 
 * Strict rule:
 * signal.eventTimeMs <= refTimeMs
 * AND
 * signal.eventTimeMs >= (refTimeMs - windowMs)
 */
function partitionSignalsByWindow(signals, refTimeMs) {
    const partitioned = {
        '1h': [],
        '6h': [],
        '24h': [],
        '7d': [],
        '30d': []
    };

    for (const s of signals) {
        const ageMs = refTimeMs - s.eventTimeMs;
        if (ageMs < 0) {
            // Future event relative to reference time - strictly ignored
            continue;
        }

        if (ageMs <= WINDOWS_MS['1h']) {
            partitioned['1h'].push(s);
        }
        if (ageMs <= WINDOWS_MS['6h']) {
            partitioned['6h'].push(s);
        }
        if (ageMs <= WINDOWS_MS['24h']) {
            partitioned['24h'].push(s);
        }
        if (ageMs <= WINDOWS_MS['7d']) {
            partitioned['7d'].push(s);
        }
        if (ageMs <= WINDOWS_MS['30d']) {
            partitioned['30d'].push(s);
        }
    }

    return partitioned;
}

module.exports = {
    partitionSignalsByWindow
};
