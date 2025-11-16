/**
 * EmptyState component for displaying empty or placeholder states.
 * Used across the application for consistent empty state UI.
 */

import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { LucideIcon } from "lucide-react";
import Link from "next/link";

interface EmptyStateProps {
  /**
   * Icon to display in the empty state
   */
  icon: LucideIcon;

  /**
   * Icon styling - determines background color and icon color
   * @default "default"
   */
  iconStyle?: "default" | "warning" | "error" | "info";

  /**
   * Title text for the empty state
   */
  title: string;

  /**
   * Description text explaining the empty state
   */
  description: string;

  /**
   * Optional action button configuration
   */
  action?: {
    /**
     * Button label
     */
    label: string;

    /**
     * Link href or onClick handler
     */
    href?: string;
    onClick?: () => void;

    /**
     * Optional icon for the button
     */
    icon?: LucideIcon;
  };

  /**
   * Whether the icon should animate (pulse)
   * @default false
   */
  animateIcon?: boolean;
}

export function EmptyState({
  icon: Icon,
  iconStyle = "default",
  title,
  description,
  action,
  animateIcon = false,
}: EmptyStateProps) {
  const iconBackgroundClasses = {
    default: "bg-gray-100",
    warning: "bg-yellow-100",
    error: "bg-red-100",
    info: "bg-blue-100",
  };

  const iconColorClasses = {
    default: "text-gray-400",
    warning: "text-yellow-600",
    error: "text-red-600",
    info: "text-blue-500",
  };

  const ActionButton = action?.icon;

  return (
    <Card>
      <CardContent className="p-12 text-center">
        <div
          className={`w-16 h-16 ${iconBackgroundClasses[iconStyle]} rounded-full flex items-center justify-center mx-auto mb-4`}
        >
          <Icon
            className={`w-8 h-8 ${iconColorClasses[iconStyle]} ${
              animateIcon ? "animate-pulse" : ""
            }`}
          />
        </div>
        <h2 className="text-xl font-semibold text-black mb-2">{title}</h2>
        <p className="text-gray-600 mb-6">{description}</p>
        {action && (
          <>
            {action.href ? (
              <Link href={action.href}>
                <Button>
                  {ActionButton && <ActionButton className="w-4 h-4 mr-2" />}
                  {action.label}
                </Button>
              </Link>
            ) : (
              <Button onClick={action.onClick}>
                {ActionButton && <ActionButton className="w-4 h-4 mr-2" />}
                {action.label}
              </Button>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}
