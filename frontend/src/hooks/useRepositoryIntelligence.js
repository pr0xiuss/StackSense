/**
 * useRepositoryIntelligence Hook (Frontend)
 *
 * Loads and validates authoritative project, repository, analysis, and architecture version
 * metadata for the unified intelligence workspace, enforcing strict cross-resource scope matching.
 */
import { useState, useEffect, useCallback, useRef } from 'react';
import { projectService } from '../services/projectService.js';
import { repositoryService } from '../services/repositoryService.js';
import { analysisService } from '../services/analysisService.js';
import { architectureService } from '../services/architectureService.js';
import { isUuid } from '../contracts/intelligenceContracts.js';

export function useRepositoryIntelligence({
  projectId,
  repositoryId,
  analysisId,
  versionId,
}) {
  const [project, setProject] = useState(null);
  const [repository, setRepository] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [version, setVersion] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const reqSeqRef = useRef(0);

  const loadContext = useCallback(async () => {
    const currentSeq = ++reqSeqRef.current;
    setLoading(true);
    setError(null);

    if (!projectId || !isUuid(projectId)) {
      setError(new Error('Invalid or missing projectId.'));
      setLoading(false);
      return;
    }
    if (!repositoryId || !isUuid(repositoryId)) {
      setError(new Error('Invalid or missing repositoryId.'));
      setLoading(false);
      return;
    }
    if (!analysisId || !isUuid(analysisId)) {
      setError(new Error('Invalid or missing analysisId.'));
      setLoading(false);
      return;
    }
    if (!versionId || !isUuid(versionId)) {
      setError(new Error('Invalid or missing versionId.'));
      setLoading(false);
      return;
    }

    const controller = new AbortController();
    const { signal } = controller;

    try {
      const [projData, repoData, analysisData, versionData] = await Promise.all([
        projectService.getProject(projectId, { signal }),
        repositoryService.getRepository(projectId, repositoryId, { signal }),
        analysisService.getAnalysis(analysisId, { projectId, signal }),
        architectureService.getVersion(versionId, { projectId, signal }),
      ]);

      if (currentSeq !== reqSeqRef.current) return;

      // Scope validation
      if (
        analysisData.repository_id &&
        String(analysisData.repository_id) !== String(repositoryId)
      ) {
        throw new Error('Analysis does not belong to the selected repository.');
      }
      if (
        versionData.repository_id &&
        String(versionData.repository_id) !== String(repositoryId)
      ) {
        throw new Error('Architecture version does not belong to the selected repository.');
      }
      if (
        versionData.analysis_id &&
        String(versionData.analysis_id) !== String(analysisId)
      ) {
        throw new Error('Architecture version does not belong to the selected analysis.');
      }

      setProject(projData);
      setRepository(repoData);
      setAnalysis(analysisData);
      setVersion(versionData);
      setError(null);
    } catch (err) {
      if (currentSeq === reqSeqRef.current) {
        if (err.name !== 'AbortError') {
          setError(err);
        }
      }
    } finally {
      if (currentSeq === reqSeqRef.current) {
        setLoading(false);
      }
    }

    return () => controller.abort();
  }, [projectId, repositoryId, analysisId, versionId]);

  useEffect(() => {
    loadContext();
  }, [loadContext]);

  return {
    project,
    repository,
    analysis,
    version,
    loading,
    error,
    reload: loadContext,
  };
}
