"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Separator } from "@/components/ui/separator";
import { ErrorAlert } from "@/components/alerts/ErrorAlert";
import { SuccessAlert } from "@/components/alerts/SuccessAlert";
import { Skeleton } from "@/components/ui/skeleton";
import { Slider } from "@/components/ui/slider";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import { FontCustomization } from "@/components/FontCustomization";
import { useSession } from "@/lib/auth-client";
import { useUserPreferences } from "@/hooks/useUserPreferences";
import { useApiUrl } from "@/hooks/useApiUrl";
import { UserPreferences } from "@/types/preferences";
import Link from "next/link";
import { PlayCircle, Settings, Clock, Sparkles, Image } from "lucide-react";

export default function SettingsPage() {
  const [clipMinLength, setClipMinLength] = useState(10);
  const [clipTargetLength, setClipTargetLength] = useState(30);
  const [clipMaxLength, setClipMaxLength] = useState(45);
  const [customAiPrompt, setCustomAiPrompt] = useState("");
  const [useCustomPrompt, setUseCustomPrompt] = useState(false);
  const [defaultPrompt, setDefaultPrompt] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [logoFile, setLogoFile] = useState<File | null>(null);
  const [logoPreview, setLogoPreview] = useState<string | null>(null);
  const [logoCornerPosition, setLogoCornerPosition] = useState<"top-left" | "top-right" | "bottom-left" | "bottom-right">("top-right");
  const [logoUploadProgress, setLogoUploadProgress] = useState(false);
  const { data: session, isPending } = useSession();
  const { preferences, isLoading: isLoadingPrefs, error: prefsError, updatePreferences } = useUserPreferences();
  const apiUrl = useApiUrl();

  // Validate clip lengths to ensure min < target < max
  const validateClipLengths = (): boolean => {
    if (clipMinLength >= clipTargetLength) {
      setError("Minimum length must be less than target length");
      return false;
    }
    if (clipTargetLength >= clipMaxLength) {
      setError("Target length must be less than maximum length");
      return false;
    }
    if (clipMinLength < 5 || clipMaxLength > 60) {
      setError("Clip lengths must be between 5 and 60 seconds");
      return false;
    }
    return true;
  };

  // Load default AI prompt from backend
  useEffect(() => {
    const loadDefaultPrompt = async () => {
      try {
        const response = await fetch(`${apiUrl}/default-prompt`);
        if (response.ok) {
          const data = await response.json();
          setDefaultPrompt(data.prompt || "");
        }
      } catch (error) {
        console.error('Failed to load default prompt:', error);
      }
    };

    loadDefaultPrompt();
  }, [apiUrl]);

  // Load initial state from preferences
  useEffect(() => {
    if (preferences) {
      setClipMinLength(preferences.clipMinLength);
      setClipTargetLength(preferences.clipTargetLength);
      setClipMaxLength(preferences.clipMaxLength);
      setCustomAiPrompt(preferences.customAiPrompt || "");
      setUseCustomPrompt(!!preferences.customAiPrompt);
    }
  }, [preferences]);

  const handleSavePreferences = async () => {
    setIsLoading(true);
    setError(null);
    setSuccess(false);

    // Validate clip lengths
    if (!validateClipLengths()) {
      setIsLoading(false);
      return;
    }

    try {
      const response = await fetch('/api/preferences', {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          clipMinLength,
          clipTargetLength,
          clipMaxLength,
          customAiPrompt: useCustomPrompt ? customAiPrompt : null,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Failed to save preferences');
      }

      setSuccess(true);
      setTimeout(() => setSuccess(false), 3000);
    } catch (error) {
      console.error('Error saving preferences:', error);
      setError(error instanceof Error ? error.message : 'Failed to save preferences');
    } finally {
      setIsLoading(false);
    }
  };

  const handleLogoFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setLogoFile(file);
      const reader = new FileReader();
      reader.onloadend = () => {
        setLogoPreview(reader.result as string);
      };
      reader.readAsDataURL(file);
    }
  };

  const handleLogoUpload = async () => {
    if (!logoFile) return;

    setLogoUploadProgress(true);
    setError(null);

    try {
      const formData = new FormData();
      formData.append("logo", logoFile);
      formData.append("corner_position", logoCornerPosition);

      const response = await fetch(`${apiUrl}/upload-logo`, {
        method: "POST",
        headers: {
          "user_id": session!.user.id,
        },
        body: formData,
      });

      if (!response.ok) {
        throw new Error("Failed to upload logo");
      }

      setSuccess(true);
      setLogoFile(null);
      setLogoPreview(null);
      setTimeout(() => setSuccess(false), 3000);
    } catch (error) {
      setError(error instanceof Error ? error.message : "Failed to upload logo");
    } finally {
      setLogoUploadProgress(false);
    }
  };

  if (isPending || isLoadingPrefs) {
    return (
      <div className="min-h-screen bg-white flex items-center justify-center p-4">
        <div className="space-y-4">
          <Skeleton className="h-4 w-32 mx-auto" />
          <Skeleton className="h-4 w-48 mx-auto" />
          <Skeleton className="h-4 w-24 mx-auto" />
        </div>
      </div>
    );
  }

  if (!session?.user) {
    return (
      <div className="min-h-screen bg-white">
        <div className="max-w-4xl mx-auto px-4 py-24">
          <div className="text-center">
            <h1 className="text-3xl font-bold text-black mb-4">
              Sign In Required
            </h1>
            <p className="text-gray-600 mb-8">
              You need to sign in to access your settings
            </p>
            <Link href="/sign-in">
              <Button size="lg">Sign In</Button>
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-white">
      {/* Header */}
      <div className="border-b bg-white">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex justify-between items-center">
            <Link href="/" className="flex items-center gap-3 hover:opacity-80 transition-opacity cursor-pointer">
              <div className="w-8 h-8 bg-black flex items-center justify-center">
                <PlayCircle className="w-5 h-5 text-white" />
              </div>
              <h1 className="text-xl font-bold text-black">SupoClip</h1>
            </Link>

            <div className="flex items-center gap-3">
              <Avatar className="w-8 h-8">
                <AvatarImage src={session.user.image || ""} />
                <AvatarFallback className="bg-gray-100 text-black text-sm">
                  {session.user.name?.charAt(0) || session.user.email?.charAt(0) || "U"}
                </AvatarFallback>
              </Avatar>
              <div className="hidden sm:block">
                <p className="text-sm font-medium text-black">{session.user.name}</p>
                <p className="text-xs text-gray-500">{session.user.email}</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-4xl mx-auto px-4 py-16">
        <div className="max-w-xl mx-auto">
          <div className="mb-8">
            <div className="flex items-center gap-2 mb-2">
              <Settings className="w-6 h-6 text-black" />
              <h2 className="text-2xl font-bold text-black">
                Settings
              </h2>
            </div>
            <p className="text-gray-600">
              Configure your default preferences for video clip generation
            </p>
          </div>

          <Separator className="my-8" />

          <div className="space-y-8">
            {/* Font Preferences Section */}
            <div className="space-y-6">
              <div>
                <h3 className="text-lg font-semibold text-black mb-1">
                  Default Font Settings
                </h3>
                <p className="text-sm text-gray-600">
                  These settings will be applied to all new video processing tasks
                </p>
              </div>

              <FontCustomization
                value={{
                  family: preferences?.fontFamily || "TikTokSans-Regular",
                  size: preferences?.fontSize || 24,
                  color: preferences?.fontColor || "#FFFFFF",
                }}
                onChange={(fontOptions) => {
                  updatePreferences({
                    fontFamily: fontOptions.family,
                    fontSize: fontOptions.size,
                    fontColor: fontOptions.color,
                  }).catch(err => console.error("Failed to update fonts:", err));
                }}
                disabled={isLoadingPrefs}
                showPreview={true}
              />
            </div>

            <Separator className="my-8" />

            {/* Clip Length Settings Section */}
            <div className="space-y-6">
              <div>
                <h3 className="text-lg font-semibold text-black mb-1 flex items-center gap-2">
                  <Clock className="w-5 h-5" />
                  Clip Length Settings
                </h3>
                <p className="text-sm text-gray-600">
                  Control the duration of generated video clips
                </p>
              </div>

              {/* Minimum Length Slider */}
              <div className="space-y-2">
                <Label className="text-sm font-medium text-black">
                  Minimum Length: {clipMinLength}s
                </Label>
                <div className="px-2">
                  <Slider
                    value={[clipMinLength]}
                    onValueChange={(value) => setClipMinLength(value[0])}
                    max={45}
                    min={5}
                    step={1}
                    disabled={isLoading}
                    className="w-full"
                  />
                </div>
                <div className="flex justify-between text-xs text-gray-500">
                  <span>5s</span>
                  <span>45s</span>
                </div>
              </div>

              {/* Target Length Slider */}
              <div className="space-y-2">
                <Label className="text-sm font-medium text-black">
                  Target Length: {clipTargetLength}s
                </Label>
                <div className="px-2">
                  <Slider
                    value={[clipTargetLength]}
                    onValueChange={(value) => setClipTargetLength(value[0])}
                    max={50}
                    min={10}
                    step={1}
                    disabled={isLoading}
                    className="w-full"
                  />
                </div>
                <div className="flex justify-between text-xs text-gray-500">
                  <span>10s</span>
                  <span>50s</span>
                </div>
              </div>

              {/* Maximum Length Slider */}
              <div className="space-y-2">
                <Label className="text-sm font-medium text-black">
                  Maximum Length: {clipMaxLength}s
                </Label>
                <div className="px-2">
                  <Slider
                    value={[clipMaxLength]}
                    onValueChange={(value) => setClipMaxLength(value[0])}
                    max={60}
                    min={15}
                    step={1}
                    disabled={isLoading}
                    className="w-full"
                  />
                </div>
                <div className="flex justify-between text-xs text-gray-500">
                  <span>15s</span>
                  <span>60s</span>
                </div>
              </div>
            </div>

            <Separator className="my-8" />

            {/* AI Prompt Customization Section */}
            <div className="space-y-6">
              <div>
                <h3 className="text-lg font-semibold text-black mb-1 flex items-center gap-2">
                  <Sparkles className="w-5 h-5" />
                  AI Prompt Customization
                </h3>
                <p className="text-sm text-gray-600">
                  Customize how AI selects video clips
                </p>
              </div>

              {/* Use Custom Prompt Checkbox */}
              <div className="flex items-center space-x-2">
                <Checkbox
                  id="useCustomPrompt"
                  checked={useCustomPrompt}
                  onCheckedChange={(checked) => {
                    const isChecked = checked as boolean;
                    setUseCustomPrompt(isChecked);
                    // Prefill with default prompt if enabling and textarea is empty
                    if (isChecked && !customAiPrompt && defaultPrompt) {
                      setCustomAiPrompt(defaultPrompt);
                    }
                  }}
                  disabled={isLoading}
                />
                <Label
                  htmlFor="useCustomPrompt"
                  className="text-sm font-medium text-black cursor-pointer"
                >
                  Use custom AI prompt
                </Label>
              </div>

              {/* Custom Prompt Textarea */}
              {useCustomPrompt && (
                <div className="space-y-2">
                  <Label className="text-sm font-medium text-black">
                    Custom Prompt
                  </Label>
                  <Textarea
                    value={customAiPrompt}
                    onChange={(e) => setCustomAiPrompt(e.target.value)}
                    disabled={isLoading}
                    placeholder="Enter your custom instructions for the AI to select clips... (e.g., 'Focus on educational content and actionable tips')"
                    className="min-h-[240px] resize-y"
                    maxLength={2000}
                  />
                  <p className="text-xs text-gray-500">
                    {customAiPrompt.length}/2000 characters
                  </p>
                  <p className="text-xs text-gray-500 mt-1">
                    This prompt will be used to guide the AI in selecting video clips. Leave as-is to use the default, or customize to match your content style.
                  </p>
                </div>
              )}
            </div>

            <Separator className="my-8" />

            {/* Logo Branding Section */}
            <div className="space-y-6">
              <div>
                <h3 className="text-lg font-semibold text-black mb-1 flex items-center gap-2">
                  <Image className="w-5 h-5" />
                  Logo Branding
                </h3>
                <p className="text-sm text-gray-600">
                  Add your logo to all generated clips
                </p>
              </div>

              {/* Logo Upload */}
              <div className="space-y-2">
                <Label className="text-sm font-medium text-black">
                  Upload Logo (PNG/JPG)
                </Label>
                <Input
                  type="file"
                  accept=".png,.jpg,.jpeg"
                  onChange={handleLogoFileChange}
                  disabled={logoUploadProgress}
                  className="cursor-pointer"
                />
                <p className="text-xs text-gray-500">
                  Logo will be resized to 60px on the longest side
                </p>
              </div>

              {/* Logo Preview */}
              {logoPreview && (
                <div className="space-y-2">
                  <Label className="text-sm font-medium text-black">Preview</Label>
                  <div className="p-4 bg-gray-100 rounded-lg inline-block">
                    <img src={logoPreview} alt="Logo preview" className="max-h-16" />
                  </div>
                </div>
              )}

              {/* Corner Position Selector */}
              <div className="space-y-2">
                <Label className="text-sm font-medium text-black">
                  Logo Position
                </Label>
                <div className="grid grid-cols-2 gap-2">
                  {[
                    { value: "top-left", label: "Top Left" },
                    { value: "top-right", label: "Top Right" },
                    { value: "bottom-left", label: "Bottom Left" },
                    { value: "bottom-right", label: "Bottom Right" },
                  ].map((position) => (
                    <Button
                      key={position.value}
                      type="button"
                      variant={logoCornerPosition === position.value ? "default" : "outline"}
                      onClick={() => setLogoCornerPosition(position.value as any)}
                      disabled={logoUploadProgress}
                    >
                      {position.label}
                    </Button>
                  ))}
                </div>
              </div>

              {/* Upload Button */}
              <Button
                onClick={handleLogoUpload}
                disabled={!logoFile || logoUploadProgress}
                className="w-full"
              >
                {logoUploadProgress ? "Uploading..." : "Upload Logo"}
              </Button>
            </div>

            {/* Success/Error Messages */}
            {success && (
              <SuccessAlert message="Preferences saved successfully!" />
            )}

            {error && (
              <ErrorAlert message={error} />
            )}

            {/* Save Button */}
            <Button
              onClick={handleSavePreferences}
              disabled={isLoading}
              className="w-full h-11"
            >
              {isLoading ? "Saving..." : "Save Preferences"}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
