import { webcrypto } from 'node:crypto';
import { beforeAll, describe, expect, it, vi } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { useIntelligenceDiagram } from '../../src/hooks/useIntelligenceDiagram.js';
import { useDiagramView } from '../../src/hooks/useDiagramView.js';
import { diagramService } from '../../src/services/diagramService.js';
import { apiClient } from '../../src/services/apiClient.js';
import { validateDiagramSummary } from '../../src/contracts/intelligenceContracts.js';
import { diagramFixture } from '../diagramFixtures.js';

beforeAll(() => vi.stubGlobal('crypto', webcrypto));

describe('M6 diagram integration with M4 prepared fixtures', () => {
  it('validates real local spec and layout and rejects a foreign version', async () => {
    const prepared = diagramFixture();
    const payload = { mode: 'local_unpublished', svg_base64: 'PHN2Zy8+', spec: prepared.spec, layout: prepared.layout };
    const get = vi.spyOn(apiClient, 'get').mockResolvedValue(payload);
    try {
      const { project_id, architecture_version_id } = prepared.spec.scope;
      const local = await diagramService.getLocalPreview(architecture_version_id, prepared.spec.template, { projectId: project_id });
      expect(local.spec.semantic_digest).toBe(prepared.spec.semantic_digest);
      await expect(diagramService.getLocalPreview('00000000-0000-4000-8000-000000000000', prepared.spec.template, { projectId: project_id })).rejects.toThrow(/scope mismatch/);
    } finally { get.mockRestore(); }
  });
  it('accepts a valid unscheduled summary with no delivery scope', () => {
    expect(validateDiagramSummary({
      canonical_scope: {}, delivery_scope: null, availability: 'NOT_SCHEDULED',
      readability: 'unknown', reference: null,
    }).availability).toBe('NOT_SCHEDULED');
  });

  it('loads an exact accepted prepared generation that the real viewer validates', async () => {
    const prepared = diagramFixture();
    const ref = prepared.descriptor.reference;
    const summary = {
      template: prepared.spec.template, canonical_scope: prepared.spec.scope,
      delivery_scope: ref.scope, availability: 'READY', readability: 'unknown',
      reference: ref,
    };
    const collection = vi.spyOn(diagramService, 'getDiagrams').mockResolvedValue({ items: [summary] });
    const getSummary = vi.spyOn(diagramService, 'getDiagramSummary').mockResolvedValue(summary);
    const getPrepared = vi.spyOn(diagramService, 'exportDiagramJson').mockResolvedValue(prepared);
    try {
      const { result } = renderHook(() => {
        const diagram = useIntelligenceDiagram(ref.scope.architecture_version_id, { projectId: ref.scope.project_id });
        const viewer = useDiagramView(diagram.prepared, vi.fn(), vi.fn());
        return { diagram, viewer };
      });
      await waitFor(() => expect(result.current.viewer.state.ready).toBe(true));
      expect(result.current.diagram.selectedGenerationId).toBe(ref.generation_id);
      expect(result.current.viewer.state.base_generation_id).toBe(ref.generation_id);
      expect(getPrepared).toHaveBeenCalledWith(ref.scope.architecture_version_id, prepared.spec.template, ref.generation_id, expect.any(Object));
    } finally {
      collection.mockRestore(); getSummary.mockRestore(); getPrepared.mockRestore();
    }
  });
});
