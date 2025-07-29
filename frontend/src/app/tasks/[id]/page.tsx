"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { useSession } from "@/lib/auth-client";
import { ArrowLeft, Download, Clock, Star } from "lucide-react";
import Link from "next/link";

interface Clip {
  id: string;
  filename: string;
  file_path: string;
  start_time: string;
  end_time: string;
  duration: number;
  text: string;
  relevance_score: number;
  reasoning: string;
  clip_order: number;
  created_at: string;
  video_url: string;
}

interface TaskDetails {
  id: string;
  user_id: string;
  source_id: string;
  source_title: string;
  source_type: string;
  clips_count: number;
  created_at: string;
  updated_at: string;
}

export default function TaskPage() {
  const params = useParams();
  const router = useRouter();
  const { data: session } = useSession();
  const [task, setTask] = useState<TaskDetails | null>(null);
  const [clips, setClips] = useState<Clip[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!session?.user?.id || !params.id) return;

    const fetchTaskData = async () => {
      try {
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

        // Fetch task details
        const taskResponse = await fetch(`${apiUrl}/tasks/${params.id}`, {
          headers: {
            'user_id': session.user.id,
          },
        });

        if (!taskResponse.ok) {
          throw new Error(`Failed to fetch task: ${taskResponse.status}`);
        }

        const taskData = await taskResponse.json();
        setTask(taskData);

        // Fetch clips for this task
        const clipsResponse = await fetch(`${apiUrl}/tasks/${params.id}/clips`, {
          headers: {
            'user_id': session.user.id,
          },
        });

        if (!clipsResponse.ok) {
          throw new Error(`Failed to fetch clips: ${clipsResponse.status}`);
        }

        const clipsData = await clipsResponse.json();
        setClips(clipsData.clips || []);

      } catch (err) {
        console.error('Error fetching task data:', err);
        setError(err instanceof Error ? err.message : 'Failed to load task');
      } finally {
        setIsLoading(false);
      }
    };

    fetchTaskData();
  }, [session?.user?.id, params.id]);

  const formatDuration = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const getScoreColor = (score: number) => {
    if (score >= 0.8) return "bg-green-100 text-green-800";
    if (score >= 0.6) return "bg-yellow-100 text-yellow-800";
    return "bg-red-100 text-red-800";
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-white p-4">
        <div className="max-w-6xl mx-auto">
          <div className="mb-6">
            <Skeleton className="h-8 w-48 mb-2" />
            <Skeleton className="h-4 w-96" />
          </div>
          <div className="grid gap-6">
            {[1, 2, 3].map((i) => (
              <Card key={i}>
                <CardContent className="p-6">
                  <Skeleton className="h-48 w-full mb-4" />
                  <Skeleton className="h-4 w-full mb-2" />
                  <Skeleton className="h-4 w-3/4" />
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-white p-4">
        <div className="max-w-6xl mx-auto">
          <Alert>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
          <Link href="/" className="mt-4 inline-block">
            <Button variant="outline">
              <ArrowLeft className="w-4 h-4 mr-2" />
              Back to Home
            </Button>
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-white">
      {/* Header */}
      <div className="border-b bg-white">
        <div className="max-w-6xl mx-auto px-4 py-6">
          <div className="flex items-center gap-4 mb-4">
            <Link href="/">
              <Button variant="ghost" size="sm">
                <ArrowLeft className="w-4 h-4 mr-2" />
                Back
              </Button>
            </Link>
          </div>

          {task && (
            <div>
              <h1 className="text-2xl font-bold text-black mb-2">
                {task.source_title}
              </h1>
              <div className="flex items-center gap-4 text-sm text-gray-600">
                <Badge variant="outline">{task.source_type}</Badge>
                <span className="flex items-center gap-1">
                  <Clock className="w-4 h-4" />
                  {new Date(task.created_at).toLocaleDateString()}
                </span>
                <span>{clips.length} clips generated</span>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-6xl mx-auto px-4 py-8">
        {clips.length === 0 ? (
          <Card>
            <CardContent className="p-8 text-center">
              <p className="text-gray-600">No clips have been generated for this task yet.</p>
            </CardContent>
          </Card>
        ) : (
          <div className="grid gap-6">
            {clips.map((clip) => (
              <Card key={clip.id} className="overflow-hidden">
                <CardContent className="p-0">
                  <div className="flex flex-col lg:flex-row">
                    {/* Video Player */}
                    <div className="bg-black relative flex-shrink-0 flex items-center justify-center lg:w-80">
                      <video
                        controls
                        className="w-full h-auto max-h-[70vh] object-contain"
                        poster="/placeholder-video.jpg"
                      >
                        <source src={`http://localhost:8000${clip.video_url}`} type="video/mp4" />
                        Your browser does not support the video tag.
                      </video>
                    </div>

                    {/* Clip Details */}
                    <div className="p-6">
                      <div className="flex items-start justify-between mb-4">
                        <div>
                          <h3 className="font-semibold text-lg text-black mb-1">
                            Clip {clip.clip_order}
                          </h3>
                          <div className="flex items-center gap-2 text-sm text-gray-600">
                            <span>{clip.start_time} - {clip.end_time}</span>
                            <span>•</span>
                            <span>{formatDuration(clip.duration)}</span>
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          <Badge className={getScoreColor(clip.relevance_score)}>
                            <Star className="w-3 h-3 mr-1" />
                            {(clip.relevance_score * 100).toFixed(0)}%
                          </Badge>
                        </div>
                      </div>

                      {clip.text && (
                        <div className="mb-4">
                          <h4 className="font-medium text-black mb-2">Transcript</h4>
                          <p className="text-sm text-gray-700 bg-gray-50 p-3 rounded">
                            {clip.text}
                          </p>
                        </div>
                      )}

                      {clip.reasoning && (
                        <div className="mb-4">
                          <h4 className="font-medium text-black mb-2">AI Analysis</h4>
                          <p className="text-sm text-gray-600">
                            {clip.reasoning}
                          </p>
                        </div>
                      )}

                      <div className="flex gap-2">
                        <Button size="sm" variant="outline" asChild>
                          <a href={`http://localhost:8000${clip.video_url}`} download={clip.filename}>
                            <Download className="w-4 h-4 mr-2" />
                            Download
                          </a>
                        </Button>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
