import React, { useEffect, useRef } from 'react';
import cytoscape from 'cytoscape';
import { CytoscapeNodeData, GraphData } from '../types';
import { ZoomIn, ZoomOut, RefreshCw, Maximize2 } from 'lucide-react';

export const formatSafeDisplayLabel = (
  rawLabel?: string | null,
  nodeType?: string,
  isSource?: boolean
): string => {
  if (nodeType === 'atm') {
    return rawLabel || 'Cash-Out Terminal';
  }
  if (nodeType === 'cluster') {
    return rawLabel ? `PREDICTED ZONE: ${rawLabel}` : 'PREDICTED CASH-OUT ZONE';
  }

  if (!rawLabel || rawLabel.trim() === '') {
    return isSource || nodeType === 'victim' ? 'Victim Account' : 'Beneficiary Account';
  }
  const trimmed = rawLabel.trim();
  const lower = trimmed.toLowerCase();

  // Neutralize labels with guilt-implying or mule strings
  if (
    lower.includes('mule.recipient') ||
    lower.includes('mule.receiver') ||
    lower.includes('confirmed mule') ||
    lower === 'mule' ||
    lower === 'suspected mule'
  ) {
    return 'Beneficiary Account';
  }

  // Replace guilt-implying suffixes inside holder names
  if (lower.includes('(terminal mule)')) {
    return trimmed.replace(/\(terminal mule\)/i, '(Beneficiary / Under Review)');
  }
  if (lower.includes('(known atm cashier)')) {
    return trimmed.replace(/\(known atm cashier\)/i, '(Cashier / Under Review)');
  }

  return trimmed;
};

interface CytoscapeNetworkProps {
  graphData: GraphData;
  onSelectNode: (nodeData: CytoscapeNodeData | null) => void;
  selectedNodeId?: string | null;
}

export const CytoscapeNetwork: React.FC<CytoscapeNetworkProps> = ({
  graphData,
  onSelectNode,
  selectedNodeId,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<cytoscape.Core | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    // Convert graph elements
    const elements: any[] = [];

    graphData.nodes.forEach((n) => {
      const safeLabel = formatSafeDisplayLabel(n.data.label, n.data.node_type, n.data.is_source);
      elements.push({
        group: 'nodes',
        data: {
          ...n.data,
          display_label: safeLabel,
        },
      });
    });

    graphData.edges.forEach((e) => {
      const edgeLabel = e.data.label || `${e.data.channel} • ₹${Number(e.data.amount || 0).toLocaleString('en-IN')}`;
      elements.push({
        group: 'edges',
        data: {
          ...e.data,
          edge_label: edgeLabel,
        },
      });
    });

    // Determine root nodes for top-to-bottom breadthfirst layout
    const rootIds = graphData.nodes
      .filter((n) => n.data.is_source || n.data.node_type === 'victim')
      .map((n) => `#${n.data.id}`);

    const cy = cytoscape({
      container: containerRef.current,
      elements,
      style: [
        {
          selector: 'node',
          style: {
            'background-color': '#e2e8f0',
            'border-width': 2,
            'border-color': '#64748b',
            'label': 'data(display_label)',
            'color': '#1e293b',
            'font-size': '10px',
            'font-family': 'Inter, sans-serif',
            'text-valign': 'bottom',
            'text-margin-y': 6,
            'text-outline-width': 2,
            'text-outline-color': '#ffffff',
            'width': 38,
            'height': 38,
            'transition-property': 'background-color, border-color, width, height',
            'transition-duration': 0.2,
          },
        },
        {
          selector: 'node[node_type = "victim"]',
          style: {
            'background-color': '#0ea5e9',
            'border-color': '#0284c7',
            'shape': 'ellipse',
            'width': 42,
            'height': 42,
          },
        },
        {
          selector: 'node[node_type = "account"]',
          style: {
            'background-color': '#f59e0b',
            'border-color': '#d97706',
            'shape': 'roundrectangle',
          },
        },
        {
          selector: 'node[node_type = "intermediary"]',
          style: {
            'background-color': '#d97706',
            'border-color': '#b45309',
            'shape': 'roundrectangle',
          },
        },
        {
          selector: 'node[node_type = "mule"]',
          style: {
            'background-color': '#ef4444',
            'border-color': '#dc2626',
            'border-width': 3,
            'shape': 'diamond',
            'width': 42,
            'height': 42,
          },
        },
        {
          selector: 'node[node_type = "sink"]',
          style: {
            'background-color': '#f97316',
            'border-color': '#ea580c',
            'border-width': 3,
            'shape': 'diamond',
            'width': 42,
            'height': 42,
          },
        },
        {
          selector: 'node[node_type = "atm"]',
          style: {
            'background-color': '#10b981',
            'border-color': '#047857',
            'border-width': 3,
            'shape': 'hexagon',
            'width': 46,
            'height': 46,
            'color': '#065f46',
            'font-weight': 'bold',
          },
        },
        {
          selector: 'node[node_type = "cluster"]',
          style: {
            'background-color': '#fef2f2',
            'border-color': '#2563eb',
            'border-style': 'dashed',
            'border-width': 3,
            'shape': 'octagon',
            'width': 52,
            'height': 52,
            'color': '#1d4ed8',
          },
        },
        {
          selector: 'edge',
          style: {
            'width': 2,
            'line-color': '#94a3b8',
            'target-arrow-color': '#94a3b8',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            'label': 'data(edge_label)',
            'font-size': '8px',
            'color': '#334155',
            'text-rotation': 'autorotate',
            'text-margin-y': -8,
            'text-background-color': '#ffffff',
            'text-background-opacity': 0.9,
            'text-background-padding': '2px',
            'text-background-shape': 'roundrectangle',
          },
        },
        {
          selector: 'edge[channel = "ATM Cash-Out"]',
          style: {
            'line-color': '#10b981',
            'target-arrow-color': '#10b981',
            'line-style': 'solid',
            'width': 2.5,
          },
        },
        {
          selector: 'edge[?is_suspicious]',
          style: {
            'line-color': '#ef4444',
            'target-arrow-color': '#ef4444',
            'line-style': 'solid',
            'width': 2.5,
          },
        },
        {
          selector: ':selected',
          style: {
            'border-color': '#2563eb',
            'border-width': 4,
          },
        },
      ],
      layout: {
        name: 'breadthfirst',
        directed: true,
        padding: 40,
        spacingFactor: 1.75,
        nodeDimensionsIncludeLabels: true,
        roots: rootIds ? rootIds : undefined,
      },
    });

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

    return () => {
      cy.destroy();
    };
  }, [graphData]);

  useEffect(() => {
    if (cyRef.current && selectedNodeId) {
      const node = cyRef.current.$id(selectedNodeId);
      if (node.length > 0) {
        cyRef.current.$(':selected').unselect();
        node.select();
      }
    }
  }, [selectedNodeId]);

  const handleZoomIn = () => cyRef.current?.zoom(cyRef.current.zoom() * 1.25);
  const handleZoomOut = () => cyRef.current?.zoom(cyRef.current.zoom() * 0.8);
  const handleFit = () => {
    cyRef.current?.fit(undefined, 35);
  };
  const handleReset = () => {
    if (cyRef.current) {
      const resetRootIds = graphData.nodes
        .filter((n) => n.data.is_source || n.data.node_type === 'victim')
        .map((n) => `#${n.data.id}`);
      cyRef.current.layout({
        name: 'breadthfirst',
        directed: true,
        padding: 40,
        spacingFactor: 1.75,
        nodeDimensionsIncludeLabels: true,
        roots: resetRootIds.length > 0 ? resetRootIds : undefined,
      }).run();
      cyRef.current.fit(undefined, 35);
      cyRef.current.center();
    }
  };

  return (
    <div className="relative w-full h-[400px] sm:h-[540px] bg-[#f8fafc] rounded-lg border border-[#DCE5F0] overflow-hidden">
      {/* Network Canvas */}
      <div ref={containerRef} className="w-full h-full cursor-grab active:cursor-grabbing" />

      {/* Graph Control Bar: Zoom In, Zoom Out, Fit to Screen, Reset Layout */}
      <div className="absolute top-3 sm:top-4 right-3 sm:right-4 flex items-center space-x-1.5 bg-white/95 backdrop-blur-xs p-1.5 rounded-md border border-[#DCE5F0] shadow-xs z-10">
        <button
          onClick={handleZoomIn}
          title="Zoom In"
          className="p-1.5 text-slate-600 hover:text-blue-600 hover:bg-blue-50 rounded transition-colors"
        >
          <ZoomIn className="w-4 h-4" />
        </button>
        <button
          onClick={handleZoomOut}
          title="Zoom Out"
          className="p-1.5 text-slate-600 hover:text-blue-600 hover:bg-blue-50 rounded transition-colors"
        >
          <ZoomOut className="w-4 h-4" />
        </button>
        <button
          onClick={handleFit}
          title="Fit to Screen"
          className="p-1.5 text-slate-600 hover:text-blue-600 hover:bg-blue-50 rounded transition-colors"
        >
          <Maximize2 className="w-4 h-4" />
        </button>
        <button
          onClick={handleReset}
          title="Reset Layout & Center"
          className="p-1.5 text-slate-600 hover:text-blue-600 hover:bg-blue-50 rounded transition-colors"
        >
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      {/* Graph Legend */}
      <div className="absolute bottom-3 sm:bottom-4 left-3 sm:left-4 right-3 sm:right-auto max-w-[calc(100%-1.5rem)] sm:max-w-none flex flex-wrap items-center gap-2 sm:gap-3 bg-white/95 backdrop-blur-xs px-2.5 sm:px-3 py-1.5 sm:py-2 rounded-md border border-[#DCE5F0] text-[10px] sm:text-xs z-10 shadow-xs">
        <div className="flex items-center space-x-1.5">
          <div className="w-3 h-3 rounded-full bg-[#0ea5e9] shrink-0"></div>
          <span className="text-slate-700">Victim</span>
        </div>
        <div className="flex items-center space-x-1.5">
          <div className="w-3 h-3 rounded bg-[#f59e0b] shrink-0"></div>
          <span className="text-slate-700">Account Layer</span>
        </div>
        <div className="flex items-center space-x-1.5">
          <div className="w-3 h-3 rounded bg-[#d97706] shrink-0"></div>
          <span className="text-slate-700">Intermediary</span>
        </div>
        <div className="flex items-center space-x-1.5">
          <div className="w-3 h-3 transform rotate-45 bg-[#ef4444] shrink-0"></div>
          <span className="text-slate-700">Potential Mule Indicator</span>
        </div>
        <div className="flex items-center space-x-1.5">
          <div className="w-3.5 h-3.5 bg-[#10b981] border border-[#047857] shrink-0" style={{ clipPath: 'polygon(50% 0%, 100% 25%, 100% 75%, 50% 100%, 0% 75%, 0% 25%)' }}></div>
          <span className="text-emerald-800 font-semibold">Cash-Out Endpoint</span>
        </div>
        <div className="flex items-center space-x-1.5">
          <div className="w-3.5 h-3.5 bg-[#fef2f2] border-2 border-dashed border-[#2563eb] shrink-0"></div>
          <span className="text-blue-700 font-semibold">Predicted Zone (Forecast)</span>
        </div>
      </div>
    </div>
  );
};
