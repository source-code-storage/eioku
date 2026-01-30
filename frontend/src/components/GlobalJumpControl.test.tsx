import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import GlobalJumpControl, { ArtifactType } from './GlobalJumpControl';

// Mock fetch
const mockFetch = vi.fn();
globalThis.fetch = mockFetch;

describe('GlobalJumpControl', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Default mock for fetch to prevent unhandled promises
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ results: [], has_more: false }),
    });
  });

  describe('Rendering modes', () => {
    it('renders without video (search page mode)', () => {
      render(<GlobalJumpControl />);
      
      // Component should render with default state
      expect(screen.getByText('Jump to:')).toBeInTheDocument();
      expect(screen.getByRole('combobox')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /previous/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /next/i })).toBeInTheDocument();
    });

    it('renders with video (player mode)', () => {
      const videoRef = { current: document.createElement('video') };
      
      render(
        <GlobalJumpControl 
          videoId="test-video-123" 
          videoRef={videoRef}
        />
      );
      
      // Component should render with video context
      expect(screen.getByText('Jump to:')).toBeInTheDocument();
      expect(screen.getByRole('combobox')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /previous/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /next/i })).toBeInTheDocument();
    });
  });

  describe('Artifact type dropdown', () => {
    it('contains all 7 artifact type options', () => {
      render(<GlobalJumpControl />);
      
      const dropdown = screen.getByRole('combobox');
      const options = dropdown.querySelectorAll('option');
      
      // Should have exactly 7 options
      expect(options).toHaveLength(7);
      
      // Verify all artifact types are present
      const expectedTypes: ArtifactType[] = ['object', 'face', 'transcript', 'ocr', 'scene', 'place', 'location'];
      const optionValues = Array.from(options).map(opt => opt.getAttribute('value'));
      
      expectedTypes.forEach(type => {
        expect(optionValues).toContain(type);
      });
    });

    it('displays correct labels for each artifact type', () => {
      render(<GlobalJumpControl />);
      
      const dropdown = screen.getByRole('combobox');
      
      // Check that labels are displayed correctly
      expect(dropdown).toHaveTextContent('Objects');
      expect(dropdown).toHaveTextContent('Faces');
      expect(dropdown).toHaveTextContent('Transcript');
      expect(dropdown).toHaveTextContent('OCR Text');
      expect(dropdown).toHaveTextContent('Scenes');
      expect(dropdown).toHaveTextContent('Places');
      expect(dropdown).toHaveTextContent('Location');
    });
  });

  describe('Input field visibility per artifact type', () => {
    it('shows label input for object type', () => {
      render(<GlobalJumpControl initialArtifactType="object" />);
      
      expect(screen.getByText('Label:')).toBeInTheDocument();
      expect(screen.getByPlaceholderText('e.g., dog, car, person')).toBeInTheDocument();
      expect(screen.queryByText('Search:')).not.toBeInTheDocument();
      expect(screen.queryByText('Face ID:')).not.toBeInTheDocument();
    });

    it('shows label input for place type', () => {
      render(<GlobalJumpControl initialArtifactType="place" />);
      
      expect(screen.getByText('Label:')).toBeInTheDocument();
      expect(screen.getByPlaceholderText('e.g., kitchen, beach, office')).toBeInTheDocument();
      expect(screen.queryByText('Search:')).not.toBeInTheDocument();
      expect(screen.queryByText('Face ID:')).not.toBeInTheDocument();
    });

    it('shows query input for transcript type', () => {
      render(<GlobalJumpControl initialArtifactType="transcript" />);
      
      expect(screen.getByText('Search:')).toBeInTheDocument();
      expect(screen.getByPlaceholderText('Search spoken words...')).toBeInTheDocument();
      expect(screen.queryByText('Label:')).not.toBeInTheDocument();
      expect(screen.queryByText('Face ID:')).not.toBeInTheDocument();
    });

    it('shows query input for ocr type', () => {
      render(<GlobalJumpControl initialArtifactType="ocr" />);
      
      expect(screen.getByText('Search:')).toBeInTheDocument();
      expect(screen.getByPlaceholderText('Search on-screen text...')).toBeInTheDocument();
      expect(screen.queryByText('Label:')).not.toBeInTheDocument();
      expect(screen.queryByText('Face ID:')).not.toBeInTheDocument();
    });

    it('shows query input for location type', () => {
      render(<GlobalJumpControl initialArtifactType="location" />);
      
      expect(screen.getByText('Search:')).toBeInTheDocument();
      expect(screen.getByPlaceholderText('e.g., Tokyo, Japan, California')).toBeInTheDocument();
      expect(screen.queryByText('Label:')).not.toBeInTheDocument();
      expect(screen.queryByText('Face ID:')).not.toBeInTheDocument();
    });

    it('shows face cluster ID input for face type', () => {
      render(<GlobalJumpControl initialArtifactType="face" />);
      
      expect(screen.getByText('Face ID:')).toBeInTheDocument();
      expect(screen.getByPlaceholderText('Face cluster ID...')).toBeInTheDocument();
      expect(screen.queryByText('Label:')).not.toBeInTheDocument();
      expect(screen.queryByText('Search:')).not.toBeInTheDocument();
    });

    it('hides both label and query inputs for scene type', () => {
      render(<GlobalJumpControl initialArtifactType="scene" />);
      
      expect(screen.queryByText('Label:')).not.toBeInTheDocument();
      expect(screen.queryByText('Search:')).not.toBeInTheDocument();
      expect(screen.queryByText('Face ID:')).not.toBeInTheDocument();
    });

    it('updates input fields when artifact type changes', () => {
      render(<GlobalJumpControl initialArtifactType="object" />);
      
      // Initially shows label input for object
      expect(screen.getByText('Label:')).toBeInTheDocument();
      
      // Change to transcript
      const dropdown = screen.getByRole('combobox');
      fireEvent.change(dropdown, { target: { value: 'transcript' } });
      
      // Now should show query input
      expect(screen.queryByText('Label:')).not.toBeInTheDocument();
      expect(screen.getByText('Search:')).toBeInTheDocument();
      
      // Change to scene
      fireEvent.change(dropdown, { target: { value: 'scene' } });
      
      // Should hide both inputs
      expect(screen.queryByText('Label:')).not.toBeInTheDocument();
      expect(screen.queryByText('Search:')).not.toBeInTheDocument();
    });
  });

  describe('Confidence slider visibility', () => {
    it('shows confidence slider for object type', () => {
      render(<GlobalJumpControl initialArtifactType="object" />);
      
      expect(screen.getByText('Confidence:')).toBeInTheDocument();
      expect(screen.getByRole('slider')).toBeInTheDocument();
    });

    it('shows confidence slider for face type', () => {
      render(<GlobalJumpControl initialArtifactType="face" />);
      
      expect(screen.getByText('Confidence:')).toBeInTheDocument();
      expect(screen.getByRole('slider')).toBeInTheDocument();
    });

    it('shows confidence slider for place type', () => {
      render(<GlobalJumpControl initialArtifactType="place" />);
      
      expect(screen.getByText('Confidence:')).toBeInTheDocument();
      expect(screen.getByRole('slider')).toBeInTheDocument();
    });

    it('hides confidence slider for transcript type', () => {
      render(<GlobalJumpControl initialArtifactType="transcript" />);
      
      expect(screen.queryByText('Confidence:')).not.toBeInTheDocument();
      expect(screen.queryByRole('slider')).not.toBeInTheDocument();
    });

    it('hides confidence slider for ocr type', () => {
      render(<GlobalJumpControl initialArtifactType="ocr" />);
      
      expect(screen.queryByText('Confidence:')).not.toBeInTheDocument();
      expect(screen.queryByRole('slider')).not.toBeInTheDocument();
    });

    it('hides confidence slider for scene type', () => {
      render(<GlobalJumpControl initialArtifactType="scene" />);
      
      expect(screen.queryByText('Confidence:')).not.toBeInTheDocument();
      expect(screen.queryByRole('slider')).not.toBeInTheDocument();
    });

    it('hides confidence slider for location type', () => {
      render(<GlobalJumpControl initialArtifactType="location" />);
      
      expect(screen.queryByText('Confidence:')).not.toBeInTheDocument();
      expect(screen.queryByRole('slider')).not.toBeInTheDocument();
    });

    it('updates confidence slider visibility when artifact type changes', () => {
      render(<GlobalJumpControl initialArtifactType="object" />);
      
      // Initially shows slider for object
      expect(screen.getByText('Confidence:')).toBeInTheDocument();
      
      // Change to transcript (no slider)
      const dropdown = screen.getByRole('combobox');
      fireEvent.change(dropdown, { target: { value: 'transcript' } });
      
      expect(screen.queryByText('Confidence:')).not.toBeInTheDocument();
      
      // Change to face (has slider)
      fireEvent.change(dropdown, { target: { value: 'face' } });
      
      expect(screen.getByText('Confidence:')).toBeInTheDocument();
    });

    it('displays confidence value as percentage', () => {
      render(<GlobalJumpControl initialArtifactType="object" initialConfidence={0.7} />);
      
      expect(screen.getByText('70%')).toBeInTheDocument();
    });

    it('updates percentage display when slider changes', () => {
      render(<GlobalJumpControl initialArtifactType="object" initialConfidence={0} />);
      
      expect(screen.getByText('0%')).toBeInTheDocument();
      
      const slider = screen.getByRole('slider');
      fireEvent.change(slider, { target: { value: '0.5' } });
      
      expect(screen.getByText('50%')).toBeInTheDocument();
    });
  });

  describe('Export Clip button', () => {
    it('does not show export button when no videoId is provided (search page mode)', () => {
      render(<GlobalJumpControl />);
      
      expect(screen.queryByRole('button', { name: /export clip/i })).not.toBeInTheDocument();
    });

    it('shows export button when videoId is provided (player mode)', () => {
      render(<GlobalJumpControl videoId="test-video-123" />);
      
      // Export button should be visible when viewing a video
      expect(screen.getByRole('button', { name: /export clip/i })).toBeInTheDocument();
    });

    it('shows timestamp inputs when videoId is provided', () => {
      render(<GlobalJumpControl videoId="test-video-123" />);
      
      // Should show start and end time inputs
      expect(screen.getByTitle('Start time (MM:SS)')).toBeInTheDocument();
      expect(screen.getByTitle('End time (MM:SS)')).toBeInTheDocument();
      
      // Should show set-to-current-time buttons
      expect(screen.getAllByTitle(/Set .* to current time/)).toHaveLength(2);
    });

    it('updates timestamps after successful navigation', async () => {
      // Mock successful API response with a result
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          results: [{
            video_id: 'test-video-123',
            video_filename: 'test.mp4',
            file_created_at: '2025-01-01T00:00:00Z',
            jump_to: { start_ms: 65000, end_ms: 125000 },
            artifact_id: 'artifact-1',
            preview: {},
          }],
          has_more: true,
        }),
      });

      render(<GlobalJumpControl videoId="test-video-123" />);
      
      // Click Next to trigger navigation
      const nextButton = screen.getByRole('button', { name: /next/i });
      fireEvent.click(nextButton);
      
      // Wait for the match display to update (indicates navigation completed)
      await screen.findByText(/test\.mp4 @ 1:05/);
      
      // Check timestamps updated (1:05 and 2:05)
      const startInput = screen.getByTitle('Start time (MM:SS)');
      const endInput = screen.getByTitle('End time (MM:SS)');
      
      expect(startInput).toHaveValue('1:05');
      expect(endInput).toHaveValue('2:05');
    });
  });
});
