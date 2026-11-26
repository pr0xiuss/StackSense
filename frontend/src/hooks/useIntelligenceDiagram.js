/**
 * useIntelligenceDiagram Hook
 *
 * Manages diagram presentation across the 4 controlled templates:
 * - CONTAINER_ISOLATION
 * - COMPONENT_COMMUNICATION
 * - DATA_FLOW
 * - CROSS_BOUNDARY
 *
 * Loads exact DiagramSpec and LayoutSpec, compiles prepared diagrams for DiagramView,
 * supports generation switching, derived views, members queries, and SVG/JSON exports.
 */
import { useState, useEffect, useRef, useCallback } from 'react';
import { diagramService } from '../services/diagramService.js';
import { DIAGRAM_TEMPLATES } from '../contracts/intelligenceContracts.js';

export { DIAGRAM_TEMPLATES };

export function useIntelligenceDiagram(versionId, {
  projectId,
  initialTemplate = 'system_overview',
} = {}) {
  const [template, setTemplate] = useState(initialTemplate);
  const [collection, setCollection] = useState(null);
  const [summary, setSummary] = useState(null);
  const [selectedGenerationId, setSelectedGenerationId] = useState(null);
  const [prepared, setPrepared] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [statusUnavailable, setStatusUnavailable] = useState(false);
  const [exportLoading, setExportLoading] = useState(false);

  const isMountedRef = useRef(true);
  const abortControllerRef = useRef(null);

  // 1. Fetch DiagramCollection (collection of all 4 templates)
  const fetchCollection = useCallback(async () => {
    if (!versionId || !projectId) return;
    try {
      const data = await diagramService.getDiagrams(versionId, { projectId });
      if (isMountedRef.current) {
        setCollection(data);
      }
    } catch (err) {
      // Collection failure should not completely block individual template loads
      console.warn('Failed to load diagram collection metadata:', err);
    }
  }, [versionId, projectId]);

  useEffect(() => {
    fetchCollection();
  }, [fetchCollection]);

  // 2. Fetch template summary & prepared diagram spec/layout
  const loadDiagram = useCallback(async (targetTemplate, targetGenId = null) => {
    if (!versionId || !projectId || !targetTemplate) return;

    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    const controller = new AbortController();
    abortControllerRef.current = controller;

    setLoading(true);
    setError(null);
    setStatusUnavailable(false);
    setSummary(null);

    try {
      // A. Get summary
      const sum = await diagramService.getDiagramSummary(versionId, targetTemplate, {
        projectId,
        generationId: targetGenId || undefined,
        signal: controller.signal,
      });

      if (!isMountedRef.current || controller.signal.aborted) return;
      setSummary(sum);

      const activeGenId = sum.reference?.generation_id;
      if (!activeGenId) {
        setPrepared(null);
        setSelectedGenerationId(null);
        setError(`Diagram ${sum.availability.toLowerCase().replaceAll('_', ' ')}${sum.reason ? `: ${sum.reason}` : '.'}`);
        return;
      }
      if (targetGenId && targetGenId !== activeGenId) throw new Error('Diagram generation changed.');
      const result = await diagramService.exportDiagramJson(versionId, targetTemplate, activeGenId, {
        projectId,
        signal: controller.signal,
      });

      if (!isMountedRef.current || controller.signal.aborted) return;

      const ref = result.descriptor.reference;
      if (ref.generation_id !== activeGenId || ref.scope.project_id !== projectId ||
          ref.scope.architecture_version_id !== versionId || result.spec.template !== targetTemplate) {
        throw new Error('Diagram scope or generation mismatch.');
      }
      setSelectedGenerationId(activeGenId);
      setPrepared(result);
      setError(null);
    } catch (err) {
      if (!isMountedRef.current || controller.signal.aborted) return;
      setPrepared(null);
      setStatusUnavailable(err?.status === 503 || err?.status === 504);
      setError(err?.message || `Failed to load diagram for ${targetTemplate}.`);
    } finally {
      if (isMountedRef.current && !controller.signal.aborted) {
        setLoading(false);
      }
    }
  }, [versionId, projectId]);

  // Load when template or version changes
  useEffect(() => {
    isMountedRef.current = true;
    loadDiagram(template, null);

    return () => {
      isMountedRef.current = false;
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
        abortControllerRef.current = null;
      }
    };
  }, [template, versionId, projectId]);

  // Callbacks for DiagramView
  const requestView = useCallback(async (body, signal) => {
    if (!versionId || !projectId || !template || !selectedGenerationId) {
      throw new Error('Diagram context missing for view request');
    }
    return diagramService.viewDiagram(versionId, template, selectedGenerationId, body, {
      projectId,
      signal,
    });
  }, [versionId, projectId, template, selectedGenerationId]);

  const requestMembers = useCallback(async (params, signal) => {
    if (!versionId || !projectId || !template || !selectedGenerationId) {
      throw new Error('Diagram context missing for members request');
    }
    return diagramService.getDiagramMembers(versionId, template, selectedGenerationId, {
      ...params,
      projectId,
    }, { signal });
  }, [versionId, projectId, template, selectedGenerationId]);

  const exportDiagram = useCallback(async (format = 'svg') => {
    if (!versionId || !projectId || !template || !selectedGenerationId) {
      throw new Error('Diagram context missing for export');
    }

    setExportLoading(true);
    try {
      if (format === 'json') {
        const json = await diagramService.exportDiagramJson(versionId, template, selectedGenerationId, {
          projectId,
        });
        const blob = new Blob([JSON.stringify(json, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `diagram-${template.toLowerCase()}-${selectedGenerationId.slice(0, 8)}.json`;
        a.click();
        URL.revokeObjectURL(url);
        return json;
      } else {
        return await diagramService.exportDiagramSvg(versionId, template, selectedGenerationId, {
          projectId,
        });
      }
    } finally {
      if (isMountedRef.current) {
        setExportLoading(false);
      }
    }
  }, [versionId, projectId, template, selectedGenerationId]);

  const switchTemplate = useCallback((nextTemplate) => {
    if (nextTemplate === template) return;
    setLoading(true);
    setError(null);
    setStatusUnavailable(false);
    setSummary(null);
    setTemplate(nextTemplate);
    setSelectedGenerationId(null);
  }, [template]);

  const switchGeneration = useCallback((genId) => {
    setSelectedGenerationId(genId);
    loadDiagram(template, genId);
  }, [template, loadDiagram]);

  return {
    template,
    templates: DIAGRAM_TEMPLATES,
    collection,
    summary,
    selectedGenerationId,
    prepared,
    loading,
    error,
    statusUnavailable,
    exportLoading,
    requestView,
    requestMembers,
    exportDiagram,
    switchTemplate,
    switchGeneration,
    refresh: () => loadDiagram(template, selectedGenerationId),
  };
}
