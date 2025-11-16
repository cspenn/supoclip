import { NextRequest, NextResponse } from "next/server";
import { auth } from "@/lib/auth";
import { headers } from "next/headers";
import prisma from "@/lib/prisma";

// Check if authentication is disabled (local development mode)
const DISABLE_AUTH = process.env.NEXT_PUBLIC_DISABLE_AUTH === "true";
const MOCK_USER_ID = process.env.NEXT_PUBLIC_MOCK_USER_ID || "local-user";

// GET /api/preferences - Get user preferences
export async function GET(request: NextRequest) {
  try {
    // Get user ID - use mock ID if auth is disabled
    let userId: string;

    if (DISABLE_AUTH) {
      userId = MOCK_USER_ID;
      console.log("Using mock user ID for preferences GET:", userId);
    } else {
      const session = await auth.api.getSession({
        headers: await headers(),
      });

      if (!session?.user?.id) {
        return NextResponse.json(
          { error: "Unauthorized" },
          { status: 401 }
        );
      }
      userId = session.user.id;
    }

    const user = await prisma.user.findUnique({
      where: { id: userId },
      select: {
        default_font_family: true,
        default_font_size: true,
        default_font_color: true,
        default_clip_min_length: true,
        default_clip_target_length: true,
        default_clip_max_length: true,
        custom_ai_prompt: true,
      },
    });

    if (!user) {
      return NextResponse.json(
        { error: "User not found" },
        { status: 404 }
      );
    }

    return NextResponse.json({
      fontFamily: user.default_font_family || "TikTokSans-Regular",
      fontSize: user.default_font_size || 24,
      fontColor: user.default_font_color || "#FFFFFF",
      clipMinLength: user.default_clip_min_length || 10,
      clipTargetLength: user.default_clip_target_length || 30,
      clipMaxLength: user.default_clip_max_length || 45,
      customAiPrompt: user.custom_ai_prompt || null,
    });
  } catch (error) {
    console.error("Error fetching preferences:", error);
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    );
  }
}

// PATCH /api/preferences - Update user preferences
export async function PATCH(request: NextRequest) {
  try {
    // Get user ID - use mock ID if auth is disabled
    let userId: string;

    if (DISABLE_AUTH) {
      userId = MOCK_USER_ID;
      console.log("Using mock user ID for preferences PATCH:", userId);
    } else {
      const session = await auth.api.getSession({
        headers: await headers(),
      });

      if (!session?.user?.id) {
        return NextResponse.json(
          { error: "Unauthorized" },
          { status: 401 }
        );
      }
      userId = session.user.id;
    }

    const body = await request.json();
    const { fontFamily, fontSize, fontColor, clipMinLength, clipTargetLength, clipMaxLength, customAiPrompt } = body;

    // Validate font inputs
    if (fontFamily && typeof fontFamily !== "string") {
      return NextResponse.json(
        { error: "Invalid fontFamily" },
        { status: 400 }
      );
    }

    if (fontSize && (typeof fontSize !== "number" || fontSize < 12 || fontSize > 48)) {
      return NextResponse.json(
        { error: "Invalid fontSize (must be between 12 and 48)" },
        { status: 400 }
      );
    }

    if (fontColor && !/^#[0-9A-Fa-f]{6}$/.test(fontColor)) {
      return NextResponse.json(
        { error: "Invalid fontColor (must be hex format like #FFFFFF)" },
        { status: 400 }
      );
    }

    // Validate clip length inputs
    if (clipMinLength !== undefined && (typeof clipMinLength !== "number" || clipMinLength < 5 || clipMinLength > 60)) {
      return NextResponse.json(
        { error: "Invalid clipMinLength (must be between 5 and 60)" },
        { status: 400 }
      );
    }

    if (clipTargetLength !== undefined && (typeof clipTargetLength !== "number" || clipTargetLength < 5 || clipTargetLength > 60)) {
      return NextResponse.json(
        { error: "Invalid clipTargetLength (must be between 5 and 60)" },
        { status: 400 }
      );
    }

    if (clipMaxLength !== undefined && (typeof clipMaxLength !== "number" || clipMaxLength < 5 || clipMaxLength > 60)) {
      return NextResponse.json(
        { error: "Invalid clipMaxLength (must be between 5 and 60)" },
        { status: 400 }
      );
    }

    // Validate clip length relationships
    if (clipMinLength !== undefined && clipTargetLength !== undefined && clipMinLength >= clipTargetLength) {
      return NextResponse.json(
        { error: "Minimum length must be less than target length" },
        { status: 400 }
      );
    }

    if (clipTargetLength !== undefined && clipMaxLength !== undefined && clipTargetLength >= clipMaxLength) {
      return NextResponse.json(
        { error: "Target length must be less than maximum length" },
        { status: 400 }
      );
    }

    // Validate custom prompt
    if (customAiPrompt !== undefined && customAiPrompt !== null && typeof customAiPrompt !== "string") {
      return NextResponse.json(
        { error: "Invalid customAiPrompt (must be string or null)" },
        { status: 400 }
      );
    }

    if (customAiPrompt && customAiPrompt.length > 2000) {
      return NextResponse.json(
        { error: "customAiPrompt too long (max 2000 characters)" },
        { status: 400 }
      );
    }

    const updatedUser = await prisma.user.update({
      where: { id: userId },
      data: {
        ...(fontFamily !== undefined && { default_font_family: fontFamily }),
        ...(fontSize !== undefined && { default_font_size: fontSize }),
        ...(fontColor !== undefined && { default_font_color: fontColor }),
        ...(clipMinLength !== undefined && { default_clip_min_length: clipMinLength }),
        ...(clipTargetLength !== undefined && { default_clip_target_length: clipTargetLength }),
        ...(clipMaxLength !== undefined && { default_clip_max_length: clipMaxLength }),
        ...(customAiPrompt !== undefined && { custom_ai_prompt: customAiPrompt }),
      },
      select: {
        default_font_family: true,
        default_font_size: true,
        default_font_color: true,
        default_clip_min_length: true,
        default_clip_target_length: true,
        default_clip_max_length: true,
        custom_ai_prompt: true,
      },
    });

    return NextResponse.json({
      fontFamily: updatedUser.default_font_family,
      fontSize: updatedUser.default_font_size,
      fontColor: updatedUser.default_font_color,
      clipMinLength: updatedUser.default_clip_min_length,
      clipTargetLength: updatedUser.default_clip_target_length,
      clipMaxLength: updatedUser.default_clip_max_length,
      customAiPrompt: updatedUser.custom_ai_prompt,
    });
  } catch (error) {
    console.error("Error updating preferences:", error);
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    );
  }
}
