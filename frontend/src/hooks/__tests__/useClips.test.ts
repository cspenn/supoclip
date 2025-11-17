/**
 * Tests for useClips hook
 *
 * Tests the clip data fetching hook that provides automatic loading,
 * error handling, and refresh capability.
 */

import { renderHook, waitFor } from '@testing-library/react';
import { useClips } from '../useClips';

// Mock the useApiUrl hook
jest.mock('../useApiUrl', () => ({
  useApiUrl: () => 'http://localhost:8000',
}));

// Mock fetch globally
global.fetch = jest.fn();

describe('useClips', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('initialization', () => {
    it('should initialize with empty clips array', () => {
      const { result } = renderHook(() => useClips(undefined));

      expect(result.current.clips).toEqual([]);
      expect(result.current.loading).toBe(false);
      expect(result.current.error).toBeNull();
    });

    it('should have refreshClips function available', () => {
      const { result } = renderHook(() => useClips(undefined));

      expect(typeof result.current.refreshClips).toBe('function');
    });
  });

  describe('fetching clips', () => {
    it('should fetch clips when taskId is provided', async () => {
      const mockClips = [
        {
          id: 'clip_1',
          filename: 'clip1.mp4',
          task_id: 'task_123',
          file_path: '/path/to/clip1.mp4',
          start_time: 0,
          end_time: 30,
          duration: 30,
          text: 'Clip text',
          relevance_score: 0.95,
          reasoning: 'Key moment',
          clip_order: 1,
          created_at: '2025-01-01T00:00:00Z',
          video_url: '/clips/clip1.mp4',
        },
      ];

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ clips: mockClips }),
      });

      const { result } = renderHook(() => useClips('task_123'));

      // Initially loading should be true
      expect(result.current.loading).toBe(true);

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      expect(result.current.clips).toEqual(mockClips);
      expect(result.current.error).toBeNull();
    });

    it('should call correct API endpoint with taskId', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ clips: [] }),
      });

      renderHook(() => useClips('task_123'));

      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledWith('http://localhost:8000/tasks/task_123/clips');
      });
    });

    it('should handle fetch errors', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: false,
        statusText: 'Not Found',
      });

      const { result } = renderHook(() => useClips('task_123'));

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      expect(result.current.error).toContain('Failed to fetch clips');
    });

    it('should handle network errors', async () => {
      (global.fetch as jest.Mock).mockRejectedValueOnce(new Error('Network error'));

      const { result } = renderHook(() => useClips('task_123'));

      await waitFor(() => {
        expect(result.current.error).toBe('Network error');
      });
    });
  });

  describe('refresh functionality', () => {
    it('should refresh clips on demand', async () => {
      const mockClips = [
        {
          id: 'clip_1',
          filename: 'clip1.mp4',
          task_id: 'task_123',
          file_path: '/path/to/clip1.mp4',
          start_time: 0,
          end_time: 30,
          duration: 30,
          text: 'Clip text',
          relevance_score: 0.95,
          reasoning: 'Key moment',
          clip_order: 1,
          created_at: '2025-01-01T00:00:00Z',
          video_url: '/clips/clip1.mp4',
        },
      ];

      (global.fetch as jest.Mock).mockResolvedValue({
        ok: true,
        json: async () => ({ clips: mockClips }),
      });

      const { result } = renderHook(() => useClips('task_123'));

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      // Call refresh
      await result.current.refreshClips();

      expect(global.fetch).toHaveBeenCalledTimes(2);
    });

    it('should reset error when refreshing', async () => {
      (global.fetch as jest.Mock)
        .mockResolvedValueOnce({
          ok: false,
          statusText: 'Error',
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ clips: [] }),
        });

      const { result } = renderHook(() => useClips('task_123'));

      // Wait for initial error
      await waitFor(() => {
        expect(result.current.error).not.toBeNull();
      });

      // Refresh should clear error
      await result.current.refreshClips();

      await waitFor(() => {
        expect(result.current.error).toBeNull();
      });
    });
  });

  describe('taskId changes', () => {
    it('should refetch when taskId changes', async () => {
      (global.fetch as jest.Mock).mockResolvedValue({
        ok: true,
        json: async () => ({ clips: [] }),
      });

      const { rerender } = renderHook(
        ({ taskId }) => useClips(taskId),
        { initialProps: { taskId: 'task_1' } }
      );

      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledWith('http://localhost:8000/tasks/task_1/clips');
      });

      // Change taskId
      rerender({ taskId: 'task_2' });

      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledWith('http://localhost:8000/tasks/task_2/clips');
      });
    });

    it('should clear clips when taskId becomes undefined', async () => {
      const mockClips = [
        {
          id: 'clip_1',
          filename: 'clip1.mp4',
          task_id: 'task_123',
          file_path: '/path/to/clip1.mp4',
          start_time: 0,
          end_time: 30,
          duration: 30,
          text: 'Clip text',
          relevance_score: 0.95,
          reasoning: 'Key moment',
          clip_order: 1,
          created_at: '2025-01-01T00:00:00Z',
          video_url: '/clips/clip1.mp4',
        },
      ];

      (global.fetch as jest.Mock).mockResolvedValue({
        ok: true,
        json: async () => ({ clips: mockClips }),
      });

      const { rerender, result } = renderHook(
        ({ taskId }) => useClips(taskId),
        { initialProps: { taskId: 'task_123' } }
      );

      await waitFor(() => {
        expect(result.current.clips.length).toBe(1);
      });

      // Change to undefined
      rerender({ taskId: undefined });

      expect(result.current.clips).toEqual([]);
    });
  });

  describe('response handling', () => {
    it('should handle empty clips response', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ clips: [] }),
      });

      const { result } = renderHook(() => useClips('task_123'));

      await waitFor(() => {
        expect(result.current.clips).toEqual([]);
      });
    });

    it('should handle missing clips key in response', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({}),
      });

      const { result } = renderHook(() => useClips('task_123'));

      await waitFor(() => {
        expect(result.current.clips).toEqual([]);
      });
    });

    it('should parse JSON response correctly', async () => {
      const mockClips = [
        {
          id: 'clip_1',
          filename: 'clip1.mp4',
          task_id: 'task_123',
          file_path: '/path/to/clip1.mp4',
          start_time: 0,
          end_time: 30,
          duration: 30,
          text: 'Clip text',
          relevance_score: 0.95,
          reasoning: 'Key moment',
          clip_order: 1,
          created_at: '2025-01-01T00:00:00Z',
          video_url: '/clips/clip1.mp4',
        },
        {
          id: 'clip_2',
          filename: 'clip2.mp4',
          task_id: 'task_123',
          file_path: '/path/to/clip2.mp4',
          start_time: 30,
          end_time: 60,
          duration: 30,
          text: 'Another clip',
          relevance_score: 0.85,
          reasoning: 'Good moment',
          clip_order: 2,
          created_at: '2025-01-01T00:00:01Z',
          video_url: '/clips/clip2.mp4',
        },
      ];

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ clips: mockClips }),
      });

      const { result } = renderHook(() => useClips('task_123'));

      await waitFor(() => {
        expect(result.current.clips).toHaveLength(2);
        expect(result.current.clips[0].id).toBe('clip_1');
        expect(result.current.clips[1].id).toBe('clip_2');
      });
    });
  });
});
