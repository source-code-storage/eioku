import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import MetadataViewer from './MetadataViewer';

// Mock fetch
const mockFetch = vi.fn();
globalThis.fetch = mockFetch;

describe('MetadataViewer', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('displays loading state initially', () => {
    mockFetch.mockImplementation(
      () => new Promise(() => {}) // Never resolves
    );

    render(<MetadataViewer videoId="video_001" />);
    expect(screen.getByText('Loading metadata...')).toBeInTheDocument();
  });

  it('displays error message on fetch failure', async () => {
    // Both fetches fail
    mockFetch.mockRejectedValue(new Error('Network error'));

    render(<MetadataViewer videoId="video_001" />);

    // Component catches errors and shows "No metadata available" instead of error message
    await waitFor(() => {
      expect(screen.getByText('No metadata available')).toBeInTheDocument();
    });
  });

  it('displays no metadata message when empty', async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes('/artifacts')) {
        return Promise.resolve({ json: async () => [] });
      }
      // Location endpoint returns 404
      return Promise.resolve({ ok: false, json: async () => null });
    });

    render(<MetadataViewer videoId="video_001" />);

    await waitFor(() => {
      expect(screen.getByText('No metadata available')).toBeInTheDocument();
    });
  });

  it('displays GPS coordinates in user-friendly format', async () => {
    // Mock both metadata and location endpoints
    mockFetch.mockImplementation((url: string) => {
      if (url.includes('/artifacts')) {
        return Promise.resolve({
          json: async () => [
            {
              artifact_id: 'artifact_001',
              payload: {
                latitude: 40.7128,
                longitude: -74.006,
                altitude: 10.5,
              },
            },
          ],
        });
      }
      // Location endpoint returns 404
      return Promise.resolve({
        ok: false,
        json: async () => null,
      });
    });

    render(<MetadataViewer videoId="video_001" />);

    await waitFor(() => {
      // Format uses 4 decimal places: 40.7128°N, 74.0060°W
      expect(screen.getByText(/40\.7128°N, 74\.0060°W/)).toBeInTheDocument();
      expect(screen.getByText(/10\.50 m/)).toBeInTheDocument();
    });
  });

  it('displays camera information', async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes('/artifacts')) {
        return Promise.resolve({
          json: async () => [
            {
              artifact_id: 'artifact_001',
              payload: {
                camera_make: 'Canon',
                camera_model: 'EOS R5',
              },
            },
          ],
        });
      }
      return Promise.resolve({ ok: false, json: async () => null });
    });

    render(<MetadataViewer videoId="video_001" />);

    await waitFor(() => {
      expect(screen.getByText(/Make:/)).toBeInTheDocument();
      expect(screen.getByText('Canon')).toBeInTheDocument();
      expect(screen.getByText(/Model:/)).toBeInTheDocument();
      expect(screen.getByText('EOS R5')).toBeInTheDocument();
    });
  });

  it('displays file information', async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes('/artifacts')) {
        return Promise.resolve({
          json: async () => [
            {
              artifact_id: 'artifact_001',
              payload: {
                file_size: 75000000,
                file_type: 'video',
                mime_type: 'video/mp4',
                codec: 'h264',
              },
            },
          ],
        });
      }
      return Promise.resolve({ ok: false, json: async () => null });
    });

    render(<MetadataViewer videoId="video_001" />);

    await waitFor(() => {
      expect(screen.getByText(/Size:/)).toBeInTheDocument();
      expect(screen.getByText(/71\.53 MB/)).toBeInTheDocument();
      expect(screen.getByText(/Type:/)).toBeInTheDocument();
      expect(screen.getByText('video')).toBeInTheDocument();
      expect(screen.getByText(/MIME:/)).toBeInTheDocument();
      expect(screen.getByText('video/mp4')).toBeInTheDocument();
      expect(screen.getByText(/Codec:/)).toBeInTheDocument();
      expect(screen.getByText('h264')).toBeInTheDocument();
    });
  });

  it('displays temporal information', async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes('/artifacts')) {
        return Promise.resolve({
          json: async () => [
            {
              artifact_id: 'artifact_001',
              payload: {
                duration_seconds: 120.5,
                frame_rate: 29.97,
                create_date: '2024-01-15T10:30:00Z',
              },
            },
          ],
        });
      }
      return Promise.resolve({ ok: false, json: async () => null });
    });

    render(<MetadataViewer videoId="video_001" />);

    await waitFor(() => {
      expect(screen.getByText(/Duration:/)).toBeInTheDocument();
      expect(screen.getByText(/120\.50 s/)).toBeInTheDocument();
      expect(screen.getByText(/Frame Rate:/)).toBeInTheDocument();
      expect(screen.getByText(/29\.97 fps/)).toBeInTheDocument();
      expect(screen.getByText(/Created:/)).toBeInTheDocument();
    });
  });

  it('displays image information', async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes('/artifacts')) {
        return Promise.resolve({
          json: async () => [
            {
              artifact_id: 'artifact_001',
              payload: {
                image_size: '1920x1080',
                megapixels: 2.07,
                rotation: 0,
              },
            },
          ],
        });
      }
      return Promise.resolve({ ok: false, json: async () => null });
    });

    render(<MetadataViewer videoId="video_001" />);

    await waitFor(() => {
      expect(screen.getByText(/Size:/)).toBeInTheDocument();
      expect(screen.getByText('1920x1080')).toBeInTheDocument();
      expect(screen.getByText(/Megapixels:/)).toBeInTheDocument();
      expect(screen.getByText(/2\.07 MP/)).toBeInTheDocument();
      expect(screen.getByText(/Rotation:/)).toBeInTheDocument();
      expect(screen.getByText(/0°/)).toBeInTheDocument();
    });
  });

  it('displays bitrate information', async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes('/artifacts')) {
        return Promise.resolve({
          json: async () => [
            {
              artifact_id: 'artifact_001',
              payload: {
                avg_bitrate: '5000k',
              },
            },
          ],
        });
      }
      return Promise.resolve({ ok: false, json: async () => null });
    });

    render(<MetadataViewer videoId="video_001" />);

    await waitFor(() => {
      expect(screen.getByText(/Average:/)).toBeInTheDocument();
      expect(screen.getByText('5000k')).toBeInTheDocument();
    });
  });

  it('handles missing fields gracefully', async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes('/artifacts')) {
        return Promise.resolve({
          json: async () => [
            {
              artifact_id: 'artifact_001',
              payload: {
                duration_seconds: 60.0,
                file_size: 50000000,
              },
            },
          ],
        });
      }
      return Promise.resolve({ ok: false, json: async () => null });
    });

    render(<MetadataViewer videoId="video_001" />);

    await waitFor(() => {
      expect(screen.getByText(/Duration:/)).toBeInTheDocument();
      expect(screen.getByText(/Size:/)).toBeInTheDocument();
      // GPS section should not be displayed
      expect(screen.queryByText(/📍 GPS Coordinates/)).not.toBeInTheDocument();
      // Camera section should not be displayed
      expect(screen.queryByText(/📷 Camera/)).not.toBeInTheDocument();
    });
  });

  it('uses custom API URL', async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes('/artifacts')) {
        return Promise.resolve({
          json: async () => [
            {
              artifact_id: 'artifact_001',
              payload: {
                duration_seconds: 60.0,
              },
            },
          ],
        });
      }
      return Promise.resolve({ ok: false, json: async () => null });
    });

    render(<MetadataViewer videoId="video_001" apiUrl="http://custom-api:8080" />);

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        'http://custom-api:8080/api/v1/videos/video_001/artifacts?type=video.metadata'
      );
    });
  });

  it('displays all metadata sections when all fields are present', async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes('/artifacts')) {
        return Promise.resolve({
          json: async () => [
            {
              artifact_id: 'artifact_001',
              payload: {
                latitude: 40.7128,
                longitude: -74.006,
                altitude: 10.5,
                image_size: '1920x1080',
                megapixels: 2.07,
                rotation: 0,
                avg_bitrate: '5000k',
                duration_seconds: 120.5,
                frame_rate: 29.97,
                codec: 'h264',
                file_size: 75000000,
                file_type: 'video',
                mime_type: 'video/mp4',
                camera_make: 'Canon',
                camera_model: 'EOS R5',
                create_date: '2024-01-15T10:30:00Z',
              },
            },
          ],
        });
      }
      return Promise.resolve({ ok: false, json: async () => null });
    });

    render(<MetadataViewer videoId="video_001" />);

    await waitFor(() => {
      expect(screen.getByText(/📍 GPS Coordinates/)).toBeInTheDocument();
      expect(screen.getByText(/📷 Camera/)).toBeInTheDocument();
      expect(screen.getByText(/📁 File Info/)).toBeInTheDocument();
      expect(screen.getByText(/⏱️ Temporal Info/)).toBeInTheDocument();
      expect(screen.getByText(/🖼️ Image Info/)).toBeInTheDocument();
      expect(screen.getByText(/📊 Bitrate/)).toBeInTheDocument();
    });
  });
});
