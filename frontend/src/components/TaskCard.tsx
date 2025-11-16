/**
 * TaskCard component for displaying task information in a card format.
 * Used in task lists and latest task previews.
 */

import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { StatusBadge } from "@/components/StatusBadge";
import { formatDate, formatSimpleDate } from "@/lib/date-utils";
import { Clock } from "lucide-react";
import Link from "next/link";

interface Task {
  id: string;
  source_title: string;
  source_type: string;
  status: string;
  clips_count: number;
  created_at: string;
}

interface TaskCardProps {
  /**
   * Task data to display
   */
  task: Task;

  /**
   * Date format to use
   * @default "detailed" - Shows full date with time
   */
  dateFormat?: "simple" | "detailed";

  /**
   * Whether the card is clickable (wrapped in Link)
   * @default true
   */
  clickable?: boolean;
}

export function TaskCard({
  task,
  dateFormat = "detailed",
  clickable = true,
}: TaskCardProps) {
  const formattedDate =
    dateFormat === "simple"
      ? formatSimpleDate(task.created_at)
      : formatDate(task.created_at);

  const content = (
    <Card className="hover:shadow-md transition-shadow cursor-pointer">
      <CardContent className="p-6">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <h3 className="text-lg font-semibold text-black mb-2 truncate">
              {task.source_title}
            </h3>
            <div className="flex flex-wrap items-center gap-3 text-sm text-gray-600">
              <Badge variant="outline" className="capitalize">
                {task.source_type}
              </Badge>
              <span className="flex items-center gap-1">
                <Clock className="w-4 h-4" />
                {formattedDate}
              </span>
              <span>
                {task.clips_count} {task.clips_count === 1 ? "clip" : "clips"}
              </span>
            </div>
          </div>
          <div className="flex-shrink-0">
            <StatusBadge status={task.status} />
          </div>
        </div>
      </CardContent>
    </Card>
  );

  if (clickable) {
    return <Link href={`/tasks/${task.id}`}>{content}</Link>;
  }

  return content;
}
