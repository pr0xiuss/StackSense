import { useCallback, useEffect, useState } from 'react';
import { useAuth } from '../auth/AuthContext.jsx';
import { projectAccessService } from '../services/projectAccessService.js';

const VALID_ROLES = ['OWNER', 'ADMIN', 'DEVELOPER', 'VIEWER'];

export function useProjectRole(projectId) {
  const { user } = useAuth();
  const [role, setRole] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const refresh = useCallback(async () => {
    if (!projectId || !user?.id) {
      setRole(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const data = await projectAccessService.listAccess(projectId);
      const current = (Array.isArray(data) ? data : []).find((item) => item.user_id === user.id);
      const resolved = current?.role?.toUpperCase();
      if (!VALID_ROLES.includes(resolved)) {
        setRole(null);
        setError('Your project role could not be resolved.');
      } else {
        setRole(resolved);
      }
    } catch (err) {
      setRole(null);
      setError(err.message || 'Failed to resolve project permissions.');
    } finally {
      setLoading(false);
    }
  }, [projectId, user?.id]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return {
    role,
    loading,
    error,
    userId: user?.id || null,
    refresh,
    canCreateOrUpdate: ['OWNER', 'ADMIN', 'DEVELOPER'].includes(role),
    canDelete: ['OWNER', 'ADMIN'].includes(role),
    canManageAccess: ['OWNER', 'ADMIN'].includes(role),
  };
}
