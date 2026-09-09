import React, { useEffect, useRef } from 'react';
import cytoscape from 'cytoscape';
import { CytoscapeNodeData, GraphData } from '../types';
import { ZoomIn, ZoomOut, RefreshCw, Maximize2 } from 'lucide-react';

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
      elements.push({
        group: 'nodes',
        data: n.data,
      });
    });

    graphData.edges.forEach((e) => {
      elements.push({
        group: 'edges',
        data: e.data,
      });
    });

    const cy = cytoscape({
      container: containerRef.current,
      elements,
      style: [
        {
          selector: 'node',
          style: {
            'background-color': '#1e293b',
            'border-width': 2,
            'border-color': '#475569',
            'label': 'data(label)',
            'color': '#cbd5e1',
            'font-size': '10px',
            'font-family': 'Inter, sans-serif',
            'text-valign': 'bottom',
            'text-margin-y': 6,
            'text-outline-width': 2,
            'text-outline-color': '#060913',
            'width': 36,
            'height': 36,
            'transition-property': 'background-color, border-color, width, height',
            'transition-duration': 0.2,
          },
        },
        {
          selector: 'node[node_type = "victim"]',
          style: {
            'background-color': '#0ea5e9',
            'border-color': '#38bdf8',
            'shape': 'ellipse',
          },
        },
        {
          selector: 'node[node_type = "account"]',
          style: {
            'background-color': '#f59e0b',
            'border-color': '#fbbf24',
            'shape': 'roundrectangle',
          },
        },
        {
          selector: 'node[node_type = "mule"]',
          style: {
            'background-color': '#ef4444',
            'border-color': '#f87171',
            'border-width': 3,
            'shape': 'diamond',
            'width': 42,
            'height': 42,
          },
        },
        {
          selector: 'node[node_type = "cluster"]',
          style: {
            'background-color': '#dc2626',
            'border-color': '#00d8ff',
            'border-width': 4,
            'shape': 'hexagon',
            'width': 50,
            'height': 50,
          },
        },
        {
          selector: 'edge',
          style: {
            'width': 2.5,
            'line-color': '#334155',
            'target-arrow-color': '#334155',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            'label': 'data(channel)',
            'font-size': '8px',
            'color': '#94a3b8',
            'text-outline-width': 1,
            'text-outline-color': '#060913',
          },
        },
        {
          selector: 'edge[?is_suspicious]',
          style: {
            'line-color': '#ef4444',
            'target-arrow-color': '#ef4444',
            'line-style': 'solid',
            'width': 3,
          },
        },
        {
          selector: ':selected',
          style: {
            'border-color': '#00d8ff',
            'border-width': 4,
          },
        },
      ],
      layout: {
        name: 'breadthfirst',
        directed: true,
        padding: 40,
        spacingFactor: 1.6,
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
  const handleReset = () => {
    cyRef.current?.fit();
    cyRef.current?.center();
  };

  return (
    <div className="relative w-full h-[520px] bg-[#070c18] rounded-xl border border-[#162544] overflow-hidden">
      {/* Network Canvas */}
      <div ref={containerRef} className="w-full h-full" />

      {/* Graph Control Bar */}
      <div className="absolute top-4 right-4 flex items-center space-x-2 bg-[#0c1428]/90 backdrop-blur-md p-1.5 rounded-lg border border-[#1b2b4d] z-10">
        <button
          onClick={handleZoomIn}
          title="Zoom In"
          className="p-1.5 text-slate-300 hover:text-cyan-400 hover:bg-[#162544] rounded transition-colors"
        >
          <ZoomIn className="w-4 h-4" />
        </button>
        <button
          onClick={handleZoomOut}
          title="Zoom Out"
          className="p-1.5 text-slate-300 hover:text-cyan-400 hover:bg-[#162544] rounded transition-colors"
        >
          <ZoomOut className="w-4 h-4" />
        </button>
        <button
          onClick={handleReset}
          title="Reset Layout"
          className="p-1.5 text-slate-300 hover:text-cyan-400 hover:bg-[#162544] rounded transition-colors"
        >
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      {/* Graph Legend */}
      <div className="absolute bottom-4 left-4 flex flex-wrap items-center gap-3 bg-[#0c1428]/90 backdrop-blur-md px-3 py-2 rounded-lg border border-[#1b2b4d] text-[11px] font-mono z-10">
        <div className="flex items-center space-x-1.5">
          <div className="w-3 h-3 rounded-full bg-[#0ea5e9]"></div>
          <span className="text-slate-300">Victim</span>
        </div>
        <div className="flex items-center space-x-1.5">
          <div className="w-3 h-3 rounded bg-[#f59e0b]"></div>
          <span className="text-slate-300">Account Layer</span>
        </div>
        <div className="flex items-center space-x-1.5">
          <div className="w-3 h-3 transform rotate-45 bg-[#ef4444]"></div>
          <span className="text-slate-300">Mule Terminal</span>
        </div>
        <div className="flex items-center space-x-1.5">
          <div className="w-3.5 h-3.5 bg-[#dc2626] border border-cyan-400"></div>
          <span className="text-cyan-300 font-bold">Cash-Out Cluster</span>
        </div>
      </div>
    </div>
  );
};
