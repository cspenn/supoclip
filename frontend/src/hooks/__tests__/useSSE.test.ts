/**
 * Tests for useSSE hook
 *
 * Tests the Server-Sent Events hook that manages EventSource connection lifecycle
 * and provides real-time updates.
 */

import { renderHook, waitFor } from '@testing-library/react';
import { useSSE } from '../useSSE';

// Mock the useApiUrl hook
jest.mock('../useApiUrl', () => ({
  useApiUrl: () => 'http://localhost:8000',
}));

// Mock EventSource
const mockEventSource = {
  close: jest.fn(),
  addEventListener: jest.fn(),
  removeEventListener: jest.fn(),
  onopen: null as any,
  onmessage: null as any,
  onerror: null as any,
};

global.EventSource = jest.fn(() => mockEventSource) as any;

describe('useSSE', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockEventSource.close.mockClear();
    mockEventSource.addEventListener.mockClear();
    mockEventSource.removeEventListener.mockClear();
  });

  describe('initialization', () => {
    it('should initialize with null data and disconnected state', () => {
      const { result } = renderHook(() => useSSE(undefined));

      expect(result.current.data).toBeNull();
      expect(result.current.connected).toBe(false);
      expect(result.current.error).toBeNull();
    });

    it('should not create EventSource when taskId is undefined', () => {
      renderHook(() => useSSE(undefined));

      expect(global.EventSource).not.toHaveBeenCalled();
    });
  });

  describe('connection management', () => {
    it('should create EventSource when taskId is provided', () => {
      renderHook(() => useSSE('task_123'));

      expect(global.EventSource).toHaveBeenCalledWith(
        'http://localhost:8000/tasks/task_123/progress'
      );
    });

    it('should set connected state to true on connection open', async () => {
      const { result } = renderHook(() => useSSE('task_123'));

      // Trigger onopen
      mockEventSource.onopen?.();

      await waitFor(() => {
        expect(result.current.connected).toBe(true);
      });
    });

    it('should close EventSource on unmount', () => {
      const { unmount } = renderHook(() => useSSE('task_123'));

      unmount();

      expect(mockEventSource.close).toHaveBeenCalled();
    });

    it('should close EventSource when taskId changes', () => {
      const { rerender } = renderHook(
        ({ taskId }) => useSSE(taskId),
        { initialProps: { taskId: 'task_1' } }
      );

      mockEventSource.close.mockClear();

      rerender({ taskId: 'task_2' });

      // The old connection should be closed
      expect(mockEventSource.close).toHaveBeenCalled();
    });
  });

  describe('message handling', () => {
    it('should parse and set data from SSE messages', async () => {
      const { result } = renderHook(() => useSSE('task_123'));

      const testData = { status: 'processing', progress: 50 };
      mockEventSource.onmessage?.({ data: JSON.stringify(testData) });

      await waitFor(() => {
        expect(result.current.data).toEqual(testData);
      });
    });

    it('should call optional onData callback when message arrives', async () => {
      const onData = jest.fn();
      const { result } = renderHook(() => useSSE('task_123', onData));

      const testData = { status: 'processing', progress: 50 };
      mockEventSource.onmessage?.({ data: JSON.stringify(testData) });

      await waitFor(() => {
        expect(onData).toHaveBeenCalledWith(testData);
      });
    });

    it('should handle JSON parsing errors gracefully', async () => {
      const { result } = renderHook(() => useSSE('task_123'));

      mockEventSource.onmessage?.({ data: 'invalid json' });

      await waitFor(() => {
        expect(result.current.error).toBe('Failed to parse server message');
      });
    });

    it('should handle multiple SSE messages', async () => {
      const onData = jest.fn();
      const { result } = renderHook(() => useSSE('task_123', onData));

      const message1 = { status: 'processing', progress: 25 };
      const message2 = { status: 'processing', progress: 50 };
      const message3 = { status: 'completed', progress: 100 };

      mockEventSource.onmessage?.({ data: JSON.stringify(message1) });
      mockEventSource.onmessage?.({ data: JSON.stringify(message2) });
      mockEventSource.onmessage?.({ data: JSON.stringify(message3) });

      await waitFor(() => {
        expect(result.current.data).toEqual(message3);
        expect(onData).toHaveBeenCalledTimes(3);
      });
    });
  });

  describe('error handling', () => {
    it('should set error state and disconnect on error', async () => {
      const { result } = renderHook(() => useSSE('task_123'));

      mockEventSource.onerror?.();

      await waitFor(() => {
        expect(result.current.error).toBe('Connection lost');
        expect(result.current.connected).toBe(false);
      });
    });

    it('should close connection on error', () => {
      renderHook(() => useSSE('task_123'));

      mockEventSource.onerror?.();

      expect(mockEventSource.close).toHaveBeenCalled();
    });

    it('should clear error on successful reconnection', async () => {
      const { result } = renderHook(() => useSSE('task_123'));

      // First cause an error
      mockEventSource.onerror?.();

      await waitFor(() => {
        expect(result.current.error).toBe('Connection lost');
      });

      // Then simulate reconnection
      mockEventSource.onopen?.();

      await waitFor(() => {
        expect(result.current.error).toBeNull();
      });
    });
  });

  describe('taskId changes', () => {
    it('should create new connection when taskId changes', () => {
      const { rerender } = renderHook(
        ({ taskId }) => useSSE(taskId),
        { initialProps: { taskId: 'task_1' } }
      );

      const firstCall = (global.EventSource as jest.Mock).mock.calls.length;

      rerender({ taskId: 'task_2' });

      expect((global.EventSource as jest.Mock).mock.calls.length).toBeGreaterThan(firstCall);
    });

    it('should not create connection when taskId changes to undefined', () => {
      const { rerender, result } = renderHook(
        ({ taskId }) => useSSE(taskId),
        { initialProps: { taskId: 'task_1' } }
      );

      mockEventSource.onopen?.();

      expect(result.current.connected).toBe(true);

      rerender({ taskId: undefined });

      expect(result.current.connected).toBe(false);
    });
  });

  describe('data types', () => {
    it('should handle data with additional unknown fields', async () => {
      const { result } = renderHook(() => useSSE('task_123'));

      const testData = {
        status: 'processing',
        progress: 50,
        message: 'Analyzing video',
        customField: 'custom value',
        nestedData: { nested: true },
      };

      mockEventSource.onmessage?.({ data: JSON.stringify(testData) });

      await waitFor(() => {
        expect(result.current.data).toEqual(testData);
        expect(result.current.data?.customField).toBe('custom value');
        expect(result.current.data?.nestedData).toEqual({ nested: true });
      });
    });

    it('should handle different progress values', async () => {
      const onData = jest.fn();
      const { result } = renderHook(() => useSSE('task_123', onData));

      const progressValues = [0, 25, 50, 75, 100];

      progressValues.forEach((progress) => {
        mockEventSource.onmessage?.({
          data: JSON.stringify({ status: 'processing', progress }),
        });
      });

      await waitFor(() => {
        expect(result.current.data?.progress).toBe(100);
      });

      expect(onData).toHaveBeenCalledTimes(5);
    });

    it('should handle different status values', async () => {
      const { result } = renderHook(() => useSSE('task_123'));

      const statuses = ['queued', 'processing', 'completed', 'error'];

      statuses.forEach((status) => {
        mockEventSource.onmessage?.({
          data: JSON.stringify({ status }),
        });
      });

      await waitFor(() => {
        expect(result.current.data?.status).toBe('error');
      });
    });
  });
});
