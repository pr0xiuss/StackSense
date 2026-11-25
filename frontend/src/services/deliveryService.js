/**
 * Delivery Service (Frontend)
 *
 * Interacts with C0 delivery status and idempotent retry endpoints.
 */
import { apiClient } from './apiClient.js';
import {
  validateDeliverySummary,
  validateRetryAccepted,
} from '../contracts/intelligenceContracts.js';

export const deliveryService = {
  /**
   * Retrieve DeliverySummary for an Architecture Version.
   */
  async getDelivery(versionId, { projectId, signal, ...options } = {}) {
    if (!versionId) throw new Error('versionId is required');
    if (!projectId) throw new Error('projectId is required');

    const data = await apiClient.get(
      `/architecture-versions/${encodeURIComponent(versionId)}/delivery?project_id=${encodeURIComponent(projectId)}`,
      { signal, ...options }
    );
    return validateDeliverySummary(data);
  },

  /**
   * Retry an eligible failed delivery work item.
   */
  async retryDelivery(versionId, payload, { projectId, signal, ...options } = {}) {
    if (!versionId) throw new Error('versionId is required');
    if (!projectId) throw new Error('projectId is required');

    const data = await apiClient.post(
      `/architecture-versions/${encodeURIComponent(versionId)}/delivery/retry?project_id=${encodeURIComponent(projectId)}`,
      payload,
      { signal, ...options }
    );
    return validateRetryAccepted(data);
  },
};
