import React, { useEffect, useState } from 'react';

interface BoundingBox {
  frame: number;
  timestamp: number;
  bbox: [number, number, number, number];
  confidence: number;
}

interface FaceGroup {
  face_id: string;
  person_id: string | null;
  occurrences: number;
  confidence: number;
  bounding_boxes: BoundingBox[];
}

interface ArtifactPayload {
  frame_index?: number;
  timestamp_ms?: number;
  confidence?: number;
  cluster_id?: string;
  bbox?: {
    x: number;
    y: number;
    width: number;
    height: number;
  };
}

interface Artifact {
  payload: ArtifactPayload;
  span_start_ms?: number;
}

interface Props {
  videoId: string;
  videoRef: React.RefObject<HTMLVideoElement>;
  canvasRef: React.RefObject<HTMLCanvasElement>;
  enabled: boolean;
  apiUrl?: string;
}

export default function FaceDetectionOverlay({
  videoId,
  videoRef,
  canvasRef,
  enabled,
  apiUrl = 'http://localhost:8080',
}: Props) {
  const [faces, setFaces] = useState<FaceGroup[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${apiUrl}/api/v1/videos/${videoId}/artifacts?type=face.detection`)
      .then(res => res.json())
      .then((data: Artifact[]) => {
        const faceMap = new Map<string, FaceGroup>();

        data.forEach(artifact => {
          const payload = artifact.payload;

          if (!payload.bbox) return;

          const clusterId = payload.cluster_id || `face_${Math.random()}`;

          if (!faceMap.has(clusterId)) {
            faceMap.set(clusterId, {
              face_id: clusterId,
              person_id: null,
              occurrences: 0,
              confidence: payload.confidence || 0,
              bounding_boxes: [],
            });
          }
          const face = faceMap.get(clusterId)!;
          face.occurrences += 1;

          const bb = payload.bbox;
          if (
            !bb ||
            typeof bb.x !== 'number' ||
            typeof bb.y !== 'number' ||
            typeof bb.width !== 'number' ||
            typeof bb.height !== 'number'
          ) {
            return;
          }

          const bbox: [number, number, number, number] = [
            bb.x,
            bb.y,
            bb.x + bb.width,
            bb.y + bb.height,
          ];

          face.bounding_boxes.push({
            frame: payload.frame_index || 0,
            timestamp: (artifact.span_start_ms || 0) / 1000,
            bbox,
            confidence: payload.confidence || 0,
          });
        });

        setFaces(Array.from(faceMap.values()));
        setLoading(false);
      })
      .catch(err => {
        setError(err.message);
        setLoading(false);
      });
  }, [videoId, apiUrl]);

  // Track video time and draw faces
  useEffect(() => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas || faces.length === 0 || !enabled) return;

    const drawFaces = (timeSeconds: number) => {
      const ctx = canvas.getContext('2d');
      if (!ctx) return;

      // Clear canvas
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      // Find boxes for current time
      const boxes: BoundingBox[] = [];

      faces.forEach(face => {
        face.bounding_boxes.forEach(box => {
          if (Math.abs(box.timestamp - timeSeconds) < 1.0) {
            boxes.push(box);
          }
        });
      });

      // Draw boxes
      boxes.forEach(box => {
        const [x1, y1, x2, y2] = box.bbox;
        const width = x2 - x1;
        const height = y2 - y1;

        // Scale coordinates to canvas size
        const scaleX = canvas.width / video.videoWidth;
        const scaleY = canvas.height / video.videoHeight;

        const scaledX = x1 * scaleX;
        const scaledY = y1 * scaleY;
        const scaledWidth = width * scaleX;
        const scaledHeight = height * scaleY;

        // Color based on confidence
        let color = 'rgba(0, 255, 0, 0.8)'; // green
        if (box.confidence < 0.5) {
          color = 'rgba(255, 0, 0, 0.8)'; // red
        } else if (box.confidence < 0.7) {
          color = 'rgba(255, 255, 0, 0.8)'; // yellow
        }

        // Draw box
        ctx.strokeStyle = color;
        ctx.lineWidth = 3;
        ctx.strokeRect(scaledX, scaledY, scaledWidth, scaledHeight);

        // Draw confidence label
        ctx.fillStyle = color;
        ctx.font = '14px Arial';
        ctx.fillText(`${(box.confidence * 100).toFixed(1)}%`, scaledX, scaledY - 5);
      });
    };

    const handleTimeUpdate = () => {
      drawFaces(video.currentTime);
    };

    const handleLoadedMetadata = () => {
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      drawFaces(video.currentTime);
    };

    video.addEventListener('timeupdate', handleTimeUpdate);
    video.addEventListener('loadedmetadata', handleLoadedMetadata);

    // Initial draw if video is already loaded
    if (video.readyState >= 1) {
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      drawFaces(video.currentTime);
    }

    return () => {
      video.removeEventListener('timeupdate', handleTimeUpdate);
      video.removeEventListener('loadedmetadata', handleLoadedMetadata);
    };
  }, [videoRef, canvasRef, faces, enabled]);

  if (loading) {
    return null;
  }

  if (error) {
    console.error('Face detection error:', error);
    return null;
  }

  return null;
}
