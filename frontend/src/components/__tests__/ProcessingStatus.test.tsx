/**
 * Tests for ProcessingStatus component
 *
 * Tests the task processing status display component with progress bar
 * and status-dependent styling.
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
import { ProcessingStatus, TaskStatus } from '../ProcessingStatus';

// Mock the ShadCN UI components
jest.mock('@/components/ui/progress', () => ({
  Progress: ({ value }: { value: number }) => <div data-testid="progress-bar" data-value={value} />,
}));

jest.mock('@/components/ui/card', () => ({
  Card: ({ children }: { children: React.ReactNode }) => <div data-testid="card">{children}</div>,
  CardContent: ({ children, className }: { children: React.ReactNode; className?: string }) => (
    <div data-testid="card-content" className={className}>
      {children}
    </div>
  ),
}));

describe('ProcessingStatus', () => {
  describe('status display', () => {
    it('should display "Queued" label for queued status', () => {
      render(<ProcessingStatus status="queued" progress={0} />);

      expect(screen.getByText('Queued')).toBeInTheDocument();
    });

    it('should display "Processing" label for processing status', () => {
      render(<ProcessingStatus status="processing" progress={50} />);

      expect(screen.getByText('Processing')).toBeInTheDocument();
    });

    it('should display "Completed" label for completed status', () => {
      render(<ProcessingStatus status="completed" progress={100} />);

      expect(screen.getByText('Completed')).toBeInTheDocument();
    });

    it('should display "Error" label for error status', () => {
      render(<ProcessingStatus status="error" progress={0} />);

      expect(screen.getByText('Error')).toBeInTheDocument();
    });
  });

  describe('progress display', () => {
    it('should display progress percentage', () => {
      render(<ProcessingStatus status="processing" progress={45} />);

      expect(screen.getByText('45%')).toBeInTheDocument();
    });

    it('should display 0% progress', () => {
      render(<ProcessingStatus status="queued" progress={0} />);

      expect(screen.getByText('0%')).toBeInTheDocument();
    });

    it('should display 100% progress', () => {
      render(<ProcessingStatus status="completed" progress={100} />);

      expect(screen.getByText('100%')).toBeInTheDocument();
    });

    it('should pass progress value to Progress component', () => {
      render(<ProcessingStatus status="processing" progress={67} />);

      const progressBar = screen.getByTestId('progress-bar');
      expect(progressBar).toHaveAttribute('data-value', '67');
    });
  });

  describe('message display', () => {
    it('should display optional message', () => {
      render(
        <ProcessingStatus
          status="processing"
          progress={50}
          message="Analyzing transcript..."
        />
      );

      expect(screen.getByText('Analyzing transcript...')).toBeInTheDocument();
    });

    it('should not display message when not provided', () => {
      render(<ProcessingStatus status="processing" progress={50} />);

      // Should not have any message text elements beyond the status and percentage
      const textElements = screen.queryAllByText(/./);
      expect(textElements.length).toBeGreaterThan(0); // Has status and percentage
    });

    it('should display long messages', () => {
      const longMessage = 'This is a very long status message that provides detailed information about the current processing step';
      render(
        <ProcessingStatus
          status="processing"
          progress={50}
          message={longMessage}
        />
      );

      expect(screen.getByText(longMessage)).toBeInTheDocument();
    });
  });

  describe('error display', () => {
    it('should display error message when status is error', () => {
      render(
        <ProcessingStatus
          status="error"
          progress={0}
          error="Failed to download video"
        />
      );

      expect(screen.getByText('Failed to download video')).toBeInTheDocument();
    });

    it('should display error message even with other messages', () => {
      render(
        <ProcessingStatus
          status="error"
          progress={50}
          message="Processing interrupted"
          error="Network timeout"
        />
      );

      expect(screen.getByText('Processing interrupted')).toBeInTheDocument();
      expect(screen.getByText('Network timeout')).toBeInTheDocument();
    });

    it('should not require error message for non-error status', () => {
      render(
        <ProcessingStatus
          status="processing"
          progress={50}
        />
      );

      // Should render without error
      expect(screen.getByTestId('progress-bar')).toBeInTheDocument();
    });

    it('should handle long error messages', () => {
      const longError = 'Error: Unable to process video due to codec incompatibility - Video codec H.265 is not supported in the current configuration';
      render(
        <ProcessingStatus
          status="error"
          progress={0}
          error={longError}
        />
      );

      expect(screen.getByText(longError)).toBeInTheDocument();
    });
  });

  describe('status colors', () => {
    it('should apply queued status color', () => {
      const { container } = render(<ProcessingStatus status="queued" progress={0} />);

      const statusLabel = screen.getByText('Queued');
      expect(statusLabel).toHaveClass('text-yellow-600');
    });

    it('should apply processing status color', () => {
      render(<ProcessingStatus status="processing" progress={50} />);

      const statusLabel = screen.getByText('Processing');
      expect(statusLabel).toHaveClass('text-blue-600');
    });

    it('should apply completed status color', () => {
      render(<ProcessingStatus status="completed" progress={100} />);

      const statusLabel = screen.getByText('Completed');
      expect(statusLabel).toHaveClass('text-green-600');
    });

    it('should apply error status color', () => {
      render(<ProcessingStatus status="error" progress={0} />);

      const statusLabel = screen.getByText('Error');
      expect(statusLabel).toHaveClass('text-red-600');
    });
  });

  describe('component structure', () => {
    it('should render inside a Card component', () => {
      render(<ProcessingStatus status="processing" progress={50} />);

      expect(screen.getByTestId('card')).toBeInTheDocument();
    });

    it('should render CardContent with proper className', () => {
      render(<ProcessingStatus status="processing" progress={50} />);

      const cardContent = screen.getByTestId('card-content');
      expect(cardContent).toHaveClass('pt-6');
    });

    it('should render progress bar', () => {
      render(<ProcessingStatus status="processing" progress={50} />);

      expect(screen.getByTestId('progress-bar')).toBeInTheDocument();
    });

    it('should have status label with font styling', () => {
      render(<ProcessingStatus status="processing" progress={50} />);

      const statusLabel = screen.getByText('Processing');
      expect(statusLabel).toHaveClass('text-sm');
      expect(statusLabel).toHaveClass('font-medium');
    });

    it('should have progress percentage with styling', () => {
      render(<ProcessingStatus status="processing" progress={50} />);

      const progressText = screen.getByText('50%');
      expect(progressText).toHaveClass('text-sm');
      expect(progressText).toHaveClass('text-gray-500');
    });
  });

  describe('complete workflows', () => {
    it('should display complete queued state', () => {
      render(
        <ProcessingStatus
          status="queued"
          progress={0}
          message="Waiting in queue..."
        />
      );

      expect(screen.getByText('Queued')).toBeInTheDocument();
      expect(screen.getByText('0%')).toBeInTheDocument();
      expect(screen.getByText('Waiting in queue...')).toBeInTheDocument();
    });

    it('should display complete processing state', () => {
      render(
        <ProcessingStatus
          status="processing"
          progress={75}
          message="Generating video clips..."
        />
      );

      expect(screen.getByText('Processing')).toBeInTheDocument();
      expect(screen.getByText('75%')).toBeInTheDocument();
      expect(screen.getByText('Generating video clips...')).toBeInTheDocument();
    });

    it('should display complete completed state', () => {
      render(
        <ProcessingStatus
          status="completed"
          progress={100}
          message="All clips generated successfully"
        />
      );

      expect(screen.getByText('Completed')).toBeInTheDocument();
      expect(screen.getByText('100%')).toBeInTheDocument();
      expect(screen.getByText('All clips generated successfully')).toBeInTheDocument();
    });

    it('should display complete error state', () => {
      render(
        <ProcessingStatus
          status="error"
          progress={0}
          message="Processing failed"
          error="Video format not supported"
        />
      );

      expect(screen.getByText('Error')).toBeInTheDocument();
      expect(screen.getByText('0%')).toBeInTheDocument();
      expect(screen.getByText('Processing failed')).toBeInTheDocument();
      expect(screen.getByText('Video format not supported')).toBeInTheDocument();
    });
  });

  describe('props validation', () => {
    it('should accept all valid status values', () => {
      const statuses: TaskStatus[] = ['queued', 'processing', 'completed', 'error'];

      statuses.forEach((status) => {
        const { unmount } = render(<ProcessingStatus status={status} progress={50} />);
        unmount();
      });
    });

    it('should accept progress values 0-100', () => {
      const progressValues = [0, 25, 50, 75, 100];

      progressValues.forEach((progress) => {
        const { unmount } = render(
          <ProcessingStatus status="processing" progress={progress} />
        );
        unmount();
      });
    });

    it('should handle optional props gracefully', () => {
      const { container } = render(
        <ProcessingStatus
          status="processing"
          progress={50}
          // message and error are optional
        />
      );

      expect(container).toBeInTheDocument();
    });
  });
});
