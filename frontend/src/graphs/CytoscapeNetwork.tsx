import React, { useEffect, useRef, useState, useCallback } from 'react';
import cytoscape from 'cytoscape';
import { CytoscapeNodeData, CytoscapeEdgeData, GraphData } from '../types';
import { ZoomIn, ZoomOut, RotateCcw, Scan, Maximize2, Minimize2, Info } from 'lucide-react';
import { computeLayeredPositions } from './layeredLayout';

import { formatSafeDisplayLabel, computeBoundedEdgeWidth } from './graphUtils';
export { formatSafeDisplayLabel, computeBoundedEdgeWidth };

interface CytoscapeNetworkProps {
  graphData: GraphData;
  onSelectNode: (nodeData: CytoscapeNodeData | null) => void;
  selectedNodeId?: string | null;
  isFullscreen?: boolean;
  onToggleFullscreen?: () => void;
}

export const CytoscapeNetwork: React.FC<CytoscapeNetworkProps> = ({
  graphData,
  onSelectNode,
  selectedNodeId,
  isFullscreen = false,
  onToggleFullscreen,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<cytoscape.Core | null>(null);
  const [showLegend, setShowLegend] = useState(true);

  // Re-layout & fit with bounded zoom
  const applyLayoutAndFit = useCallback((cyInstance: cytoscape.Core) => {
    const rawNodes = graphData.nodes.map((n) => n.data);
    const rawEdges = graphData.edges.map((e) => e.data);

    const layoutRes = computeLayeredPositions(rawNodes, rawEdges, {
      layerGapX: 270,
      nodeGapY: 115,
      startX: 90,
      startY: 100,
    });

    // Apply preset positions
    cyInstance.layout({
      name: 'preset',
      positions: layoutRes.positions,
      fit: false,
    }).run();

    // Perform bounded fit so small graphs don't overzoom and large graphs stay framed
    cyInstance.fit(undefined, 45);
    const currentZoom = cyInstance.zoom();
    if (currentZoom > 1.25) {
      cyInstance.zoom(1.25);
      cyInstance.center();
    } else if (currentZoom < 0.45) {
      cyInstance.zoom(0.45);
      cyInstance.center();
    }
  }, [graphData]);

  // Main Cytoscape Lifecycle
  useEffect(() => {
    if (!containerRef.current) return;

    // Convert graph elements
    const elements: any[] = [];

    graphData.nodes.forEach((n) => {
      const isMuleIndicator = Boolean(n.data.is_potential_mule_indicator);
      const safeDisplay = formatSafeDisplayLabel(
        n.data.label,
        n.data.node_type,
        n.data.is_source,
        n.data.masked_id,
        isMuleIndicator
      );

      elements.push({
        group: 'nodes',
        data: {
          ...n.data,
          display_label: safeDisplay,
          is_potential_mule_indicator: isMuleIndicator,
        },
      });
    });

    graphData.edges.forEach((e) => {
      const edgeAmt = Number(e.data.amount || e.data.total_amount || 0);
      const edgeLabel = e.data.label || `${e.data.channel || 'Transfer'} • ₹${edgeAmt.toLocaleString('en-IN')}`;
      const boundedWidth = computeBoundedEdgeWidth(edgeAmt);

      elements.push({
        group: 'edges',
        data: {
          ...e.data,
          edge_label: edgeLabel,
          edge_width: boundedWidth,
        },
      });
    });

    const cy = cytoscape({
      container: containerRef.current,
      elements,
      boxSelectionEnabled: false,
      autounselectify: false,
      style: [
        {
          selector: 'node',
          style: {
            'background-color': '#f1f5f9',
            'border-width': 2.5,
            'border-color': '#64748b',
            'label': 'data(display_label)',
            'color': '#0f172a',
            'font-size': '10px',
            'font-weight': 600,
            'font-family': 'Inter, system-ui, sans-serif',
            'text-valign': 'bottom',
            'text-margin-y': 7,
            'text-wrap': 'wrap',
            'text-max-width': '135px',
            'text-outline-width': 2.5,
            'text-outline-color': '#ffffff',
            'text-outline-opacity': 0.95,
            'width': 44,
            'height': 44,
            'transition-property': 'background-color, border-color, width, height, border-width',
            'transition-duration': 0.2,
          },
        },
        // Role 1: Victim / Source Account
        {
          selector: 'node[node_type = "victim"], node[?is_source]',
          style: {
            'background-color': '#e0f2fe',
            'border-color': '#0284c7',
            'border-width': 3,
            'shape': 'ellipse',
            'width': 48,
            'height': 48,
          },
        },
        // Role 2: Regular Account
        {
          selector: 'node[node_type = "account"]',
          style: {
            'background-color': '#f8fafc',
            'border-color': '#64748b',
            'shape': 'roundrectangle',
          },
        },
        // Role 3: Intermediary Account
        {
          selector: 'node[node_type = "intermediary"], node[?is_intermediary]',
          style: {
            'background-color': '#fef3c7',
            'border-color': '#d97706',
            'border-width': 3,
            'shape': 'roundrectangle',
            'width': 46,
            'height': 46,
          },
        },
        // Role 4: Terminal Recipient / Sink (Normal sink remains terminal rectangle)
        {
          selector: 'node[node_type = "sink"], node[?is_sink]',
          style: {
            'background-color': '#f3e8ff',
            'border-color': '#7c3aed',
            'border-width': 3,
            'shape': 'roundrectangle',
            'width': 46,
            'height': 46,
          },
        },
        // Role 5: Potential Mule Indicator (Under Review) - Red Diamond ONLY when is_potential_mule_indicator === true
        {
          selector: 'node[?is_potential_mule_indicator]',
          style: {
            'background-color': '#ffe4e6',
            'border-color': '#e11d48',
            'border-width': 3,
            'shape': 'diamond',
            'width': 48,
            'height': 48,
          },
        },
        // Role 6: ATM Cash-Out Endpoint
        {
          selector: 'node[node_type = "atm"]',
          style: {
            'background-color': '#d1fae5',
            'border-color': '#059669',
            'border-width': 3.5,
            'shape': 'hexagon',
            'width': 52,
            'height': 52,
            'color': '#065f46',
            'font-weight': 700,
          },
        },
        // Role 7: Predicted Cash-Out Zone (Advisory)
        {
          selector: 'node[node_type = "cluster"]',
          style: {
            'background-color': '#e0e7ff',
            'border-color': '#4338ca',
            'border-style': 'dashed',
            'border-width': 3,
            'shape': 'octagon',
            'width': 54,
            'height': 54,
            'color': '#3730a3',
          },
        },
        // Base Edge Styling
        {
          selector: 'edge',
          style: {
            'width': 'data(edge_width)',
            'line-color': '#94a3b8',
            'target-arrow-color': '#94a3b8',
            'target-arrow-shape': 'triangle',
            'arrow-scale': 1.25,
            'curve-style': 'bezier',
            'label': 'data(edge_label)',
            'font-size': '8.5px',
            'font-weight': 500,
            'color': '#1e293b',
            'text-rotation': 'autorotate',
            'text-margin-y': -9,
            'text-background-color': '#ffffff',
            'text-background-opacity': 0.95,
            'text-background-padding': '3px',
            'text-background-shape': 'roundrectangle',
            'text-border-color': '#cbd5e1',
            'text-border-width': 1,
            'text-border-opacity': 0.85,
          },
        },
        // ATM Cash-Out Edge
        {
          selector: 'edge[channel = "ATM Cash-Out"]',
          style: {
            'line-color': '#10b981',
            'target-arrow-color': '#10b981',
            'line-style': 'solid',
          },
        },
        // Suspicious / Multi-hop Edge
        {
          selector: 'edge[?is_suspicious]',
          style: {
            'line-color': '#f43f5e',
            'target-arrow-color': '#f43f5e',
            'line-style': 'solid',
          },
        },
        // Obvious Selected-Node Styling
        {
          selector: 'node:selected',
          style: {
            'border-color': '#2563eb',
            'border-width': 4.5,
            'overlay-color': '#93c5fd',
            'overlay-opacity': 0.35,
            'overlay-padding': 6,
          },
        },
      ],
    });

    // Event Bindings
    cy.on('tap', 'node', (evt) => {
      const node = evt.target;
      onSelectNode(node.data());
    });

    cy.on('tap', (evt) => {
      if (evt.target === cy) {
        onSelectNode(null);
      }
    });

    cyRef.current = cy;

    // Apply the deterministic layered layout
    applyLayoutAndFit(cy);

    // Attach ResizeObserver to container to call cy.resize() smoothly
    // NOTE: Does NOT call cy.fit() on resize so user's chosen view/pan is preserved!
    const ro = new ResizeObserver(() => {
      if (cyRef.current) {
        cyRef.current.resize();
      }
    });

    ro.observe(containerRef.current);

    return () => {
      ro.disconnect();
      cy.destroy();
      cyRef.current = null;
    };
  }, [graphData, applyLayoutAndFit, onSelectNode]);

  // Synchronize selection changes with Cytoscape canvas
  useEffect(() => {
    if (!cyRef.current) return;
    if (selectedNodeId) {
      const targetNode = cyRef.current.$id(selectedNodeId);
      if (targetNode.length > 0 && !targetNode.selected()) {
        cyRef.current.$(':selected').unselect();
        targetNode.select();
      }
    } else {
      cyRef.current.$(':selected').unselect();
    }
  }, [selectedNodeId]);

  // Canvas Control Handlers
  const handleZoomIn = () => {
    if (!cyRef.current) return;
    cyRef.current.zoom({
      level: cyRef.current.zoom() * 1.25,
      renderedPosition: {
        x: cyRef.current.width() / 2,
        y: cyRef.current.height() / 2,
      },
    });
  };

  const handleZoomOut = () => {
    if (!cyRef.current) return;
    cyRef.current.zoom({
      level: cyRef.current.zoom() * 0.8,
      renderedPosition: {
        x: cyRef.current.width() / 2,
        y: cyRef.current.height() / 2,
      },
    });
  };

  const handleFit = () => {
    if (!cyRef.current) return;
    cyRef.current.fit(undefined, 45);
    const z = cyRef.current.zoom();
    if (z > 1.25) {
      cyRef.current.zoom(1.25);
      cyRef.current.center();
    }
  };

  const handleReset = () => {
    if (!cyRef.current) return;
    applyLayoutAndFit(cyRef.current);
  };

  return (
    <div
      className={`relative w-full bg-[#f8fafc] rounded-lg border border-[#DCE5F0] overflow-hidden transition-all duration-200 ${
        isFullscreen
          ? 'fixed inset-0 z-50 h-screen w-screen rounded-none'
          : 'h-[460px] sm:h-[580px] shadow-xs'
      }`}
    >
      {/* Cytoscape Canvas Container */}
      <div
        ref={containerRef}
        className="w-full h-full cursor-grab active:cursor-grabbing focus:outline-hidden"
        tabIndex={0}
        role="region"
        aria-label="Interactive transaction network graph. Use mouse or controls to zoom, pan, and select entities."
      />

      {/* Control Bar: Zoom In, Zoom Out, Fit, Reset, Fullscreen */}
      <div
        className="absolute top-3 sm:top-4 right-3 sm:right-4 flex items-center space-x-1.5 bg-white/95 backdrop-blur-xs p-1.5 rounded-md border border-[#DCE5F0] shadow-xs z-10"
        role="toolbar"
        aria-label="Graph viewport controls"
      >
        <button
          onClick={handleZoomIn}
          title="Zoom in"
          aria-label="Zoom in"
          className="p-1.5 text-slate-600 hover:text-blue-600 hover:bg-blue-50 rounded transition-colors focus:outline-hidden focus:ring-2 focus:ring-blue-500"
        >
          <ZoomIn className="w-4 h-4" />
        </button>
        <button
          onClick={handleZoomOut}
          title="Zoom out"
          aria-label="Zoom out"
          className="p-1.5 text-slate-600 hover:text-blue-600 hover:bg-blue-50 rounded transition-colors focus:outline-hidden focus:ring-2 focus:ring-blue-500"
        >
          <ZoomOut className="w-4 h-4" />
        </button>
        <button
          onClick={handleFit}
          title="Fit entire graph"
          aria-label="Fit entire graph"
          className="p-1.5 text-slate-600 hover:text-blue-600 hover:bg-blue-50 rounded transition-colors focus:outline-hidden focus:ring-2 focus:ring-blue-500"
        >
          <Scan className="w-4 h-4" />
        </button>
        <button
          onClick={handleReset}
          title="Reset layout and view"
          aria-label="Reset layout and view"
          className="p-1.5 text-slate-600 hover:text-blue-600 hover:bg-blue-50 rounded transition-colors focus:outline-hidden focus:ring-2 focus:ring-blue-500"
        >
          <RotateCcw className="w-4 h-4" />
        </button>
        {onToggleFullscreen && (
          <button
            onClick={onToggleFullscreen}
            title={isFullscreen ? 'Exit expanded view' : 'Expand workspace'}
            aria-label={isFullscreen ? 'Exit expanded view' : 'Expand workspace'}
            className="p-1.5 text-slate-600 hover:text-blue-600 hover:bg-blue-50 rounded transition-colors border-l border-slate-200 pl-2 focus:outline-hidden focus:ring-2 focus:ring-blue-500"
          >
            {isFullscreen ? <Minimize2 className="w-4 h-4 text-blue-600" /> : <Maximize2 className="w-4 h-4" />}
          </button>
        )}
      </div>

      {/* Collapsible Legend Overlay */}
      <div className="absolute bottom-3 left-3 z-10">
        {showLegend ? (
          <div className="bg-white/95 backdrop-blur-xs p-2.5 rounded-md border border-[#DCE5F0] shadow-xs text-[11px] space-y-1.5 max-w-xs">
            <div className="flex items-center justify-between gap-3 pb-1 border-b border-slate-100">
              <span className="font-bold text-slate-700 uppercase tracking-wider text-[10px]">Entity Roles</span>
              <button
                onClick={() => setShowLegend(false)}
                className="text-slate-400 hover:text-slate-600 text-[10px]"
                aria-label="Hide legend"
              >
                Hide
              </button>
            </div>
            <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-slate-600">
              <div className="flex items-center space-x-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-[#0284c7] shrink-0"></span>
                <span>Victim Account</span>
              </div>
              <div className="flex items-center space-x-1.5">
                <span className="w-2.5 h-2.5 rounded-xs bg-[#d97706] shrink-0"></span>
                <span>Intermediary</span>
              </div>
              <div className="flex items-center space-x-1.5">
                <span className="w-2.5 h-2.5 rotate-45 bg-[#e11d48] shrink-0"></span>
                <span>Potential Mule Indicator / Under Review</span>
              </div>
              <div className="flex items-center space-x-1.5">
                <span className="w-2.5 h-2.5 rounded-xs bg-[#7c3aed] shrink-0"></span>
                <span>Terminal Recipient</span>
              </div>
              <div className="flex items-center space-x-1.5 col-span-2">
                <span className="w-2.5 h-2.5 bg-[#059669] shrink-0 clip-hexagon"></span>
                <span className="text-emerald-700 font-semibold">ATM Cash-Out Terminal</span>
              </div>
            </div>
          </div>
        ) : (
          <button
            onClick={() => setShowLegend(true)}
            className="flex items-center space-x-1 bg-white/95 backdrop-blur-xs px-2 py-1 rounded-md border border-[#DCE5F0] shadow-xs text-xs text-slate-600 hover:text-blue-600 focus:outline-hidden focus:ring-2 focus:ring-blue-500"
            aria-label="Show graph legend"
          >
            <Info className="w-3.5 h-3.5" />
            <span>Legend</span>
          </button>
        )}
      </div>

      {/* Neutral Legal & Causal Disclaimer Badge */}
      <div className="hidden sm:block absolute bottom-3 right-3 z-10 text-[10px] text-slate-500 bg-white/90 backdrop-blur-xs px-2 py-0.5 rounded border border-slate-200">
        Directed flow reflects recorded telemetry • Indicators do not establish legal culpability
      </div>
    </div>
  );
};
