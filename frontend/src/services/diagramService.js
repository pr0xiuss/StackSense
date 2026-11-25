/**
 * Diagram Service (Frontend)
 *
 * Interacts with C2 diagram collection, summaries, generations, layout, views, and exports.
 */
import { apiClient } from './apiClient.js';
import {
  validateDiagramCollection,
  validateDiagramSummary,
  validateGenerationPage,
  validateDiagramSpec,
  validateLayoutSpec,
  validateDiagramViewResponse,
  validateMemberPage,
  validatePreparedDiagram,
} from '../contracts/intelligenceContracts.js';

export const diagramService = {
  /**
   * Retrieve four-template DiagramCollection.
   */
  async getDiagrams(versionId, { projectId, signal, ...options } = {}) {
    if (!versionId) throw new Error('versionId is required');
    if (!projectId) throw new Error('projectId is required');

    const data = await apiClient.get(
      `/architecture-versions/${encodeURIComponent(versionId)}/diagrams?project_id=${encodeURIComponent(projectId)}`,
      { signal, ...options }
    );
    return validateDiagramCollection(data);
  },

  /**
   * Retrieve DiagramSummary for a specific template.
   */
  async getDiagramSummary(versionId, template, { projectId, generationId, signal, ...options } = {}) {
    if (!versionId) throw new Error('versionId is required');
    if (!template) throw new Error('template is required');
    if (!projectId) throw new Error('projectId is required');

    const qs = new URLSearchParams({ project_id: projectId });
    if (generationId) qs.set('generation_id', generationId);

    const data = await apiClient.get(
      `/architecture-versions/${encodeURIComponent(versionId)}/diagrams/${encodeURIComponent(template)}?${qs.toString()}`,
      { signal, ...options }
    );
    return validateDiagramSummary(data);
  },

  /**
   * Retrieve paginated generation history for a template.
   */
  async getDiagramGenerations(versionId, template, params = {}, { signal, ...options } = {}) {
    if (!versionId) throw new Error('versionId is required');
    if (!template) throw new Error('template is required');
    if (!params.projectId) throw new Error('projectId is required');

    const qs = new URLSearchParams({ project_id: params.projectId });
    if (params.limit) qs.set('limit', String(params.limit));
    if (params.cursor) qs.set('cursor', params.cursor);

    const data = await apiClient.get(
      `/architecture-versions/${encodeURIComponent(versionId)}/diagrams/${encodeURIComponent(template)}/generations?${qs.toString()}`,
      { signal, ...options }
    );
    return validateGenerationPage(data);
  },

  /**
   * Retrieve exact DiagramSpec.
   */
  async getDiagramSpec(versionId, template, generationId, { projectId, signal, ...options } = {}) {
    if (!versionId || !template || !generationId) throw new Error('versionId, template, and generationId are required');
    if (!projectId) throw new Error('projectId is required');

    const data = await apiClient.get(
      `/architecture-versions/${encodeURIComponent(versionId)}/diagrams/${encodeURIComponent(template)}/generations/${encodeURIComponent(generationId)}/spec?project_id=${encodeURIComponent(projectId)}`,
      { signal, ...options }
    );
    return validateDiagramSpec(data);
  },

  /**
   * Retrieve exact LayoutSpec.
   */
  async getDiagramLayout(versionId, template, generationId, { projectId, signal, ...options } = {}) {
    if (!versionId || !template || !generationId) throw new Error('versionId, template, and generationId are required');
    if (!projectId) throw new Error('projectId is required');

    const data = await apiClient.get(
      `/architecture-versions/${encodeURIComponent(versionId)}/diagrams/${encodeURIComponent(template)}/generations/${encodeURIComponent(generationId)}/layout?project_id=${encodeURIComponent(projectId)}`,
      { signal, ...options }
    );
    return validateLayoutSpec(data);
  },

  /**
   * Post transient view request to derive focused/collapsed geometry.
   */
  async viewDiagram(versionId, template, generationId, body, { projectId, signal, ...options } = {}) {
    if (!versionId || !template || !generationId) throw new Error('versionId, template, and generationId are required');
    if (!projectId) throw new Error('projectId is required');

    const data = await apiClient.post(
      `/architecture-versions/${encodeURIComponent(versionId)}/diagrams/${encodeURIComponent(template)}/generations/${encodeURIComponent(generationId)}/view?project_id=${encodeURIComponent(projectId)}`,
      body,
      { signal, ...options }
    );
    return validateDiagramViewResponse(data);
  },

  /**
   * Retrieve paginated members of a group or entity.
   */
  async getDiagramMembers(versionId, template, generationId, params = {}, { signal, ...options } = {}) {
    if (!versionId || !template || !generationId) throw new Error('versionId, template, and generationId are required');
    if (!params.projectId) throw new Error('projectId is required');

    const qs = new URLSearchParams({ project_id: params.projectId });
    if (params.group_id) qs.set('group_id', params.group_id);
    if (params.entity_id) qs.set('entity_id', params.entity_id);
    if (params.limit) qs.set('limit', String(params.limit));
    if (params.cursor) qs.set('cursor', params.cursor);

    const data = await apiClient.get(
      `/architecture-versions/${encodeURIComponent(versionId)}/diagrams/${encodeURIComponent(template)}/generations/${encodeURIComponent(generationId)}/members?${qs.toString()}`,
      { signal, ...options }
    );
    return validateMemberPage(data);
  },

  /**
   * Export PreparedDiagram JSON.
   */
  async exportDiagramJson(versionId, template, generationId, { projectId, signal, ...options } = {}) {
    if (!versionId || !template || !generationId) throw new Error('versionId, template, and generationId are required');
    if (!projectId) throw new Error('projectId is required');

    const data = await apiClient.get(
      `/architecture-versions/${encodeURIComponent(versionId)}/diagrams/${encodeURIComponent(template)}/generations/${encodeURIComponent(generationId)}/export?project_id=${encodeURIComponent(projectId)}&format=json`,
      { signal, ...options }
    );
    return validatePreparedDiagram(data);
  },

  /**
   * Export diagram as SVG download.
   */
  async exportDiagramSvg(versionId, template, generationId, { projectId, signal, ...options } = {}) {
    if (!versionId || !template || !generationId) throw new Error('versionId, template, and generationId are required');
    if (!projectId) throw new Error('projectId is required');

    return apiClient.download(
      `/architecture-versions/${encodeURIComponent(versionId)}/diagrams/${encodeURIComponent(template)}/generations/${encodeURIComponent(generationId)}/export?project_id=${encodeURIComponent(projectId)}&format=svg`,
      {
        expectedMediaType: 'image/svg+xml',
        signal,
        filename: `diagram-${template}-${generationId}.svg`,
        ...options,
      }
    );
  },
};
